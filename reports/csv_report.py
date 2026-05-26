import csv
import os
from datetime import datetime

from core.models import Opportunity

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")

_FIELDS = [
    "card_name", "set_name", "game", "tcg_market", "ebay_median",
    "tcg_net_payout", "total_cost", "gross_profit", "roi_pct",
    "ebay_comps_count", "scanned_at",
]


def export_csv(opportunities: list[Opportunity]) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(OUTPUT_DIR, f"arbitrage_{timestamp}.csv")

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_FIELDS)
        writer.writeheader()
        for opp in opportunities:
            writer.writerow({
                "card_name": opp.card_name,
                "set_name": opp.set_name or "",
                "game": opp.game,
                "tcg_market": opp.tcg_market,
                "ebay_median": opp.ebay_median,
                "tcg_net_payout": opp.tcg_net_payout,
                "total_cost": opp.total_cost,
                "gross_profit": opp.gross_profit,
                "roi_pct": opp.roi_pct,
                "ebay_comps_count": opp.ebay_comps_count,
                "scanned_at": opp.scanned_at.isoformat(),
            })

    return filepath
