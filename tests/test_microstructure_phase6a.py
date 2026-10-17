"""Phase 6A Microstructure Research Test Suite.

Validates all 20 required acceptance criteria for:
- Module 1: Trade-Flow Innovation
- Module 2: Trade Duration / Arrival Pressure
- Data Quality, Provenance, and Research Isolation
"""
import time
import pytest
from models.microstructure import (
    AggressorSource,
    FlowDirection,
    FreshnessState,
    QualityState,
    TradeTick,
)
from control_plane.microstructure_engine import (
    MicrostructureService,
    TradeDurationEngine,
    TradeFlowInnovationEngine,
)
from control_plane import db


@pytest.fixture(autouse=True)
def setup_db():
    db.init_db()
    db.set_max_open_trades(4)


def test_01_direct_aggressor_side():
    engine = TradeFlowInnovationEngine(instrument="BTC-USDT", min_sample_size=3)
    now = int(time.time() * 1000)

    tick = TradeTick(
        instrument="BTC-USDT",
        venue="BINGX",
        event_timestamp=now,
        received_timestamp=now,
        price=50000.0,
        quantity=1.5,
        aggressor_side="BUY",
        trade_id="t1"
    )
    obs = engine.process_tick(tick)
    assert obs.aggressor_source == AggressorSource.DIRECT
    assert obs.signed_flow == 1.5
    assert obs.flow_direction == FlowDirection.BUY


def test_02_inferred_aggressor_side():
    engine = TradeFlowInnovationEngine(instrument="BTC-USDT", min_sample_size=3)
    now = int(time.time() * 1000)

    # Base price tick
    t1 = TradeTick("BTC-USDT", "BINGX", now, now, 50000.0, 1.0, aggressor_side=None, trade_id="t1")
    engine.process_tick(t1)

    # Uptick -> Inferred BUY
    t2 = TradeTick("BTC-USDT", "BINGX", now + 100, now + 100, 50005.0, 2.0, aggressor_side=None, trade_id="t2")
    obs2 = engine.process_tick(t2)
    assert obs2.aggressor_source == AggressorSource.INFERRED
    assert obs2.flow_direction == FlowDirection.BUY
    assert obs2.signed_flow == 2.0

    # Downtick -> Inferred SELL
    t3 = TradeTick("BTC-USDT", "BINGX", now + 200, now + 200, 49995.0, 0.5, aggressor_side=None, trade_id="t3")
    obs3 = engine.process_tick(t3)
    assert obs3.aggressor_source == AggressorSource.INFERRED
    assert obs3.flow_direction == FlowDirection.SELL
    assert obs3.signed_flow == -0.5


def test_03_missing_aggressor_side():
    engine = TradeFlowInnovationEngine(instrument="BTC-USDT")
    now = int(time.time() * 1000)

    # First tick without side and without previous price
    tick = TradeTick("BTC-USDT", "BINGX", now, now, 50000.0, 1.0, aggressor_side=None, trade_id="t1")
    obs = engine.process_tick(tick)
    assert obs.aggressor_source == AggressorSource.NOT_AVAILABLE
    assert obs.signed_flow == 0.0
    assert obs.flow_direction == FlowDirection.NEUTRAL


def test_04_empty_trade_stream():
    engine = TradeFlowInnovationEngine(instrument="BTC-USDT")
    dur_engine = TradeDurationEngine(instrument="BTC-USDT")

    assert engine._get_expected_flow() == 0.0
    assert engine._get_std_flow() == 0.0
    assert dur_engine._get_median_duration() == 0.0
    assert dur_engine._get_arrival_intensity() == 1.0


def test_05_one_trade_stream():
    dur_engine = TradeDurationEngine(instrument="BTC-USDT", min_sample_size=5)
    now = int(time.time() * 1000)

    tick = TradeTick("BTC-USDT", "BINGX", now, now, 50000.0, 1.0, trade_id="t1")
    obs = dur_engine.process_tick(tick)

    # First tick has no prior duration
    assert obs.duration_ms == 0.0
    assert obs.provenance.sample_count == 0
    assert obs.provenance.quality_state == QualityState.INSUFFICIENT_SAMPLE


def test_06_duplicate_trade():
    engine = TradeFlowInnovationEngine(instrument="BTC-USDT", min_sample_size=3)
    dur_engine = TradeDurationEngine(instrument="BTC-USDT", min_sample_size=3)
    now = int(time.time() * 1000)

    tick = TradeTick("BTC-USDT", "BINGX", now, now, 50000.0, 1.0, aggressor_side="BUY", trade_id="same_id_1")
    obs1 = engine.process_tick(tick)
    assert obs1.provenance.quality_state != QualityState.DUPLICATE
    assert len(engine.signed_volumes) == 1

    # Exact duplicate trade
    obs2 = engine.process_tick(tick)
    assert obs2.provenance.quality_state == QualityState.DUPLICATE
    assert len(engine.signed_volumes) == 1  # Not double counted!

    obs_dur2 = dur_engine.process_tick(tick)
    obs_dur_dup = dur_engine.process_tick(tick)
    assert obs_dur_dup.provenance.quality_state == QualityState.DUPLICATE


def test_07_out_of_order_trade():
    engine = TradeFlowInnovationEngine(instrument="BTC-USDT")
    dur_engine = TradeDurationEngine(instrument="BTC-USDT")
    now = int(time.time() * 1000)

    t1 = TradeTick("BTC-USDT", "BINGX", now, now, 50000.0, 1.0, aggressor_side="BUY", trade_id="t1")
    t2 = TradeTick("BTC-USDT", "BINGX", now + 2000, now + 2000, 50010.0, 1.0, aggressor_side="BUY", trade_id="t2")
    # t3 has older timestamp than t2
    t3 = TradeTick("BTC-USDT", "BINGX", now + 1000, now + 2001, 50005.0, 1.0, aggressor_side="BUY", trade_id="t3")

    engine.process_tick(t1)
    engine.process_tick(t2)
    obs3 = engine.process_tick(t3)
    assert obs3.provenance.quality_state == QualityState.OUT_OF_ORDER

    dur_engine.process_tick(t1)
    dur_engine.process_tick(t2)
    dur_obs3 = dur_engine.process_tick(t3)
    assert dur_obs3.provenance.quality_state == QualityState.OUT_OF_ORDER


def test_08_zero_quantity():
    engine = TradeFlowInnovationEngine(instrument="BTC-USDT")
    now = int(time.time() * 1000)

    tick = TradeTick("BTC-USDT", "BINGX", now, now, 50000.0, 0.0, aggressor_side="BUY", trade_id="zero_qty")
    obs = engine.process_tick(tick)
    assert obs.provenance.quality_state == QualityState.DEGRADED
    assert len(engine.signed_volumes) == 0


def test_09_very_large_trade():
    engine = TradeFlowInnovationEngine(instrument="BTC-USDT", min_sample_size=3)
    now = int(time.time() * 1000)

    # Establish normal baseline
    for i in range(10):
        t = TradeTick("BTC-USDT", "BINGX", now + i * 100, now + i * 100, 50000.0, 1.0, aggressor_side="BUY", trade_id=f"t_{i}")
        engine.process_tick(t)

    # Mega trade
    mega_tick = TradeTick("BTC-USDT", "BINGX", now + 1000, now + 1000, 50000.0, 500000.0, aggressor_side="BUY", trade_id="mega")
    obs = engine.process_tick(mega_tick)
    # Z-score must be winsorized at exactly 5.0
    assert obs.flow_zscore == 5.0


def test_10_stale_data():
    engine = TradeFlowInnovationEngine(instrument="BTC-USDT", max_freshness_ms=60000)
    now = int(time.time() * 1000)
    ten_mins_ago = now - 600000

    tick = TradeTick("BTC-USDT", "BINGX", ten_mins_ago, now, 50000.0, 1.0, aggressor_side="BUY", trade_id="stale")
    obs = engine.process_tick(tick)
    assert obs.provenance.quality_state == QualityState.STALE
    assert obs.provenance.freshness_state == FreshnessState.STALE


def test_11_insufficient_sample():
    engine = TradeFlowInnovationEngine(instrument="BTC-USDT", min_sample_size=20)
    now = int(time.time() * 1000)

    for i in range(5):
        t = TradeTick("BTC-USDT", "BINGX", now + i * 100, now + i * 100, 50000.0, 1.0, aggressor_side="BUY", trade_id=f"t_{i}")
        obs = engine.process_tick(t)

    assert obs.provenance.quality_state == QualityState.INSUFFICIENT_SAMPLE
    assert obs.provenance.sample_count == 5


def test_12_duration_calculation():
    dur_engine = TradeDurationEngine(instrument="BTC-USDT", min_sample_size=2)
    now = int(time.time() * 1000)

    t1 = TradeTick("BTC-USDT", "BINGX", now, now, 50000.0, 1.0, trade_id="t1")
    t2 = TradeTick("BTC-USDT", "BINGX", now + 350, now + 350, 50000.0, 1.0, trade_id="t2")

    dur_engine.process_tick(t1)
    obs2 = dur_engine.process_tick(t2)
    assert obs2.duration_ms == 350.0


def test_13_duration_baseline():
    dur_engine = TradeDurationEngine(instrument="BTC-USDT", min_sample_size=2)
    now = int(time.time() * 1000)

    dur_engine.process_tick(TradeTick("BTC-USDT", "BINGX", now, now, 50000.0, 1.0, trade_id="t0"))
    durations = [100, 200, 300, 400, 500]  # median is 300
    cum_ts = now
    for i, d in enumerate(durations):
        cum_ts += d
        obs = dur_engine.process_tick(TradeTick("BTC-USDT", "BINGX", cum_ts, cum_ts, 50000.0, 1.0, trade_id=f"t_{i+1}"))

    assert obs.expected_duration_ms == 300.0


def test_14_arrival_intensity():
    dur_engine = TradeDurationEngine(instrument="BTC-USDT", min_sample_size=2)
    now = int(time.time() * 1000)

    dur_engine.process_tick(TradeTick("BTC-USDT", "BINGX", now, now, 50000.0, 1.0, trade_id="t0"))
    dur_engine.process_tick(TradeTick("BTC-USDT", "BINGX", now + 250, now + 250, 50000.0, 1.0, trade_id="t1"))
    obs = dur_engine.process_tick(TradeTick("BTC-USDT", "BINGX", now + 500, now + 500, 50000.0, 1.0, trade_id="t2"))

    # median duration = 250ms -> intensity = 1.0 / 250 = 0.004
    assert pytest.approx(obs.arrival_intensity, rel=1e-3) == 0.004


def test_15_missing_timestamps():
    engine = TradeFlowInnovationEngine(instrument="BTC-USDT")
    tick = TradeTick("BTC-USDT", "BINGX", event_timestamp=0, received_timestamp=0, price=50000.0, quantity=1.0)
    obs = engine.process_tick(tick)
    # Stale/out of order
    assert obs.provenance.quality_state in (QualityState.STALE, QualityState.OUT_OF_ORDER)


def test_16_future_timestamp_rejection():
    engine = TradeFlowInnovationEngine(instrument="BTC-USDT")
    now = int(time.time() * 1000)
    future_ts = now + 3600000  # 1 hour in future

    tick = TradeTick("BTC-USDT", "BINGX", event_timestamp=future_ts, received_timestamp=now, price=50000.0, quantity=1.0)
    obs = engine.process_tick(tick)
    assert obs.provenance.quality_state == QualityState.OUT_OF_ORDER
    assert obs.detail.get("reason") == "FUTURE_TIMESTAMP_REJECTED"


def test_17_provenance_persistence():
    now = int(time.time() * 1000)
    flow_data = {
        "instrument": "ETH-USDT",
        "venue": "BINGX",
        "event_timestamp": now,
        "received_timestamp": now,
        "feature_version": "1.0.0",
        "schema_version": "v1",
        "source_data_type": "TRADE_TICKS",
        "sample_count": 45,
        "quality_state": "VALID",
        "freshness_state": "FRESH",
        "missingness_state": "COMPLETE",
        "calculation_window": 60000,
        "signed_flow": 12.5,
        "expected_flow": 10.0,
        "flow_innovation": 2.5,
        "flow_zscore": 0.85,
        "flow_direction": 1,
        "flow_persistence": 0.32,
        "aggressor_source": "DIRECT",
        "detail": {"source": "TEST"}
    }
    dur_data = {
        "instrument": "ETH-USDT",
        "venue": "BINGX",
        "event_timestamp": now,
        "received_timestamp": now,
        "feature_version": "1.0.0",
        "schema_version": "v1",
        "source_data_type": "TRADE_TICKS",
        "sample_count": 45,
        "quality_state": "VALID",
        "freshness_state": "FRESH",
        "missingness_state": "COMPLETE",
        "calculation_window": 60000,
        "duration_ms": 150.0,
        "expected_duration_ms": 200.0,
        "duration_pressure": 0.45,
        "arrival_intensity": 0.005,
        "duration_zscore": -0.45,
        "persistence": 0.15,
        "detail": {"source": "TEST"}
    }

    fid = db.persist_microstructure_flow(flow_data)
    did = db.persist_microstructure_duration(dur_data)
    assert fid > 0
    assert did > 0

    saved_flow = db.get_latest_microstructure_flow("ETH-USDT")
    saved_dur = db.get_latest_microstructure_duration("ETH-USDT")

    assert saved_flow is not None
    assert saved_flow["signed_flow"] == 12.5
    assert saved_flow["flow_innovation"] == 2.5
    assert saved_flow["mode"] == "RESEARCH"

    assert saved_dur is not None
    assert saved_dur["duration_ms"] == 150.0
    assert saved_dur["arrival_intensity"] == 0.005
    assert saved_dur["mode"] == "RESEARCH"


def test_18_research_isolation():
    # Verify that research records are tagged strictly with mode="RESEARCH"
    # and zero records were written to live/trading tables
    flow = db.get_latest_microstructure_flow("ETH-USDT")
    assert flow["mode"] == "RESEARCH"

    c = db._connect()
    pos_before = c.execute("SELECT COUNT(*) FROM positions").fetchone()[0]
    svc = MicrostructureService.get_instance()
    now = int(time.time() * 1000)
    svc.process_tick(TradeTick("ETH-USDT", "BINGX", now, now, 3000.0, 1.0, aggressor_side="BUY", trade_id="iso_tick_1"))
    pos_after = c.execute("SELECT COUNT(*) FROM positions").fetchone()[0]
    assert pos_after == pos_before  # Zero positions written!


def test_19_no_order_submission():
    # Verify MicrostructureService does not place orders or touch order book execution
    c = db._connect()
    orders_before = c.execute("SELECT COUNT(*) FROM manual_orders").fetchone()[0]

    svc = MicrostructureService.get_instance()
    now = int(time.time() * 1000)
    tick = TradeTick("BTC-USDT", "BINGX", now, now, 50000.0, 1.0, aggressor_side="BUY", trade_id="ord_test_99")
    svc.process_tick(tick)

    orders_after = c.execute("SELECT COUNT(*) FROM manual_orders").fetchone()[0]
    assert orders_after == orders_before  # Zero orders submitted!


def test_20_no_slot_mutation():
    # Verify open trade capacity / slots are untouched by microstructure features
    cap_before = db.get_max_open_trades()
    assert cap_before == 4

    svc = MicrostructureService.get_instance()
    now = int(time.time() * 1000)
    svc.process_tick(TradeTick("SOL-USDT", "BINGX", now, now, 150.0, 10.0, aggressor_side="SELL", trade_id="slot_t_99"))

    cap_after = db.get_max_open_trades()
    assert cap_after == cap_before  # Cap remains exactly 4

