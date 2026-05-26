import logging
import os
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
BASE_URL = "https://api.tcgapi.dev/v1"


def get_tcg_price(
    card_name: str, game: str = "pokemon", set_name: Optional[str] = None
) -> Optional[dict]:
    api_key = os.getenv("TCGAPI_KEY")
    if not api_key:
        logger.warning("TCGAPI_KEY not configured — skipping TCG fetch")
        return None

    params: dict = {"game": game, "name": card_name}
    if set_name:
        params["set"] = set_name

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"{BASE_URL}/cards",
                params=params,
                headers={"X-API-Key": api_key},
            )
            resp.raise_for_status()
            data = resp.json()

        if not data:
            logger.warning(f"No TCGApi result for '{card_name}' ({game})")
            return None

        card = data[0] if isinstance(data, list) else data
        market = card.get("market_price") or card.get("marketPrice")
        low = card.get("low_price") or card.get("lowPrice")

        if not market:
            logger.warning(f"No market price in TCGApi response for '{card_name}'")
            return None

        return {
            "name": card.get("name", card_name),
            "set_name": card.get("set_name") or card.get("setName") or set_name,
            "market_price": float(market),
            "low_price": float(low) if low else None,
            "game": game,
        }
    except httpx.HTTPStatusError as e:
        logger.warning(f"TCGApi HTTP {e.response.status_code} for '{card_name}': {e}")
    except httpx.RequestError as e:
        logger.warning(f"TCGApi request error for '{card_name}': {e}")
    return None
