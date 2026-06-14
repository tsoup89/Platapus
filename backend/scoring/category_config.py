"""
Config-driven, per-category scoring rules.

Single source of truth for every knob the new scoring modules
(net_flip, bad_listing, bundle) and the photo-analysis pipeline read.
Add a new category by appending an entry to ``CATEGORY_OVERRIDES`` — anything
omitted falls back to ``CATEGORY_DEFAULTS``.

Python 3.9 — use Optional[...] / List[...], never the ``X | None`` syntax.
"""
from copy import deepcopy
from typing import Optional


# ── Defaults applied to every category ──────────────────────────────────────
CATEGORY_DEFAULTS = {
    # Resale economics
    "resale_channel": "ebay",
    "platform_fee_pct": 0.13,          # eBay-ish final value fee blend
    "default_shipping_cost": 15.0,     # sell-side outbound shipping per item
    "local_pickup": False,             # True → shipping defaults to 0 (sold local)
    "default_repair_cost": 0.0,        # baseline refurb/cleaning cost
    "unknown_condition_repair": 20.0,  # added when condition is unknown/poor
    "avg_days_to_sell": 21,            # used for the time-to-sell penalty

    # Net-Flip scoring weights (all blended in net_flip.compute_net_flip)
    "min_comps_for_confidence": 5,     # fewer comps → confidence penalty
    "good_roi_pct": 60.0,             # ROI at/above which the ROI term saturates
    "good_profit_dollars": 120.0,      # net profit at which the profit term saturates
    "travel_cost_per_mile": 0.30,      # round-trip-ish travel penalty
    "free_travel_miles": 15.0,         # no travel penalty within this radius

    # Bad-listing / undervaluation detection
    "generic_title_terms": [
        "lot", "bundle", "stuff", "items", "various", "miscellaneous", "misc",
        "old", "vintage", "untested", "unknown", "no name", "generic",
    ],
    "urgency_phrases": [
        "must go", "must sell", "need gone", "need it gone", "moving",
        "moving sale", "pickup today", "pick up today", "asap", "today only",
        "garage cleanout", "estate sale", "downsizing", "first come",
        "cash only", "no holds", "make offer", "obo", "quick sale",
    ],
    "bundle_terms": [
        "lot", "bundle", "set", "everything pictured", "all pictured",
        "box of", "lot of", "bulk", "collection", "moving sale",
        "garage cleanout", "estate", "package deal", "plus", "and more",
        "+ more", "various",
    ],
    "misspellings": {
        # global brand/category typos seen across many categories
        "game cube": "gamecube",
        "nintendo game cube": "nintendo gamecube",
    },
    "known_models": {},                # brand -> [model strings] for OCR/bundle hints
    "bundle_item_catalog": {},         # item name -> {"est_price": float, "confidence": str}
}


# ── Per-category overrides (shallow-merged onto the defaults) ────────────────
CATEGORY_OVERRIDES = {
    "espresso": {
        "resale_channel": "ebay",
        "platform_fee_pct": 0.13,
        "default_shipping_cost": 35.0,     # heavy, bulky
        "default_repair_cost": 10.0,       # descale / clean
        "unknown_condition_repair": 35.0,
        "avg_days_to_sell": 18,
        "good_profit_dollars": 140.0,
        "misspellings": {
            "expresso": "espresso",
            "exspresso": "espresso",
            "esspresso": "espresso",
            "breveille": "breville",
            "brevile": "breville",
            "breville": "breville",
            "delonghi": "delonghi",
            "de longhi": "delonghi",
            "gaggia": "gaggia",
            "rancillio": "rancilio",
            "nespreso": "nespresso",
        },
        "known_models": {
            "Breville": ["BES870XL", "BES878", "BES880", "BES900", "Barista Express",
                         "Barista Pro", "Barista Touch", "Bambino", "Dual Boiler"],
            "Gaggia": ["Classic Pro", "Classic", "Brera", "Anima"],
            "Rancilio": ["Silvia", "Silvia Pro"],
            "De'Longhi": ["La Specialista", "Dedica", "Magnifica", "Eletta"],
            "Nespresso": ["Vertuo", "Vertuo Next", "Creatista", "Lattissima"],
        },
        "bundle_item_catalog": {
            "espresso machine": {"est_price": 250.0, "confidence": "MEDIUM"},
            "grinder": {"est_price": 80.0, "confidence": "MEDIUM"},
            "tamper": {"est_price": 15.0, "confidence": "HIGH"},
            "knock box": {"est_price": 20.0, "confidence": "HIGH"},
            "milk frother": {"est_price": 25.0, "confidence": "MEDIUM"},
            "portafilter": {"est_price": 30.0, "confidence": "MEDIUM"},
            "scale": {"est_price": 20.0, "confidence": "MEDIUM"},
        },
    },

    "gamecube": {
        "resale_channel": "ebay",
        "platform_fee_pct": 0.13,
        "default_shipping_cost": 12.0,
        "avg_days_to_sell": 14,
        "good_profit_dollars": 80.0,
        "misspellings": {
            "game cube": "gamecube",
            "gamecub": "gamecube",
            "nintindo": "nintendo",
            "nintedo": "nintendo",
        },
        "known_models": {
            "Nintendo": ["GameCube", "DOL-001", "DOL-101"],
        },
        # Per-item values for gamecube come from GameCubePrice rows + title_matcher;
        # this catalog only covers hardware/accessory fallbacks.
        "bundle_item_catalog": {
            "console": {"est_price": 60.0, "confidence": "HIGH"},
            "controller": {"est_price": 25.0, "confidence": "HIGH"},
            "memory card": {"est_price": 10.0, "confidence": "HIGH"},
            "game": {"est_price": 15.0, "confidence": "LOW"},
        },
    },

    "sonos": {
        "resale_channel": "ebay",
        "platform_fee_pct": 0.13,
        "default_shipping_cost": 20.0,
        "avg_days_to_sell": 16,
        "good_profit_dollars": 100.0,
        "misspellings": {
            "sonnos": "sonos",
            "sonus": "sonos",
            "sono": "sonos",
        },
        "known_models": {
            "Sonos": ["One", "One SL", "Era 100", "Era 300", "Play:1", "Play:3",
                      "Play:5", "Beam Gen 1", "Beam Gen 2", "Arc", "Sub", "Sub Gen 3",
                      "Move", "Roam", "Five", "Port", "Amp", "Connect"],
        },
        "bundle_item_catalog": {
            "sonos one": {"est_price": 130.0, "confidence": "HIGH"},
            "sonos beam": {"est_price": 280.0, "confidence": "HIGH"},
            "sonos arc": {"est_price": 600.0, "confidence": "HIGH"},
            "sonos sub": {"est_price": 400.0, "confidence": "MEDIUM"},
            "sonos play:1": {"est_price": 90.0, "confidence": "MEDIUM"},
            "sonos move": {"est_price": 200.0, "confidence": "MEDIUM"},
        },
    },

    "monitor": {
        "resale_channel": "ebay",
        "platform_fee_pct": 0.13,
        "default_shipping_cost": 30.0,
        "unknown_condition_repair": 0.0,   # monitors aren't really repairable
        "avg_days_to_sell": 20,
        "good_profit_dollars": 100.0,
        "misspellings": {
            "ultra wide": "ultrawide",
            "ultra-wide": "ultrawide",
            "samsumg": "samsung",
            "delll": "dell",
        },
        "known_models": {
            "Dell": ["U3818DW", "U3419W", "S3422DWG", "AW3423DW"],
            "LG": ["34GP83A", "38WN95C", "34WN80C"],
            "Samsung": ["Odyssey G9", "Odyssey G7", "CRG9"],
        },
        "bundle_item_catalog": {
            "monitor": {"est_price": 150.0, "confidence": "MEDIUM"},
            "monitor arm": {"est_price": 40.0, "confidence": "MEDIUM"},
            "docking station": {"est_price": 60.0, "confidence": "MEDIUM"},
            "keyboard": {"est_price": 30.0, "confidence": "LOW"},
        },
    },

    "furniture": {
        "resale_channel": "facebook",
        "platform_fee_pct": 0.0,           # FB Marketplace local — no fees
        "local_pickup": True,
        "default_shipping_cost": 0.0,
        "default_repair_cost": 0.0,
        "unknown_condition_repair": 25.0,  # cushions / cleaning
        "avg_days_to_sell": 25,
        "good_profit_dollars": 120.0,
        "known_models": {
            "Herman Miller": ["Aeron", "Embody", "Mirra", "Sayl"],
            "Steelcase": ["Leap", "Leap V2", "Gesture", "Amia", "Series 1"],
            "Humanscale": ["Freedom", "Liberty", "Diffrient"],
        },
        "bundle_item_catalog": {
            "table": {"est_price": 80.0, "confidence": "MEDIUM"},
            "chair": {"est_price": 35.0, "confidence": "MEDIUM"},
            "umbrella": {"est_price": 40.0, "confidence": "MEDIUM"},
            "cushions": {"est_price": 30.0, "confidence": "LOW"},
            "cover": {"est_price": 20.0, "confidence": "LOW"},
            "office chair": {"est_price": 120.0, "confidence": "MEDIUM"},
        },
    },

    "tools": {
        "resale_channel": "ebay",
        "platform_fee_pct": 0.13,
        "default_shipping_cost": 18.0,
        "unknown_condition_repair": 15.0,
        "avg_days_to_sell": 15,
        "good_profit_dollars": 90.0,
        "misspellings": {
            "milwakee": "milwaukee",
            "milwakie": "milwaukee",
            "dewalt": "dewalt",
            "de walt": "dewalt",
            "makta": "makita",
        },
        "known_models": {
            "Milwaukee": ["M18", "M18 Fuel", "M12", "M12 Fuel"],
            "DeWalt": ["20V Max", "Flexvolt", "Atomic", "Xtreme"],
            "Makita": ["18V LXT", "XGT"],
        },
        "bundle_item_catalog": {
            "drill": {"est_price": 60.0, "confidence": "MEDIUM"},
            "impact driver": {"est_price": 70.0, "confidence": "MEDIUM"},
            "battery": {"est_price": 40.0, "confidence": "MEDIUM"},
            "charger": {"est_price": 25.0, "confidence": "MEDIUM"},
            "case": {"est_price": 15.0, "confidence": "LOW"},
        },
    },
}


# ── Category aliasing ───────────────────────────────────────────────────────
# Map watchlist category strings (which vary) onto a canonical config key.
_CATEGORY_ALIASES = {
    "espresso machines": "espresso",
    "espresso machine": "espresso",
    "coffee": "espresso",
    "ultrawide": "monitor",
    "ultrawide monitor": "monitor",
    "monitors": "monitor",
    "display": "monitor",
    "outdoor furniture": "furniture",
    "outdoor_furniture": "furniture",
    "patio": "furniture",
    "patio furniture": "furniture",
    "patio_furniture": "furniture",
    "outdoor": "furniture",
    "office": "furniture",
    "sonos speakers": "sonos",
    "sonos outdoor speakers": "sonos",
    "speakers": "sonos",
    "speaker": "sonos",
    "tool": "tools",
    "tool lot": "tools",
    "power tools": "tools",
}


def canonical_category(category: Optional[str]) -> Optional[str]:
    """Normalise a free-form watchlist category to a config key, if known."""
    if not category:
        return None
    key = category.strip().lower()
    if key in CATEGORY_OVERRIDES:
        return key
    return _CATEGORY_ALIASES.get(key)


def get_category_config(category: Optional[str]) -> dict:
    """
    Return the merged config for a category: a deep copy of CATEGORY_DEFAULTS
    with the matching override shallow-merged on top. Dict-valued keys
    (misspellings, known_models, bundle_item_catalog) are merged, not replaced,
    so a category inherits the global misspellings plus its own.
    """
    config = deepcopy(CATEGORY_DEFAULTS)
    canon = canonical_category(category)
    if canon and canon in CATEGORY_OVERRIDES:
        override = CATEGORY_OVERRIDES[canon]
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(config.get(key), dict):
                merged = dict(config[key])
                merged.update(value)
                config[key] = merged
            else:
                config[key] = value
        config["_category"] = canon
    else:
        config["_category"] = None
    return config
