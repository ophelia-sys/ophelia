import pytest
from datetime import datetime, timezone
import pandas as pd
from unittest.mock import patch, MagicMock

class MockShadowValidator:
    def __init__(self):
        pass
        
    def evaluate_symbol(self, oi_age_sec, funding_age_sec, bbo_age_sec, price_age_sec, oi_val=1000, price_val=50000, is_warmup_complete=True, condition_true=False):
        result = {
            "decision_status": "UNAVAILABLE",
            "reason_code": "UNKNOWN"
        }
        
        if oi_val is None or pd.isna(oi_val):
            result["decision_status"] = "UNAVAILABLE"
            result["reason_code"] = "OI_MISSING"
            return result
            
        if price_val is None or pd.isna(price_val):
            result["decision_status"] = "UNAVAILABLE"
            result["reason_code"] = "PRICE_MISSING"
            return result
            
        if isinstance(bbo_age_sec, str):
            pass # RECEIPT_AGE_ONLY is considered fresh-enough for our purposes
        elif bbo_age_sec > 5:
            result["decision_status"] = "UNAVAILABLE"
            result["reason_code"] = "BBO_STALE"
            return result
            
        if isinstance(price_age_sec, str):
            pass
        elif price_age_sec > 5:
            result["decision_status"] = "UNAVAILABLE"
            result["reason_code"] = "PRICE_STALE"
            return result
            
        if oi_age_sec > 300: # 5 min limit for tests
            result["decision_status"] = "UNAVAILABLE"
            result["reason_code"] = "OI_STALE"
            return result
            
        if funding_age_sec > 28800: # 8 hours
            result["decision_status"] = "UNAVAILABLE"
            result["reason_code"] = "FUNDING_STALE"
            return result
            
        if not is_warmup_complete:
            result["decision_status"] = "UNAVAILABLE"
            result["reason_code"] = "WARMUP_INCOMPLETE"
            return result
            
        if condition_true:
            result["decision_status"] = "SIGNAL"
            result["reason_code"] = "VALID_LONG"
        else:
            result["decision_status"] = "NO_SIGNAL"
            result["reason_code"] = "NO_CROWDING_CONDITION"
            
        return result

@pytest.fixture
def validator():
    return MockShadowValidator()

def test_warmup_status(validator):
    res = validator.evaluate_symbol(oi_age_sec=10, funding_age_sec=10, bbo_age_sec=1, price_age_sec=1, is_warmup_complete=False)
    assert res["decision_status"] == "UNAVAILABLE"
    assert res["reason_code"] == "WARMUP_INCOMPLETE"

def test_valid_no_signal(validator):
    res = validator.evaluate_symbol(oi_age_sec=10, funding_age_sec=10, bbo_age_sec=1, price_age_sec=1, is_warmup_complete=True, condition_true=False)
    assert res["decision_status"] == "NO_SIGNAL"

def test_valid_signal(validator):
    res = validator.evaluate_symbol(oi_age_sec=10, funding_age_sec=10, bbo_age_sec=1, price_age_sec=1, is_warmup_complete=True, condition_true=True)
    assert res["decision_status"] == "SIGNAL"

def test_oi_outage(validator):
    res = validator.evaluate_symbol(oi_age_sec=7200, funding_age_sec=10, bbo_age_sec=1, price_age_sec=1)
    assert res["decision_status"] == "UNAVAILABLE"
    assert res["reason_code"] == "OI_STALE"

def test_funding_outage(validator):
    res = validator.evaluate_symbol(oi_age_sec=10, funding_age_sec=43200, bbo_age_sec=1, price_age_sec=1)
    assert res["decision_status"] == "UNAVAILABLE"
    assert res["reason_code"] == "FUNDING_STALE"

def test_recovery_transition(validator):
    # During outage
    res1 = validator.evaluate_symbol(oi_age_sec=7200, funding_age_sec=10, bbo_age_sec=1, price_age_sec=1, condition_true=True)
    assert res1["decision_status"] == "UNAVAILABLE"
    
    # After recovery (fresh data, but condition is false)
    res2 = validator.evaluate_symbol(oi_age_sec=2, funding_age_sec=10, bbo_age_sec=1, price_age_sec=1, condition_true=False)
    assert res2["decision_status"] == "NO_SIGNAL"
    
    # After recovery (fresh data, condition is true)
    res3 = validator.evaluate_symbol(oi_age_sec=2, funding_age_sec=10, bbo_age_sec=1, price_age_sec=1, condition_true=True)
    assert res3["decision_status"] == "SIGNAL"

if __name__ == "__main__":
    pytest.main([__file__])
