"""
Orchestrates scraper runs: fetches listings, scores them, saves to DB,
and sends Discord alerts and Expo push notifications.
"""
import logging
import re
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from backend.models.database import SessionLocal
from backend.models.models import (
    Watchlist, Source, ScraperRun, Listing, DealScore, GameCubePrice, AppSetting,
    ListingPriceHistory, ClaudeReview, EspressoPrice,
)
from backend.services.market_value import get_market_value, extract_search_keyword
from backend.scoring.espresso_pricing import match_espresso_price
from backend.services.photo_analysis import get_photo_analyzer, PhotoAnalysis
from backend.scoring.category_config import get_category_config
from backend.scoring.net_flip import compute_net_flip
from backend.scoring.bad_listing import detect_bad_listing
from backend.scoring.bundle import detect_bundle
from backend.scoring.deal_scorer import (
    CONDITION_KEYWORDS_NEGATIVE,
    CONDITION_KEYWORDS_POSITIVE,
)
from backend.scrapers.base import NormalizedListing
from backend.scrapers.mock_scraper import MockScraper
from backend.scrapers.auctionninja import AuctionNinjaScraper
from backend.scrapers.facebook import FacebookScraper
from backend.scrapers.craigslist import CraigslistScraper
from backend.scrapers.offerup import OfferUpScraper
from backend.scrapers.mercari import MercariScraper
from backend.scrapers.ebay import EbayScraper
from backend.scoring.deal_scorer import score_listing
from backend.scoring.gamecube_scorer import score_gamecube_listing
from backend.services import discord as discord_service
from backend.services import push_notifications as push_service
from backend.services.settings import get_all_settings

logger = logging.getLogger("platapicker.runner")

SCRAPER_REGISTRY = {
    "mock": MockScraper,
    "auctionninja": AuctionNinjaScraper,
    "facebook": FacebookScraper,
    "craigslist": CraigslistScraper,
    "offerup": OfferUpScraper,
    "mercari": MercariScraper,
    "ebay": EbayScraper,
}


# Sources that are live auctions rather than fixed-price marketplaces. For these
# the listed "price" is the current bid, which early in an auction is far below
# the item's resale value — so the watchlist's min_price floor (meant to skip
# junk on fixed-price sites) must NOT apply, or every fresh lot gets dropped
# before it can be scored against comps. max_price and the free/zero guard still
# apply. The low bid vs. comp value is exactly what makes an auction a deal.
AUCTION_SOURCES = {"auctionninja"}

# Listings whose "price" isn't a real, firm number — Craigslist/OfferUp posts that
# say "best offer", "OBO", or carry no price at all ($0/missing). Price-vs-value
# scoring is meaningless for these, yet they're often the BEST deals — so instead of
# dropping them (the old behavior silently discarded every no-price CL post) we keep
# them, estimate resale value, and alert as a "lead" when the value clears the
# watchlist's per-category bar. Auctions are excluded — their current bid is a real
# (rising) number handled by the auction end-time gate, not a placeholder.
NEGOTIABLE_MARKERS = (
    "best offer", "or best offer", "obo", "o.b.o", "make offer", "make an offer",
    "make me an offer", "open to offers", "price negotiable", "negotiable",
    "b/o", "/offer", "no price",
)


def _is_negotiable_price(title, description, price, source) -> bool:
    """True when a listing has no reliable firm price (best-offer / $0 / OBO)."""
    if source in AUCTION_SOURCES:
        return False
    if price is None or price <= 0:
        return True
    text = f"{title or ''} {description or ''}".lower()
    return any(m in text for m in NEGOTIABLE_MARKERS)

# Auctions are only actionable near close — early on, a $1 opening bid says
# nothing about the final price, so alerting on it just floods. We skip saving
# auction lots that end further out than this window; when a lot later enters the
# window it's a fresh (non-duplicate) listing and gets saved/scored/alerted with
# a bid that's actually meaningful. Tunable via the `auction_max_hours_to_alert`
# setting. Lots with an unparseable end time fail open (kept).
DEFAULT_AUCTION_MAX_HOURS = 48


def _auction_hours_left(raw: Optional[dict]) -> Optional[float]:
    """Parse AuctionNinja's "9 days 14 hours left" countdown into hours. None if absent/unparseable."""
    text = (raw or {}).get("end_time") or ""
    if not text:
        return None
    days = re.search(r"(\d+)\s*day", text, re.I)
    hours = re.search(r"(\d+)\s*hour", text, re.I)
    mins = re.search(r"(\d+)\s*min", text, re.I)
    if not (days or hours or mins):
        return None
    total = 0.0
    if days:
        total += int(days.group(1)) * 24
    if hours:
        total += int(hours.group(1))
    if mins:
        total += int(mins.group(1)) / 60.0
    return total


def _get_scraper(source_name: str, config: dict):
    cls = SCRAPER_REGISTRY.get(source_name)
    if not cls:
        raise ValueError(f"Unknown scraper: {source_name}")
    return cls(config=config)


def _record_price_change(db: Session, existing: Listing, new_price: Optional[float]):
    """Record a ListingPriceHistory entry when price changes by more than $1."""
    old_price = existing.price
    if (
        new_price is not None
        and old_price is not None
        and abs(new_price - old_price) > 1.0
    ):
        logger.info(
            f"Price change detected: ${old_price:.2f} → ${new_price:.2f} for '{existing.title}'"
        )
        history = ListingPriceHistory(
            listing_id=existing.id,
            price=new_price,
            recorded_at=datetime.utcnow(),
        )
        db.add(history)
        existing.price = new_price


def _deduplicate(db: Session, listing: NormalizedListing, watchlist_id: int) -> Optional[Listing]:
    """Returns existing DB listing for this watchlist if duplicate, else None."""
    q = db.query(Listing).filter(Listing.watchlist_id == watchlist_id)

    if listing.source_listing_id:
        existing = q.filter(
            Listing.source == listing.source,
            Listing.source_listing_id == listing.source_listing_id,
        ).first()
        if existing:
            existing.last_seen_at = datetime.utcnow()
            _record_price_change(db, existing, listing.price)
            return existing

    # Fallback: URL match within this watchlist
    if listing.url:
        existing = q.filter(Listing.url == listing.url).first()
        if existing:
            existing.last_seen_at = datetime.utcnow()
            _record_price_change(db, existing, listing.price)
            return existing

    return None


def _save_listing(db: Session, listing: NormalizedListing, watchlist_id: int) -> Listing:
    row = Listing(
        source=listing.source,
        source_listing_id=listing.source_listing_id,
        watchlist_id=watchlist_id,
        title=listing.title,
        description=listing.description or "",
        price=listing.price,
        url=listing.url,
        image_url=listing.image_url,
        location=listing.location,
        distance_miles=listing.distance_miles,
        seller=listing.seller,
        posted_at=listing.posted_at,
    )
    row.raw_payload = listing.raw_payload
    db.add(row)
    db.flush()

    # Record initial price history entry
    if listing.price is not None:
        initial_history = ListingPriceHistory(
            listing_id=row.id,
            price=listing.price,
            recorded_at=datetime.utcnow(),
        )
        db.add(initial_history)

    return row


def _condition_flags(text: str):
    """Returns (condition_unknown, condition_poor) from listing text."""
    t = text.lower()
    poor = any(kw in t for kw in CONDITION_KEYWORDS_NEGATIVE)
    good = any(kw in t for kw in CONDITION_KEYWORDS_POSITIVE)
    unknown = not poor and not good
    return unknown, poor


def _run_photo_analysis(db: Session, listing: Listing, cat_config: dict, settings: dict) -> PhotoAnalysis:
    """Run photo analysis if enabled; persist results on the listing. Never raises."""
    analyzer = get_photo_analyzer(settings)
    try:
        analysis = analyzer.analyze(listing.image_url or "", category_config=cat_config)
    except Exception as e:  # belt-and-suspenders — providers are already fail-open
        logger.warning(f"Photo analysis errored for '{listing.title}': {e}")
        analysis = PhotoAnalysis(error=str(e))

    if not analysis.is_empty:
        listing.detected_brand = analysis.detected_brand
        listing.detected_model = analysis.detected_model
        listing.photo_analysis = analysis.to_dict()
        logger.info(
            f"📷 Photo analysis: brand={analysis.detected_brand} "
            f"model={analysis.detected_model} conf={analysis.image_confidence}"
        )
    return analysis


def _attach_new_signals(
    db: Session,
    listing: Listing,
    watchlist: Watchlist,
    score_row: DealScore,
    result,
    cat_config: dict,
    photo: PhotoAnalysis,
    comp_sample_count: int,
):
    """Compute Net Flip / Bad-Listing / Bundle signals and persist on the score."""
    text = f"{listing.title} {listing.description or ''}"
    condition_unknown, condition_poor = _condition_flags(text)

    # ── Net Flip Score ────────────────────────────────────────────────────────
    net = compute_net_flip(
        deal_label=result.rating,
        buy_price=listing.price,
        resale_price=getattr(result, "conservative_value", None) or getattr(result, "estimated_value", None),
        category_config=cat_config,
        comp_sample_count=comp_sample_count,
        condition_unknown=condition_unknown,
        condition_poor=condition_poor,
        distance_miles=listing.distance_miles,
        tax_rate=watchlist.sales_tax_rate or 0.0,
        photo_missing_parts_risk=(photo.missing_parts_risk if photo else None),
        photo_confidence=(photo.image_confidence if photo else None),
    )
    score_row.net_flip_score = net.net_flip_score
    score_row.estimated_roi_percent = net.estimated_roi_percent
    score_row.net_profit = net.estimated_net_profit
    score_row.risk_level = net.risk_level
    score_row.confidence_label = net.confidence
    score_row.net_flip = net.to_dict()

    # ── Bad Listing, Good Item ────────────────────────────────────────────────
    bad = detect_bad_listing(
        title=listing.title,
        description=listing.description or "",
        brands=watchlist.brands,
        category_config=cat_config,
        photo_analysis=photo if (photo and not photo.is_empty) else None,
    )
    score_row.bad_listing = bad.to_dict()

    # ── Bundle arbitrage ──────────────────────────────────────────────────────
    gc_prices = db.query(GameCubePrice).all() if watchlist.category == "gamecube" else None

    def _comp_lookup(name: str):
        est = get_market_value(keyword=name, category=watchlist.category, db=db)
        return est.median_price if est and not est.error else None

    bundle = detect_bundle(
        title=listing.title,
        description=listing.description or "",
        category=watchlist.category,
        category_config=cat_config,
        buy_price=listing.price,
        gamecube_prices=gc_prices,
        aliases=watchlist.aliases,
        comp_lookup=_comp_lookup if cat_config.get("bundle_item_catalog") else None,
        whole_resale_value=getattr(result, "conservative_value", None),
        photo_analysis=photo if (photo and not photo.is_empty) else None,
    )
    score_row.bundle = bundle.to_dict()

    logger.info(
        f"🧮 {listing.title[:48]!r}: {result.rating} · NetFlip {net.net_flip_score} "
        f"· ROI {net.estimated_roi_percent:.0f}% · risk {net.risk_level}"
        + (f" · 🧩 {bundle.recommended_strategy}" if bundle.is_bundle else "")
        + (f" · 🔎 underpriced({bad.undervaluation_score})" if bad.bad_listing_good_item else "")
    )


def _score_listing(db: Session, listing: Listing, watchlist: Watchlist, settings: dict):
    thresholds = settings.get("deal_thresholds", {
        "STEAL": 0.45, "GREAT": 0.55, "GOOD": 0.65, "FAIR": 0.75
    })
    cat_config = get_category_config(watchlist.category)

    # Photo analysis (opt-in; fail-open). Runs once per listing before comps so a
    # detected model number can sharpen the eBay comp keyword.
    photo = _run_photo_analysis(db, listing, cat_config, settings)

    # No firm price (best-offer / $0 / OBO)? We'll alert on resale value, not a ratio.
    negotiable = _is_negotiable_price(
        listing.title, listing.description, listing.price, listing.source
    )

    if watchlist.category == "gamecube":
        gc_prices = db.query(GameCubePrice).all()
        aliases = watchlist.aliases
        result = score_gamecube_listing(
            title=listing.title,
            description=listing.description or "",
            price=listing.price or 0,
            gamecube_prices=gc_prices,
            platform_fee_pct=settings.get("gamecube_platform_fee_pct", 0.13),
            bundle_discount=settings.get("gamecube_bundle_discount", 0.85),
            low_demand_discount=settings.get("gamecube_low_demand_discount", 0.60),
            thresholds=thresholds,
            aliases=aliases,
        )
        score_row = DealScore(
            listing_id=listing.id,
            rating=result.rating,
            score=result.score,
            estimated_value=result.estimated_value,
            conservative_value=result.conservative_value,
            target_buy_price=result.target_buy_30pct,
            estimated_profit=result.estimated_profit,
            profit_margin=result.profit_margin,
            confidence=result.confidence,
        )
        score_row.reasons = result.reasons
        score_row.warnings = result.warnings
        score_row.value_source = "gamecube"
        # GameCube doesn't use eBay comps directly; use matched-game count as the
        # comp-quality proxy for the Net Flip confidence calculation.
        comp_sample_count = len(getattr(result, "matched_games", []) or [])
    else:
        estimated_value = None
        conservative_value = None
        comp_sample_count = 0
        value_source = None
        pricing_breakdown = None

        # Espresso prices from a manual reference table instead of eBay sold comps
        # (eBay rate-limits the sold-listing scrape too aggressively to be reliable).
        priced_from_table = False
        if watchlist.category == "espresso":
            esp_prices = db.query(EspressoPrice).all()
            used_price, matched = match_espresso_price(listing.title, esp_prices)
            if used_price is not None:
                estimated_value = used_price
                conservative_value = round(used_price * 0.8, 2)
                comp_sample_count = 1  # table value = one authoritative comp
                priced_from_table = True
                value_source = "table"
                logger.info(
                    f"Espresso price table: '{listing.title}' → "
                    f"{matched.brand} {matched.model} = ${used_price}"
                )

        if not priced_from_table:
            # Prefer a photo-detected "Brand Model" keyword (most precise), else fall
            # back to extracting brand+model from the verbose Facebook title. Raw
            # titles ("Vertuo Creatista by Breville Coffee and Espresso Machine in
            # Stainless Steel") are too verbose and return no eBay results.
            if listing.detected_brand and listing.detected_model:
                search_keyword = f"{listing.detected_brand} {listing.detected_model}"
                logger.info(f"Keyword from photo: '{listing.title}' → '{search_keyword}'")
            else:
                search_keyword = extract_search_keyword(listing.title, watchlist.brands)
                if search_keyword != listing.title:
                    logger.info(f"Keyword extracted: '{listing.title}' → '{search_keyword}'")
            market = get_market_value(
                keyword=search_keyword,
                category=watchlist.category,
                db=db,
            )
            comp_sample_count = market.sample_count if market and not market.error else 0
            estimated_value = market.median_price if market and not market.error else None
            if estimated_value is not None:
                # A cached row may itself be a previously-computed local-LLM value
                # (get_market_value reads any source); attribute + surface it correctly.
                if (getattr(market, "source", "") or "").startswith("local_llm"):
                    value_source = "maker_checker"
                    from backend.services.local_llm_pricing import get_cached_breakdown
                    pricing_breakdown = get_cached_breakdown(db, search_keyword, watchlist.category)
                else:
                    value_source = "ebay"

            # Gap-fill with the local LLM when eBay returns no comp. eBay only
            # prices ~15% of table-less listings (furniture/apparel/grills/etc.);
            # the rest would otherwise have no value and never score as a deal.
            # Two models (maker + checker) cross-check the price; cached per keyword
            # in MarketValueCache so the next run reads it back without a model query.
            if estimated_value is None and settings.get("local_llm_pricing_enabled", True):
                from backend.services.local_llm_pricing import estimate_value_dual
                local = estimate_value_dual(
                    search_keyword, watchlist.category, db=db, settings=settings
                )
                if local.estimated_value is not None:
                    estimated_value = local.estimated_value
                    comp_sample_count = max(comp_sample_count, 1)
                    value_source = "maker_checker"
                    pricing_breakdown = local.to_breakdown()

            conservative_value = (
                round(estimated_value * 0.8, 2)
                if estimated_value is not None
                else None
            )

        result = score_listing(
            title=listing.title,
            description=listing.description or "",
            price=listing.price or 0,
            watchlist_keywords=watchlist.keywords,
            watchlist_brands=watchlist.brands,
            watchlist_negative_keywords=watchlist.negative_keywords,
            thresholds=thresholds,
            estimated_value=estimated_value,
            conservative_value=conservative_value,
            shipping_cost=watchlist.estimated_shipping_cost or 0.0,
            tax_rate=watchlist.sales_tax_rate or 0.0,
        )
        score_row = DealScore(
            listing_id=listing.id,
            rating=result.rating,
            score=result.score,
            estimated_value=result.estimated_value,
            conservative_value=result.conservative_value,
            target_buy_price=result.target_buy_price,
            estimated_profit=result.estimated_profit,
            profit_margin=result.profit_margin,
            confidence=result.confidence,
        )
        score_row.reasons = result.reasons
        score_row.warnings = result.warnings
        score_row.value_source = value_source
        score_row.pricing_breakdown = pricing_breakdown

    # ── Negotiable / no-fixed-price lead ───────────────────────────────────────
    # When the price isn't firm, alert on resale value instead of a price ratio.
    # The per-category "good profit" figure is the value bar (user-chosen flood
    # control). If we couldn't value it at all we still flag it — these best-offer
    # posts are often the best deals and we never want to miss them. `is_lead`
    # bypasses the normal rating gate in _should_alert.
    score_row.is_lead = False
    if negotiable:
        cons = score_row.conservative_value
        value_floor = cat_config.get("good_profit_dollars", 100.0)
        is_lead = (cons is None) or (cons >= value_floor)
        score_row.is_lead = is_lead
        if is_lead:
            rv = f"${cons:,.0f}" if cons is not None else "unknown"
            score_row.reasons = score_row.reasons + [
                f"💬 Negotiable / no fixed price — est. resale {rv}; verify actual price."
            ]
            score_row.warnings = score_row.warnings + [
                "Price is 'best offer' or missing — confirm the real price before pursuing."
            ]
            if not score_row.value_source:
                score_row.value_source = "negotiable"

    # ── Net Flip / Bad-Listing / Bundle signals (informational; never gate alerts) ──
    try:
        _attach_new_signals(
            db, listing, watchlist, score_row, result, cat_config, photo, comp_sample_count
        )
    except Exception as e:
        logger.warning(f"New-signal scoring failed for '{listing.title}': {e}", exc_info=True)

    db.add(score_row)
    return score_row


RATING_ORDER = ["STEAL", "GREAT", "GOOD", "FAIR", "PASS"]


def _should_alert(score: DealScore, watchlist: Watchlist) -> bool:
    # Negotiable / no-fixed-price leads always alert (when they cleared the
    # per-category value bar in _score_listing) — these are often the best deals.
    if getattr(score, "is_lead", False):
        return True
    if score.rating == "PASS":
        return False
    min_rating = watchlist.min_rating_to_alert or "GOOD"
    try:
        return RATING_ORDER.index(score.rating) <= RATING_ORDER.index(min_rating)
    except ValueError:
        return False


def _send_alert(listing: Listing, score: DealScore, watchlist: Watchlist, claude_review=None):
    if not watchlist.discord_webhook or not watchlist.discord_webhook.enabled:
        return False
    return discord_service.send_deal_alert(
        webhook_url=watchlist.discord_webhook.webhook_url,
        title=listing.title,
        price=listing.price or 0,
        rating=score.rating,
        estimated_value=score.estimated_value,
        conservative_value=score.conservative_value,
        target_buy_price=score.target_buy_price,
        estimated_profit=score.estimated_profit,
        source=listing.source,
        watchlist_name=watchlist.name,
        url=listing.url or "",
        location=listing.location,
        reasons=score.reasons,
        warnings=score.warnings,
        image_url=listing.image_url,
        claude_summary=claude_review.summary if claude_review else None,
        claude_flags=claude_review.flags if claude_review else None,
        claude_positives=claude_review.positives if claude_review else None,
        net_flip=score.net_flip,
        bad_listing=score.bad_listing,
        bundle=score.bundle,
    )


def run_scraper_for_watchlist(
    source_name: Optional[str] = None,
    watchlist_id: Optional[int] = None,
):
    """Main runner — called from background tasks or CLI."""
    db = SessionLocal()
    try:
        settings = get_all_settings(db)
        watchlists = db.query(Watchlist).filter(Watchlist.enabled == True).all()
        sources = db.query(Source).filter(Source.enabled == True).all()

        if watchlist_id:
            watchlists = [w for w in watchlists if w.id == watchlist_id]
        if source_name:
            sources = [s for s in sources if s.name == source_name]

        for watchlist in watchlists:
            enabled_sources = watchlist.sources_enabled or [s.name for s in sources]
            for source in sources:
                if source.name not in enabled_sources:
                    continue
                _run_one(db, source, watchlist, settings)
    finally:
        db.close()


def _run_one(db: Session, source: Source, watchlist: Watchlist, settings: dict):
    logger.info(f"▶ Running {source.name} for watchlist '{watchlist.name}'")
    run = ScraperRun(
        source_name=source.name,
        watchlist_id=watchlist.id,
        started_at=datetime.utcnow(),
        status="running",
    )
    db.add(run)
    db.flush()

    try:
        scraper = _get_scraper(source.name, source.config)

        keywords = watchlist.keywords or []
        location = (watchlist.locations or ["New York, NY"])[0]
        radius = watchlist.radius_miles or 50

        all_raw = []
        for keyword in keywords[:5]:
            raw, health = scraper.run(keyword, location, radius)
            all_raw.extend(raw)
            run.raw_count += health.raw_count

        seen: set = set()
        new_listings = []
        min_price = max(watchlist.min_price or 0, 1)  # always block free/zero listings
        max_price = watchlist.max_price or 99999
        # Relevance gate — if required keywords are set, a listing's title/description
        # must contain at least one (any-of, case-insensitive) or it's dropped before
        # saving. Filters loosely-matched marketplace results (generic clothing, etc.).
        required = [kw.lower() for kw in (watchlist.required_keywords or []) if kw.strip()]
        for item in all_raw:
            key = item.source_listing_id or item.url or item.title
            if key in seen:
                continue
            seen.add(key)
            # Price gate — skip free, zero, or out-of-range listings before saving.
            # Auction sources are exempt from the min_price floor (see AUCTION_SOURCES):
            # a $4 current bid on a $400 machine must reach scoring, not be filtered.
            price = item.price
            is_auction = item.source in AUCTION_SOURCES
            is_negotiable = _is_negotiable_price(
                item.title, getattr(item, "description", None), price, item.source
            )
            if is_negotiable:
                # No firm price — don't apply the min floor (these best-offer/$0 posts
                # are often the best deals); we alert on resale value later. Still drop
                # anything that DOES name a price above the watchlist ceiling.
                if price is not None and price > 0 and price > max_price:
                    run.filtered_count += 1
                    continue
            else:
                floor = 1 if is_auction else min_price
                if price is None or price <= 0 or price < floor or price > max_price:
                    run.filtered_count += 1
                    continue
            # Auction end-time gate — only surface lots closing within the window,
            # so we alert on meaningful (near-final) bids instead of $1 openers
            # days out. Out-of-window lots are skipped now and picked up fresh
            # when they enter the window. Unparseable end time → keep (fail open).
            if is_auction:
                max_hours = settings.get("auction_max_hours_to_alert", DEFAULT_AUCTION_MAX_HOURS)
                hours_left = _auction_hours_left(item.raw_payload)
                if hours_left is not None and hours_left > max_hours:
                    run.filtered_count += 1
                    continue
            # Relevance gate — drop listings that match none of the required terms
            if required:
                haystack = f"{item.title or ''} {getattr(item, 'description', '') or ''}".lower()
                if not any(term in haystack for term in required):
                    run.filtered_count += 1
                    continue
            existing = _deduplicate(db, item, watchlist.id)
            if existing:
                run.duplicate_count += 1
                continue
            row = _save_listing(db, item, watchlist.id)
            new_listings.append(row)
            run.parsed_count += 1

        alert_count = 0
        qualifying: list[tuple] = []  # (listing, score)
        for listing in new_listings:
            score = _score_listing(db, listing, watchlist, settings)
            db.flush()
            if not listing.ignored and _should_alert(score, watchlist):
                qualifying.append((listing, score))

        # ── Claude review gate ────────────────────────────────────────────
        claude_enabled = settings.get("claude_enabled", False)
        claude_api_key = settings.get("claude_api_key", "")
        qualifying_with_review: list[tuple] = []  # (listing, score, review_or_none)

        if claude_enabled and claude_api_key:
            from backend.services.claude_analyzer import review_listing
            claude_model = settings.get("claude_model", "claude-haiku-4-5")
            for listing, score in qualifying:
                review = review_listing(
                    title=listing.title,
                    description=listing.description or "",
                    price=listing.price,
                    image_url=listing.image_url,
                    keywords=watchlist.keywords,
                    category=watchlist.category,
                    api_key=claude_api_key,
                    model=claude_model,
                )
                # Save review row
                cr = ClaudeReview(
                    listing_id=listing.id,
                    approved=review.approved,
                    confidence=review.confidence,
                    summary=review.summary,
                    model=review.model,
                    error=review.error,
                    photo_notes=review.photo_notes,
                )
                cr.flags = review.flags
                cr.positives = review.positives
                db.add(cr)
                db.flush()
                if review.approved:
                    qualifying_with_review.append((listing, score, review))
                else:
                    logger.info(
                        f"🤖 Claude rejected '{listing.title}': {review.summary}"
                    )
        else:
            qualifying_with_review = [(l, s, None) for l, s in qualifying]

        batch_threshold = settings.get("alert_batch_threshold", 3)

        if len(qualifying_with_review) > batch_threshold:
            # Send one batch alert
            if watchlist.discord_webhook and watchlist.discord_webhook.enabled:
                deals = []
                for listing, score, review in qualifying_with_review:
                    deal = {
                        "title": listing.title,
                        "price": listing.price,
                        "rating": score.rating,
                        "conservative_value": score.conservative_value,
                        "target_buy_price": score.target_buy_price,
                        "estimated_profit": score.estimated_profit,
                        "url": listing.url or "",
                        "reasons": score.reasons or [],
                        "net_flip": score.net_flip,
                        "bad_listing": score.bad_listing,
                        "bundle": score.bundle,
                    }
                    if review:
                        deal["claude_summary"] = review.summary
                    deals.append(deal)
                run_summary = {
                    "raw_count": run.raw_count,
                    "parsed_count": run.parsed_count,
                    "duplicate_count": run.duplicate_count,
                }
                ok = discord_service.send_batch_alert(
                    webhook_url=watchlist.discord_webhook.webhook_url,
                    watchlist_name=watchlist.name,
                    deals=deals,
                    run_summary=run_summary,
                )
                if ok:
                    for listing, _, __ in qualifying_with_review:
                        listing.alert_sent = True
                        listing.alert_sent_at = datetime.utcnow()
                    alert_count = len(qualifying_with_review)
        else:
            # Send individual alerts
            for listing, score, review in qualifying_with_review:
                ok = _send_alert(listing, score, watchlist, claude_review=review)
                if ok:
                    listing.alert_sent = True
                    listing.alert_sent_at = datetime.utcnow()
                    alert_count += 1

        # Send Expo push notifications for every qualifying deal (alongside Discord).
        # Use qualifying_with_review so push respects the Claude review gate, matching Discord.
        push_token = settings.get("expo_push_token")
        if push_token and qualifying_with_review:
            for listing, score, review in qualifying_with_review:
                push_service.send_deal_push(
                    token=push_token,
                    title=listing.title,
                    price=listing.price or 0,
                    rating=score.rating,
                    listing_id=listing.id,
                    source=listing.source,
                    estimated_profit=score.estimated_profit,
                )

        run.alert_count = alert_count

        # ── Auto-outreach ─────────────────────────────────────────────────────
        # If watchlist has auto_outreach_enabled and the listing is from FB
        # Marketplace, send an automated message to the seller.
        if watchlist.auto_outreach_enabled:
            from backend.services.outreach import send_outreach, _check_rate_limit
            for listing, score, review in qualifying_with_review:
                if not listing.url or "facebook.com" not in listing.url:
                    continue
                if listing.outreach_status in ("SENT", "QUEUED"):
                    continue

                allowed, reason = _check_rate_limit()
                if not allowed:
                    logger.info(f"Outreach rate limited ({reason}) — skipping remaining")
                    break

                template = watchlist.outreach_message_template or ""
                listing.outreach_status = "QUEUED"
                db.flush()

                result = send_outreach(listing.url, listing.title, template)
                if result.success:
                    listing.outreach_status = "SENT"
                    listing.outreach_sent_at = datetime.utcnow()
                    logger.info(f"✉ Outreach sent to seller for '{listing.title}'")
                else:
                    listing.outreach_status = "FAILED"
                    logger.warning(
                        f"Outreach failed for '{listing.title}': {result.error}"
                    )

        run.status = "success"
        run.ended_at = datetime.utcnow()

        source.last_run_at = datetime.utcnow()
        source.last_success_at = datetime.utcnow()
        source.status = "healthy"

        db.commit()
        logger.info(
            f"✅ {source.name}/{watchlist.name}: "
            f"{run.raw_count} raw, {run.parsed_count} new, "
            f"{run.duplicate_count} dupes, {alert_count} alerts"
        )

    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)
        run.ended_at = datetime.utcnow()
        source.last_run_at = datetime.utcnow()
        source.status = "failed"
        source.last_error = str(e)
        db.commit()
        logger.error(f"❌ {source.name}/{watchlist.name} failed: {e}", exc_info=True)
