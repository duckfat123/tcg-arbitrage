import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class FeeConfig:
    tcg_fee_rate: float = 0.1025
    tcg_payment_rate: float = 0.025
    shipping_in: float = 4.00
    shipping_out: float = 4.50


@dataclass
class ProfitResult:
    tcg_net_payout: float
    total_cost: float
    gross_profit: float
    roi_pct: float


def load_fee_config() -> FeeConfig:
    return FeeConfig(
        tcg_fee_rate=float(os.getenv("TCG_FEE_RATE", "0.1025")),
        tcg_payment_rate=float(os.getenv("TCG_PAYMENT_RATE", "0.025")),
        shipping_in=float(os.getenv("DEFAULT_SHIPPING_IN", "4.00")),
        shipping_out=float(os.getenv("DEFAULT_SHIPPING_OUT", "4.50")),
    )


def calculate_profit(
    tcg_market_price: float,
    ebay_median_price: float,
    fee_config: Optional[FeeConfig] = None,
) -> ProfitResult:
    if fee_config is None:
        fee_config = load_fee_config()

    take_rate = fee_config.tcg_fee_rate + fee_config.tcg_payment_rate
    tcg_net_payout = tcg_market_price * (1 - take_rate)
    total_cost = ebay_median_price + fee_config.shipping_in + fee_config.shipping_out
    gross_profit = tcg_net_payout - total_cost
    roi_pct = (gross_profit / total_cost * 100) if total_cost > 0 else 0.0

    return ProfitResult(
        tcg_net_payout=round(tcg_net_payout, 2),
        total_cost=round(total_cost, 2),
        gross_profit=round(gross_profit, 2),
        roi_pct=round(roi_pct, 1),
    )
