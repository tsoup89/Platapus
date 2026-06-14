# 🦆 Platapicker

**Deal monitoring control center for resale, auction, and marketplace opportunities.**

Platapicker monitors multiple sources (Facebook Marketplace, AuctionNinja) for deals matching your watchlists, scores them automatically, and sends Discord alerts when something looks like a steal.

---

## What it does

- **Monitors** Facebook Marketplace and AuctionNinja for deals
- **Scores** every listing using a deal-scoring engine
- **Alerts** you on Discord when a strong deal is found
- **Tracks** scraper health so you always know if something is broken
- **Values** GameCube bundles using a pricing table with fuzzy title matching
- **Remembers** seen listings to avoid duplicate alerts
- **Shows** everything in a local web dashboard
- **Scores deeper** with a **Net Flip Score** (real net profit/ROI after fees,
  shipping, repair, tax & risk), a **bad-listing / undervaluation detector**,
  **bundle break-apart valuation**, and opt-in **photo OCR / model recognition** —
  see [docs/scoring.md](docs/scoring.md)

---

## Install as a Linux Service (Recommended)

Run once. Platapicker starts automatically on boot and runs in the background — no window to keep open.

**Prerequisites:** Python 3.11+, Node.js 18+, npm

```bash
git clone https://github.com/tsoup89/Platapus.git
cd Platapus
chmod +x install.sh
./install.sh
```

The installer will:
1. Create a Python virtualenv and install all dependencies
2. Build the React frontend
3. Install a systemd service that starts on boot
4. Start the service immediately

Once installed:

```bash
# Open the dashboard
xdg-open http://localhost:8000

# View live logs
journalctl -u platapicker -f

# Check status
systemctl status platapicker

# Stop / start / restart
sudo systemctl stop platapicker
sudo systemctl start platapicker
sudo systemctl restart platapicker

# Uninstall
./uninstall.sh
```

After install, edit `.env` with your Discord webhook URLs and Facebook credentials, then restart:

```bash
nano .env
sudo systemctl restart platapicker
```

---

## Manual Quick Start (development)

### 1. Clone and set up Python environment

```bash
cd Platapus
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and add your Discord webhook URLs
```

### 3. Start the backend

```bash
python run.py
```

The API and dashboard will be available at **http://localhost:8000**

### 4. Start the frontend dev server (optional, for hot-reload)

```bash
cd frontend
npm install
npm run dev
```

The dashboard will be available at **http://localhost:5173**

---

## Dashboard

Open **http://localhost:5173** in your browser.

You'll see:

- **Overview** — scraper status, alerts today, quick actions
- **Scraper Health** — detailed status for each source, run history
- **Watchlists** — add/edit/delete deal searches
- **Listings** — all scraped deals with scores, filter/sort/ignore
- **Pricing Tables** — GameCube game prices, CSV import, unmatched title review
- **Settings** — Discord webhooks, deal thresholds, Facebook slow mode, maintenance

---

## Command Line

```bash
# Run all scrapers
python -m platapicker run --all

# Run a specific source
python -m platapicker run --source auctionninja
python -m platapicker run --source facebook

# Run a specific watchlist
python -m platapicker run --watchlist gamecube

# Check scraper health
python -m platapicker health

# Test a Discord webhook
python -m platapicker test-discord

# Import GameCube prices from CSV
python -m platapicker import-gamecube-prices data/gamecube_prices_sample.csv

# Facebook login (opens browser)
python -m platapicker facebook-login

# Check Facebook session status
python -m platapicker facebook-status

# Clear duplicate cache (re-evaluate all listings)
python -m platapicker reset-duplicates

# Seed database with defaults
python -m platapicker seed
```

---

## Setting Up Facebook Marketplace

Facebook requires a logged-in session. The scraper stores your session so you don't need to log in every time.

1. Run: `python -m platapicker facebook-login`
2. A browser window will open. Log in to Facebook normally.
3. Navigate to Marketplace. The scraper will save your session.
4. Close the browser when done.

Your session is stored locally in `browser_sessions/facebook/`. It is excluded from git.

**Dashboard indicators:**
- 🔑 **Needs Login** — session expired, run facebook-login again
- ⚠️ **Possible Block / Rate Limit** — Facebook is rate limiting, wait and try later
- ✅ **Healthy** — everything is working

Facebook slow mode is enabled by default. This adds random delays between actions to avoid detection. You can adjust timing in Settings.

---

## GameCube Pricing

Platapicker uses a CSV pricing table to value GameCube bundles.

### Import pricing data

1. Download pricing from PriceCharting.com (or use the sample CSV at `data/gamecube_prices_sample.csv`)
2. In the dashboard, go to **Pricing Tables** and click **Import CSV**
3. Or from the command line: `python -m platapicker import-gamecube-prices path/to/file.csv`

### CSV format

```
Game,Loose Price,Complete Price,New Price,Graded Price,Box Only,Manual Only
Mario Kart: Double Dash!!,24.99,44.99,89.99,199.99,12.99,4.99
Super Smash Bros. Melee,29.99,54.99,119.99,249.99,14.99,5.99
```

### Fuzzy matching

Platapicker uses fuzzy text matching so listing text doesn't need to match exactly:
- "Double Dash" → matches "Mario Kart: Double Dash!!"
- "Smash Melee" → matches "Super Smash Bros. Melee"
- "Mario Sunshine" → matches "Super Mario Sunshine"

You can add custom aliases in the Watchlists editor.

### Bundle valuation

When a listing contains multiple games, Platapicker:
1. Identifies each game using fuzzy matching
2. Values each game (loose or complete price depending on condition mentioned)
3. Applies bundle discount for large lots
4. Discounts low-demand/sports games more heavily
5. Values console, controllers, and memory cards separately
6. Applies platform selling fee estimate
7. Calculates target buy price for 30% and 40% profit margins

---

## Discord Alerts

### Setup

1. Go to **Settings → Discord Webhooks**
2. Create a webhook for each channel you want to use
3. Go to **Watchlists** and assign a webhook to each watchlist
4. Click **Test** to verify the webhook works

### Alert example

```
⭐ Platapicker Deal Found

Rating: GREAT
Source: Facebook Marketplace
Watchlist: GameCube
Title: Nintendo GameCube Bundle
Price: $180
Conservative Value: $320
Target Buy Price: $220
Estimated Profit: $120

Top Reasons:
- Matched: Mario Kart Double Dash ($45 complete)
- Matched: Super Smash Bros Melee ($55 complete)
- Console detected ($40)
- Price is 56% of conservative value

⚠️ Warnings:
- 2 games could not be matched

🔗 https://facebook.com/marketplace/item/...
```

---

## Deal Ratings

| Rating | What it means |
|--------|---------------|
| 🔥 STEAL | Price ≤ 45% of conservative value — very strong deal |
| ⭐ GREAT | Price ≤ 55% — good deal, worth pursuing |
| ✅ GOOD | Price ≤ 65% — decent margin |
| 🟡 FAIR | Price ≤ 75% — thin margin, proceed with caution |
| ⛔ PASS | Above 75% — not worth it |

Thresholds are configurable in **Settings → Deal Thresholds**.

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Project Structure

```
Platapus/
├── backend/
│   ├── api/           # FastAPI routes and schemas
│   ├── models/        # SQLAlchemy database models
│   ├── scrapers/      # Scraper implementations
│   ├── scoring/       # Deal scoring and GameCube pricing engine
│   ├── services/      # Discord, logging, runner, seed, settings
│   ├── main.py        # FastAPI app entry point
│   └── __main__.py    # CLI entry point
├── frontend/
│   └── src/
│       ├── pages/     # React page components
│       ├── api.js     # API client
│       └── App.jsx    # App shell and routing
├── tests/             # Pytest test suite
├── data/              # Sample pricing CSVs
├── logs/              # Log files (gitignored)
├── screenshots/       # Scraper error screenshots (gitignored)
├── browser_sessions/  # Facebook session (gitignored)
├── .env.example       # Environment variable template
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Security Notes

- Never commit `.env` — it's gitignored
- Never commit `browser_sessions/` — it's gitignored
- Discord webhook URLs are stored in the database (local SQLite), not in code
- The database file is gitignored — do not commit it

---

## Troubleshooting

**"No module named backend"**
Make sure you're running commands from the root `Platapus/` directory, not from inside `backend/`.

**"Facebook needs login"**
Run `python -m platapicker facebook-login` and log in through the browser.

**"No deals found"**
- Check that your watchlist keywords match the listing text
- Check that scrapers are enabled in the watchlist
- Check Scraper Health for errors
- Run a test scrape from the dashboard

**Discord alerts not sending**
- Test the webhook in Settings
- Make sure the watchlist has a webhook assigned
- Check that the deal rating meets the watchlist's minimum alert rating

**GameCube titles not matching**
- Add aliases in the Watchlist editor
- Review unmatched terms in the Pricing Tables page
- Import a more complete pricing CSV

---

## Roadmap

- [x] Scheduled automatic scraping (per-watchlist APScheduler)
- [x] Heartbeat Discord alerts after each run
- [x] Craigslist scraper
- [x] eBay sold-listings market value for scoring
- [x] Alert batching (ranked Discord embed for high-volume runs)
- [x] PriceCharting price sync
- [x] Price history tracking
- [x] Linux systemd service installer
- [ ] Platapicker mascot / logo
- [ ] Mobile-friendly dashboard
- [ ] Email alerts
