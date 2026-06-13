"""GameCube-specific pricing and bundle scoring engine."""
from dataclasses import dataclass, field
from typing import Optional
import re
import logging

from .title_matcher import match_titles_in_text, TitleMatch

logger = logging.getLogger("platapicker.gamecube")

DEAL_THRESHOLDS = {
    "STEAL": 0.45,
    "GREAT": 0.55,
    "GOOD": 0.65,
    "FAIR": 0.75,
}

CONSOLE_VALUE = 40.0
CONTROLLER_VALUE = 20.0
MEMORY_CARD_VALUE = 8.0

SPORTS_GAME_KEYWORDS = [
    "madden", "nba", "nfl", "mlb", "nhl", "fifa", "ncaa", "nascar",
    "espn", "backyard sports",
]

CORE_TITLES = [
    "mario kart", "super smash bros", "mario party", "super mario sunshine",
    "luigi's mansion", "the legend of zelda", "wind waker", "twilight princess",
    "metroid prime", "pikmin", "animal crossing", "f-zero gx", "paper mario",
    "resident evil 4", "tales of symphonia", "baten kaitos",
]

BAD_CONDITION_KEYWORDS = [
    "broken", "cracked", "sticky lid", "won't read", "disc read error",
    "parts only", "for parts",
]


@dataclass
class MatchedGame:
    raw_text: str
    matched_title: Optional[str]
    loose_price: Optional[float]
    complete_price: Optional[float]
    confidence: float
    is_core: bool = False
    demand_tier: str = "medium"


@dataclass
class GameCubeResult:
    rating: str = "PASS"
    score: float = 0.0
    matched_games: list = field(default_factory=list)
    unmatched_terms: list = field(default_factory=list)
    total_game_value: float = 0.0
    console_value: float = 0.0
    accessory_value: float = 0.0
    estimated_value: float = 0.0
    conservative_value: float = 0.0
    target_buy_30pct: float = 0.0
    target_buy_40pct: float = 0.0
    estimated_profit: float = 0.0
    profit_margin: float = 0.0
    confidence: float = 0.0
    top_value_games: list = field(default_factory=list)
    reasons: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def _detect_condition(text: str) -> str:
    """Returns 'complete', 'loose', or 'unknown'."""
    t = text.lower()
    if any(kw in t for kw in ["complete", "cib", "box and manual", "with box", "with manual"]):
        return "complete"
    if any(kw in t for kw in ["disc only", "disc", "loose", "no box", "no manual"]):
        return "loose"
    return "unknown"


def _detect_console(text: str) -> bool:
    t = text.lower()
    # Require GameCube/Nintendo context so unrelated "console"s (e.g. a console
    # table, or an Xbox/PS2 console in a mixed estate auction) aren't counted.
    has_gc_context = "gamecube" in t or "game cube" in t or "nintendo" in t
    return has_gc_context and ("console" in t or "system" in t)


def _detect_controllers(text: str) -> int:
    t = text.lower()
    matches = re.findall(r"(\d+)\s*controller", t)
    if matches:
        return int(matches[0])
    if "controller" in t:
        return 1
    return 0


def _detect_memory_cards(text: str) -> int:
    t = text.lower()
    matches = re.findall(r"(\d+)\s*memory card", t)
    if matches:
        return int(matches[0])
    if "memory card" in t:
        return 1
    return 0


def _is_sports_filler(title: str) -> bool:
    t = title.lower()
    return any(kw in t for kw in SPORTS_GAME_KEYWORDS)


def score_gamecube_listing(
    title: str,
    description: str,
    price: float,
    gamecube_prices: list,  # list of GameCubePrice ORM objects
    platform_fee_pct: float = 0.13,
    bundle_discount: float = 0.85,
    low_demand_discount: float = 0.60,
    thresholds: Optional[dict] = None,
    aliases: Optional[list] = None,
) -> GameCubeResult:
    result = GameCubeResult()
    thresholds = thresholds or DEAL_THRESHOLDS
    full_text = f"{title} {description}"

    # --- Detect hardware ---
    has_console = _detect_console(full_text)
    num_controllers = _detect_controllers(full_text)
    num_memory_cards = _detect_memory_cards(full_text)

    bad_condition = any(kw in full_text.lower() for kw in BAD_CONDITION_KEYWORDS)
    condition_type = _detect_condition(full_text)

    # --- Console value ---
    if has_console:
        console_val = CONSOLE_VALUE
        if bad_condition:
            console_val *= 0.60
            result.warnings.append("Console condition issues mentioned (sticky lid, disc read error, etc.)")
        result.console_value = console_val
        result.reasons.append(f"Console detected (value: ${console_val:.0f})")

    result.accessory_value = (
        num_controllers * CONTROLLER_VALUE + num_memory_cards * MEMORY_CARD_VALUE
    )
    if num_controllers > 0:
        result.reasons.append(f"{num_controllers} controller(s) detected (value: ${num_controllers * CONTROLLER_VALUE:.0f})")

    # --- Match game titles ---
    matched, unmatched = match_titles_in_text(full_text, gamecube_prices, aliases=aliases)
    result.unmatched_terms = unmatched

    if unmatched:
        result.warnings.append(f"{len(unmatched)} game title(s) could not be matched — manual review needed.")

    # --- Relevance gate ---
    # If there are no GameCube games (matched or even plausibly game-like) and
    # no GameCube hardware, this isn't a GameCube listing — bail out before it
    # can accrue any value and get rated as a deal.
    if (
        not matched
        and not unmatched
        and not has_console
        and num_controllers == 0
        and num_memory_cards == 0
    ):
        result.rating = "PASS"
        result.score = 0
        result.warnings.append(
            "No GameCube games or hardware detected — filtered as off-topic."
        )
        return result

    # --- Calculate game values ---
    total_game_value = 0.0
    num_games = len(matched)
    matched_game_objects = []

    for m in matched:
        price_row = m.gamecube_price
        is_core = price_row.core_title if price_row else False
        demand = price_row.demand_tier if price_row else "medium"

        if condition_type == "complete" and price_row and price_row.complete_price:
            game_val = price_row.complete_price
        elif price_row and price_row.loose_price:
            game_val = price_row.loose_price
        else:
            game_val = 5.0

        # Apply discounts for filler/low demand
        if demand == "low" or _is_sports_filler(m.matched_title or ""):
            game_val *= low_demand_discount
        elif demand == "medium":
            game_val *= 0.90

        total_game_value += game_val

        matched_game_objects.append(MatchedGame(
            raw_text=m.raw_text,
            matched_title=m.matched_title,
            loose_price=price_row.loose_price if price_row else None,
            complete_price=price_row.complete_price if price_row else None,
            confidence=m.confidence,
            is_core=is_core,
            demand_tier=demand,
        ))

    result.matched_games = matched_game_objects
    result.total_game_value = total_game_value

    # --- Bundle discount ---
    if num_games > 5:
        total_game_value *= bundle_discount
        result.warnings.append(f"Bundle discount applied ({int(bundle_discount * 100)}% of game value for {num_games}+ games).")

    # --- Total estimated value ---
    result.estimated_value = result.console_value + result.accessory_value + total_game_value
    result.conservative_value = result.estimated_value * 0.80  # 20% haircut for conservative

    # --- Confidence ---
    if len(matched) + len(unmatched) > 0:
        match_ratio = len(matched) / max(len(matched) + len(unmatched), 1)
        avg_confidence = sum(m.confidence for m in matched) / max(len(matched), 1)
        result.confidence = match_ratio * avg_confidence
    elif has_console:
        result.confidence = 0.5
    else:
        result.confidence = 0.2

    if result.confidence < 0.5:
        result.warnings.append("Low overall confidence — recommend manual review.")

    # --- Top value games ---
    sorted_games = sorted(
        matched_game_objects,
        key=lambda g: g.complete_price or g.loose_price or 0,
        reverse=True,
    )
    result.top_value_games = [
        g.matched_title for g in sorted_games[:5] if g.matched_title
    ]

    if result.top_value_games:
        result.reasons.append(f"Top value titles: {', '.join(result.top_value_games[:3])}")

    # --- Deal rating ---
    if price and price > 0 and result.conservative_value > 0:
        sell_price = result.conservative_value * (1 - platform_fee_pct)
        result.target_buy_30pct = sell_price * 0.70
        result.target_buy_40pct = sell_price * 0.60

        ratio = price / result.conservative_value
        pct = int(ratio * 100)
        result.reasons.append(f"Price is {pct}% of conservative value (${result.conservative_value:,.0f})")

        result.estimated_profit = sell_price - price
        if sell_price > 0:
            result.profit_margin = result.estimated_profit / sell_price

        th = thresholds
        if ratio <= th.get("STEAL", 0.45):
            result.rating = "STEAL"
        elif ratio <= th.get("GREAT", 0.55):
            result.rating = "GREAT"
        elif ratio <= th.get("GOOD", 0.65):
            result.rating = "GOOD"
        elif ratio <= th.get("FAIR", 0.75):
            result.rating = "FAIR"
        else:
            result.rating = "PASS"

        score_ratio = max(0, 1 - ratio)
        result.score = round(min(score_ratio * 100, 100), 1)
    else:
        result.rating = "FAIR" if result.conservative_value > 0 else "PASS"
        result.score = 20

    return result
