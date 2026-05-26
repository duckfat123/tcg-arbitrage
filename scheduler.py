"""
Scheduled scanner — runs run_scan() on a configurable interval.
Default: every 8 hours (3x/day).

Free-tier API budget with 30-card watchlist:
  TCGPlayer (tcgapi.dev):  30 calls on first daily scan, 0 after (24h cache) = ~30/day  ✅ (limit 100)
  eBay (RapidAPI):         30 calls per scan × 3 scans/day = ~90/day
                           Tune SCAN_INTERVAL_HOURS up if hitting RapidAPI limits.
"""
import logging
import os
import time

import schedule
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

WATCHLIST_CSV = os.path.join(os.path.dirname(__file__), "watchlist.csv")
SCAN_INTERVAL_HOURS = int(os.getenv("SCAN_INTERVAL_HOURS", "8"))


def scan_job() -> None:
    logger.info("Scheduled scan starting...")
    try:
        from scanner import run_scan
        opps = run_scan()
        logger.info(f"Scan complete — {len(opps)} opportunities found")
    except Exception as e:
        logger.error(f"Scan failed: {e}", exc_info=True)


def main() -> None:
    from core.database import init_db, seed_watchlist_from_csv

    init_db()
    seeded = seed_watchlist_from_csv(WATCHLIST_CSV)
    if seeded:
        logger.info(f"Seeded {seeded} cards from watchlist.csv")

    # Run immediately on startup then on schedule
    scan_job()
    schedule.every(SCAN_INTERVAL_HOURS).hours.do(scan_job)
    logger.info(f"Scheduler running — next scan in {SCAN_INTERVAL_HOURS}h")

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
