"""Canonical engine tests T01-T12 (spec §22). All fixtures hand-computed."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from research.canonical.data_contract import DataIntegrityError, _gates_on_frame
from research.canonical.indicators import session_vwap, supertrend, atr_rma, true_range
from research.canonical.strategies.vwap_supertrend import detect_active_line_crosses
from research.canonical.execution import resolve_trade
from research.canonical.strategies.base import SignalIntent, TargetSpec


# ------------------------------------------------------------------ fixtures

def mk_candles(n=20, start_ms=1_783_045_800_000, price=100.0):
    tf = 300_000
    rows = []
    p = price
    for i in range(n):
        rows.append({"candle_open_time": start_ms + i * tf,
                     "candle_close_time": start_ms + (i + 1) * tf,
                     "open": p, "high": p * 1.001, "low": p * 0.999,
                     "close": p, "volume": 10.0})
    return pd.DataFrame(rows)


def base_intent(entry_ref_ms, direction=1, stop=95.0, sid="S_TEST_LONG"):
    return SignalIntent(
        signal_id=sid, strategy_id="T", strategy_version="t", dataset_id="SYN",
        dataset_version="SYN.v1", symbol="SOLUSDT", timeframe_minutes=5,
        signal_timeframe_minutes=5, signal_candle_open_time_ms=entry_ref_ms - 300_000,
        signal_time_ms=entry_ref_ms, entry_reference_open_time_ms=entry_ref_ms,
        direction=direction, theoretical_entry_price=None, stop_price=stop,
        target_spec=TargetSpec(use_standard_policies=True),
        entry_model="NEXT_OPEN", trigger=None)


class _Cfg:
    fee_rate_per_side_bps = 5.0
    slippage_scenarios_bps = (0.0, 1.0, 2.0)
    r_targets = (1.0, 1.5, 2.0, 3.0)
    abs_targets_bps = (50.0, 75.0, 100.0)
    primary_exit_policy = "FIXED_R_150"
    position_mode = "SINGLE_POSITION"
    timeframe_minutes = 5


CFG = _Cfg()


def run_one(candles, intent):
    from research.canonical.execution import simulate
    trades, skipped, eod = simulate(candles, [intent], CFG)
    return (trades[0] if trades else None), skipped


def policies_for(entry, risk, direction=1):
    out = {}
    for k in CFG.r_targets:
        out[f"FIXED_R_{int(round(k*100)):03d}"] = entry + direction * k * risk
    for p in CFG.abs_targets_bps:
        out[f"ABS_{int(p):03d}BP"] = entry * (1 + direction * p * 1e-4)
    return out


# ------------------------------------------------------------------ T01 VWAP reset

def test_t01_vwap_session_reset():
    tf = 300_000
    day0 = 86_400_000 * 20000          # arbitrary aligned epoch day
    rows = [
        # day1: two bars, vols 10 & 10 -> vwap bar2 == 101
        dict(candle_open_time=day0, open=100., high=100., low=100., close=100., volume=10.),
        dict(candle_open_time=day0 + tf, open=101., high=103., low=101., close=102., volume=10.),
        # day2 first bar: must reset to its own tp == 50
        dict(candle_open_time=day0 + 86_400_000, open=50., high=50., low=50., close=50., volume=4.),
    ]
    df = pd.DataFrame(rows)
    df["candle_close_time"] = df["candle_open_time"] + tf
    vw = session_vwap(df)
    assert vw[0] == pytest.approx(100.0)
    assert vw[1] == pytest.approx((2020.0 / 20.0))   # (100*10 + 102*10)/20 = 101
    assert vw[2] == pytest.approx(50.0)              # session reset


# ------------------------------------------------------------------ T02/T03 Supertrend

def test_t02_supertrend_matches_legacy_reference():
    from research.experiments.vwap_supertrend.indicators import calc_supertrend as legacy
    rng = np.random.default_rng(7)
    n = 400
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    df = mk_candles(n)
    df["close"] = close
    df["open"] = np.roll(close, 1)
    df.loc[df.index[0], "open"] = close[0]
    df["high"] = np.maximum(df["open"], df["close"]) + np.abs(rng.normal(0, .2, n))
    df["low"] = np.minimum(df["open"], df["close"]) - np.abs(rng.normal(0, .2, n))
    leg = legacy(df.copy(), length=10, factor=3.0)
    d, active, fl, fu = supertrend(df, 10, 3.0)
    assert (d == leg["ST_Direction"].to_numpy()).all()
    assert np.allclose(active[np.isfinite(active)],
                       leg["Supertrend"].to_numpy()[np.isfinite(active)], atol=1e-9)


def test_t03_supertrend_flip_rule():
    # engineered crash forces a flip; verify line switches to finalUpper and rule holds
    n = 60
    df = mk_candles(n, price=100.0)
    df.loc[n - 1, "close"] = 90.0
    df.loc[n - 1, "low"] = 89.5
    d, active, fl, fu = supertrend(df, 10, 3.0)
    k = int(np.where(np.diff(d) != 0)[0][0]) + 1
    if d[k] == -1:
        assert df["close"].iloc[k] < fl[k]
        assert active[k] == pytest.approx(fu[k])
    else:
        assert df["close"].iloc[k] > fu[k]
        assert active[k] == pytest.approx(fl[k])


# ------------------------------------------------------------------ T04 signal detection

def test_t04_signal_detection_inclusive_touch():
    nan = np.nan
    up = np.array([nan, 9.9, 10.0, nan, nan])
    dn = np.array([nan, nan, nan, 10.1, 10.0])
    vw = np.array([10.0, 10.0, 10.0, 10.0, 10.0])
    cl = np.array([10.0, 10.0, 10.05, 9.99, 9.98])
    L, S = detect_active_line_crosses(up, dn, vw, cl)
    assert L == [2] and S == [4]      # inclusive-at-touch on both sides


# ------------------------------------------------------------------ T05 next-open entry

def test_t05_next_open_entry():
    df = mk_candles(10, price=100.0)
    t0 = int(df["candle_open_time"].iloc[3])
    it = base_intent(t0, 1, stop=95.0)
    tr, sk = run_one(df, it)
    assert tr.entry_idx == 3 and tr.entry_price_theoretical == pytest.approx(df["open"].iloc[3])


# ------------------------------------------------------------------ T06-T11 stop/target fills

def _candles_with_bar(idx, o, h, l, c, n=8, start=1_783_045_800_000):
    df = mk_candles(n, start_ms=start, price=100.0)
    df.loc[idx, ["open", "high", "low", "close"]] = [o, h, l, c]
    return df


LONG_STOP = 95.0


def test_t06_touch_stop_long():
    df = _candles_with_bar(4, o=96., h=97., l=94.0, c=96.)
    t0 = int(df["candle_open_time"].iloc[2])
    tr, _ = run_one(df, base_intent(t0, 1, LONG_STOP))
    po = tr.outcomes["FIXED_R_150"]
    assert po.reason == "LOSS" and po.exit_price == pytest.approx(LONG_STOP)
    assert po.exit_idx == 4


def test_t07_gap_through_stop_long():
    df = _candles_with_bar(4, o=93., h=94., l=92.5, c=93.5)
    t0 = int(df["candle_open_time"].iloc[2])
    tr, _ = run_one(df, base_intent(t0, 1, LONG_STOP))
    po = tr.outcomes["FIXED_R_150"]
    assert po.reason == "LOSS" and po.exit_price == pytest.approx(93.0)  # fill at OPEN


def test_t08_gap_through_target_long():
    df = mk_candles(8, price=100.0)
    tgt = 100 * 1.0075
    df.loc[5, ["open", "high", "low", "close"]] = [tgt * 1.002, tgt * 1.004, tgt, tgt * 1.003]
    t0 = int(df["candle_open_time"].iloc[2])
    tr, _ = run_one(df, base_intent(t0, 1, LONG_STOP))
    po = tr.outcomes["ABS_075BP"]
    assert po.reason == "WIN" and po.exit_price == pytest.approx(tgt * 1.002)  # better fill at open


def test_t09_same_candle_stop_and_target_is_loss():
    df = mk_candles(8, price=100.0)
    # one huge bar spanning both stop (95) and 1.5R target (~107.5)
    df.loc[5, ["open", "high", "low", "close"]] = [100., 108., 94.0, 105.]
    t0 = int(df["candle_open_time"].iloc[2])
    tr, _ = run_one(df, base_intent(t0, 1, LONG_STOP))
    po = tr.outcomes["FIXED_R_150"]
    assert po.reason == "LOSS" and po.exit_price == pytest.approx(LONG_STOP)   # A1 STOP FIRST


def test_t10_entry_candle_stop():
    df = mk_candles(8, price=100.0)
    df.loc[2, ["high", "low", "close"]] = [100.2, 94.5, 96.]     # entry bar itself
    t0 = int(df["candle_open_time"].iloc[2])
    tr, _ = run_one(df, base_intent(t0, 1, LONG_STOP))
    prim = tr.outcomes["FIXED_R_150"]
    assert prim.reason == "LOSS" and prim.exit_idx == 2


def test_t11_open_at_stop_fills_at_open_full_loss():
    # Bar OPENS at the stop -> gap rule fills at open => full -1R (no magic stop save).
    df = mk_candles(8, price=100.0)
    df.loc[3, ["open", "high", "low", "close"]] = [95., 95.5, 94.7, 95.2]
    t0 = int(df["candle_open_time"].iloc[2])
    tr, _ = run_one(df, base_intent(t0, 1, LONG_STOP))
    prim = tr.outcomes["FIXED_R_150"]
    assert prim.exit_price == pytest.approx(95.0)
    assert prim.realized_R == pytest.approx(-1.0)


# ------------------------------------------------------------------ T12 end-of-data

def test_t12_end_of_data_censored():
    df = mk_candles(6, price=100.0)                 # drifts nowhere near stop/target
    t0 = int(df["candle_open_time"].iloc[2])
    tr, _ = run_one(df, base_intent(t0, 1, stop=95.02))
    assert tr.censored is True
    assert tr.outcomes["FIXED_R_150"].reason == "CENSORED"
