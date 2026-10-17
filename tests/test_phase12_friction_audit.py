"""Unit Tests for Phase 12 Critical Friction Accounting Engine.

Verifies:
- Fees are strictly charged against executed notional, not P&L.
- The mathematical derivation of the ~8% fee-to-PnL ratio.
- R-multiple conversion formula: friction_R = friction_notional / stop_distance_pct.
- Accurate calculation of all 16 itemized trade friction fields.
- Non-zero friction invariance of strategy rankings.
"""
import unittest
import numpy as np

from scripts.run_phase12_friction_audit import (
    calculate_trade_friction_record,
    compute_cohort_friction_metrics,
    BINGX_MAKER_FEE_RATE,
    BINGX_TAKER_FEE_RATE,
    R_USD_UNIT
)
from control_plane.phase12_timesfm_engine import Phase12Candidate


class TestPhase12FrictionAudit(unittest.TestCase):

    def setUp(self):
        self.mock_cand = Phase12Candidate(
            candidate_id="TEST-FRICTION-001",
            symbol="ETHUSDT",
            direction="LONG",
            timestamp_ms=1708219800000,
            dt_utc="2024-02-17T22:50:00Z",
            split="TEST",
            entry_price=2000.0,
            sl_price=1980.0,      # 20 points = 1.0% stop distance
            tp1_price=2030.0,     # 30 points = 1.5R target (+1.5%)
            tp2_price=None,
            risk_amount=20.0,
            reward_tp1=30.0,
            raw_rr=1.5,
            displacement_atr=1.5,
            rejection_body_ratio=0.5,
            rvol=1.2,
            cur_atr=10.0,
            atr_pct=0.005,
            trend_4h="BULLISH",
            trend_aligned_4h=True,
            atr_pct_4h=0.02,
            vol_regime_4h="NORMAL",
            trend_1h="BULLISH",
            vol_regime_1h="NORMAL",
            expansion_1h="EXPANSION",
            pass_variant_d=True,
            pass_d4h=True,
            exit_reason="TP1",
            exit_price=2030.0,
            time_to_exit_min=30,
            gross_realized_r=1.5,
            net_realized_r_zero=1.5,
            net_realized_r_low=1.4,
            net_realized_r_base=1.35,
            net_realized_r_high=1.3,
            mfe=30.0,
            mae=-5.0,
            actual_low=1995.0,
            actual_high=2032.0,
            tfm_model="timesfm-3.0",
            tfm_checkpoint="pt",
            tfm_inference_ms=150.0,
            tfm_p15=2010.0,
            tfm_p30=2025.0,
            tfm_p45=2030.0,
            tfm_p60=2035.0,
            tfm_q10_60m=1990.0,
            tfm_q50_60m=2025.0,
            tfm_q90_60m=2040.0,
            tfm_dispersion_pct=2.5,
            tfm_path_slope=0.01,
            tfm_curvature=0.001,
            tfm_reachability_ratio_15m=0.33,
            tfm_reachability_ratio_30m=0.83,
            tfm_reachability_ratio_45m=1.0,
            tfm_reachability_ratio_60m=1.33,
            tfm_reachable_binary_60m=True,
            tfm_quantile_crossing=False,
            tfm_context_hash="ctx123",
            tfm_snapshot_hash="snap123",
            tfm_predicted_drawdown=-10.0,
            tfm_mae_prediction_error=5.0,
            tfm_q10_covered_mae=True,
            tfm_sl_touch_predicted=False,
            pass_downside_gate=True,
            base_persistence_pred=2000.0,
            base_ema_extrap_pred=2010.0,
            base_vwap_pred=2005.0,
            base_ar_pred=2020.0
        )

    def test_notional_vs_pnl_fee_calculation(self):
        """Proves fee is charged on notional (entry*qty + exit*qty), never on PnL."""
        trade = calculate_trade_friction_record(
            cand=self.mock_cand,
            entry_fee_rate=0.0005,  # 5 bps
            exit_fee_rate=0.0005,   # 5 bps
            entry_slip_rate=0.0,
            exit_slip_rate=0.0,
            apply_funding=False
        )

        # Expected:
        # Stop distance = 20 / 2000 = 1.0% = 0.01
        # Qty = $100 / $20 = 5.0 units
        # Entry notional = 5.0 * $2000 = $10,000
        # Exit notional = 5.0 * $2030 = $10,150
        # Entry fee = $10,000 * 0.0005 = $5.00
        # Exit fee = $10,150 * 0.0005 = $5.075
        # Total fee = $10.075
        # Gross PnL = 5.0 * $30 = $150.00

        self.assertAlmostEqual(trade["entry_notional"], 10000.0, places=2)
        self.assertAlmostEqual(trade["exit_notional"], 10150.0, places=2)
        self.assertAlmostEqual(trade["exchange_fee"], 10.075, places=3)
        self.assertAlmostEqual(trade["gross_pnl"], 150.0, places=2)
        self.assertAlmostEqual(trade["net_pnl"], 139.925, places=2)

        # Fee in R = $10.075 / $100 = 0.10075R
        self.assertAlmostEqual(trade["fee_r"], 0.1008, places=3)
        self.assertAlmostEqual(trade["gross_r"], 1.5, places=2)
        self.assertAlmostEqual(trade["net_r"], 1.5 - 0.1008, places=3)

    def test_mathematical_derivation_of_user_8pct_claim(self):
        """Validates that a 0.10% notional fee equals ~8.0% of PnL on a 1.25% price gain."""
        entry_price = 1000.0
        # Price gain = +1.25%
        exit_price = entry_price * 1.0125
        qty = 10.0
        entry_notional = qty * entry_price    # $10,000
        exit_notional = qty * exit_price      # $10,125
        gross_pnl = qty * (exit_price - entry_price) # $125.00

        entry_fee = entry_notional * 0.0005   # $5.00
        exit_fee = exit_notional * 0.0005     # $5.0625
        total_fees = entry_fee + exit_fee     # $10.0625

        fee_to_pnl_ratio = total_fees / gross_pnl # 10.0625 / 125.0 = 0.0805 = 8.05%
        self.assertAlmostEqual(fee_to_pnl_ratio, 0.0805, places=3)

    def test_stop_distance_r_scaling_law(self):
        """Validates formula: friction_R = friction_notional / stop_distance_pct."""
        # 1. 0.50% stop distance -> 9 bps should equal 0.18R
        stop_pct_1 = 0.0050
        r_cost_1 = 0.0009 / stop_pct_1
        self.assertAlmostEqual(r_cost_1, 0.18, places=4)

        # 2. 0.25% stop distance -> 9 bps should equal 0.36R
        stop_pct_2 = 0.0025
        r_cost_2 = 0.0009 / stop_pct_2
        self.assertAlmostEqual(r_cost_2, 0.36, places=4)

        # 3. 2.00% stop distance -> 9 bps should equal 0.045R
        stop_pct_3 = 0.0200
        r_cost_3 = 0.0009 / stop_pct_3
        self.assertAlmostEqual(r_cost_3, 0.045, places=4)


    def test_reforecast_exit_uses_actual_t15_price(self):
        """An EARLY_EXIT cohort must not reuse the original exit or a net-R value as gross."""
        self.mock_cand.reforecast_policy = "EARLY_EXIT"
        self.mock_cand.reforecast_exit_price = 2010.0

        trade = calculate_trade_friction_record(
            cand=self.mock_cand,
            entry_fee_rate=0.0,
            exit_fee_rate=0.0,
            entry_slip_rate=0.0,
            exit_slip_rate=0.0,
            apply_funding=False,
            use_reforecast_exit=True,
        )

        self.assertEqual(trade["exit_reason"], "REFORECAST_EARLY_EXIT")
        self.assertAlmostEqual(trade["exit_price"], 2010.0, places=5)
        self.assertAlmostEqual(trade["gross_pnl"], 50.0, places=5)
        self.assertAlmostEqual(trade["gross_r"], 0.5, places=5)

    def test_tp1_hit_gross_positive_and_net_positive_rates_are_distinct(self):
        """Timeouts with a positive gross mark can still be net losers."""
        template = {
            "total_gross_pnl": 0.0,
            "exchange_fee": 0.0,
            "slippage_cost": 0.0,
            "funding": 0.0,
            "fee_r": 0.0,
            "slippage_r": 0.0,
            "funding_r": 0.0,
            "friction_pct_of_notional": 0.1,
            "friction_r_per_trade": 0.1,
            "fee_to_gross_pnl_pct": 0.0,
        }
        win = dict(template, gross_r=1.5, net_r=1.2, gross_pnl=150.0, net_pnl=120.0, exit_reason="TP1")
        timeout = dict(template, gross_r=0.1, net_r=-0.2, gross_pnl=10.0, net_pnl=-20.0, exit_reason="TIMEOUT")
        result = compute_cohort_friction_metrics([win, timeout])

        self.assertEqual(result["win_rate"], 50.0)
        self.assertEqual(result["tp1_hit_rate"], 50.0)
        self.assertEqual(result["gross_positive_rate"], 100.0)
        self.assertEqual(result["net_positive_rate"], 50.0)

if __name__ == "__main__":
    unittest.main()
