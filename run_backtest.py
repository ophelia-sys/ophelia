import traceback
try:
    from research.experiments.vwap_supertrend.backtest import run_backtest
    run_backtest()
except Exception as e:
    with open("crash.log", "w") as f:
        traceback.print_exc(file=f)
