# Scoring & Signal Reference

Platapicker scores every listing with the legacy **deal label**
(STEAL / GREAT / GOOD / FAIR / PASS — a discount-to-resale ratio) and, since
2026‑06‑01, layers four additional, **informational** signals on top. The new
signals never change which listings trigger Discord alerts — the legacy label and
`min_rating_to_alert` still control that. They simply add depth to the alert and
the API.

All per-category knobs live in one file:
[`backend/scoring/category_config.py`](../backend/scoring/category_config.py).
Add or tune a category there — fees, shipping, repair allowances, misspellings,
known models, generic/urgency/bundle vocab, and the bundle item catalog.

---

## 1. Net Flip Score — `backend/scoring/net_flip.py`

A 0–100 score answering *"after all real costs, is this actually worth buying?"*

```
net_profit = resale − platform_fees − shipping − repair − travel − tax − buy
roi%       = net_profit / (buy + tax) × 100
```

Persisted on `DealScore`:

| Field | Meaning |
|---|---|
| `net_flip_score` | 0–100 blend of ROI, absolute profit, confidence, risk |
| `estimated_roi_percent` | ROI after all costs |
| `net_profit` | estimated dollars in pocket |
| `risk_level` | LOW / MEDIUM / HIGH (unknown condition, poor photos, thin comps) |
| `confidence_label` | LOW / MEDIUM / HIGH (driven by comp count + photo confidence) |
| `net_flip_json` | full breakdown incl. `score_reasons` (the "why") |

Key config knobs per category: `platform_fee_pct`, `default_shipping_cost`,
`local_pickup`, `default_repair_cost`, `unknown_condition_repair`,
`min_comps_for_confidence`, `good_roi_pct`, `good_profit_dollars`,
`travel_cost_per_mile`, `free_travel_miles`.

## 2. Bad Listing, Good Item — `backend/scoring/bad_listing.py`

Flags under-described listings where value is hidden. Signals: misspelled brands
(explicit map **and** `rapidfuzz` against the watchlist brands), generic/short
titles, urgency phrases, bundle language, weak descriptions, and **brand/model
visible in the photo but absent from the title**. Persisted as `bad_listing_json`
(`bad_listing_good_item`, `undervaluation_score`, `detected_signals`,
`suggested_reason`).

## 3. Bundle Arbitrage — `backend/scoring/bundle.py`

Detects multi-item listings and estimates the break-apart economics.
GameCube uses the real `GameCubePrice` table via `title_matcher`; other categories
use the per-category `bundle_item_catalog`, upgraded with a live eBay comp when
available. Persisted as `bundle_json` (`is_bundle`, `bundle_items`,
`estimated_bundle_resale_total`, `estimated_bundle_net_profit`,
`recommended_strategy`, `liquidation_plan`, `confidence`). Strategies:
*Sell together · Break apart · Keep one + sell the rest · Pass — low confidence*.

## 4. Photo Analysis (OCR / model recognition) — `backend/services/photo_analysis.py`

Pluggable pipeline. **Off by default.** Enable with the `photo_analysis_enabled`
app setting (a Claude API key must already be configured). When on,
`ClaudeVisionAnalyzer` reads the listing photo and extracts `ocr_text`,
`detected_brand`, `detected_model`, `detected_accessories`,
`detected_condition_issues`, `missing_parts_risk`, and `image_confidence`
(stored on `Listing.detected_brand`, `detected_model`, `photo_analysis_json`).

The pipeline is **fail-open**: any error returns an empty result and the scrape
continues. A detected model number is fed back into the eBay comp keyword
(sharper comps) and into the Net Flip risk/repair adjustments. To plug in another
provider (OpenAI, local OCR), implement `PhotoAnalyzer` and return it from
`get_photo_analyzer()`.

---

### Discord

Alerts gain a concise extras line only when data is present, e.g.:

```
💰 Net Flip 82/100 · ROI 68% · net $122 · risk MEDIUM
🧩 Bundle: Break apart and sell items separately (~$195 total)
🔎 Possibly underpriced (78): Generic listing title, Urgency language detected
```

### API

All fields are exposed on `DealScoreOut` / `ListingOut`
([`backend/api/schemas.py`](../backend/api/schemas.py)) for the frontend.
