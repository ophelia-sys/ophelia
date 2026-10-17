# Ophelia: GitHub Checkpoint & Independent Review Index

**Repository:** `ophelia-sys/ophelia`  
**Purpose:** Production-grade algorithmic cryptocurrency trading and microstructure research system for BingX Perpetual Swap Futures.  
**Checkpoint Date:** 2026-10-17  
**Branch:** `checkpoint/pre-argon-review-2026-10-17`  
**Target Reviewer:** Gemini 4 Argon  

---

## 1. Executive Summary & Core Research Context

This repository checkpoint establishes a verified, secure, and reproducible snapshot of Ophelia across all development and quant research phases (Phases 1 through 13).

Before independent review, the following empirical findings and research constraints define the state of the project:

1. **Retest Strategy Edge Reality:** The current 5-minute breakout/retest deterministic strategy has **not** demonstrated a robust, economically viable edge once realistic friction (taker fees, slippage, and funding) is applied.
2. **Microstructure & Conditional Interaction Reality:** While isolated linear microstructure signals (OFI, book imbalance, VPIN, delta OI) exhibit weak or decaying unconditioned standalone predictive power, previous findings do **not** establish that all conditional interactions or nonlinear regime-conditioned states lack alpha.
3. **TimesFM Incremental Value:** Google TimesFM 3.0 was integrated with strict zero-lookahead, multi-scale causal feature alignment, and rigorous OOS evaluation. However, its value remains **unproven as a profitable incremental trading component** when combined with the baseline retest architecture.
4. **Friction Accounting Law:** Friction must strictly be evaluated in terms of **executed-notional fees relative to structural stop distance** ($R$). A 0.08%–0.10% roundtrip notional taker fee imposes an insurmountable 0.37R to 0.50R penalty on tight 0.20%–0.25% stops, making small-timeframe scalping mathematically negative-expectancy regardless of win rate.
5. **Stop-Room & Structural Invalidation:** High-frequency entry timeframe (e.g. 5m) swing stops suffer from frequent Class B premature stop-outs (price touches stop before reversing and hitting target). Decoupling entry timeframe from stop timeframe (`ENTRY TIMEFRAME != STOP TIMEFRAME`) and providing structural breathing room ($\ge 0.50\% - 0.75\%$) is an essential open direction.
6. **Deterministic Trading Authority & ML Isolation:** Machine learning (LLM, TradingAgents, Qwen, TimesFM) remains strictly **advisory and research-only**. Deterministic Rust/Python modules retain absolute authority over position sizing, risk gating, and order lifecycle. Live execution is disabled (`EXECUTION_MODE = SHADOW`).

---

## 2. Repository Architecture & Key Entry Points

Ophelia enforces a strict layered architecture:

```
[External Market Data / BingX REST & WS / Binance AggTrades]
                           ↓
                   [exchange/ & brokers/]
                           ↓
                     [models/ (Typed)]
                           ↓
        [institutional/ & control_plane/ (Core Logic)]
                           ↓
                 [risk/ & Validator]
                           ↓
              [PaperBroker / Shadow Execution]
                           ↓
                   [android-app/ UI]
```

### Main Entry Points
- **Control Plane API Server:** [control_plane/api.py](file:///c:/Users/dopa.mine/Desktop/ophelia/control_plane/api.py) — FastAPI application exposing REST endpoints for market diagnostics, candidates, slot management, microstructure metrics, and shadow telemetry.
- **Control Plane Orchestrator:** [control_plane/core.py](file:///c:/Users/dopa.mine/Desktop/ophelia/control_plane/core.py) — Coordinates data feeds, candidate evaluation, slot management, and shadow execution.
- **Microstructure Engine:** [control_plane/microstructure_engine.py](file:///c:/Users/dopa.mine/Desktop/ophelia/control_plane/microstructure_engine.py) — Evaluates Order Book Imbalance, Spread/Liquidity Stress, Kyle Price Impact, and VPIN Toxicity under strict causal forward constraints.
- **Credential Vault:** [control_plane/credential_vault.py](file:///c:/Users/dopa.mine/Desktop/ophelia/control_plane/credential_vault.py) — Enforces AES-GCM credential encryption and zero hardcoded secret storage.
- **Typed Models:** [models/](file:///c:/Users/dopa.mine/Desktop/ophelia/models/) — Strongly-typed dataclass contracts for instruments, positions, orders, candidates, and microstructure features.
- **Android Client:** [android-app/](file:///c:/Users/dopa.mine/Desktop/ophelia/android-app/) — Jetpack Compose native mobile client (Admin and User flavors) communicating exclusively via REST API.

---

## 3. Comprehensive Research Phase Map & Report Locations

All major quantitative investigations are fully documented with corresponding scripts, test suites, and serialized results:

| Research Phase | Core Topic & Finding | Formal Report Location | Key Scripts & Tests | Serialized Results |
| :--- | :--- | :--- | :--- | :--- |
| **Phase 5D.3 / 5.5 / 5.6** | High-concurrency resource optimization & TimesFM steady-state CPU benchmarking | [docs/PHASE_5_5_RESOURCE_OPTIMIZATION_REPORT.md](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/PHASE_5_5_RESOURCE_OPTIMIZATION_REPORT.md)<br>[docs/PHASE_5_6_MANUAL_TERMINAL_REPORT.md](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/PHASE_5_6_MANUAL_TERMINAL_REPORT.md) | `scripts/benchmark_vps_runtime.py`<br>`tests/test_timesfm_phase6f.py` | `vps_evidence/timesfm_stress_benchmark.json` |
| **Phase 6A–6D** | Microstructure metrics (OFI, Kyle $\lambda$, VPIN, Spread Stress) | [docs/PHASE_6A_MICROSTRUCTURE_REPORT.md](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/PHASE_6A_MICROSTRUCTURE_REPORT.md)<br>[docs/PHASE_6B_MICROSTRUCTURE_REPORT.md](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/PHASE_6B_MICROSTRUCTURE_REPORT.md)<br>[docs/PHASE_6C_MICROSTRUCTURE_REPORT.md](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/PHASE_6C_MICROSTRUCTURE_REPORT.md)<br>[docs/PHASE_6D_MICROSTRUCTURE_REPORT.md](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/PHASE_6D_MICROSTRUCTURE_REPORT.md) | `scripts/run_phase6_validation.py`<br>`tests/test_microstructure_phase6a.py`<br>`tests/test_microstructure_phase6d.py` | `institutional/` |
| **Phase 10.1–10.3** | TimesFM forecast roles & out-of-sample retest validation | [docs/PHASE_10_1_RETEST_TIMESFM_VALIDATION_REPORT.md](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/PHASE_10_1_RETEST_TIMESFM_VALIDATION_REPORT.md)<br>[docs/PHASE_10_2_TIMESFM_FORECAST_ROLE_DISCOVERY_REPORT.md](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/PHASE_10_2_TIMESFM_FORECAST_ROLE_DISCOVERY_REPORT.md)<br>[docs/PHASE_10_3_TIMESFM_OUT_OF_SAMPLE_VALIDATION_REPORT.md](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/PHASE_10_3_TIMESFM_OUT_OF_SAMPLE_VALIDATION_REPORT.md) | `scripts/run_phase10_2_forensic_investigation.py`<br>`scripts/run_phase10_3_oos_validation.py`<br>`tests/test_phase10_3_out_of_sample.py` | [data/phase10_3_validation_results.json](file:///c:/Users/dopa.mine/Desktop/ophelia/data/phase10_3_validation_results.json) |
| **Phase 11 & 11.5** | Deterministic strategy repair (CVD, RVOL, volume filters) & HTF regime management | [docs/PHASE_11_DETERMINISTIC_STRATEGY_REPAIR_REPORT.md](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/PHASE_11_DETERMINISTIC_STRATEGY_REPAIR_REPORT.md)<br>[docs/PHASE_11_5_HTF_REGIME_TRADE_MANAGEMENT_REPORT.md](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/PHASE_11_5_HTF_REGIME_TRADE_MANAGEMENT_REPORT.md) | `scripts/run_phase11_repair.py`<br>`scripts/run_phase11_5_htf_research.py`<br>`tests/test_phase11_deterministic_repair.py`<br>`tests/test_phase11_5_htf_management.py` | [data/phase11_repair_results.json](file:///c:/Users/dopa.mine/Desktop/ophelia/data/phase11_repair_results.json)<br>[data/phase11_5_htf_results.json](file:///c:/Users/dopa.mine/Desktop/ophelia/data/phase11_5_htf_results.json) |
| **Phase 12** | Fresh period (Jan–Mar 2024) OOS TimesFM validation & friction accounting audit | [docs/PHASE_12_FRESH_PERIOD_INCREMENTAL_TIMESFM_VALIDATION_REPORT.md](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/PHASE_12_FRESH_PERIOD_INCREMENTAL_TIMESFM_VALIDATION_REPORT.md)<br>[docs/PHASE_12_FRICTION_ACCOUNTING_AUDIT.md](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/PHASE_12_FRICTION_ACCOUNTING_AUDIT.md) | `scripts/run_phase12_incremental_timesfm.py`<br>`scripts/run_phase12_friction_audit.py`<br>`tests/test_phase12_incremental_timesfm.py`<br>`tests/test_phase12_friction_audit.py` | [data/phase12_friction_audit.json](file:///c:/Users/dopa.mine/Desktop/ophelia/data/phase12_friction_audit.json)<br>[data/phase12_incremental_timesfm_results.json](file:///c:/Users/dopa.mine/Desktop/ophelia/data/phase12_incremental_timesfm_results.json) |
| **Phase 13** | Alpha discovery reset (1.5M continuous candles, 423k events) & stop-room research | [docs/PHASE_13_ALPHA_DISCOVERY_REPORT.md](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/PHASE_13_ALPHA_DISCOVERY_REPORT.md)<br>[docs/PHASE_13_STOP_ROOM_RESEARCH.md](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/PHASE_13_STOP_ROOM_RESEARCH.md)<br>[docs/PHASE_13_ECONOMIC_VALIDATION.md](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/PHASE_13_ECONOMIC_VALIDATION.md)<br>[docs/PHASE_13_EVENT_UNIVERSE_REPORT.md](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/PHASE_13_EVENT_UNIVERSE_REPORT.md)<br>[docs/PHASE_13_STATISTICAL_VALIDATION.md](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/PHASE_13_STATISTICAL_VALIDATION.md) | `scripts/run_phase13_alpha_discovery.py`<br>`tests/test_phase13_discovery.py` | [data/phase13_results.json](file:///c:/Users/dopa.mine/Desktop/ophelia/data/phase13_results.json)<br>[data/phase13_stop_room.json](file:///c:/Users/dopa.mine/Desktop/ophelia/data/phase13_stop_room.json) |

---

## 4. Test Verification Suite & Reproduction

All tests are designed to be reproducible locally:

```bash
# Run core Phase 11, 12, and 13 research test suite
pytest tests/test_phase11_deterministic_repair.py tests/test_phase11_5_htf_management.py tests/test_phase12_friction_audit.py tests/test_phase12_incremental_timesfm.py tests/test_phase13_discovery.py -v

# Run microstructure unit tests
pytest tests/test_microstructure_phase6a.py tests/test_microstructure_phase6d.py tests/test_microstructure_phase6e.py -v

# Run full project test suite
pytest tests/
```

---

## 5. Environment & Dependencies

- **Python Runtime:** Python 3.11.x (tested on 3.11.9)
- **Primary Dependencies:** [requirements.txt](file:///c:/Users/dopa.mine/Desktop/ophelia/requirements.txt) & [research-requirements.txt](file:///c:/Users/dopa.mine/Desktop/ophelia/research-requirements.txt)
  - Core: `fastapi`, `uvicorn`, `pydantic`, `httpx`, `cryptography`, `pandas`, `numpy`, `scipy`
  - Quant/ML: `scikit-learn`, `statsmodels`, `arch`, `torch`, `transformers`
- **Android Mobile App:** JDK 17, Android SDK 34, Jetpack Compose (`android-app/`)

---

## 6. Dataset Provenance & Exclusions

To comply with GitHub repository storage limits and clean revision tracking, multi-gigabyte raw market datasets have been excluded from git:
- **Binance UM AggTrades & BookTicker:** Historical raw data resides locally in `data/raw/` and can be reconstructed using [scripts/download_and_normalize_btcusdt.py](file:///c:/Users/dopa.mine/Desktop/ophelia/scripts/download_and_normalize_btcusdt.py) and [scripts/download_expanded_dataset.py](file:///c:/Users/dopa.mine/Desktop/ophelia/scripts/download_expanded_dataset.py).
- **Normalized Parquet Files:** Stored locally in `data/normalized/` and `data/processed/`.
- **Manifests & Checkpoints:** Fully tracked under [data/manifests/](file:///c:/Users/dopa.mine/Desktop/ophelia/data/manifests/) with timestamp ranges, row counts, and column schemas.
- **Machine-Readable Summaries:** All empirical results, contingency matrices, FDR p-values, and trade evaluations are preserved in version-controlled JSON files under [data/](file:///c:/Users/dopa.mine/Desktop/ophelia/data/) and [results/](file:///c:/Users/dopa.mine/Desktop/ophelia/results/).

---

## 7. Security Exclusions & Safety Boundaries

- **Zero Hardcoded Secrets:** No live API keys, BingX secrets, Telegram tokens, SSH private keys, or passwords exist in version control.
- **Excluded Files:** `.env`, `.env.*`, `control.env`, `*.key`, `*.pem`, `*.db`, `*.sqlite`, `*.pkl`, `*.hprof`.
- **Operating Mode:** Ophelia is hard-locked to `SHADOW` execution mode. Live trading authority is `DISABLED`. AI models have zero execution authority.

---

## 8. Recommended Reading Order for Gemini 4 Argon

When conducting an independent audit of Ophelia, follow this sequence:

1. **System Mission & Rules:** [AGENTS.md](file:///c:/Users/dopa.mine/Desktop/ophelia/AGENTS.md) and [docs/OPHELIA_PLATFORM_ARCHITECTURE_AND_AGENCY_REPORT.md](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/OPHELIA_PLATFORM_ARCHITECTURE_AND_AGENCY_REPORT.md)
2. **Current Checkpoint Index:** This document ([docs/GITHUB_CHECKPOINT_AND_REVIEW_INDEX.md](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/GITHUB_CHECKPOINT_AND_REVIEW_INDEX.md))
3. **Friction Accounting Audit:** [docs/PHASE_12_FRICTION_ACCOUNTING_AUDIT.md](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/PHASE_12_FRICTION_ACCOUNTING_AUDIT.md) — Crucial quantitative analysis explaining why 5m retest strategies fail under taker friction.
4. **TimesFM OOS & Incremental Value:** [docs/PHASE_12_FRESH_PERIOD_INCREMENTAL_TIMESFM_VALIDATION_REPORT.md](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/PHASE_12_FRESH_PERIOD_INCREMENTAL_TIMESFM_VALIDATION_REPORT.md) & [docs/PHASE_10_3_TIMESFM_OUT_OF_SAMPLE_VALIDATION_REPORT.md](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/PHASE_10_3_TIMESFM_OUT_OF_SAMPLE_VALIDATION_REPORT.md)
5. **Alpha Discovery & Stop-Room Reality:** [docs/PHASE_13_ALPHA_DISCOVERY_REPORT.md](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/PHASE_13_ALPHA_DISCOVERY_REPORT.md), [docs/PHASE_13_STOP_ROOM_RESEARCH.md](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/PHASE_13_STOP_ROOM_RESEARCH.md), and [docs/PHASE_13_ECONOMIC_VALIDATION.md](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/PHASE_13_ECONOMIC_VALIDATION.md)
6. **Microstructure Methodology:** [docs/MICROSTRUCTURE_METHODOLOGY_SPEC.md](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/MICROSTRUCTURE_METHODOLOGY_SPEC.md) & Phase 6 reports.
7. **Control Plane & Microstructure Source:** [control_plane/api.py](file:///c:/Users/dopa.mine/Desktop/ophelia/control_plane/api.py), [control_plane/microstructure_engine.py](file:///c:/Users/dopa.mine/Desktop/ophelia/control_plane/microstructure_engine.py), [models/microstructure.py](file:///c:/Users/dopa.mine/Desktop/ophelia/models/microstructure.py).
