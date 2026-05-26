# TCG Arbitrage Scanner

Python CLI tool that finds profitable arbitrage opportunities between eBay sold listings and TCGPlayer market prices for Pokémon and One Piece TCG singles.

**Flow:** Buy cheap on eBay → sell on TCGPlayer → profit after all fees and shipping.

## How It Works

1. Pulls TCGPlayer market price via [tcgapi.dev](https://tcgapi.dev)
2. Pulls eBay completed/sold listing comps via [RapidAPI eBay Average Selling Price](https://rapidapi.com/ecommet/api/ebay-average-selling-price)
3. Runs fee math: TCGPlayer 12.75% take rate + shipping both ways
4. Flags cards where `gross_profit >= MIN_PROFIT_DOLLARS` AND `roi >= MIN_ROI_PCT`
5. Outputs a Rich console table + CSV report

## Setup

```bash
git clone https://github.com/duckfat123/tcg-arbitrage.git
cd tcg-arbitrage
pip install -r requirements.txt
cp .env.example .env
# fill in TCGAPI_KEY and RAPIDAPI_KEY in .env
```

**API keys needed:**
- `TCGAPI_KEY` — [tcgapi.dev](https://tcgapi.dev) (free tier: 100 req/day)
- `RAPIDAPI_KEY` — [RapidAPI](https://rapidapi.com/ecommet/api/ebay-average-selling-price) (free tier available)

## Usage

```bash
# Full scan of all 30 watchlist cards
python main.py scan

# Pokémon only
python main.py scan --game pokemon

# Override min profit threshold for this run
python main.py scan --min-profit 5

# Show last scan results from DB (no API calls)
python main.py report

# Export last results to CSV
python main.py report --export

# Add a card to the watchlist
python main.py add "Charizard ex" --set "Obsidian Flames" --game pokemon

# Print current watchlist
python main.py watchlist
```

## Fee Math

```
TCGPlayer net payout  = market_price × (1 - 0.1275)   # 10.25% fee + 2.5% payment processing
Total cost            = ebay_median + shipping_in ($4.00) + shipping_out ($4.50)
Gross profit          = TCGPlayer net payout - total cost
ROI                   = (gross profit / total cost) × 100
```

Default thresholds (configurable in `.env`):

| Setting | Default |
|---------|---------|
| `MIN_PROFIT_DOLLARS` | $3.00 |
| `MIN_ROI_PCT` | 20% |
| `MIN_TCG_PRICE` | $5.00 |
| `MIN_EBAY_COMPS` | 5 sold comps |

## Example Output

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Card                     ┃ Set             ┃ TCG Mkt    ┃ eBay Med   ┃ Cost     ┃ Profit   ┃ ROI %      ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Charizard ex (Alt Art)   │ Obsidian Flames │ $140.00    │ $92.00     │ $100.50  │ $21.95   │ 21.8% ✅   │
│ Umbreon VMAX (Alt Art)   │ Evolving Skies  │ $85.00     │ $52.00     │ $60.50   │ $13.90   │ 22.9% ✅   │
└──────────────────────────┴─────────────────┴────────────┴────────────┴──────────┴──────────┴────────────┘
Scanned 30 cards | 2 opportunities found
```

## Project Structure

```
tcg-arbitrage/
├── main.py              CLI entry point
├── scanner.py           Scan loop — cache-first, skip-on-failure
├── watchlist.csv        Seed watchlist (30 cards: 20 Pokémon + 10 One Piece)
├── core/
│   ├── models.py        Dataclasses: Card, TcgPrice, EbayComp, Opportunity
│   ├── fee_engine.py    calculate_profit() — pure math, no I/O
│   └── database.py      SQLite CRUD + cache TTL logic
├── fetchers/
│   ├── tcg_fetcher.py   tcgapi.dev integration
│   └── ebay_fetcher.py  RapidAPI eBay sold comps + query builder
└── reports/
    ├── console_report.py  Rich table output
    └── csv_report.py      CSV export to output/
```

## Caching

Results are cached in `arbitrage.db` (SQLite) to protect API rate limits:
- TCGPlayer prices: 24-hour TTL
- eBay sold comps: 6-hour TTL (eBay moves faster)

Cache TTLs are configurable via `TCG_CACHE_HOURS` and `EBAY_CACHE_HOURS` in `.env`.

## Watchlist

`watchlist.csv` seeds the DB on first run. Each row:

```csv
card_name,set_name,game,ebay_search_query_override
Charizard ex (Alt Art),Obsidian Flames,pokemon,Charizard ex Obsidian Flames Alternate Art Pokemon NM -PSA -BGS -CGC
```

`ebay_search_query_override` is optional — use when the card name alone returns bad comps. All default queries append `-PSA -BGS -CGC` to exclude graded cards from the median.

## Notes

- eBay API returns **sold/completed** listings (median price), not active asking prices
- TCGPlayer prices assume NM condition — eBay queries target NM raw cards only
- No auto-buying, no auto-listing, no payment info stored
- `arbitrage.db` and `output/` are gitignored
