import sys
import os
import json

sys.path.insert(0, r"c:\Users\dopa.mine\Desktop\ophelia")

os.environ["OPH_OLLAMA_URL"] = "http://15.235.193.47:11434"
os.environ["OPH_LLM_PRIMARY"] = "qwen3:4b-direct"

# Mock the database function to prevent errors
from control_plane import db
db.get_max_open_trades = lambda: 2

from control_plane.tradingagents_crypto import execute_tradingagents_crypto_intelligence

res = execute_tradingagents_crypto_intelligence(
    symbol="GOLD (XAU)",
    price=2500.0,
    vwap=2490.0,
    cvd_delta=50000.0,
    rvol=1.5,
    retest_state="CONFIRMED",
    fvg_state="CLOSED",
    structural_sl=2480.0,
    suggested_tp1=2520.0,
    suggested_tp2=2550.0,
    macro_context="Rates steady, DXY down",
    geopolitical_summary="No major events"
)

print(json.dumps(res, indent=2))
