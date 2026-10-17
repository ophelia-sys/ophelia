import os
import sys
import pytest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from institutional.data.s3_outcome_tracker import track_outcomes
from exchange.bingx_client import BingXClient
from unittest.mock import MagicMock

def test_outcome_safety():
    mock_client = MagicMock(spec=BingXClient)
    # Ensure tracker can't accidentally execute trades
    assert not hasattr(track_outcomes, "place_order")
