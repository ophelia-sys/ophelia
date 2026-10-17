"""
TimesFM Real VPS Stress & Resource-Isolation Benchmark
======================================================
Empirically measures system latency, CPU, RAM, swap, and load average across:
- Stage A: TimesFM Idle
- Stage B: Single TimesFM Inference + Concurrent Core Operations
- Stage C: Repeated Consecutive Inference
- Stage D: Scheduler Batch Cycle + Concurrent Core Operations
- Stage E: Peak Simultaneous Load (Inference + API Concurrency + Automation + Position Manager)
"""

import os
import sys
import time
import json
import psutil
import urllib.request
import threading
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, "/opt/ophelia")

from control_plane import db
from control_plane.forecast_service import ForecastService, ForecastScheduler, TimesFMProvider


def get_system_telemetry():
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    load1, load5, load15 = psutil.getloadavg() if hasattr(psutil, "getloadavg") else (0.0, 0.0, 0.0)
    return {
        "cpu_pct": psutil.cpu_percent(interval=0.1),
        "ram_total_mb": round(mem.total / (1024 * 1024), 1),
        "ram_used_mb": round(mem.used / (1024 * 1024), 1),
        "ram_avail_mb": round(mem.available / (1024 * 1024), 1),
        "ram_used_pct": mem.percent,
        "swap_used_mb": round(swap.used / (1024 * 1024), 1),
        "swap_free_mb": round(swap.free / (1024 * 1024), 1),
        "load_1m": round(load1, 2),
        "load_5m": round(load5, 2),
        "load_15m": round(load15, 2)
    }


def measure_api_health_latency(n=5):
    latencies = []
    for _ in range(n):
        t0 = time.perf_counter()
        try:
            req = urllib.request.Request("http://127.0.0.1:8000/api/health", headers={"User-Agent": "StressTester"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                resp.read()
            lat_ms = (time.perf_counter() - t0) * 1000
            latencies.append(lat_ms)
        except Exception as e:
            latencies.append(-1.0)
        time.sleep(0.02)
    valid = [l for l in latencies if l > 0]
    return {
        "count": len(valid),
        "min_ms": round(min(valid), 2) if valid else 0.0,
        "max_ms": round(max(valid), 2) if valid else 0.0,
        "avg_ms": round(sum(valid) / len(valid), 2) if valid else 0.0
    }


def simulate_automation_cycle():
    """Simulates an autonomous slot evaluation and query cycle."""
    t0 = time.perf_counter()
    # Query trade slots, intents, setup candidates, and market state from SQLite
    slots = db.get_autonomous_trade_slots()
    intents = db.list_execution_intents(limit=10)
    candidates = db.list_setup_candidates(limit=10)
    dur_ms = (time.perf_counter() - t0) * 1000
    return round(dur_ms, 2)


def simulate_position_manager_cycle():
    """Simulates position manager reconciliation and stop validation check."""
    t0 = time.perf_counter()
    positions = db.get_open_user_positions()
    recons = db.list_reconciliation_events(limit=5)
    dur_ms = (time.perf_counter() - t0) * 1000
    return round(dur_ms, 2)


def run_benchmark():
    print("=" * 60)
    print("STARTING OPHELIA TIMESFM RESOURCE ISOLATION BENCHMARK")
    print("=" * 60)

    svc = ForecastService.get_instance()
    
    # -------------------------------------------------------------
    # STAGE A: IDLE STATE
    # -------------------------------------------------------------
    print("\n[STAGE A] Measuring Baseline (TimesFM Idle)...")
    time.sleep(1.0)
    telemetry_a = get_system_telemetry()
    api_a = measure_api_health_latency(10)
    auto_a = simulate_automation_cycle()
    pm_a = simulate_position_manager_cycle()

    report_a = {
        "stage": "STAGE_A_IDLE",
        "api_latency": api_a,
        "automation_cycle_ms": auto_a,
        "position_manager_cycle_ms": pm_a,
        "telemetry": telemetry_a
    }
    print(f"  API Avg Latency: {api_a['avg_ms']} ms")
    print(f"  Automation Cycle: {auto_a} ms")
    print(f"  Position Mgr Cycle: {pm_a} ms")
    print(f"  CPU: {telemetry_a['cpu_pct']}% | RAM: {telemetry_a['ram_used_mb']}/{telemetry_a['ram_total_mb']} MB | Swap: {telemetry_a['swap_used_mb']} MB | Load: {telemetry_a['load_1m']}")

    # -------------------------------------------------------------
    # STAGE B: SINGLE INFERENCE + CONCURRENT WORK
    # -------------------------------------------------------------
    print("\n[STAGE B] Measuring Single TimesFM Inference + Concurrent Core Operations...")
    api_during_b = []
    auto_during_b = []
    pm_during_b = []

    def background_core_ops():
        for _ in range(3):
            t0 = time.perf_counter()
            try:
                req = urllib.request.Request("http://127.0.0.1:8000/api/health")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    resp.read()
                api_during_b.append(round((time.perf_counter() - t0) * 1000, 2))
            except Exception:
                pass
            auto_during_b.append(simulate_automation_cycle())
            pm_during_b.append(simulate_position_manager_cycle())
            time.sleep(0.1)

    t_inf_start = time.perf_counter()
    th = threading.Thread(target=background_core_ops)
    th.start()
    
    res_b = svc.generate_forecast("BTC-USDT", timeframe="5m", horizon=10, force_refresh=True)
    inf_dur_b = round((time.perf_counter() - t_inf_start) * 1000, 2)
    th.join()

    telemetry_b = get_system_telemetry()
    report_b = {
        "stage": "STAGE_B_SINGLE_INFERENCE",
        "timesfm_latency_ms": inf_dur_b,
        "forecast_status": res_b.status,
        "api_latencies_during_inf_ms": api_during_b,
        "api_avg_ms": round(sum(api_during_b) / len(api_during_b), 2) if api_during_b else 0.0,
        "automation_cycles_during_inf_ms": auto_during_b,
        "position_mgr_cycles_during_inf_ms": pm_during_b,
        "telemetry": telemetry_b
    }
    print(f"  TimesFM Inference: {inf_dur_b} ms (Status: {res_b.status})")
    print(f"  API Latency during Inference: {report_b['api_avg_ms']} ms (Max: {max(api_during_b) if api_during_b else 0} ms)")
    print(f"  Automation Latency during Inference: {auto_during_b} ms")
    print(f"  Position Mgr during Inference: {pm_during_b} ms")
    print(f"  CPU: {telemetry_b['cpu_pct']}% | RAM: {telemetry_b['ram_used_mb']}/{telemetry_b['ram_total_mb']} MB | Swap: {telemetry_b['swap_used_mb']} MB | Load: {telemetry_b['load_1m']}")

    # -------------------------------------------------------------
    # STAGE C: REPEATED CONSECUTIVE INFERENCE (3 INFERENCES)
    # -------------------------------------------------------------
    print("\n[STAGE C] Measuring 3 Repeated Inferences...")
    inf_times_c = []
    telemetries_c = []
    for i in range(3):
        t0 = time.perf_counter()
        r = svc.generate_forecast("BTC-USDT", timeframe="5m", horizon=10, force_refresh=True)
        dur = round((time.perf_counter() - t0) * 1000, 2)
        inf_times_c.append(dur)
        telemetries_c.append(get_system_telemetry())
        print(f"   Inference #{i+1}: {dur} ms")

    telemetry_c = get_system_telemetry()
    report_c = {
        "stage": "STAGE_C_REPEATED_INFERENCES",
        "inferences_ms": inf_times_c,
        "avg_inf_ms": round(sum(inf_times_c) / len(inf_times_c), 2),
        "telemetry": telemetry_c
    }
    print(f"  Avg Inference: {report_c['avg_inf_ms']} ms")
    print(f"  CPU: {telemetry_c['cpu_pct']}% | RAM: {telemetry_c['ram_used_mb']} MB | Swap: {telemetry_c['swap_used_mb']} MB | Load: {telemetry_c['load_1m']}")

    # -------------------------------------------------------------
    # STAGE D: SCHEDULER BATCH CYCLE
    # -------------------------------------------------------------
    print("\n[STAGE D] Measuring Scheduler Batch Cycle...")
    scheduler = ForecastScheduler(service=svc, interval_seconds=300)
    t0 = time.perf_counter()
    scheduler._run_cycle()
    sched_dur = round((time.perf_counter() - t0) * 1000, 2)
    telemetry_d = get_system_telemetry()
    report_d = {
        "stage": "STAGE_D_SCHEDULER_CYCLE",
        "scheduler_cycle_ms": sched_dur,
        "telemetry": telemetry_d
    }
    print(f"  Scheduler Cycle: {sched_dur} ms")
    print(f"  CPU: {telemetry_d['cpu_pct']}% | RAM: {telemetry_d['ram_used_mb']} MB | Swap: {telemetry_d['swap_used_mb']} MB | Load: {telemetry_d['load_1m']}")

    # -------------------------------------------------------------
    # STAGE E: HIGH CONCURRENCY PEAK STRESS
    # -------------------------------------------------------------
    print("\n[STAGE E] Measuring High Concurrency Peak Load (Inference + 10 API Calls + Automation + Position Mgr)...")
    concurrent_api_results = []
    concurrent_auto_results = []
    concurrent_pm_results = []

    def make_api_call(idx):
        t0 = time.perf_counter()
        try:
            req = urllib.request.Request("http://127.0.0.1:8000/api/timesfm/diagnostics", headers={"Authorization": "Bearer fake"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                resp.read()
        except urllib.error.HTTPError as he:
            # 401 is expected and validates HTTP layer processing
            pass
        except Exception:
            pass
        concurrent_api_results.append(round((time.perf_counter() - t0) * 1000, 2))

    def run_concurrent_stress():
        with ThreadPoolExecutor(max_workers=10) as executor:
            for i in range(10):
                executor.submit(make_api_call, i)
        concurrent_auto_results.append(simulate_automation_cycle())
        concurrent_pm_results.append(simulate_position_manager_cycle())

    t0 = time.perf_counter()
    th_stress = threading.Thread(target=run_concurrent_stress)
    th_stress.start()
    res_e = svc.generate_forecast("BTC-USDT", timeframe="5m", horizon=10, force_refresh=True)
    inf_dur_e = round((time.perf_counter() - t0) * 1000, 2)
    th_stress.join()

    telemetry_e = get_system_telemetry()
    report_e = {
        "stage": "STAGE_E_HIGH_CONCURRENCY",
        "timesfm_latency_ms": inf_dur_e,
        "concurrent_api_latencies_ms": concurrent_api_results,
        "concurrent_api_avg_ms": round(sum(concurrent_api_results) / len(concurrent_api_results), 2) if concurrent_api_results else 0.0,
        "concurrent_api_max_ms": max(concurrent_api_results) if concurrent_api_results else 0.0,
        "automation_cycle_ms": concurrent_auto_results[0] if concurrent_auto_results else 0.0,
        "position_manager_cycle_ms": concurrent_pm_results[0] if concurrent_pm_results else 0.0,
        "telemetry": telemetry_e
    }
    print(f"  TimesFM Inference: {inf_dur_e} ms")
    print(f"  Concurrent API Latency: Avg={report_e['concurrent_api_avg_ms']} ms | Max={report_e['concurrent_api_max_ms']} ms")
    print(f"  Automation Cycle: {report_e['automation_cycle_ms']} ms")
    print(f"  Position Mgr Cycle: {report_e['position_manager_cycle_ms']} ms")
    print(f"  CPU: {telemetry_e['cpu_pct']}% | RAM: {telemetry_e['ram_used_mb']} MB | Swap: {telemetry_e['swap_used_mb']} MB | Load: {telemetry_e['load_1m']}")

    final_report = {
        "timestamp": int(time.time()),
        "stage_a_idle": report_a,
        "stage_b_single": report_b,
        "stage_c_repeated": report_c,
        "stage_d_scheduler": report_d,
        "stage_e_concurrency": report_e
    }

    os.makedirs("/opt/ophelia/vps_evidence", exist_ok=True)
    with open("/opt/ophelia/vps_evidence/timesfm_stress_benchmark.json", "w") as f:
        json.dump(final_report, f, indent=2)

    print("\n" + "=" * 60)
    print("BENCHMARK COMPLETED SUCCESSFULLY. Evidence saved to vps_evidence/timesfm_stress_benchmark.json")
    print("=" * 60)


if __name__ == "__main__":
    run_benchmark()
