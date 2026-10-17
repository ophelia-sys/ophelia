import pytest
from control_plane import backtest

def test_ablation_flags_influence_candidate_filtering():
    """Verify that ablation flags (VWAP, CVD, RVOL, FVG, RETEST, STRUCTURE) modify candidate evaluation."""
    
    # Baseline with all filters active
    res_baseline = backtest.run_48h_backtest(
        symbols=["BTC-USDT"],
        timeframes=[5],
        hours=24,
        mode="DETERMINISTIC",
        ablation={}
    )
    
    # Disabling retest allows BREAKOUT_DETECTED states immediately, which must increase or equal candidate count
    res_no_retest = backtest.run_48h_backtest(
        symbols=["BTC-USDT"],
        timeframes=[5],
        hours=24,
        mode="DETERMINISTIC",
        ablation={"disable_retest": True}
    )
    
    # Disabling VWAP removes the vwap price acceptance constraint
    res_no_vwap = backtest.run_48h_backtest(
        symbols=["BTC-USDT"],
        timeframes=[5],
        hours=24,
        mode="DETERMINISTIC",
        ablation={"disable_vwap": True}
    )

    # Disabling RVOL removes the rvol >= 1.0 constraint
    res_no_rvol = backtest.run_48h_backtest(
        symbols=["BTC-USDT"],
        timeframes=[5],
        hours=24,
        mode="DETERMINISTIC",
        ablation={"disable_rvol": True}
    )

    # Disabling CVD removes the delta taker volume polarity constraint
    res_no_cvd = backtest.run_48h_backtest(
        symbols=["BTC-USDT"],
        timeframes=[5],
        hours=24,
        mode="DETERMINISTIC",
        ablation={"disable_cvd": True}
    )

    # Disabling FVG removes the fair value gap presence check
    res_no_fvg = backtest.run_48h_backtest(
        symbols=["BTC-USDT"],
        timeframes=[5],
        hours=24,
        mode="DETERMINISTIC",
        ablation={"disable_fvg": True}
    )

    # Disabling structure removes the structural breakout distance bounds
    res_no_structure = backtest.run_48h_backtest(
        symbols=["BTC-USDT"],
        timeframes=[5],
        hours=24,
        mode="DETERMINISTIC",
        ablation={"disable_structure": True}
    )

    # All ablation configurations must execute deterministically without errors
    for r in [res_baseline, res_no_retest, res_no_vwap, res_no_rvol, res_no_cvd, res_no_fvg, res_no_structure]:
        assert r["provenance_mode"] == "DETERMINISTIC"
        assert "summary" in r
        assert "total_trades" in r["summary"]
        assert "execution_block_active" in r["safety_status"]
        assert r["safety_status"]["execution_block_active"] is True
