import pytest
import os
import json
from research.backtest.engine import OpheliaBacktest
from research.backtest.portfolio import PortfolioSimulation
from research.backtest.cost_models import CostModels

def test_hard_fail_missing_dataset():
    """
    Engine MUST fail if dataset does not exist locally.
    It must not silently download.
    """
    with pytest.raises(FileNotFoundError):
        engine = OpheliaBacktest(dataset_id="nonexistent_dataset_v1")

def test_portfolio_accounting():
    """
    Validates long/short PnL and fee deduction.
    """
    portfolio = PortfolioSimulation(initial_capital=10000.0)
    
    # 0 fee environment for pure math test
    cost = CostModels.OPTIMISTIC
    
    # Open Long
    portfolio.execute_trade(1000, "BUY", 100.0, 1.0, cost)
    assert portfolio.current_position == 1.0
    assert portfolio.average_entry_price == 100.0
    
    # Close Long at profit
    portfolio.execute_trade(2000, "SELL", 110.0, 1.0, cost)
    assert portfolio.current_position == 0.0
    assert portfolio.realized_pnl == 10.0
    assert portfolio.capital == 10010.0
    
    # Open Short
    portfolio.execute_trade(3000, "SELL", 100.0, 2.0, cost)
    assert portfolio.current_position == -2.0
    assert portfolio.average_entry_price == 100.0
    
    # Close Short at loss
    portfolio.execute_trade(4000, "BUY", 110.0, 2.0, cost)
    assert portfolio.current_position == 0.0
    assert portfolio.realized_pnl == -10.0
    assert portfolio.capital == 9990.0

def test_cost_model_simulation():
    """
    Validates that BingX simulation subtracts correctly from capital.
    """
    portfolio = PortfolioSimulation(initial_capital=10000.0)
    cost = CostModels.BINGX_SIMULATION  # 5 bps fee + 2 bps slippage
    
    # Open Long 1 BTC at $10,000
    portfolio.execute_trade(1000, "BUY", 10000.0, 1.0, cost)
    
    # Expected deduction: Notional * (entry_fee + entry_slippage)
    # 10000 * (0.00050 + 0.0002) = 10000 * 0.0007 = 7.0
    assert portfolio.total_fees == 5.0
    assert portfolio.total_slippage == 2.0
    assert portfolio.capital == 9993.0
    
    # Close Long at $10,000 (0 raw PnL, just exit costs)
    portfolio.execute_trade(2000, "SELL", 10000.0, 1.0, cost)
    assert portfolio.total_fees == 10.0
    assert portfolio.total_slippage == 4.0
    assert portfolio.capital == 9986.0
