from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Card:
    card_name: str
    game: str
    set_name: Optional[str] = None
    ebay_query_override: Optional[str] = None
    active: bool = True


@dataclass
class TcgPrice:
    card_name: str
    game: str
    market_price: float
    set_name: Optional[str] = None
    low_price: Optional[float] = None
    fetched_at: datetime = field(default_factory=datetime.now)


@dataclass
class EbayComp:
    search_query: str
    avg_price: float
    median_price: float
    min_price: float
    max_price: float
    num_results: int
    fetched_at: datetime = field(default_factory=datetime.now)


@dataclass
class Opportunity:
    card_name: str
    game: str
    tcg_market: float
    ebay_median: float
    tcg_net_payout: float
    total_cost: float
    gross_profit: float
    roi_pct: float
    ebay_comps_count: int
    set_name: Optional[str] = None
    scanned_at: datetime = field(default_factory=datetime.now)
