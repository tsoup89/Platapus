"""Discord webhook alerting service."""
import json
import logging
from datetime import datetime, timezone
from typing import Optional
import httpx

logger = logging.getLogger("platapicker.discord")

RATING_EMOJI = {
    "STEAL": "🔥",
    "GREAT": "⭐",
    "GOOD": "✅",
    "FAIR": "🟡",
    "PASS": "⛔",
}


_HEADERS = {"User-Agent": "DiscordBot (platapicker, 1.0)", "Content-Type": "application/json"}

def _post_webhook(webhook_url: str, payload: dict) -> bool:
    try:
        resp = httpx.post(webhook_url, json=payload, headers=_HEADERS, timeout=10)
        if resp.status_code in (200, 204):
            return True
        logger.error(f"Discord webhook returned {resp.status_code}: {resp.text[:200]}")
        return False
    except Exception as e:
        logger.error(f"Discord webhook failed: {e}")
        return False


def send_deal_alert(
    webhook_url: str,
    title: str,
    price: float,
    rating: str,
    estimated_value: Optional[float],
    conservative_value: Optional[float],
    target_buy_price: Optional[float],
    estimated_profit: Optional[float],
    source: str,
    watchlist_name: str,
    url: str,
    location: Optional[str] = None,
    reasons: Optional[list] = None,
    warnings: Optional[list] = None,
    image_url: Optional[str] = None,
    claude_summary: Optional[str] = None,
    claude_flags: Optional[list] = None,
    claude_positives: Optional[list] = None,
    net_flip: Optional[dict] = None,
    bad_listing: Optional[dict] = None,
    bundle: Optional[dict] = None,
) -> bool:
    emoji = RATING_EMOJI.get(rating, "📦")

    def fmt_money(v):
        return f"${v:,.0f}" if v is not None else "N/A"

    profit_margin = ""
    if estimated_profit and conservative_value and conservative_value > 0:
        margin = (estimated_profit / conservative_value) * 100
        profit_margin = f" ({margin:.0f}%)"

    lines = [
        f"**{emoji} Platapicker Deal Found**",
        "",
        f"**Rating:** {rating}",
        f"**Source:** {source}",
        f"**Watchlist:** {watchlist_name}",
        f"**Title:** {title}",
        f"**Price:** {fmt_money(price)}",
    ]
    if conservative_value:
        lines.append(f"**Conservative Value:** {fmt_money(conservative_value)}")
    if target_buy_price:
        lines.append(f"**Target Buy Price:** {fmt_money(target_buy_price)}")
    if estimated_profit:
        lines.append(f"**Estimated Profit:** {fmt_money(estimated_profit)}{profit_margin}")
    # ── Net Flip Score (concise economics line) ──────────────────────────────
    if net_flip and net_flip.get("net_flip_score") is not None:
        nf_parts = [f"Net Flip {net_flip['net_flip_score']}/100"]
        if net_flip.get("estimated_roi_percent") is not None:
            nf_parts.append(f"ROI {net_flip['estimated_roi_percent']:.0f}%")
        if net_flip.get("estimated_net_profit") is not None:
            nf_parts.append(f"net {fmt_money(net_flip['estimated_net_profit'])}")
        if net_flip.get("risk_level"):
            nf_parts.append(f"risk {net_flip['risk_level']}")
        lines.append("**💰 " + " · ".join(nf_parts) + "**")
    # ── Bundle break-apart hint ──────────────────────────────────────────────
    if bundle and bundle.get("is_bundle"):
        total = bundle.get("estimated_bundle_resale_total")
        strat = bundle.get("recommended_strategy", "")
        lines.append(f"**🧩 Bundle:** {strat} (~{fmt_money(total)} total)")
    # ── Underpriced / bad-listing hint ───────────────────────────────────────
    if bad_listing and bad_listing.get("bad_listing_good_item"):
        sigs = ", ".join(bad_listing.get("detected_signals", [])[:2])
        lines.append(f"**🔎 Possibly underpriced** ({bad_listing.get('undervaluation_score')}): {sigs}")
    if location:
        lines.append(f"**Location:** {location}")
    if reasons:
        lines.append("")
        lines.append("**Top Reasons:**")
        for r in reasons[:5]:
            lines.append(f"- {r}")
    if warnings:
        lines.append("")
        lines.append("**⚠️ Warnings:**")
        for w in warnings[:3]:
            lines.append(f"- {w}")
    if claude_summary:
        lines.append("")
        lines.append(f"**🤖 Claude:** {claude_summary}")
        if claude_flags:
            for f_ in claude_flags[:3]:
                lines.append(f"  ⚠ {f_}")
        if claude_positives:
            for p in claude_positives[:3]:
                lines.append(f"  ✓ {p}")
    lines.append("")
    lines.append(f"🔗 {url}")

    embed = {
        "description": "\n".join(lines),
        "color": _rating_color(rating),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": "Platapicker"},
    }
    if image_url:
        embed["thumbnail"] = {"url": image_url}

    payload = {"embeds": [embed]}
    return _post_webhook(webhook_url, payload)


def send_health_alert(
    webhook_url: str,
    source: str,
    error: str,
    last_success: Optional[datetime],
    suggested_action: Optional[str] = None,
) -> bool:
    last_str = last_success.strftime("%b %d %I:%M %p") if last_success else "Never"
    lines = [
        "**⚠️ Platapicker Health Alert**",
        "",
        f"**Source:** {source}",
        f"**Error:** {error}",
        f"**Last Successful Run:** {last_str}",
    ]
    if suggested_action:
        lines.append(f"**Suggested Action:** {suggested_action}")

    payload = {"content": "\n".join(lines)}
    return _post_webhook(webhook_url, payload)


def send_heartbeat(
    webhook_url: str,
    source_summaries: list[dict],
    errors: Optional[list[str]] = None,
) -> bool:
    lines = ["**✅ Platapicker Heartbeat**", ""]
    for s in source_summaries:
        status_icon = "✅" if s.get("status") == "healthy" else "⚠️"
        line = (
            f"{status_icon} **{s['name']}**: "
            f"{s.get('raw_count', 0)} raw, "
            f"{s.get('parsed_count', 0)} parsed, "
            f"{s.get('alert_count', 0)} alerts"
        )
        if s.get("note"):
            line += f" — {s['note']}"
        lines.append(line)

    if errors:
        lines.append("")
        lines.append("**Errors:**")
        for e in errors:
            lines.append(f"- {e}")

    payload = {"content": "\n".join(lines)}
    return _post_webhook(webhook_url, payload)


def send_batch_alert(
    webhook_url: str,
    watchlist_name: str,
    deals: list[dict],
    run_summary: dict = None,
) -> bool:
    """Send one Discord embed listing all qualifying deals, ranked by rating."""
    RATING_RANK = {"STEAL": 0, "GREAT": 1, "GOOD": 2, "FAIR": 3, "PASS": 4}
    sorted_deals = sorted(deals, key=lambda d: RATING_RANK.get(d.get("rating", "PASS"), 99))

    def fmt_money(v):
        return f"${v:,.0f}" if v is not None else "N/A"

    shown = sorted_deals[:10]
    remainder = len(sorted_deals) - len(shown)

    lines = [f"**{len(deals)} deal{'s' if len(deals) != 1 else ''} found — {watchlist_name}**", ""]

    for deal in shown:
        emoji = RATING_EMOJI.get(deal.get("rating", "PASS"), "📦")
        rating = deal.get("rating", "?")
        title = deal.get("title", "Unknown")[:60]
        price = deal.get("price")
        cons_val = deal.get("conservative_value")
        profit = deal.get("estimated_profit")
        url = deal.get("url", "")

        price_str = fmt_money(price)
        meta_parts = []
        if cons_val is not None:
            meta_parts.append(f"value: {fmt_money(cons_val)}")
        if profit is not None:
            meta_parts.append(f"profit: ~{fmt_money(profit)}")
        meta = f" ({', '.join(meta_parts)})" if meta_parts else ""

        lines.append(f"{emoji} **{rating}** — {title} — {price_str}{meta}")
        # Compact signal line
        signal_parts = []
        nf = deal.get("net_flip")
        if nf and nf.get("net_flip_score") is not None:
            signal_parts.append(f"⚡{nf['net_flip_score']} ROI {nf.get('estimated_roi_percent', 0):.0f}%")
        if deal.get("bundle", {}) and deal["bundle"].get("is_bundle"):
            signal_parts.append(f"🧩 Bundle ~{fmt_money(deal['bundle'].get('estimated_bundle_resale_total'))}")
        if deal.get("bad_listing", {}) and deal["bad_listing"].get("bad_listing_good_item"):
            signal_parts.append(f"🔎 Underpriced ({deal['bad_listing'].get('undervaluation_score')})")
        if signal_parts:
            lines.append("  " + " · ".join(signal_parts))
        if url:
            lines.append(f"🔗 {url}")
        lines.append("")

    if remainder > 0:
        lines.append(f"*...and {remainder} more*")

    if run_summary:
        lines.append("")
        parts = []
        if "raw_count" in run_summary:
            parts.append(f"{run_summary['raw_count']} raw")
        if "parsed_count" in run_summary:
            parts.append(f"{run_summary['parsed_count']} new")
        if "duplicate_count" in run_summary:
            parts.append(f"{run_summary['duplicate_count']} dupes")
        if parts:
            lines.append(f"*Run: {', '.join(parts)}*")

    # Pick embed color from best deal rating
    best_rating = sorted_deals[0].get("rating", "PASS") if sorted_deals else "PASS"
    embed = {
        "description": "\n".join(lines),
        "color": _rating_color(best_rating),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": "Platapicker — Batch Alert"},
    }
    payload = {"embeds": [embed]}
    return _post_webhook(webhook_url, payload)


def send_test_message(webhook_url: str) -> bool:
    payload = {
        "content": "✅ **Platapicker** — Discord webhook is working! Your deal alerts will appear here."
    }
    return _post_webhook(webhook_url, payload)


def send_weekly_review(webhook_url: str, review: dict) -> bool:
    """Post the weekly review as a Discord embed. Built from the dict produced by
    backend.services.weekly_review.generate_weekly_review()."""
    h = review.get("health", {}) or {}
    f = review.get("flow", {}) or {}
    errs = review.get("errors", {}) or {}
    tips = review.get("tuning", []) or []
    days = review.get("window_days", 7)

    o = h.get("ollama", {}) or {}
    ebay = h.get("ebay") or {}
    fields = []

    # 1. Pricing pipeline health
    ollama_line = "🟢 online" if o.get("reachable") else "🔴 offline"
    if o.get("reachable") and (not o.get("maker_present") or not o.get("checker_present")):
        ollama_line = "🟡 online (a model missing)"
    ebay_line = "n/a"
    if ebay:
        ebay_line = f"{'🟢' if ebay.get('status') == 'healthy' else '🟡'} {ebay.get('status', '?')}"
    disagree = h.get("maker_checker_disagree_pct")
    disagree_line = (
        f"{disagree}% needs-review ({h.get('maker_checker_needs_review', 0)}/{h.get('maker_checker_priced', 0)})"
        if disagree is not None else "no AI pricing this week"
    )
    fields.append({
        "name": "🩺 Pricing pipeline",
        "value": (f"Ollama: {ollama_line}\neBay comps: {ebay_line}\n"
                  f"Maker-checker disagreement: {disagree_line}"),
        "inline": False,
    })

    # 2. Deal flow & alerts
    r = f.get("ratings", {}) or {}
    fields.append({
        "name": "📦 Deal flow",
        "value": (f"{f.get('new_listings', 0)} new listings · {f.get('alerts_sent', 0)} alerts · "
                  f"💬 {f.get('leads', 0)} leads\n"
                  f"💎 {r.get('STEAL', 0)} STEAL · 🔥 {r.get('GREAT', 0)} GREAT · "
                  f"✅ {r.get('GOOD', 0)} GOOD"),
        "inline": False,
    })

    # 3. Scraper / source errors
    failed = errs.get("failed_by_source", {}) or {}
    unhealthy = errs.get("unhealthy_sources", []) or []
    if failed or unhealthy:
        lines = []
        for src, info in failed.items():
            lines.append(f"⚠️ {src}: {info['count']} failed run(s)")
        for u in unhealthy:
            lines.append(f"⚠️ {u['name']}: {u['status']}")
        fields.append({"name": "🛠️ Scraper errors", "value": "\n".join(lines[:8]) or "none",
                       "inline": False})
    else:
        fields.append({"name": "🛠️ Scraper errors", "value": "None this week ✅", "inline": False})

    # 4. Tuning suggestions
    fields.append({
        "name": "🎛️ Tuning suggestions",
        "value": "\n".join(f"• {t}" for t in tips)[:1024],
        "inline": False,
    })

    embed = {
        "title": "📊 Platapicker Weekly Review",
        "description": f"Last {days} days",
        "color": 0x6C8EF7,
        "fields": fields,
        "footer": {"text": "Platapicker · automated weekly review"},
    }
    return _post_webhook(webhook_url, {"embeds": [embed]})


def _rating_color(rating: str) -> int:
    colors = {
        "STEAL": 0xFF0000,
        "GREAT": 0xFF8C00,
        "GOOD": 0x00CC44,
        "FAIR": 0xFFD700,
        "PASS": 0x888888,
    }
    return colors.get(rating, 0x888888)
