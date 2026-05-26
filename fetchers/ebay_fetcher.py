import logging
import os
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
RAPIDAPI_HOST = "ebay-average-selling-price.p.rapidapi.com"
API_URL = f"https://{RAPIDAPI_HOST}/findCompletedItems"

# Exclude graded cards — they skew prices far above raw NM comps
DEFAULT_EXCLUDED = "PSA BGS CGC SGC graded fake proxy reprint"


def build_ebay_query(card_name: str, set_name: Optional[str], game: str) -> str:
    game_tag = "Pokemon TCG" if game == "pokemon" else "One Piece TCG"
    parts = [card_name]
    if set_name:
        parts.append(set_name)
    parts.append(game_tag)
    parts.append("NM")
    return " ".join(parts)


def get_ebay_comps(
    keywords: str, excluded_keywords: str = DEFAULT_EXCLUDED
) -> Optional[dict]:
    api_key = os.getenv("RAPIDAPI_KEY")
    if not api_key:
        logger.warning("RAPIDAPI_KEY not configured — skipping eBay fetch")
        return None

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                API_URL,
                json={"keywords": keywords, "excluded_keywords": excluded_keywords},
                headers={
                    "X-RapidAPI-Key": api_key,
                    "X-RapidAPI-Host": RAPIDAPI_HOST,
                    "content-type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        median = data.get("median_price")
        if not median:
            logger.warning(f"No median price in eBay response for '{keywords}'")
            return None

        avg = data.get("average_price") or data.get("avg_price")
        lo = data.get("min_price")
        hi = data.get("max_price")
        results = int(data.get("results") or data.get("num_results") or 0)

        return {
            "avg_price": float(avg) if avg else 0.0,
            "median_price": float(median),
            "min_price": float(lo) if lo else 0.0,
            "max_price": float(hi) if hi else 0.0,
            "num_results": results,
        }
    except httpx.HTTPStatusError as e:
        logger.warning(f"eBay API HTTP {e.response.status_code} for '{keywords}': {e}")
    except httpx.RequestError as e:
        logger.warning(f"eBay API request error for '{keywords}': {e}")
    return None
