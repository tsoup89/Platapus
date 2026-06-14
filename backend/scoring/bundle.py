"""
Bundle arbitrage detection.

Identifies listings that contain multiple sellable items and estimates whether
the bundle is more profitable broken apart and sold individually. Category-aware:

* GameCube reuses ``title_matcher.match_titles_in_text`` against ``GameCubePrice``
  rows for real per-game values, plus hardware/accessory detection.
* Other categories parse against the per-category ``bundle_item_catalog`` and,
  when a ``comp_lookup`` callable is supplied, upgrade each item's value with a
  live eBay comp.

Text-first; an optional ``photo_analysis`` adds detected accessories as items.

Python 3.9 — Optional[...] / List[...], never ``X | None``.
"""
import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional


@dataclass
class BundleItem:
    item: str
    estimated_resale_price: float
    confidence: str = "MEDIUM"   # LOW | MEDIUM | HIGH

    def to_dict(self) -> dict:
        return {
            "item": self.item,
            "estimated_resale_price": round(self.estimated_resale_price, 2),
            "confidence": self.confidence,
        }


@dataclass
class BundleResult:
    is_bundle: bool = False
    bundle_score: int = 0
    bundle_items: List[BundleItem] = field(default_factory=list)
    estimated_bundle_resale_total: float = 0.0
    estimated_bundle_net_profit: float = 0.0
    recommended_strategy: str = "Sell together"
    liquidation_plan: str = ""
    confidence: str = "LOW"

    def to_dict(self) -> dict:
        return {
            "is_bundle": self.is_bundle,
            "bundle_score": self.bundle_score,
            "bundle_items": [i.to_dict() for i in self.bundle_items],
            "estimated_bundle_resale_total": round(self.estimated_bundle_resale_total, 2),
            "estimated_bundle_net_profit": round(self.estimated_bundle_net_profit, 2),
            "recommended_strategy": self.recommended_strategy,
            "liquidation_plan": self.liquidation_plan,
            "confidence": self.confidence,
        }


# Strategy labels
SELL_TOGETHER = "Sell together"
BREAK_APART = "Break apart and sell items separately"
KEEP_ONE = "Keep one item and sell the rest"
PASS_LOW_CONF = "Pass — low confidence"

_CONF_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
_QTY_WORDS = {
    "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "pair": 2, "couple": 2, "several": 3, "multiple": 2,
}


def _looks_like_bundle(text: str, cfg: dict) -> List[str]:
    """Return the bundle-term signals present in the text."""
    hits = [b for b in cfg.get("bundle_terms", []) if b in text]
    # Quantity signals like "3 controllers", "two chairs"
    if re.search(r"\b([2-9]|1[0-9])\s+\w+s\b", text):
        hits.append("explicit quantity")
    for word in _QTY_WORDS:
        if re.search(rf"\b{word}\b", text):
            hits.append(f"quantity word '{word}'")
            break
    return hits


def _min_conf(items: List[BundleItem]) -> str:
    if not items:
        return "LOW"
    return min((i.confidence for i in items), key=lambda c: _CONF_RANK.get(c, 0))


def _gamecube_items(text: str, gamecube_prices, aliases, cfg) -> List[BundleItem]:
    """Per-item values for a GameCube bundle using the pricing table."""
    from .title_matcher import match_titles_in_text

    items: List[BundleItem] = []
    catalog = cfg.get("bundle_item_catalog", {})
    t = text.lower()

    # Hardware / accessories
    if "console" in t or "gamecube system" in t or "nintendo gamecube" in t:
        c = catalog.get("console", {"est_price": 60.0, "confidence": "HIGH"})
        items.append(BundleItem("Nintendo GameCube console", c["est_price"], c["confidence"]))

    ctrl = re.search(r"(\d+)\s*controller", t)
    n_ctrl = int(ctrl.group(1)) if ctrl else (1 if "controller" in t else 0)
    if n_ctrl:
        c = catalog.get("controller", {"est_price": 25.0, "confidence": "HIGH"})
        for _ in range(min(n_ctrl, 4)):
            items.append(BundleItem("OEM GameCube controller", c["est_price"], c["confidence"]))

    mc = re.search(r"(\d+)\s*memory card", t)
    n_mc = int(mc.group(1)) if mc else (1 if "memory card" in t else 0)
    if n_mc:
        c = catalog.get("memory card", {"est_price": 10.0, "confidence": "HIGH"})
        items.append(BundleItem("GameCube memory card", c["est_price"], c["confidence"]))

    # Games via the real pricing table
    if gamecube_prices:
        matched, _ = match_titles_in_text(text, gamecube_prices, aliases=aliases)
        for m in matched:
            gp = m.gamecube_price
            val = (gp.loose_price or gp.complete_price or 12.0) if gp else 12.0
            conf = "HIGH" if m.confidence >= 0.9 else ("MEDIUM" if m.confidence >= 0.75 else "LOW")
            items.append(BundleItem(m.matched_title or m.raw_text, val, conf))

    return items


def _catalog_items(text: str, cfg: dict, comp_lookup: Optional[Callable]) -> List[BundleItem]:
    """Per-item values for a generic bundle using the category catalog."""
    items: List[BundleItem] = []
    catalog = cfg.get("bundle_item_catalog", {})
    t = text.lower()

    for name, meta in catalog.items():
        if name not in t:
            continue
        # Count occurrences / explicit quantities like "3 chairs"
        qty = 1
        m = re.search(rf"(\d+)\s*{re.escape(name)}", t)
        if m:
            qty = min(int(m.group(1)), 8)

        est = meta.get("est_price", 0.0)
        conf = meta.get("confidence", "MEDIUM")
        # Upgrade with a live comp when available
        if comp_lookup is not None:
            try:
                comp = comp_lookup(name)
                if comp and comp > 0:
                    est = comp
                    conf = "HIGH"
            except Exception:
                pass
        for _ in range(qty):
            items.append(BundleItem(name.title(), est, conf))

    return items


def detect_bundle(
    *,
    title: str,
    description: str = "",
    category: Optional[str] = None,
    category_config: Optional[dict] = None,
    buy_price: Optional[float] = None,
    gamecube_prices: Optional[list] = None,
    aliases: Optional[list] = None,
    comp_lookup: Optional[Callable] = None,   # name -> Optional[float]
    whole_resale_value: Optional[float] = None,
    photo_analysis=None,
) -> BundleResult:
    """Detect a multi-item bundle and estimate the break-apart economics."""
    cfg = category_config or {}
    result = BundleResult()
    text = f"{title or ''} {description or ''}".lower().strip()

    signals = _looks_like_bundle(text, cfg)

    canon = cfg.get("_category")
    if canon == "gamecube" or (category and "gamecube" in category.lower()):
        items = _gamecube_items(text, gamecube_prices, aliases, cfg)
    else:
        items = _catalog_items(text, cfg, comp_lookup)

    # Photo-detected accessories become low-confidence line items if not already counted.
    if photo_analysis is not None:
        existing = {i.item.lower() for i in items}
        for acc in getattr(photo_analysis, "detected_accessories", []) or []:
            if acc.lower() not in existing and acc.lower() not in text:
                items.append(BundleItem(acc.title(), 10.0, "LOW"))

    # A bundle needs either explicit bundle language + ≥1 item, or ≥2 distinct items.
    distinct = len({i.item for i in items})
    result.is_bundle = bool((signals and items) or distinct >= 2)

    if not result.is_bundle:
        result.recommended_strategy = SELL_TOGETHER
        result.liquidation_plan = "Single item — no bundle break-apart opportunity detected."
        return result

    result.bundle_items = items
    total = sum(i.estimated_resale_price for i in items)
    result.estimated_bundle_resale_total = total
    result.confidence = _min_conf(items)

    # Net profit if broken apart: total resale − fees − per-item shipping − buy.
    fee_pct = cfg.get("platform_fee_pct", 0.13)
    ship = 0.0 if cfg.get("local_pickup") else cfg.get("default_shipping_cost", 15.0)
    sell_fees = total * fee_pct
    shipping_total = ship * len(items)
    buy = buy_price or 0.0
    broken_net = total - sell_fees - shipping_total - buy
    result.estimated_bundle_net_profit = broken_net

    # Profit if sold whole (one shipment, one fee).
    whole = whole_resale_value if whole_resale_value else total * 0.75  # bundles sell at a discount
    whole_net = whole - (whole * fee_pct) - ship - buy

    # ── Strategy ──────────────────────────────────────────────────────────────
    if result.confidence == "LOW" and distinct < 2:
        result.recommended_strategy = PASS_LOW_CONF
        result.liquidation_plan = "Item values are low-confidence — verify before buying."
    elif broken_net > whole_net * 1.25 and distinct >= 2:
        result.recommended_strategy = BREAK_APART
        top = max(items, key=lambda i: i.estimated_resale_price)
        result.liquidation_plan = (
            f"Break apart: ~${broken_net:,.0f} net vs ~${whole_net:,.0f} whole. "
            f"Lead with {top.item} (${top.estimated_resale_price:,.0f})."
        )
    elif distinct >= 2 and broken_net > whole_net:
        top = max(items, key=lambda i: i.estimated_resale_price)
        result.recommended_strategy = KEEP_ONE
        result.liquidation_plan = (
            f"Marginal upside breaking apart; consider keeping {top.item} and "
            f"flipping the rest (~${broken_net - top.estimated_resale_price:,.0f})."
        )
    else:
        result.recommended_strategy = SELL_TOGETHER
        result.liquidation_plan = (
            f"Sell together: bundle premium not worth the listing effort "
            f"(~${whole_net:,.0f} net)."
        )

    # ── Bundle score (0-100) ──────────────────────────────────────────────────
    good_profit = cfg.get("good_profit_dollars", 120.0)
    profit_term = max(0.0, min(1.0, broken_net / (good_profit * 1.5)))
    conf_factor = {"LOW": 0.6, "MEDIUM": 0.85, "HIGH": 1.0}[result.confidence]
    count_term = min(1.0, distinct / 4.0)
    score = (0.6 * profit_term + 0.4 * count_term) * 100.0 * conf_factor
    if broken_net <= 0:
        score = min(score, 10.0)
    result.bundle_score = int(round(max(0.0, min(100.0, score))))

    return result
