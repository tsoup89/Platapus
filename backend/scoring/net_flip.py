"""
Net Flip Score — realistic flip economics.

Layers on top of the existing STEAL/GREAT/GOOD/FAIR/PASS label (which is passed
through unchanged) and answers the question the ratio-based label cannot:
*after fees, shipping, repair, travel, tax, time and risk, is this actually worth
buying — and how confident are we?*

Output is a 0-100 ``net_flip_score`` plus a full economics breakdown. Every
adjustment appends a human-readable line to ``score_reasons`` so a listing's
score can always be explained (and logged).

Python 3.9 — Optional[...] / List[...], never ``X | None``.
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class NetFlipResult:
    deal_label: str = "PASS"
    net_flip_score: int = 0
    estimated_buy_price: float = 0.0
    estimated_resale_price: float = 0.0
    estimated_fees: float = 0.0
    estimated_shipping_cost: float = 0.0
    estimated_repair_cost: float = 0.0
    estimated_net_profit: float = 0.0
    estimated_roi_percent: float = 0.0
    estimated_days_to_sell: int = 0
    confidence: str = "LOW"          # LOW | MEDIUM | HIGH
    risk_level: str = "MEDIUM"       # LOW | MEDIUM | HIGH
    score_reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "deal_label": self.deal_label,
            "net_flip_score": self.net_flip_score,
            "estimated_buy_price": round(self.estimated_buy_price, 2),
            "estimated_resale_price": round(self.estimated_resale_price, 2),
            "estimated_fees": round(self.estimated_fees, 2),
            "estimated_shipping_cost": round(self.estimated_shipping_cost, 2),
            "estimated_repair_cost": round(self.estimated_repair_cost, 2),
            "estimated_net_profit": round(self.estimated_net_profit, 2),
            "estimated_roi_percent": round(self.estimated_roi_percent, 1),
            "estimated_days_to_sell": self.estimated_days_to_sell,
            "confidence": self.confidence,
            "risk_level": self.risk_level,
            "score_reasons": self.score_reasons,
        }


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def compute_net_flip(
    *,
    deal_label: str,
    buy_price: Optional[float],
    resale_price: Optional[float],
    category_config: dict,
    comp_sample_count: int = 0,
    condition_unknown: bool = False,
    condition_poor: bool = False,
    distance_miles: Optional[float] = None,
    tax_rate: float = 0.0,
    photo_missing_parts_risk: Optional[str] = None,   # "LOW" | "MEDIUM" | "HIGH"
    photo_confidence: Optional[str] = None,           # "LOW" | "MEDIUM" | "HIGH" | "NONE"
) -> NetFlipResult:
    """
    Estimate the true net economics of a flip and produce a 0-100 score.

    ``deal_label`` is passed straight through from the existing scorer so the
    legacy label stays authoritative; this function never overrides it.
    """
    cfg = category_config
    result = NetFlipResult(deal_label=deal_label)

    # Guard: without buy + resale we can't do economics — return a neutral shell.
    if not buy_price or not resale_price or buy_price <= 0 or resale_price <= 0:
        result.net_flip_score = 0
        result.confidence = "LOW"
        result.risk_level = "HIGH"
        result.score_reasons.append(
            "No buy/resale pricing available — net flip economics not computable."
        )
        return result

    result.estimated_buy_price = float(buy_price)
    result.estimated_resale_price = float(resale_price)

    # ── Costs ───────────────────────────────────────────────────────────────
    fees = resale_price * cfg.get("platform_fee_pct", 0.13)
    result.estimated_fees = fees

    shipping = 0.0 if cfg.get("local_pickup") else cfg.get("default_shipping_cost", 15.0)
    result.estimated_shipping_cost = shipping

    repair = cfg.get("default_repair_cost", 0.0)
    if condition_poor:
        repair += cfg.get("unknown_condition_repair", 20.0)
        result.score_reasons.append(
            f"Poor/parts condition — +${cfg.get('unknown_condition_repair', 20.0):.0f} repair allowance."
        )
    elif condition_unknown:
        repair += cfg.get("unknown_condition_repair", 20.0) * 0.5
        result.score_reasons.append(
            "Unknown condition — half repair allowance added as a buffer."
        )
    if photo_missing_parts_risk in ("MEDIUM", "HIGH"):
        bump = 15.0 if photo_missing_parts_risk == "HIGH" else 8.0
        repair += bump
        result.score_reasons.append(
            f"Photos suggest missing parts ({photo_missing_parts_risk}) — +${bump:.0f}."
        )
    result.estimated_repair_cost = repair

    tax_amount = buy_price * (tax_rate or 0.0)

    # Travel penalty (treated as a soft cost in the score, not in net profit dollars)
    travel_cost = 0.0
    if distance_miles is not None:
        free = cfg.get("free_travel_miles", 15.0)
        if distance_miles > free:
            travel_cost = (distance_miles - free) * cfg.get("travel_cost_per_mile", 0.30)
            result.score_reasons.append(
                f"{distance_miles:.0f} mi away — ~${travel_cost:.0f} travel penalty."
            )

    # ── Net profit & ROI ──────────────────────────────────────────────────────
    net_profit = resale_price - fees - shipping - repair - travel_cost - tax_amount - buy_price
    result.estimated_net_profit = net_profit

    roi = (net_profit / (buy_price + tax_amount)) * 100 if (buy_price + tax_amount) > 0 else 0.0
    result.estimated_roi_percent = roi
    result.estimated_days_to_sell = int(cfg.get("avg_days_to_sell", 21))

    result.score_reasons.append(
        f"Resale ${resale_price:,.0f} − fees ${fees:,.0f} − shipping ${shipping:,.0f} "
        f"− repair ${repair:,.0f} − buy ${buy_price:,.0f} ⇒ net ${net_profit:,.0f} ({roi:.0f}% ROI)."
    )

    # ── Confidence ────────────────────────────────────────────────────────────
    min_comps = cfg.get("min_comps_for_confidence", 5)
    if comp_sample_count >= min_comps * 2:
        confidence = "HIGH"
    elif comp_sample_count >= min_comps:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"
        result.score_reasons.append(
            f"Only {comp_sample_count} comp(s) (<{min_comps}) — resale estimate is low-confidence."
        )
    # Photo confidence can lift a LOW to MEDIUM when it positively IDs the item.
    if photo_confidence in ("HIGH", "MEDIUM") and confidence == "LOW":
        confidence = "MEDIUM"
        result.score_reasons.append("Photo analysis positively identified the item — confidence raised.")
    result.confidence = confidence

    # ── Risk ──────────────────────────────────────────────────────────────────
    risk_points = 0
    if condition_poor:
        risk_points += 2
    elif condition_unknown:
        risk_points += 1
    if photo_missing_parts_risk == "HIGH":
        risk_points += 2
    elif photo_missing_parts_risk == "MEDIUM":
        risk_points += 1
    if confidence == "LOW":
        risk_points += 1
    if net_profit < 0:
        risk_points += 2
    risk_level = "LOW" if risk_points <= 1 else ("MEDIUM" if risk_points <= 3 else "HIGH")
    result.risk_level = risk_level

    # ── 0-100 Net Flip Score ──────────────────────────────────────────────────
    # Blend of normalized ROI, absolute profit, confidence, and risk penalties.
    good_roi = cfg.get("good_roi_pct", 60.0)
    good_profit = cfg.get("good_profit_dollars", 120.0)

    roi_term = _clamp(roi / good_roi, 0.0, 1.0)              # 0..1
    profit_term = _clamp(net_profit / good_profit, 0.0, 1.0)  # 0..1
    conf_factor = {"HIGH": 1.0, "MEDIUM": 0.85, "LOW": 0.65}[confidence]
    risk_penalty = {"LOW": 0.0, "MEDIUM": 0.12, "HIGH": 0.30}[risk_level]

    base = (0.55 * roi_term + 0.45 * profit_term) * 100.0
    score = base * conf_factor * (1.0 - risk_penalty)
    if net_profit <= 0:
        score = min(score, 10.0)
        result.score_reasons.append("Net profit ≤ $0 — score capped.")

    result.net_flip_score = int(round(_clamp(score, 0.0, 100.0)))
    result.score_reasons.append(
        f"Net Flip {result.net_flip_score}/100 "
        f"(confidence {confidence}, risk {risk_level})."
    )

    return result
