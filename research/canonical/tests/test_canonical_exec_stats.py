"""Canonical engine tests T13-T22: state machine, accounting, stats, gates, determinism."""
from __future__ import annotations

import hashlib
import os
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from research.canonical.strategies.base import SignalIntent, TargetSpec, TriggerEvent
from research.canonical.execution import simulate, resolve_trade
from research.canonical.indicators import session_vwap
from research.canonical import accounting as ACC
from research.canonical import metrics as MET
from research.canonical.data_contract import DataIntegrityError, _gates_on_frame
from test_canonical_core import mk_candles, base_intent, _Cfg


CFG = _Cfg()


def _intent(sid, entry_ref_ms, direction=1, stop=95.0, model="NEXT_OPEN", trigger=None):
    return SignalIntent(
        signal_id=sid, strategy_id="T", strategy_version="t", dataset_id="SYN",
        dataset_version="SYN.v1", symbol="SOLUSDT", timeframe_minutes=5,
        signal_timeframe_minutes=5,
        signal_candle_open_time_ms=entry_ref_ms - 300_000,
        signal_time_ms=entry_ref_ms, entry_reference_open_time_ms=entry_ref_ms,
        direction=direction, theoretical_entry_price=None, stop_price=stop,
        target_spec=TargetSpec(use_standard_policies=True),
        entry_model=model, trigger=trigger)


# ------------------------------------------------------------------ T13 ignored signals

def test_t13_signal_while_open_recorded_not_discarded():
    df = mk_candles(20, price=100.0)
    t0 = int(df["candle_open_time"].iloc[2])
    t1 = int(df["candle_open_time"].iloc[3])       # inside first trade's life (wide stop)
    trades, skipped, eod = simulate(df, [_intent("A", t0), _intent("B", t1)], CFG)
    assert len(trades) == 1 and skipped[0].reason == "POSITION_OPEN"
    # MULTI_POSITION mode trades both (ext EX2)
    class CfgMulti(_Cfg):
        position_mode = "MULTI_POSITION"
    cfg2 = CfgMulti()
    trades2, skipped2, _ = simulate(df, [_intent("A", t0), _intent("B", t1)], cfg2)
    assert len(trades2) == 2 and not skipped2


# ------------------------------------------------------------------ T14 costs

def test_t14_fees_and_slippage_lines():
    df = mk_candles(10, price=100.0)
    df.loc[5, ["open", "high", "low", "close"]] = [102., 103., 101.9, 102.5]
    t0 = int(df["candle_open_time"].iloc[2])

    class CfgT(_Cfg):
        pass
    cfg = CfgT()
    it = base_intent(t0, 1, stop=95.0)
    from research.canonical.execution import resolve_trade
    otime = df["candle_open_time"].to_numpy().astype(np.int64)
    tr = resolve_trade(df["open"].to_numpy(float), df["high"].to_numpy(float),
                       df["low"].to_numpy(float), df["close"].to_numpy(float),
                       otime, 2, 1, 95.0,
                       {f"FIXED_R_{int(round(k*100)):03d}": 100 + k * 5 for k in cfg.r_targets},
                       "FIXED_R_150")
    it = base_intent(t0, 1, stop=95.0)
    tr.intent = it                      # direct-resolve: attach intent for accounting
    rows = ACC.trade_ledger_rows([tr], cfg)
    r = [x for x in rows if x["exit_policy"] == "FIXED_R_150"
         and x["slippage_scenario_bps_per_side"] == 2.0][0]
    gross = (tr.outcomes["FIXED_R_150"].exit_price / 100.0 - 1) * 1e4
    assert r["fees_bps"] == pytest.approx(10.0)
    assert r["slippage_bps_total"] == pytest.approx(4.0)
    assert r["realized_price_return_net_bps"] == pytest.approx(gross - 10.0 - 4.0)
    assert all(x["funding_status"] == "NOT_MODELED" for x in rows)


# ------------------------------------------------------------------ T15/T16 geometry

def test_t15_r_geometry_exact():
    entry, risk = 100.0, 5.0
    pols = {(f"FIXED_R_{int(round(k*100)):03d}"): 100 + k * risk
            for k in CFG.r_targets}
    assert pols["FIXED_R_150"] == pytest.approx(107.5)
    assert pols["FIXED_R_300"] == pytest.approx(115.0)


def test_t16_absolute_target_touch():
    df = mk_candles(8, price=100.0)
    tgt = 100 * 1.0075
    df.loc[4, ["open", "high", "low", "close"]] = [100.1, tgt + .001, 99.9, 100.4]
    from research.canonical.execution import resolve_trade
    otime = df["candle_open_time"].to_numpy().astype(np.int64)
    pols = {"ABS_075BP": tgt}
    tr = resolve_trade(df["open"].to_numpy(float), df["high"].to_numpy(float),
                       df["low"].to_numpy(float), df["close"].to_numpy(float),
                       otime, 2, 1, 95.0, pols, "ABS_075BP")
    po = tr.outcomes["ABS_075BP"]
    assert po.reason == "WIN" and po.exit_price == pytest.approx(tgt)   # touch fill at level


# ------------------------------------------------------------------ T17 short mirror

def test_t17_short_mirror_gap_stop_and_target():
    otime = np.arange(1_783_045_800_000, 1_783_045_800_000 + 300_000 * 8, 300_000).astype(np.int64)
    o = np.full(8, 100.); h = np.full(8, 100.2); l = np.full(8, 99.8); c = np.full(8, 100.)
    # short entry at idx2, stop=105; gap-up through stop at idx4 open=106 -> fill 106
    h[4] = l[4] = c[4] = o[4] = 106.
    tr_stop = resolve_trade(o, h, l, c, otime, 2, -1, 105.0,
                            {"FIXED_R_150": 90.0}, "FIXED_R_150")
    assert tr_stop.outcomes["FIXED_R_150"].reason == "LOSS"
    assert tr_stop.outcomes["FIXED_R_150"].exit_price == pytest.approx(106.)
    # gap-down through target (92.5): fill at open (better); neutralize the stop bar first
    o2 = o.copy(); h2 = h.copy(); l2 = l.copy(); c2 = c.copy()
    h2[4] = 100.2; l2[4] = 99.8; o2[4] = c2[4] = 100.0
    o2[5] = 92.0; h2[5] = 92.5; l2[5] = 91.5; c2[5] = 92.2
    tr_tgt = resolve_trade(o2, h2, l2, c2, otime, 2, -1, 105.0,
                           {"ABS_075BP": 100 * (1 - 0.0075)}, "ABS_075BP")
    assert tr_tgt.outcomes["ABS_075BP"].reason == "WIN"
    assert tr_tgt.outcomes["ABS_075BP"].exit_price == pytest.approx(92.0)


# ------------------------------------------------------------------ T18 integrity gates

def _bad_frame(**mut):
    tf = 300_000
    base = {"candle_open_time": [tf * i for i in range(5)],
            "candle_close_time": [tf * i + tf for i in range(5)],
            "open": [100.] * 5, "high": [101.] * 5, "low": [99.] * 5,
            "close": [100.] * 5, "volume": [10.] * 5}
    base.update(mut)
    return pd.DataFrame(base)


def test_t18_integrity_gates_fail_closed():
    with pytest.raises(DataIntegrityError):
        _gates_on_frame(_bad_frame(candle_open_time=[0, 0, 300000, 600000, 900000],
                                   candle_close_time=[300000] * 5))
    with pytest.raises(DataIntegrityError):
        _gates_on_frame(_bad_frame(candle_open_time=[600000, 0, 300000, 1200000, 1500000],
                                   candle_close_time=[900000] * 5))
    with pytest.raises(DataIntegrityError):
        _gates_on_frame(_bad_frame(high=[98.] * 5))


# ------------------------------------------------------------------ T19 zero volume

def test_t19_zero_volume_vwap_guard():
    df = mk_candles(4)
    df.loc[1, "volume"] = 0.0
    vw = session_vwap(df)
    # bar1 excluded: vwap[1] equals vwap[0]
    assert vw[1] == pytest.approx(vw[0])
    df_all0 = df.copy(); df_all0["volume"] = 0.0
    assert np.isnan(session_vwap(df_all0)).all()


# ------------------------------------------------------------------ T20 determinism

def test_t20_determinism_two_runs_byte_identical(tmp_path):
    from research.canonical.config import CanonicalConfig
    from research.canonical.runner import run_pipeline
    rng = np.random.default_rng(11)
    n = 700
    close = 100 + np.cumsum(rng.normal(0, .3, n))
    df = mk_candles(n)
    df["close"] = close
    df["open"] = np.roll(close, 1); df.iloc[0, df.columns.get_loc("open")] = close[0]
    df["high"] = np.maximum(df["open"], df["close"]) + .1
    df["low"] = np.minimum(df["open"], df["close"]) - .1
    from research.canonical.indicators import supertrend as st, session_vwap as sv
    d, active, fl, fu = st(df, 10, 4.0)
    df["vwap_vendor"] = sv(df)
    df["up_trend_vendor"] = np.where(d == 1, active, np.nan)
    df["down_trend_vendor"] = np.where(d == -1, active, np.nan)
    cfg = CanonicalConfig(dataset_id="SYN", dataset_version="SYN.v1",
                          strategy_id="VWAP_SUPERTREND_ACTIVE_LINE_CROSS",
                          indicator_source="VENDOR_PROVIDED", bootstrap_B=200)
    hashes = []
    for run in range(2):
        out = tmp_path / f"run{run}"
        res = run_pipeline(cfg, df, str(out), dataset_sha256="SYNSHA")
        blob = b"".join(open(res["paths"][k], "rb").read()
                        for k in ("signals", "trades", "metrics", "audit"))
        hashes.append(hashlib.sha256(blob).hexdigest())
    assert hashes[0] == hashes[1]


# ------------------------------------------------- capability extensions T21/T22

def test_t21_model_b_trigger_entry_fill():
    df = mk_candles(10, price=100.0)
    trig = TriggerEvent(trigger_price=101.0, direction=+1,
                        valid_from_open_time_ms=int(df["candle_open_time"].iloc[2]),
                        valid_to_open_time_ms_exclusive=int(df["candle_open_time"].iloc[7]))
    df.loc[4, ["open", "high", "low", "close"]] = [100.6, 101.5, 100.5, 101.2]
    it = _intent("TRIG", int(df["candle_open_time"].iloc[2]), 1, stop=99.0,
                 model="TRIGGER", trigger=trig)
    trades, skipped, eod = simulate(df, [it], CFG)
    assert len(trades) == 1
    tr = trades[0]
    assert tr.entry_idx == 4 and tr.entry_price_theoretical == pytest.approx(101.0)


def test_t21b_trigger_expiry_recorded():
    df = mk_candles(10, price=100.0)
    trig = TriggerEvent(101.0, +1, int(df["candle_open_time"].iloc[2]),
                        int(df["candle_open_time"].iloc[3]))
    it = _intent("TRIGX", int(df["candle_open_time"].iloc[2]), 1, stop=99.0,
                 model="TRIGGER", trigger=trig)
    trades, skipped, eod = simulate(df, [it], CFG)
    assert not trades and skipped[0].reason == "TRIGGER_EXPIRED"


LONG_STOP = 95.0


def run_one(candles, intent):
    trades, skipped = simulate(candles, [intent], CFG)[0:2]
    return (trades[0] if trades else None), skipped
