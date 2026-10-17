from dataclasses import dataclass
from typing import Optional

@dataclass
class CostModelConfig:
    entry_fee: float
    exit_fee: float
    entry_slippage: float
    exit_slippage: float
    funding_rate_hourly: Optional[float] = 0.0

class CostModels:
    """
    Standardized execution-cost simulation configurations.
    """
    
    # 0 fees, 0 slippage - theoretical best case
    OPTIMISTIC = CostModelConfig(
        entry_fee=0.0,
        exit_fee=0.0,
        entry_slippage=0.0,
        exit_slippage=0.0,
    )
    
    # Maker-taker average assuming somewhat mixed execution
    REALISTIC = CostModelConfig(
        entry_fee=0.0002,
        exit_fee=0.0002,
        entry_slippage=0.0001,
        exit_slippage=0.0001,
    )
    
    # Taker only execution + bad slippage
    PESSIMISTIC = CostModelConfig(
        entry_fee=0.0006,
        exit_fee=0.0006,
        entry_slippage=0.0003,
        exit_slippage=0.0003,
    )
    
    # Simulation based on assumed BingX VIP/Standard rates (e.g., Taker 0.050%)
    # Do not claim this is exact without verification, this is a SIMULATION.
    BINGX_SIMULATION = CostModelConfig(
        entry_fee=0.00050,  # 5 bps taker
        exit_fee=0.00050,   # 5 bps taker
        entry_slippage=0.0002,
        exit_slippage=0.0002,
    )

    @staticmethod
    def calculate_round_trip_cost(config: CostModelConfig, price: float, quantity: float) -> float:
        notional = price * quantity
        entry_cost = notional * (config.entry_fee + config.entry_slippage)
        exit_cost = notional * (config.exit_fee + config.exit_slippage)
        return entry_cost + exit_cost
