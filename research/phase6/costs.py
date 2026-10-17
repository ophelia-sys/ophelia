import numpy as np
from typing import Dict, Any, List

class CostModel:
    """
    Centralized transaction cost and expectancy modeling.
    Outputs the mandated metrics: Gross, Net, Win Rate, PF, MAE, MFE, Frequency.
    """
    def __init__(self, maker_fee: float = 0.0002, taker_fee: float = 0.0005):
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        
    def calculate_net_return(
        self, 
        gross_return: float, 
        scenario: str = "REALISTIC",
        entry_slippage: float = 0.0,
        exit_slippage: float = 0.0,
        funding_cost: float = 0.0
    ) -> Dict[str, float]:
        if scenario == "OPTIMISTIC":
            entry_fee = self.maker_fee
            exit_fee = self.maker_fee
            entry_slip = 0.0
            exit_slip = 0.0
        elif scenario == "REALISTIC":
            entry_fee = self.maker_fee
            exit_fee = self.taker_fee
            entry_slip = entry_slippage
            exit_slip = exit_slippage
        elif scenario == "PESSIMISTIC":
            entry_fee = self.taker_fee
            exit_fee = self.taker_fee
            entry_slip = entry_slippage * 2.0
            exit_slip = exit_slippage * 2.0
        elif scenario == "BINGX_SIMULATION":
            entry_fee = 0.0002
            exit_fee = 0.0005
            entry_slip = entry_slippage if entry_slippage > 0 else 0.0001
            exit_slip = exit_slippage if exit_slippage > 0 else 0.0002
        else:
            raise ValueError(f"Unknown cost scenario: {scenario}")
            
        total_costs = entry_fee + exit_fee + entry_slip + exit_slip + funding_cost
        net_return = gross_return - total_costs
        
        return {
            "gross_return": float(gross_return),
            "total_costs": float(total_costs),
            "net_return": float(net_return)
        }

    def evaluate_trades(self, events: List[Dict[str, Any]], horizon: int, scenario: str = "REALISTIC") -> Dict[str, Any]:
        """
        Evaluate a list of events to produce mandated performance metrics.
        """
        if not events:
            return {
                "N": 0, "gross_expectancy": 0.0, "net_expectancy": 0.0,
                "win_rate": 0.0, "profit_factor": 0.0, "mean_mae": 0.0, "mean_mfe": 0.0,
                "trade_frequency_per_day": 0.0
            }
            
        net_returns = []
        gross_returns = []
        mae_list = []
        mfe_list = []
        total_costs = 0.0
        
        for ev in events:
            gross = ev.get(f"R_{horizon}")
            if gross is None or np.isnan(gross):
                continue
                
            cost_details = self.calculate_net_return(gross, scenario=scenario)
            net_returns.append(cost_details["net_return"])
            gross_returns.append(gross)
            total_costs += cost_details["total_costs"]
            
            mae = ev.get(f"MAE_{horizon}")
            mfe = ev.get(f"MFE_{horizon}")
            if mae is not None and not np.isnan(mae):
                mae_list.append(mae)
            if mfe is not None and not np.isnan(mfe):
                mfe_list.append(mfe)

        N = len(net_returns)
        if N == 0:
            return {
                "N": 0, "gross_expectancy": 0.0, "net_expectancy": 0.0,
                "win_rate": 0.0, "profit_factor": 0.0, "mean_mae": 0.0, "mean_mfe": 0.0,
                "trade_frequency_per_day": 0.0
            }
            
        net_returns = np.array(net_returns)
        gross_returns = np.array(gross_returns)
        
        wins = net_returns[net_returns > 0]
        losses = net_returns[net_returns < 0]
        
        gross_wins = np.sum(wins) if len(wins) > 0 else 0.0
        gross_losses = abs(np.sum(losses)) if len(losses) > 0 else 0.0
        profit_factor = float(gross_wins / gross_losses) if gross_losses > 0 else float('inf')
        
        win_rate = len(wins) / N
        
        # Trade frequency (assume timestamps are in ms)
        timestamps = [ev["timestamp"] for ev in events if "timestamp" in ev]
        if len(timestamps) > 1:
            days = (max(timestamps) - min(timestamps)) / (1000 * 60 * 60 * 24)
            freq = N / days if days > 0 else 0.0
        else:
            freq = 0.0

        return {
            "N": N,
            "gross_expectancy": float(np.mean(gross_returns)),
            "net_expectancy": float(np.mean(net_returns)),
            "total_costs_bps": float((total_costs / N) * 10000), 
            "win_rate": float(win_rate),
            "profit_factor": profit_factor,
            "mean_mae": float(np.mean(mae_list)) if mae_list else 0.0,
            "mean_mfe": float(np.mean(mfe_list)) if mfe_list else 0.0,
            "trade_frequency_per_day": float(freq)
        }
