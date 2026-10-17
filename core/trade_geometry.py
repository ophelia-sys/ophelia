from dataclasses import dataclass
from typing import Optional
import math
from institutional.types import MarketState, Direction

@dataclass
class TradeGeometry:
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    estimated_cost_usdt: float
    reward_to_risk: float

class TradeGeometryEngine:
    def __init__(self, atr_multiplier_sl: float = 2.0, atr_multiplier_tp: float = 3.0):
        self.atr_multiplier_sl = atr_multiplier_sl
        self.atr_multiplier_tp = atr_multiplier_tp

    def calculate_geometry(self, current_price: float, atr: float, direction: Direction, spread: float = 0.0) -> Optional[TradeGeometry]:
        """
        Calculates trade geometry separating execution concerns from predictive probability.
        """
        if direction not in (Direction.BULLISH, Direction.BEARISH) or atr <= 0:
            return None
            
        # Simplified cost estimation: spread + assumed 0.05% fee per side
        estimated_cost = spread + (current_price * 0.001)

        if direction == Direction.BULLISH:
            entry_price = current_price + (spread / 2)
            stop_loss = entry_price - (atr * self.atr_multiplier_sl) - estimated_cost
            tp1 = entry_price + (atr * self.atr_multiplier_tp) + estimated_cost
            tp2 = entry_price + (atr * (self.atr_multiplier_tp * 1.5)) + estimated_cost
            tp3 = entry_price + (atr * (self.atr_multiplier_tp * 2.0)) + estimated_cost
            
            risk = entry_price - stop_loss
            reward = tp1 - entry_price
            
        else: # BEARISH
            entry_price = current_price - (spread / 2)
            stop_loss = entry_price + (atr * self.atr_multiplier_sl) + estimated_cost
            tp1 = entry_price - (atr * self.atr_multiplier_tp) - estimated_cost
            tp2 = entry_price - (atr * (self.atr_multiplier_tp * 1.5)) - estimated_cost
            tp3 = entry_price - (atr * (self.atr_multiplier_tp * 2.0)) - estimated_cost
            
            risk = stop_loss - entry_price
            reward = entry_price - tp1
            
        r_multiple = reward / risk if risk > 0 else 0.0
        
        return TradeGeometry(
            entry_price=round(entry_price, 2),
            stop_loss=round(stop_loss, 2),
            take_profit_1=round(tp1, 2),
            take_profit_2=round(tp2, 2),
            take_profit_3=round(tp3, 2),
            estimated_cost_usdt=round(estimated_cost, 4),
            reward_to_risk=round(r_multiple, 2)
        )
