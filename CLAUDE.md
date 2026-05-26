# TCG Arbitrage Scanner — Developer Context

## Project Overview

Python CLI tool that identifies eBay → TCGPlayer arbitrage for Pokémon and One Piece TCG singles.
Buys signal: eBay sold median price. Sell signal: TCGPlayer market price. Profit = net TCGPlayer payout minus all costs.

## Tech Stack

- **Language**: Python 3.10+
- **HTTP**: `httpx` (sync client, timeout configured per fetcher)
- **Config**: `.env` via `python-dotenv`
- **Database**: SQLite via stdlib `sqlite3` — file: `arbitrage.db` in project root
- **Output**: `rich` console table + CSV to `output/`

## External APIs

### tcgapi.dev (TCGPlayer pricing)
- Base URL: `https://api.tcgapi.dev/v1`
- Auth: `X-API-Key` header
- Key endpoint: `GET /cards?game=pokemon&name=Charizard`
- Response fields used: `market_price`, `low_price`, `name`, `set_name`
- Rate limit: 100 req/day free tier, 10k/day Pro ($49.99/mo)
- Cache TTL: 24 hours (`TCG_CACHE_HOURS`)

### RapidAPI — ebay-average-selling-price
- URL: `https://ebay-average-selling-price.p.rapidapi.com/findCompletedItems`
- Auth: `X-RapidAPI-Key` + `X-RapidAPI-Host` headers
- Method: POST, JSON body: `{"keywords": "...", "excluded_keywords": "..."}`
- Response fields used: `median_price`, `average_price`, `min_price`, `max_price`, `results`
- **Use `median_price` as buy estimate** — average is skewed by graded outliers
- Cache TTL: 6 hours (`EBAY_CACHE_HOURS`)

## Fee Math (IMPORTANT — verify before changing)

```
TCGPlayer take rate   = TCG_FEE_RATE (10.25%) + TCG_PAYMENT_RATE (2.5%) = 12.75%
TCGPlayer net payout  = market_price × (1 - 0.1275)
Total cost            = ebay_median + DEFAULT_SHIPPING_IN ($4.00) + DEFAULT_SHIPPING_OUT ($4.50)
Gross profit          = net_payout - total_cost
ROI                   = (gross_profit / total_cost) × 100
```

All fee rates are configurable in `.env`. Logic lives in `core/fee_engine.py`.

## Project Structure

```
tcg-arbitrage/
├── main.py              CLI entry — argparse, dispatches to cmd_* functions
├── scanner.py           run_scan() — cache-first loop, skip-on-failure, returns sorted Opportunity list
├── watchlist.csv        Seed file — loaded once on first run if DB watchlist is empty
├── core/
│   ├── models.py        Dataclasses: Card, TcgPrice, EbayComp, Opportunity
│   ├── fee_engine.py    calculate_profit(), load_fee_config(), FeeConfig, ProfitResult
│   └── database.py      init_db(), seed_watchlist_from_csv(), get/save for all tables, cache TTL checks
├── fetchers/
│   ├── tcg_fetcher.py   get_tcg_price() — returns dict or None on any failure
│   └── ebay_fetcher.py  get_ebay_comps(), build_ebay_query() — returns dict or None on any failure
└── reports/
    ├── console_report.py  print_opportunities() via Rich table
    └── csv_report.py      export_csv() → output/arbitrage_<timestamp>.csv
```

## Database Schema

```sql
watchlist       — cards to scan (seeded from watchlist.csv on first run)
tcg_prices      — cached TCGPlayer prices with fetched_at timestamp
ebay_comps      — cached eBay sold comps keyed by search_query string
opportunities   — all flagged arb hits, persisted for report/history
```

Cache reads in `database.py` filter by `fetched_at > (now - TTL hours)` and return the most recent match.

## CLI Commands

```bash
python main.py scan                      # full watchlist scan
python main.py scan --game pokemon       # filter by game
python main.py scan --min-profit 5       # override threshold for this run
python main.py report                    # show last 50 from DB (no API calls)
python main.py report --export           # + export CSV
python main.py add "Card Name" --set "Set" --game pokemon
python main.py watchlist                 # print all active watchlist cards
```

## Key Constraints

- **API failures must not crash the scan.** Both fetchers return `None` on any error; scanner logs a warning and skips the card.
- **Never hardcode API keys.** Always read from environment via `os.getenv()`.
- **eBay query quality matters.** Default queries append the game name, "NM", and `-PSA -BGS -CGC` to exclude graded cards. Override per-card via `ebay_query_override` column in watchlist.
- **TCGPlayer prices assume NM condition.** Keep eBay queries targeting NM raw only.
- **Cache aggressively.** Free TCGPlayer API tier is 100 req/day — a full 30-card scan would consume it in one run without caching.
- **Median, not average** for eBay buy estimate. PSA 10 sales will skew averages on high-demand cards.

## Thresholds (all configurable in .env)

| Env Var | Default | Purpose |
|---------|---------|---------|
| `MIN_PROFIT_DOLLARS` | 3.00 | Skip if gross profit < $3 |
| `MIN_ROI_PCT` | 20.0 | Skip if ROI < 20% |
| `MIN_TCG_PRICE` | 5.00 | Skip if TCGPlayer market < $5 |
| `MIN_EBAY_COMPS` | 5 | Skip if fewer than 5 sold comps |

## Environment Variables

```env
TCGAPI_KEY=
RAPIDAPI_KEY=
MIN_PROFIT_DOLLARS=3.00
MIN_ROI_PCT=20.0
MIN_TCG_PRICE=5.00
MIN_EBAY_COMPS=5
TCG_FEE_RATE=0.1025
TCG_PAYMENT_RATE=0.025
DEFAULT_SHIPPING_IN=4.00
DEFAULT_SHIPPING_OUT=4.50
TCG_CACHE_HOURS=24
EBAY_CACHE_HOURS=6
```

## Known Limitations / Phase 2

- No scheduled auto-scan yet — runs are manual only
- eBay active BIN listings not checked (only completed/sold)
- No Discord/email alert integration
- One Piece card catalog browsing not implemented (Pokémon only for set browsing)
