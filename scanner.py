import logging
import os
from typing import Optional

from dotenv import load_dotenv

from core.database import (
    get_cached_ebay_comp,
    get_cached_tcg_price,
    get_watchlist,
    save_ebay_comp,
    save_opportunity,
    save_tcg_price,
)
from core.fee_engine import calculate_profit, load_fee_config
from core.models import EbayComp, Opportunity, TcgPrice
from fetchers.ebay_fetcher import build_ebay_query, get_ebay_comps
from fetchers.tcg_fetcher import get_tcg_price

load_dotenv()
logger = logging.getLogger(__name__)


def _thresholds() -> dict:
    return {
        "min_profit": float(os.getenv("MIN_PROFIT_DOLLARS", "3.00")),
        "min_roi": float(os.getenv("MIN_ROI_PCT", "20.0")),
        "min_tcg_price": float(os.getenv("MIN_TCG_PRICE", "5.00")),
        "min_ebay_comps": int(os.getenv("MIN_EBAY_COMPS", "5")),
        "tcg_cache_hours": int(os.getenv("TCG_CACHE_HOURS", "24")),
        "ebay_cache_hours": int(os.getenv("EBAY_CACHE_HOURS", "6")),
    }


def run_scan(
    game: Optional[str] = None,
    min_profit_override: Optional[float] = None,
) -> list[Opportunity]:
    t = _thresholds()
    if min_profit_override is not None:
        t["min_profit"] = min_profit_override

    fee_config = load_fee_config()
    watchlist = get_watchlist(game=game)

    if not watchlist:
        logger.warning("Watchlist empty. Add cards with: python main.py add <name>")
        return []

    opportunities: list[Opportunity] = []
    skipped_price = skipped_comps = skipped_threshold = 0

    for card in watchlist:
        # TCGPlayer price (cache-first)
        tcg_price = get_cached_tcg_price(
            card.card_name, card.game, card.set_name,
            max_age_hours=t["tcg_cache_hours"],
        )
        if tcg_price is None:
            raw = get_tcg_price(card.card_name, card.game, card.set_name)
            if raw is None:
                logger.warning(f"Skipping '{card.card_name}' — TCGPlayer fetch failed")
                skipped_price += 1
                continue
            tcg_price = TcgPrice(
                card_name=raw["name"],
                game=raw["game"],
                set_name=raw.get("set_name"),
                market_price=raw["market_price"],
                low_price=raw.get("low_price"),
            )
            save_tcg_price(tcg_price)

        if tcg_price.market_price < t["min_tcg_price"]:
            logger.debug(f"Skipping '{card.card_name}' — TCG ${tcg_price.market_price:.2f} below minimum")
            skipped_price += 1
            continue

        # eBay sold comps (cache-first)
        query = card.ebay_query_override or build_ebay_query(
            card.card_name, card.set_name, card.game
        )
        ebay_comp = get_cached_ebay_comp(query, max_age_hours=t["ebay_cache_hours"])
        if ebay_comp is None:
            raw_ebay = get_ebay_comps(query)
            if raw_ebay is None:
                logger.warning(f"Skipping '{card.card_name}' — eBay fetch failed")
                skipped_comps += 1
                continue
            ebay_comp = EbayComp(
                search_query=query,
                avg_price=raw_ebay["avg_price"],
                median_price=raw_ebay["median_price"],
                min_price=raw_ebay["min_price"],
                max_price=raw_ebay["max_price"],
                num_results=raw_ebay["num_results"],
            )
            save_ebay_comp(ebay_comp)

        if ebay_comp.num_results < t["min_ebay_comps"]:
            logger.warning(f"Skipping '{card.card_name}' — only {ebay_comp.num_results} eBay comps")
            skipped_comps += 1
            continue

        # Fee math
        result = calculate_profit(
            tcg_market_price=tcg_price.market_price,
            ebay_median_price=ebay_comp.median_price,
            fee_config=fee_config,
        )

        if result.gross_profit < t["min_profit"] or result.roi_pct < t["min_roi"]:
            skipped_threshold += 1
            continue

        opp = Opportunity(
            card_name=card.card_name,
            game=card.game,
            set_name=card.set_name,
            tcg_market=tcg_price.market_price,
            ebay_median=ebay_comp.median_price,
            tcg_net_payout=result.tcg_net_payout,
            total_cost=result.total_cost,
            gross_profit=result.gross_profit,
            roi_pct=result.roi_pct,
            ebay_comps_count=ebay_comp.num_results,
        )
        save_opportunity(opp)
        opportunities.append(opp)

    opportunities.sort(key=lambda o: o.gross_profit, reverse=True)

    logger.info(
        f"Scan complete — {len(watchlist)} scanned, {len(opportunities)} found "
        f"({skipped_price} price skip, {skipped_comps} comp skip, {skipped_threshold} below threshold)"
    )
    return opportunities
