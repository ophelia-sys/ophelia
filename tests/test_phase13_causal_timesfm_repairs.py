"""Regression tests for Phase 13 causal feature availability and TimesFM provenance.

These tests are deterministic and use synthetic candles. They are not alpha or
profitability evidence; they verify implementation invariants only.
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd

from control_plane import phase13_discovery_engine as p13
from control_plane import timesfm_candidate as tfm


def make_1m_frame(periods: int = 600) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01 00:00:00", periods=periods, freq="min")
    x = np.arange(periods, dtype=float)
    close = 100.0 + 0.01 * x + 0.5 * np.sin(x / 11.0)
    open_ = close + 0.02 * np.cos(x / 5.0)
    high = np.maximum(open_, close) + 0.15
    low = np.minimum(open_, close) - 0.15
    return pd.DataFrame(
        {
            "timestamp": idx.asi8 // 1_000_000,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": 10.0 + (x % 7.0),
        },
        index=idx,
    )


def build_completed_features(df_1m: pd.DataFrame) -> pd.DataFrame:
    source = df_1m.copy().sort_index()
    source.index.name = "dt"
    bars_5m, bars_15m, bars_1h, bars_4h = p13.resample_phase13_bars(source)
    bars_5m["atr_14"] = p13.compute_atr(bars_5m["high"], bars_5m["low"], bars_5m["close"], 14)
    bars_15m["atr_14"] = p13.compute_atr(bars_15m["high"], bars_15m["low"], bars_15m["close"], 14)
    bars_1h["atr_14"] = p13.compute_atr(bars_1h["high"], bars_1h["low"], bars_1h["close"], 14)
    bars_4h["ema20"] = bars_4h["close"].ewm(span=20, adjust=False).mean()
    bars_4h["ema50"] = bars_4h["close"].ewm(span=50, adjust=False).mean()
    bars_4h["trend_4h"] = np.where(
        bars_4h["ema20"] > bars_4h["ema50"] * 1.001,
        "BULL",
        np.where(bars_4h["ema20"] < bars_4h["ema50"] * 0.999, "BEAR", "NEUTRAL"),
    )
    return p13.merge_completed_htf_features(bars_5m, bars_15m, bars_1h, bars_4h)


def make_candidate_candles(n: int = 20) -> list[dict]:
    base_ts = 1_704_067_200_000
    return [
        {
            "ts": base_ts + i * 300_000,
            "open": 100.0 + i,
            "high": 101.0 + i,
            "low": 99.0 + i,
            "close": 100.5 + i,
            "volume": 1000.0 + i,
            "closed": True,
        }
        for i in range(n)
    ]


def make_forecast_context(candidate_ts: int) -> tfm.CandidateForecastContext:
    return tfm.CandidateForecastContext(
        candidate_id="CAUSAL-TEST-001",
        canonical_instrument_id="CRYPTO:BTCUSDT",
        symbol="BTCUSDT",
        direction="LONG",
        candidate_timestamp_ms=candidate_ts,
        entry_price=119.5,
        sl_price=118.0,
        tp1_price=122.0,
        tp2_price=None,
    )


class FakeTimesFMModel:
    def __init__(self) -> None:
        self.context = None

    def predict(self, context, horizon, return_quantiles, sort_quantiles):
        self.context = np.asarray(context).copy()
        return SimpleNamespace(
            forecast=np.asarray([float(context[-1]) + 0.1 * (i + 1) for i in range(horizon)]),
            quantiles=np.tile(np.asarray([float(context[-1]) - 2.0, float(context[-1]), float(context[-1]) + 2.0]), (horizon, 1)),
        )


class TestPhase13CausalFeatureRepairs(unittest.TestCase):
    def test_htf_features_are_unavailable_until_the_source_bar_closes(self):
        source = make_1m_frame()
        merged = build_completed_features(source)
        start = source.index[0]

        # At 00:05 the 15m, 1h and 4h source candles are not completed.
        early = merged.loc[start]
        self.assertTrue(pd.isna(early["atr_15m"]))
        self.assertTrue(pd.isna(early["atr_1h"]))
        self.assertTrue(pd.isna(early["trend_4h"]))

        # The 00:00-04:00 4h bar is available at 04:00, before the 04:00-04:05
        # 5m decision is made.
        four_hour_decision = merged.loc[start + pd.Timedelta(hours=4)]
        self.assertTrue(pd.notna(four_hour_decision["trend_4h"]))

    def test_future_corruption_cannot_change_earlier_htf_features_or_swings(self):
        source = make_1m_frame()
        altered = source.copy()
        start = source.index[0]
        decision_bar_open = start + pd.Timedelta(hours=6)
        future_start = decision_bar_open + pd.Timedelta(minutes=5)

        future_mask = altered.index >= future_start
        altered.loc[future_mask, ["open", "high", "low", "close"]] += 250.0

        original_features = build_completed_features(source)
        altered_features = build_completed_features(altered)

        feature_columns = [
            "atr_15m", "atr_1h", "trend_4h",
            "swing_low_15m", "swing_high_15m",
            "swing_low_1h", "swing_high_1h",
        ]
        pd.testing.assert_frame_equal(
            original_features.loc[[decision_bar_open], feature_columns],
            altered_features.loc[[decision_bar_open], feature_columns],
            check_exact=True,
        )

    def test_incomplete_ohlcv_bucket_is_dropped(self):
        source = make_1m_frame()
        gap_ts = source.index[2]
        source = source.drop(index=gap_ts)
        bars_5m, _, _, _ = p13.resample_phase13_bars(source)
        self.assertNotIn(pd.Timestamp("2024-01-01 00:00:00"), bars_5m.index)

    def test_absent_orderflow_is_not_replaced_by_counts_or_zeros(self):
        bars_5m, _, _, _ = p13.resample_phase13_bars(make_1m_frame())
        for field in ("delta_v", "aggressive_buy_volume", "aggressive_sell_volume"):
            self.assertIn(field, bars_5m.columns)
            self.assertTrue(bars_5m[field].isna().all())

    def test_partial_orderflow_bucket_remains_unavailable(self):
        source = make_1m_frame()
        source["delta_v"] = 1.0
        source.loc[source.index[2], "delta_v"] = np.nan
        bars_5m, _, _, _ = p13.resample_phase13_bars(source)
        self.assertTrue(pd.isna(bars_5m.loc[source.index[0], "delta_v"]))
        self.assertEqual(float(bars_5m.iloc[1]["delta_v"]), 5.0)

    def test_vwap_dispersion_uses_consistent_volume_weighted_second_moment(self):
        idx = pd.date_range("2024-01-01", periods=3, freq="5min")
        frame = pd.DataFrame(
            {"close": [100.0, 102.0, 101.0], "volume": [1.0, 3.0, 2.0]},
            index=idx,
        )
        vwap, std = p13.compute_vwap(frame)
        self.assertAlmostEqual(float(vwap.iloc[1]), 101.5, places=10)
        self.assertAlmostEqual(float(std.iloc[1]), np.sqrt(0.75), places=10)
        self.assertTrue(pd.isna(std.iloc[0]))

    def test_sub_02_stop_regime_is_accounted_for(self):
        self.assertEqual(p13.classify_stop_regime(0.0015), "SUB_02")
        self.assertEqual(p13.classify_stop_regime(0.0020), "TIGHT_02_03")

class TestTimesFMCausalAndProvenanceRepairs(unittest.TestCase):
    def test_triggering_closed_candle_is_included_at_close_timestamp(self):
        candles = make_candidate_candles(20)
        cutoff = candles[-1]["ts"] + 300_000
        context = make_forecast_context(cutoff)
        fake_model = FakeTimesFMModel()
        provider = SimpleNamespace(model=fake_model, checkpoint="test-checkpoint", device="cpu")

        with patch.object(tfm.db, "insert_candidate_forecast", return_value=None):
            result = tfm.generate_candidate_forecast(
                context, candles, model_override=provider, require_timesfm=True
            )

        self.assertEqual(len(fake_model.context), len(candles))
        self.assertEqual(float(fake_model.context[-1]), candles[-1]["close"])
        self.assertEqual(result.model, "TimesFM_3.0_PyTorch")
        self.assertEqual(result.context_length, len(candles))

    def test_research_mode_fails_closed_if_neural_model_is_unavailable(self):
        candles = make_candidate_candles(20)
        context = make_forecast_context(candles[-1]["ts"] + 300_000)
        with patch.object(tfm, "get_timesfm_provider", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "TimesFM research inference required"):
                tfm.generate_candidate_forecast(context, candles, require_timesfm=True)

    def test_research_mode_fails_closed_if_context_is_insufficient(self):
        candles = make_candidate_candles(11)
        context = make_forecast_context(candles[-1]["ts"] + 300_000)
        with self.assertRaisesRegex(RuntimeError, "only 11 completed context bars"):
            tfm.generate_candidate_forecast(context, candles, require_timesfm=True)


if __name__ == "__main__":
    unittest.main()
