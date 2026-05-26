"""
Local test suite — validates imports, fee math, DB CRUD, query builder,
FastAPI routes, and compose port config. No API keys needed.
Run: python _test_local.py
"""
import os
import sys
import tempfile

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
errors = []


def check(label, cond, detail=""):
    if cond:
        print(f"  {PASS}  {label}")
    else:
        print(f"  {FAIL}  {label}  {detail}")
        errors.append(label)


# ── 1. Import chain ──────────────────────────────────────────────────────────
print("\n=== 1. Import chain ===")
try:
    from core.models import Card, TcgPrice, EbayComp, Opportunity
    from core.fee_engine import FeeConfig, calculate_profit, load_fee_config
    from core.database import (
        init_db, get_watchlist, add_to_watchlist,
        save_tcg_price, save_ebay_comp, save_opportunity,
        get_recent_opportunities, log_scan, get_last_scans,
        get_cached_tcg_price, get_cached_ebay_comp,
        seed_watchlist_from_csv,
    )
    from fetchers.tcg_fetcher import get_tcg_price
    from fetchers.ebay_fetcher import build_ebay_query, get_ebay_comps
    from reports.csv_report import export_csv
    from reports.console_report import print_opportunities
    from dashboard.app import app
    check("all modules import cleanly", True)
except Exception as e:
    check("all modules import cleanly", False, str(e))
    print("Cannot continue — fix imports first.")
    sys.exit(1)


# ── 2. Fee engine math ───────────────────────────────────────────────────────
print("\n=== 2. Fee engine — core math ===")
cfg = FeeConfig(tcg_fee_rate=0.1025, tcg_payment_rate=0.025, shipping_in=4.0, shipping_out=4.5)

r = calculate_profit(140.0, 92.0, cfg)
expected_payout = round(140.0 * (1 - 0.1275), 2)
expected_cost   = round(92.0 + 4.0 + 4.5, 2)
expected_profit = round(expected_payout - expected_cost, 2)
expected_roi    = round(expected_profit / expected_cost * 100, 1)

check("tcg_net_payout correct",  r.tcg_net_payout == expected_payout,
      f"got {r.tcg_net_payout} expected {expected_payout}")
check("total_cost correct",      r.total_cost == expected_cost,
      f"got {r.total_cost} expected {expected_cost}")
check("gross_profit correct",    r.gross_profit == expected_profit,
      f"got {r.gross_profit} expected {expected_profit}")
check("roi_pct correct",         r.roi_pct == expected_roi,
      f"got {r.roi_pct} expected {expected_roi}")

# Loss scenario
r_loss = calculate_profit(5.0, 20.0, cfg)
check("negative profit on loss", r_loss.gross_profit < 0,
      f"got {r_loss.gross_profit}")

# Zero prices — no crash
try:
    r_zero = calculate_profit(0.0, 0.0, cfg)
    check("zero prices no crash", True)
except Exception as e:
    check("zero prices no crash", False, str(e))

print(f"  payout={r.tcg_net_payout}  cost={r.total_cost}  profit={r.gross_profit}  ROI={r.roi_pct}%")


# ── 3. DB CRUD (temp DB) ─────────────────────────────────────────────────────
print("\n=== 3. SQLite DB CRUD ===")
import core.database as db_mod
tmp_db = tempfile.mktemp(suffix=".db")
db_mod.DB_PATH = tmp_db

try:
    init_db()
    check("init_db() creates tables", True)
except Exception as e:
    check("init_db() creates tables", False, str(e))

# Watchlist
card = Card("Charizard ex", "pokemon", "Obsidian Flames")
add_to_watchlist(card)
wl = get_watchlist()
check("add/get watchlist",
      len(wl) == 1 and wl[0].card_name == "Charizard ex",
      str(wl))

# TCG price cache
price = TcgPrice("Charizard ex", "pokemon", 140.0, "Obsidian Flames", 110.0)
save_tcg_price(price)
cached = get_cached_tcg_price("Charizard ex", "pokemon", "Obsidian Flames", max_age_hours=24)
check("TCG price cache hit",
      cached is not None and cached.market_price == 140.0,
      str(cached))

# eBay comp cache
comp = EbayComp("Charizard ex Obsidian Flames", 60.0, 58.0, 45.0, 90.0, 12)
save_ebay_comp(comp)
cached_ebay = get_cached_ebay_comp("Charizard ex Obsidian Flames", max_age_hours=6)
check("eBay comp cache hit",
      cached_ebay is not None and cached_ebay.median_price == 58.0,
      str(cached_ebay))

# Opportunity
opp = Opportunity("Charizard ex", "pokemon", 140.0, 58.0, 122.15, 66.5, 55.65, 83.7, 12, "Obsidian Flames")
save_opportunity(opp)
opps = get_recent_opportunities()
check("save/get opportunity",
      len(opps) == 1 and opps[0].gross_profit == 55.65,
      str(opps))

# Scan log
log_scan(30, 1)
scans = get_last_scans()
check("scan_log write/read",
      len(scans) == 1 and scans[0]["opps_found"] == 1,
      str(scans))

# CSV export
csv_path = export_csv(opps)
check("CSV export creates file", os.path.isfile(csv_path), csv_path)

# Cleanup
os.unlink(tmp_db)
if os.path.isfile(csv_path):
    os.unlink(csv_path)
check("temp files cleaned up", True)


# ── 4. eBay query builder ────────────────────────────────────────────────────
print("\n=== 4. eBay query builder ===")
q_poke = build_ebay_query("Charizard ex", "Obsidian Flames", "pokemon")
check("pokemon query contains card name", "Charizard ex" in q_poke, q_poke)
check("pokemon query contains game tag",  "Pokemon TCG" in q_poke, q_poke)
check("pokemon query contains NM",        "NM" in q_poke, q_poke)

q_op = build_ebay_query("Monkey D. Luffy", "OP-01", "one-piece")
check("one-piece query contains game tag", "One Piece TCG" in q_op, q_op)
print(f"  pokemon: {q_poke}")
print(f"  one-piece: {q_op}")


# ── 5. FastAPI routes ────────────────────────────────────────────────────────
print("\n=== 5. FastAPI routes ===")
routes = [r.path for r in app.routes]
check("/ route registered",       "/" in routes,       str(routes))
check("/health route registered", "/health" in routes, str(routes))
print(f"  routes: {routes}")


# ── 6. docker-compose port ───────────────────────────────────────────────────
print("\n=== 6. docker-compose.yml port ===")
compose = open("docker-compose.yml").read()
check("port 9000:9000 present",  "9000:9000" in compose, "")
check("port 8080 removed",       "8080" not in compose,  "old port still present")
check("uvicorn port 9000",       "--port 9000" in compose, "")


# ── Summary ──────────────────────────────────────────────────────────────────
print()
if errors:
    print(f"\033[91mFAILED — {len(errors)} check(s):\033[0m")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("\033[92mALL CHECKS PASSED\033[0m")
