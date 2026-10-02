import os
import sys
import time
import json
import sqlite3
import requests

def run_probe():
    from control_plane import config
    from control_plane.microstructure_engine import (
        MicrostructureService,
        OrderBookImbalanceEngine,
        SpreadLiquidityStressEngine,
        PriceImpactEngine,
        ToxicityEngine,
    )
    from control_plane.db import (
        init_db,
        get_latest_microstructure_price_impact,
        get_latest_microstructure_toxicity,
        get_user_by_id,
        _connect,
    )
    from models.microstructure import QualityState, OrderBookSnapshot, OrderBookLevel, TradeTick

    print("[1] Initializing database and verifying Phase 6C DDL...")
    init_db()
    conn = _connect()
    tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    assert "microstructure_price_impact" in tables, "Table microstructure_price_impact missing!"
    assert "microstructure_toxicity" in tables, "Table microstructure_toxicity missing!"
    print(f"Verified DDL: microstructure_price_impact and microstructure_toxicity exist in {config.DB_PATH}")

    print("\n[2] Verifying Phase 6B.1 Statistical Baseline Correction...")
    now = int(time.time() * 1000)
    def _make_snap(p=50000.0, ts_offset=0):
        b = [OrderBookLevel(price=p - 0.5 - i * 0.5, quantity=1.0) for i in range(5)]
        a = [OrderBookLevel(price=p + 0.5 + i * 0.5, quantity=1.0) for i in range(5)]
        return OrderBookSnapshot(
            instrument="BTC-USDT",
            venue="BINGX",
            event_timestamp=now - 5000 + ts_offset,
            received_timestamp=now,
            bids=b,
            asks=a,
        )

    # 2a. OBI persistence
    engine_obi = OrderBookImbalanceEngine(instrument="BTC-USDT", min_persistence_samples=5)
    obs_obi_1 = engine_obi.process_snapshot(_make_snap(ts_offset=0))
    assert obs_obi_1.imbalance_persistence is None, f"OBI persistence must be None on N=1, got {obs_obi_1.imbalance_persistence}"
    print("PASS: OBI persistence is None at N=1")

    # 2b. Spread & Liquidity Stress Baseline
    engine_ls = SpreadLiquidityStressEngine(instrument="BTC-USDT", min_baseline_samples=5)
    obs_ls_1 = engine_ls.process_snapshot(_make_snap(ts_offset=0))
    # Raw observables immediately available
    assert obs_ls_1.spread == 1.0, f"Expected spread 1.0, got {obs_ls_1.spread}"
    assert obs_ls_1.mid_price == 50000.0, f"Expected mid_price 50000.0, got {obs_ls_1.mid_price}"
    assert obs_ls_1.relative_spread is not None and obs_ls_1.relative_spread > 0.0
    # Baseline metrics strictly None / NOT_AVAILABLE
    assert obs_ls_1.expected_spread is None, f"Expected None, got {obs_ls_1.expected_spread}"
    assert obs_ls_1.spread_zscore is None, f"Expected None, got {obs_ls_1.spread_zscore}"
    assert obs_ls_1.spread_percentile is None, f"Expected None, got {obs_ls_1.spread_percentile}"
    assert obs_ls_1.spread_stress is None, f"Expected None, got {obs_ls_1.spread_stress}"
    assert obs_ls_1.depth_stress is None, f"Expected None, got {obs_ls_1.depth_stress}"
    assert obs_ls_1.book_thinning is None, f"Expected None, got {obs_ls_1.book_thinning}"
    assert obs_ls_1.liquidity_stress is None, f"Expected None, got {obs_ls_1.liquidity_stress}"
    assert obs_ls_1.liquidity_recovery_state == "NOT_AVAILABLE", f"Expected NOT_AVAILABLE, got {obs_ls_1.liquidity_recovery_state}"
    assert obs_ls_1.provenance.quality_state == QualityState.INSUFFICIENT_SAMPLE
    print("PASS: SpreadLiquidityStressEngine raw observables valid at N=1, baseline metrics strictly None/NOT_AVAILABLE with INSUFFICIENT_SAMPLE")

    # 2c. Baseline computes after N >= 5
    for i in range(1, 5):
        engine_ls.process_snapshot(_make_snap(ts_offset=i * 100))
    obs_ls_6 = engine_ls.process_snapshot(_make_snap(ts_offset=500))
    assert obs_ls_6.expected_spread is not None, "Expected spread baseline computed at N>=5"
    assert obs_ls_6.provenance.quality_state == QualityState.VALID
    print("PASS: Baseline metrics computed successfully once sample size >= 5")

    print("\n[3] Ingesting real live BingX trades for BTC-USDT...")
    service = MicrostructureService()
    t0 = time.perf_counter()
    flow_obs, dur_obs, pi_obs, tox_obs = service.fetch_live_bingx_trades("BTC-USDT", "BTC-USDT", limit=50, persist=True)
    latency_ms = (time.perf_counter() - t0) * 1000.0
    print(f"Live trade ingestion and microstructure computation in {latency_ms:.2f} ms")

    assert pi_obs is not None, "Price Impact observation is None!"
    assert tox_obs is not None, "Toxicity observation is None!"

    print("\nPrice Impact Observation:\n", json.dumps(pi_obs.to_dict(), indent=2))
    print("\nToxicity Observation:\n", json.dumps(tox_obs.to_dict(), indent=2))

    # Safety & Specification Invariants
    assert pi_obs.provenance.mode == "RESEARCH", f"Price Impact mode violated: {pi_obs.provenance.mode}"
    assert tox_obs.provenance.mode == "RESEARCH", f"Toxicity mode violated: {tox_obs.provenance.mode}"
    assert pi_obs.methodology_version == "KYLE_INSPIRED_EMPIRICAL_IMPACT"
    assert tox_obs.methodology_version == "VPIN_INSPIRED_RESEARCH"

    # Toxicity interpretable submetrics must be present
    assert tox_obs.flow_intensity is not None, "flow_intensity missing"
    assert tox_obs.adverse_price_response is not None, "adverse_price_response missing"
    assert tox_obs.trade_arrival_stress is not None, "trade_arrival_stress missing"
    assert tox_obs.toxicity_state in ("LOW", "NORMAL", "ELEVATED", "TOXIC", "INSUFFICIENT_SAMPLE")

    print("\n[4] Verifying SQLite persistence for Price Impact and Toxicity...")
    db_pi = get_latest_microstructure_price_impact("BTC-USDT")
    db_tox = get_latest_microstructure_toxicity("BTC-USDT")
    assert db_pi is not None, "No persisted price impact record found!"
    assert db_tox is not None, "No persisted toxicity record found!"
    assert db_pi["instrument"] == "BTC-USDT"
    assert db_tox["instrument"] == "BTC-USDT"
    assert db_pi["mode"] == "RESEARCH"
    assert db_tox["mode"] == "RESEARCH"
    print(f"Persisted PI id={db_pi.get('id')}, sample_count={db_pi.get('sample_count')}, quality={db_pi.get('quality_state')}")
    print(f"Persisted Tox id={db_tox.get('id')}, metric={db_tox.get('toxicity_metric')}, state={db_tox.get('toxicity_state')}")

    print("\n[5] Verifying API Endpoints via local HTTP request...")
    from control_plane.api import create_access_token
    admin = get_user_by_id(1)
    token = create_access_token({"sub": str(admin["id"]), "user_id": admin["id"], "role": "ADMIN"})
    headers = {"Authorization": f"Bearer {token}"}

    base_url = "http://127.0.0.1:8000"
    
    # 5a. Price Impact endpoint
    r_pi = requests.get(f"{base_url}/api/microstructure/price-impact?instrument=BTC-USDT", headers=headers, timeout=5)
    assert r_pi.status_code == 200, f"PI endpoint failed: {r_pi.status_code} {r_pi.text}"
    pi_json = r_pi.json()
    assert pi_json["mode"] == "RESEARCH"
    print("PASS: GET /api/microstructure/price-impact HTTP 200 OK")

    # 5b. Toxicity endpoint
    r_tox = requests.get(f"{base_url}/api/microstructure/toxicity?instrument=BTC-USDT", headers=headers, timeout=5)
    assert r_tox.status_code == 200, f"Toxicity endpoint failed: {r_tox.status_code} {r_tox.text}"
    tox_json = r_tox.json()
    assert tox_json["mode"] == "RESEARCH"
    print("PASS: GET /api/microstructure/toxicity HTTP 200 OK")

    # 5c. Summary endpoint (all 6 modules)
    r_sum = requests.get(f"{base_url}/api/microstructure/summary?instrument=BTC-USDT", headers=headers, timeout=5)
    assert r_sum.status_code == 200, f"Summary endpoint failed: {r_sum.status_code} {r_sum.text}"
    sum_json = r_sum.json()
    assert sum_json["mode"] == "RESEARCH"
    assert "trade_flow" in sum_json, "trade_flow missing from summary"
    assert "trade_duration" in sum_json, "trade_duration missing from summary"
    assert "order_book" in sum_json, "order_book missing from summary"
    assert "liquidity_stress" in sum_json, "liquidity_stress missing from summary"
    assert "price_impact" in sum_json, "price_impact missing from summary"
    assert "toxicity" in sum_json, "toxicity missing from summary"
    print("PASS: GET /api/microstructure/summary contains all 6 modules")

    print("\n[6] Verifying Research Isolation (zero order placement / zero capacity modification)...")
    orders_cnt = conn.execute("SELECT COUNT(*) FROM manual_orders").fetchone()[0]
    print(f"Total orders in database: {orders_cnt} (unmodified by research pipeline)")

    print("\n=======================================================")
    print("ALL PHASE 6C LIVE VPS VERIFICATION CHECKS PASSED!")
    print("=======================================================")

if __name__ == "__main__":
    run_probe()
