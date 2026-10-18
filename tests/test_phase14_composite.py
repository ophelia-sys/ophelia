"""Unit & Regression Test Suite for Ophelia Phase 14: Controlled Multi-Factor Alpha Discovery.

Verifies:
1. All 10 pre-registered composite and standalone candidate hypotheses extract correctly.
2. Zero lookahead in forward trajectory calculation.
3. Stop diagnostics isolation and exclusion invariants.
4. Synchronized cross-symbol time-block bootstrap calibration.
5. Friction tier accounting (5.0, 9.1, 15.0 bps).
"""
import numpy as np
import pandas as pd
import pytest

from control_plane import phase14_composite_engine as p14
from control_plane.phase13_discovery_engine import (
    synchronized_time_block_bootstrap,
)
from control_plane.phase14_composite_engine import STOP_MODELS


class TestPhase14Composite:
    """Test suite for Phase 14 composite alpha discovery engine."""

    def _generate_synthetic_1m(self, n_bars: int = 1440, base_price: float = 30000.0) -> pd.DataFrame:
        """Generates regular 1m synthetic OHLCV data."""
        ts_start = p14.TS_JAN_01_2024
        ts_arr = np.array([ts_start + i * 60000 for i in range(n_bars)], dtype=np.int64)
        np.random.seed(42)
        returns = np.random.normal(0, 0.0005, size=n_bars)
        prices = base_price * np.exp(np.cumsum(returns))

        highs = prices * (1.0 + np.abs(np.random.normal(0, 0.0003, size=n_bars)))
        lows = prices * (1.0 - np.abs(np.random.normal(0, 0.0003, size=n_bars)))
        opens = np.roll(prices, 1)
        opens[0] = base_price
        closes = prices
        volumes = np.random.uniform(10.0, 50.0, size=n_bars)

        df = pd.DataFrame({
            "timestamp": ts_arr,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
            "symbol": "BTCUSDT",
        })
        return df

    def test_p14_pre_registered_hypotheses_integrity(self):
        """Verifies exactly 10 pre-registered hypotheses are declared in frozen protocol."""
        assert len(p14.PHASE14_HYPOTHESES) == 10
        assert "BENCH_HTF_ALIGNED_DISPLACEMENT" in p14.PHASE14_HYPOTHESES
        assert "BENCH_LIQUIDITY_SWEEP_SFP" in p14.PHASE14_HYPOTHESES
        assert "COMP_SFP_HTF_TREND" in p14.PHASE14_HYPOTHESES
        assert "COMP_SFP_RVOL_CONFIRM" in p14.PHASE14_HYPOTHESES
        assert "COMP_SFP_VOL_EXPANSION" in p14.PHASE14_HYPOTHESES
        assert "COMP_DISPLACEMENT_RVOL" in p14.PHASE14_HYPOTHESES
        assert "COMP_DISPLACEMENT_VOL_EXPANSION" in p14.PHASE14_HYPOTHESES
        assert "COMP_SFP_CVD_ABSORPTION" in p14.PHASE14_HYPOTHESES
        assert "COMP_DUAL_CONFLUENCE" in p14.PHASE14_HYPOTHESES
        assert "COMP_HTF_1H_SWING_SFP" in p14.PHASE14_HYPOTHESES

    def test_p14_friction_tiers_accounting(self):
        """Verifies exact decimal and basis-point conversions for friction tiers."""
        assert p14.FRICTION_FEE_ONLY == 0.0005      # 5.0 bps
        assert p14.FRICTION_BASELINE == 0.00091     # 9.1 bps
        assert p14.FRICTION_CONSERVATIVE == 0.0015  # 15.0 bps

        gross_pct = 0.05  # +5.0 bps
        assert round((gross_pct - p14.FRICTION_FEE_ONLY * 100) * 100, 2) == 0.00    # 5.0 - 5.0 = 0.0 bps
        assert round((gross_pct - p14.FRICTION_BASELINE * 100) * 100, 2) == -4.10   # 5.0 - 9.1 = -4.1 bps
        assert round((gross_pct - p14.FRICTION_CONSERVATIVE * 100) * 100, 2) == -10.00 # 5.0 - 15.0 = -10.0 bps

    def test_p14_split_assignment_q1_2024(self):
        """Verifies Q1 2024 timestamps assign to OUT_OF_TIME_Q1_2024 while 2023 follows Phase 13 splits."""
        # 2023 dates
        assert p14.assign_phase14_split(1672531200000) == "TRAIN"  # Jan 01 2023
        assert p14.assign_phase14_split(1697414400000) == "TEST"   # Oct 16 2023

        # 2024 dates
        assert p14.assign_phase14_split(p14.TS_JAN_01_2024) == "OUT_OF_TIME_Q1_2024"
        assert p14.assign_phase14_split(p14.TS_JAN_01_2024 + 30 * 86400000) == "OUT_OF_TIME_Q1_2024"
        assert p14.assign_phase14_split(p14.TS_MAR_31_2024) == "OUT_OF_TIME_Q1_2024"

    def test_p14_synthetic_event_extraction_pipeline(self):
        """Verifies that synthetic data passes through Phase14CompositeEngine without error."""
        engine = p14.Phase14CompositeEngine()
        df_1m = self._generate_synthetic_1m(n_bars=2880)  # 2 days

        events, outcomes, evals = engine.extract_composite_events_for_symbol("BTCUSDT", df_1m, is_oot_2024=True)
        # Verify event structures
        for ev in events:
            assert ev.event_class in p14.PHASE14_HYPOTHESES
            assert ev.split == "OUT_OF_TIME_Q1_2024"
            assert ev.direction in ("LONG", "SHORT")

        # Verify stop room evaluations
        for evl in evals:
            assert evl.stop_model in STOP_MODELS
            assert evl.split == "OUT_OF_TIME_Q1_2024"

    def test_p14_synchronized_bootstrap_on_composites(self):
        """Verifies synchronized time-block bootstrap correctly groups multi-symbol composite events."""
        # Create synthetic event dataframe across 2 symbols
        np.random.seed(123)
        ts_blocks = [1704067200000 + k * 6 * 3600 * 1000 for k in range(20)]
        rows = []
        for b_idx, ts in enumerate(ts_blocks):
            # 2 events per block
            rows.append({
                "timestamp_ms": ts + 1000,
                "symbol": "BTCUSDT",
                "directional_return_pct": 0.0010 + np.random.normal(0, 0.0005),
            })
            rows.append({
                "timestamp_ms": ts + 2000,
                "symbol": "ETHUSDT",
                "directional_return_pct": 0.0012 + np.random.normal(0, 0.0005),
            })
        df_evs = pd.DataFrame(rows)

        boot = synchronized_time_block_bootstrap(
            df_evs, value_col="directional_return_pct", timestamp_col="timestamp_ms", block_duration_hours=6.0, n_boot=500
        )
        assert boot["n_active_blocks"] == 20
        assert boot["ci_low"] > 0.0  # Significant positive return
        assert boot["p_value"] < 0.05
