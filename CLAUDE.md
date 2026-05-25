# Platapicker — CLAUDE.md

AI assistant guide for the **Platapus / Platapicker** codebase. Read this before making any changes.

---

## Project Overview

Platapicker is a **deal-monitoring control center** for resale, auction, and marketplace opportunities. It:

- **Scrapes** Facebook Marketplace, AuctionNinja, and Craigslist for listings matching configurable watchlists
- **Scores** every listing with a deal-scoring engine (price vs. estimated market value)
- **Alerts** via Discord webhooks when strong deals are found
- **Tracks** scraper health, listing history, and price changes
- **Specialises** in GameCube bundle valuation using a fuzzy-matched pricing table
- **Serves** a local React dashboard at `http://localhost:8000`

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | Python 3.11+, FastAPI, Uvicorn |
| ORM / DB | SQLAlchemy 2.x, SQLite (`platapicker.db`) |
| Task scheduling | APScheduler 3.x |
| Web scraping | Playwright (Facebook), HTTPX/BeautifulSoup (others) |
| Fuzzy matching | `thefuzz` + `python-Levenshtein` |
| CLI | Click 8 |
| Frontend | React 18, Vite 5, React Router v6 |
| Data fetching | TanStack Query (React Query v5), Axios |
| Icons | Lucide React |
| Testing | pytest, pytest-asyncio |

---

## Repository Structure

```
Platapus/
├── backend/
│   ├── __init__.py
│   ├── __main__.py          # CLI entry point (python -m platapicker <cmd>)
│   ├── main.py              # FastAPI app factory + lifespan handler
│   ├── api/
│   │   ├── routes.py        # ALL FastAPI route handlers (~33 KB)
│   │   └── schemas.py       # Pydantic request/response schemas
│   ├── models/
│   │   ├── database.py      # SQLAlchemy engine, SessionLocal, Base, init_db()
│   │   └── models.py        # All ORM models (see Database Models section)
│   ├── scrapers/
│   │   ├── base.py          # Abstract BaseScraper + NormalizedListing dataclass
│   │   ├── facebook.py      # Playwright-based Facebook Marketplace scraper
│   │   ├── auctionninja.py  # AuctionNinja scraper
│   │   ├── craigslist.py    # Craigslist scraper
│   │   └── mock_scraper.py  # In-memory mock for tests
│   ├── scoring/
│   │   ├── deal_scorer.py   # Generic price-vs-value scoring engine
│   │   ├── gamecube_scorer.py # GameCube bundle valuation
│   │   └── title_matcher.py # Fuzzy title normalisation & matching
│   └── services/
│       ├── discord.py       # Discord webhook formatting & delivery
│       ├── logging_service.py
│       ├── market_value.py  # eBay sold-listings market value lookup
│       ├── pricecharting.py # PriceCharting.com price sync
│       ├── runner.py        # Scraper orchestration (run_scraper_for_watchlist)
│       ├── scheduler.py     # APScheduler startup/shutdown + heartbeat job
│       ├── seed.py          # Database seeding with default watchlists & sources
│       └── settings.py      # Key-value app settings (get_setting / set_setting)
├── frontend/
│   ├── index.html
│   ├── package.json         # React 18 + Vite + TanStack Query + Axios
│   ├── vite.config.js       # Dev proxy: /api → localhost:8000
│   └── src/
│       ├── main.jsx
│       ├── App.jsx          # App shell + React Router routes
│       ├── App.css          # All custom styles (no CSS framework)
│       ├── api.js           # Axios client (base URL from VITE_API_URL)
│       └── pages/
│           ├── Overview.jsx      # Dashboard summary + quick actions
│           ├── ScraperHealth.jsx # Scraper status + run history
│           ├── Watchlists.jsx    # CRUD for watchlist configs
│           ├── Listings.jsx      # Scraped deals, filter/sort/ignore
│           ├── PricingTables.jsx # GameCube prices, CSV import
│           └── SettingsPage.jsx  # Discord webhooks, thresholds, FB settings
├── tests/
│   ├── test_deal_scorer.py
│   ├── test_discord.py
│   ├── test_duplicate_detection.py
│   ├── test_gamecube_scorer.py
│   ├── test_title_matcher.py
│   └── test_watchlist_filtering.py
├── data/
│   └── gamecube_prices_sample.csv
├── .env.example             # Template — copy to .env
├── requirements.txt
├── run.py                   # Starts Uvicorn (python run.py)
├── platapicker.py           # Thin shim (rarely used)
├── install.sh               # Linux systemd service installer
└── uninstall.sh
```

---

## Development Workflows

### Initial Setup

```bash
# From the repo root
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with Discord webhooks and (optionally) Facebook credentials

# Install Playwright browsers
playwright install chromium
```

### Running the App

```bash
# Backend (API + serves built frontend at localhost:8000)
python run.py

# Frontend dev server with hot-reload (localhost:5173, proxies /api → :8000)
cd frontend
npm install
npm run dev
```

### Running Tests

```bash
# Always run from the repo root
pytest tests/ -v
```

### Building the Frontend

```bash
cd frontend
npm run build   # outputs to frontend/dist/
```

The FastAPI backend automatically serves `frontend/dist/` at `/` if the directory exists.

### CLI Commands

```bash
# All commands run from repo root with venv active
python -m platapicker run --all                        # Run all scrapers
python -m platapicker run --source auctionninja        # One source
python -m platapicker run --watchlist gamecube         # One watchlist
python -m platapicker health                           # Scraper health
python -m platapicker seed                             # Seed DB defaults
python -m platapicker test-discord                     # Test Discord webhook
python -m platapicker import-gamecube-prices <csv>    # Import pricing CSV
python -m platapicker facebook-login                   # Open FB login browser
python -m platapicker facebook-status                  # Check FB session
python -m platapicker reset-duplicates                 # Clear listings cache
python -m platapicker heartbeat                        # Send Discord heartbeat
python -m platapicker scheduler-status                 # Show scheduler config
```

---

## Database Models

All models are in `backend/models/models.py`. The database is **SQLite** by default.

### Models Overview

| Model | Table | Purpose |
|---|---|---|
| `Watchlist` | `watchlists` | Search configuration (keywords, sources, thresholds, Discord) |
| `Source` | `sources` | Scraper source tracking (health, last run, status) |
| `ScraperRun` | `scraper_runs` | Run history with counts and status |
| `Listing` | `listings` | Scraped marketplace listings |
| `DealScore` | `deal_scores` | Scoring result per listing (1-to-1 with Listing) |
| `DiscordWebhook` | `discord_webhooks` | Discord notification endpoints |
| `GameCubePrice` | `gamecube_prices` | GameCube game pricing table |
| `TitleMapping` | `title_mappings` | Fuzzy title match cache |
| `AppSetting` | `app_settings` | Key-value app settings |
| `ListingPriceHistory` | `listing_price_history` | Price change tracking |
| `MarketValueCache` | `market_value_cache` | Cached eBay sold-listing values |

### Critical Pattern: JSON Array Fields

SQLite does not have native array/JSON columns. All list-type fields are stored as
`*_json` `Text` columns containing a JSON-encoded string. Each model exposes them
via `@property` / `@<field>.setter` pairs that handle the JSON encode/decode:

```python
# Correct — uses the property
watchlist.keywords = ["gamecube", "nintendo"]
print(watchlist.keywords)   # ['gamecube', 'nintendo']

# WRONG — sets the raw JSON string directly
watchlist.keywords_json = '["gamecube"]'   # bypasses the property; avoid this
```

Affected fields on `Watchlist`: `keywords`, `negative_keywords`, `brands`,
`aliases`, `locations`, `sources_enabled`.

Affected fields on `Source`: `config`.

Affected fields on `DealScore`: `reasons`, `warnings`.

Affected fields on `GameCubePrice`: `aliases`.

### Source Status Values

```
healthy | warning | failed | needs_login | possible_block | unknown
```

### ScraperRun Status Values

```
running | success | failed | partial
```

### Deal Rating Values (always uppercase)

```
STEAL | GREAT | GOOD | FAIR | PASS
```

Thresholds (price as % of conservative value):
- **STEAL** ≤ 45%
- **GREAT** ≤ 55%
- **GOOD** ≤ 65%
- **FAIR** ≤ 75%
- **PASS** > 75%

---

## API Structure

All routes live in `backend/api/routes.py` and are mounted at the `/api` prefix in `backend/main.py`.

Key route groups:
- `/api/watchlists` — CRUD watchlists
- `/api/sources` — list/toggle scraper sources
- `/api/listings` — list, ignore, re-score listings
- `/api/scraper-runs` — run history
- `/api/discord-webhooks` — CRUD webhook configs
- `/api/gamecube-prices` — pricing table CRUD + CSV import
- `/api/title-mappings` — fuzzy match review
- `/api/settings` — get/set app settings
- `/api/run` — trigger a scrape run (POST)
- `/api/overview` — dashboard stats

CORS allows origins: `http://localhost:5173`, `http://localhost:3000`, `http://localhost:8000`.

### Schema Serialization Pattern

Always use the `from_orm_safe()` class method when constructing Pydantic output
schemas from ORM objects. Direct `model_validate(obj)` calls may fail because
Pydantic tries to read `keywords_json` instead of `keywords`:

```python
# Correct
return WatchlistOut.from_orm_safe(watchlist)

# Risky — may fail on JSON-backed properties
return WatchlistOut.model_validate(watchlist)
```

---

## Scraper Architecture

All scrapers extend `backend/scrapers/base.py::BaseScraper` (ABC).

### Contract

```python
class MyNewScraper(BaseScraper):
    name = "mysource"          # lowercase, matches Source.name in DB

    def fetch_raw_listings(self, keyword: str, location: str, radius_miles: int) -> list[dict]:
        """Fetch raw listing dicts from the external source."""
        ...

    def parse_listing(self, raw: dict) -> Optional[NormalizedListing]:
        """Map a raw dict to a NormalizedListing. Return None to skip."""
        ...
```

### NormalizedListing Fields

```python
@dataclass
class NormalizedListing:
    source: str                          # required
    source_listing_id: Optional[str]     # dedup key
    title: str                           # required
    description: str = ""
    price: Optional[float] = None
    url: Optional[str] = None
    image_url: Optional[str] = None
    location: Optional[str] = None
    distance_miles: Optional[float] = None
    seller: Optional[str] = None
    posted_at: Optional[datetime] = None
    raw_payload: dict = {}               # store the full raw dict for debugging
```

### Facebook Scraper Notes

- Uses **Playwright** (Chromium, headful for login, headless for scraping)
- Session stored in `browser_sessions/facebook/` (gitignored)
- Requires `python -m platapicker facebook-login` before first use
- Implements slow-mode random delays to avoid detection
- Status is updated to `needs_login` or `possible_block` on failure

### Runner Orchestration (`backend/services/runner.py`)

`run_scraper_for_watchlist(source_name, watchlist_id)` is the single entry point
for all scrape runs. It:
1. Queries enabled watchlists + sources from DB
2. Instantiates the correct scraper class
3. Calls `scraper.run(keyword, location, radius)`
4. Deduplicates listings by `source_listing_id`
5. Scores each new listing (GameCube scorer if category matches, else generic scorer)
6. Persists `Listing` + `DealScore` records
7. Sends Discord alerts for listings meeting the watchlist's `min_rating_to_alert`
8. Updates `Source` health and creates `ScraperRun` records

---

## Scoring Engine

### Generic Scorer (`backend/scoring/deal_scorer.py`)

`score_listing(title, description, price, watchlist_keywords, ...) -> DealResult`

- Checks negative keywords first — returns PASS immediately if any match
- Scores keyword/brand matches for confidence
- Computes price-to-conservative-value ratio for rating
- Returns a `DealResult` dataclass (rating, score, profit estimate, reasons, warnings)

### GameCube Scorer (`backend/scoring/gamecube_scorer.py`)

Used when a watchlist has `category == "gamecube"`. It:
1. Fuzzy-matches game titles in the listing against `gamecube_prices` table
2. Values each matched game (loose vs. complete price)
3. Applies bundle discount for large lots
4. Values hardware (console, controllers, memory cards) separately
5. Applies platform selling fee and profit margin targets
6. Returns a `DealResult` with detailed game-by-game reasons

### Title Matcher (`backend/scoring/title_matcher.py`)

- `normalize_title(text)` — strips punctuation, lowercases, collapses whitespace
- `fuzzy_match(query, candidates, threshold=80)` — uses `thefuzz.fuzz.token_set_ratio`
- `TitleMatcher` class caches results in `title_mappings` table; sets `user_confirmed=True` when a human approves a mapping via the dashboard

---

## Frontend Conventions

### State Management

- **TanStack Query** (`useQuery`, `useMutation`) for all server state — do not use local
  `useState` for data fetched from the API
- **Axios** via `src/api.js` for all HTTP calls — the base URL defaults to
  `import.meta.env.VITE_API_URL` or `/` (served by backend in production)
- Local `useState` is fine for UI-only state (modal open, form fields, filters)

### Routing

Routes are defined in `src/App.jsx` using React Router v6 `<Routes>` / `<Route>`.
All pages live in `src/pages/`. Add new pages there and register them in `App.jsx`.

### Styling

- **No CSS framework** — all styles are in `frontend/src/App.css`
- Use existing CSS class names and patterns before adding new ones
- The design is dark-themed; maintain that aesthetic for new UI
- Icons come from **Lucide React** — import named components: `import { RefreshCw } from 'lucide-react'`

### API Client (`src/api.js`)

All API calls go through the exported functions in `api.js`. When adding a new
endpoint, add a corresponding function there — don't inline `axios.get(...)` in
page components.

---

## Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./platapicker.db` | SQLAlchemy DB URL |
| `APP_HOST` | `0.0.0.0` | Uvicorn bind host |
| `APP_PORT` | `8000` | Uvicorn port |
| `DEBUG` | `false` | Enable debug logging |
| `FACEBOOK_EMAIL` | — | FB login (stored for reference, session is used) |
| `FACEBOOK_PASSWORD` | — | FB login |
| `DISCORD_WEBHOOK_*` | — | Optional pre-configured webhooks (also stored in DB) |
| `VITE_API_URL` | `http://localhost:8000` | Frontend API base URL |

**Never commit `.env`** — it is gitignored.

---

## Gitignored Paths (Never Commit)

```
.env
platapicker.db
browser_sessions/
logs/
screenshots/
frontend/dist/
.venv/
__pycache__/
*.pyc
```

---

## Testing

Tests live in `tests/` and use **pytest**. Run from repo root:

```bash
pytest tests/ -v
```

### Test Files

| File | What it covers |
|---|---|
| `test_deal_scorer.py` | Generic scoring ratings, profit margins, negative keywords |
| `test_discord.py` | Discord message formatting, webhook send logic |
| `test_duplicate_detection.py` | Dedup by source_listing_id |
| `test_gamecube_scorer.py` | Bundle valuation, fuzzy game matching |
| `test_title_matcher.py` | Title normalisation, fuzzy thresholds |
| `test_watchlist_filtering.py` | Keyword/negative-keyword/price filtering |

### Writing New Tests

- Use `pytest` fixtures, not `unittest.TestCase`
- Use `pytest-asyncio` for async tests (mark with `@pytest.mark.asyncio`)
- Use `mock_scraper.py` as inspiration for in-memory test doubles
- Do **not** hit live external services in tests
- In-memory SQLite (`sqlite:///:memory:`) is preferred for DB-touching tests

---

## Common Pitfalls

### Running Commands from the Wrong Directory

Always run Python commands from the **repo root** (`Platapus/`), not from inside `backend/`:

```bash
# Correct
cd Platapus
python run.py
python -m platapicker run --all
pytest tests/ -v

# Wrong — will raise "No module named backend"
cd Platapus/backend
python main.py
```

### Accessing JSON-backed Fields

Use the Python property, not the `_json` column:

```python
# Correct
watchlist.keywords          # ['gamecube', 'nintendo']
watchlist.keywords = ['snes']

# Wrong
watchlist.keywords_json     # '["gamecube", "nintendo"]' — raw string
```

### Schema Serialisation

Use `from_orm_safe()` to build Pydantic response objects from ORM instances (see
`backend/api/schemas.py`). This avoids attribute-resolution issues with
JSON-backed properties.

### Database Initialisation

Always call `init_db()` before the first DB access in any script or test.
`init_db()` imports all models (which registers them with `Base.metadata`) and
calls `Base.metadata.create_all()`.

### Adding a New Scraper

1. Create `backend/scrapers/mysource.py` subclassing `BaseScraper`
2. Set `name = "mysource"` (must match the `Source.name` value in the DB)
3. Implement `fetch_raw_listings()` and `parse_listing()`
4. Register it in `backend/scrapers/__init__.py`
5. Add a seed entry in `backend/services/seed.py` so the Source row is created
6. Add it to the scraper-selection logic in `backend/services/runner.py`

### Adding a New API Route

1. Add handler to `backend/api/routes.py`
2. Add request/response Pydantic schemas to `backend/api/schemas.py`
3. Add corresponding API function to `frontend/src/api.js`
4. Call via `useQuery` or `useMutation` in the page component

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                     React Frontend                      │
│  Overview | Health | Watchlists | Listings | Settings   │
│              TanStack Query + Axios (api.js)             │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP /api/*
┌──────────────────────▼──────────────────────────────────┐
│              FastAPI (backend/main.py)                   │
│            CORS | StaticFiles | /api router              │
│                  backend/api/routes.py                   │
└──┬──────────────┬──────────────┬───────────────┬────────┘
   │              │              │               │
   ▼              ▼              ▼               ▼
models/       scoring/       scrapers/       services/
SQLAlchemy    DealScorer     Facebook        Discord
SQLite        GameCube       AuctionNinja    Scheduler
              TitleMatcher   Craigslist      Runner
                             (Playwright)    MarketValue
```

---

## Systemd Service (Production)

For persistent background operation on Linux:

```bash
# Install
chmod +x install.sh && ./install.sh

# Manage
systemctl status platapicker
sudo systemctl restart platapicker
journalctl -u platapicker -f

# Uninstall
./uninstall.sh
```

The service runs `python run.py` from the repo directory as the installing user.
