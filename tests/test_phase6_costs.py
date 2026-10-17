import pytest
from research.phase6.costs import CostModel

def test_cost_scenarios():
    model = CostModel(maker_fee=0.0002, taker_fee=0.0005)
    
    # OPTIMISTIC: Maker + Maker = 0.0004
    net_opt = model.calculate_net_return(0.01, scenario="OPTIMISTIC")
    assert pytest.approx(net_opt["net_return"]) == 0.01 - 0.0004
    
    # REALISTIC: Maker + Taker = 0.0007
    net_real = model.calculate_net_return(0.01, scenario="REALISTIC")
    assert pytest.approx(net_real["net_return"]) == 0.01 - 0.0007
    
    # PESSIMISTIC: Taker + Taker = 0.0010 + double slippage (0.0002) = 0.0012
    net_pess = model.calculate_net_return(0.01, scenario="PESSIMISTIC", entry_slippage=0.0001, exit_slippage=0.0001)
    assert pytest.approx(net_pess["net_return"]) == 0.01 - 0.0010 - 0.0004
    
    # Funding Test
    net_fund = model.calculate_net_return(0.01, scenario="OPTIMISTIC", funding_cost=0.0001)
    assert pytest.approx(net_fund["net_return"]) == 0.01 - 0.0004 - 0.0001
