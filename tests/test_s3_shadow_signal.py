import os
import sys
import pytest
from pathlib import Path

# Add project root to path for imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

from institutional.data.s3_shadow_engine import evaluate_symbol
from exchange.bingx_client import BingXClient
from unittest.mock import MagicMock

def test_shadow_staleness_and_warmup():
    mock_client = MagicMock(spec=BingXClient)
    
    # Mock missing OI archive data
    result = evaluate_symbol(mock_client, "SOL-USDT", 1000000000)
    assert result["data_quality"] == "UNAVAILABLE"
    assert result["reason_code"] == "BBO_UNAVAILABLE" or result["reason_code"] == "OI_MISSING"
    assert result["signal_direction"] == 0
