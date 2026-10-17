# OPHELIA — SESSION CHECKPOINT / SAFE PAUSE

This document represents the authoritative handoff state for the Ophelia system at the end of the current development session. It must be read before any new work is initiated.

## 1. Current Architecture
The foundation of the trading and execution system is structurally built, incorporating:
- **Core Components**: TradingEngine, DecisionEngine, RiskManager, Strategy layer, BingX execution, Telegram/safety infrastructure.
- **Institutional Math Engine v3**: 
  - *Robust volatility*: Realized Volatility, Parkinson, Garman-Klass, ATR
  - *Trend*: Kaufman Efficiency Ratio, ATR-scaled trend distance, directional persistence
  - *Momentum*: Robust MAD-based measurements, acceleration
  - *Normalization*: MAD / robust Z-score, ECDF / rank normalization
  - *Inputs*: Evidence entropy, Open Interest, funding inputs.
- **Microstructure**: Mid price, spread, relative spread, queue imbalance, depth imbalance, microprice, visible-book impact, book concentration, bid/ask book slope.
- **Order Flow**: CVD, TVI, aggressor-side trade flow. 
- *CRITICAL NOTE ON OFI*: Canonical Cont-Kukanov-Stoikov OFI is **UNAVAILABLE** from the BingX depth feed. It must **NEVER** be substituted with depth/queue imbalance, microprice, CVD, TVI, book slope, price movement, or spread. A full OFI lineage audit was completed to enforce this.

## 2. Completed Phases
- **PHASE 4**: Institutional Data Acquisition
- **PHASE 4.1**: Real-data BingX verification
- **PHASE 4.2**: CVD / TVI aggregation and deduplication
- **PHASE 4.3**: BingX order-book microstructure verification
- **PHASE 4.4**: Verified BingX microstructure metrics
- **PHASE 4.5**: Institutional Math integration + order-book slope audit
- **PHASE 4.5.1**: Repository-wide OFI / microstructure lineage audit
- **PHASE 6.1**: Flow-Price Divergence empirical validation
- **PHASE 6.2**: Research Validation Framework Hardening

## 3. In-Progress Phase
- **PHASE 6**: Canonical research dataset / feature research framework (Overall Progress: ~50%). The research foundation is hardened, but predictive modeling has not yet begun.

## 4. Rejected Features
- **FLOW_PRICE_DIVERGENCE_V1**: `REJECTED / REMOVE`. 
  - *Reason*: Failed to demonstrate incremental out-of-sample predictive value and was economically negative after realistic transaction costs. The original experiment also contained methodological defects in HAC/bootstrap/FDR application. This decision is immutable.

## 5. Dataset Hashes
- **Canonical Dataset (binance_um_universe_1m_v2)**: 
  - SHA-256: `D2E839EDECFAE88B798993CFF9545FA626071EFCB722F266FBE15E0BEA3E20B5`

## 6. Current Research Framework
The Phase 6.2 validation framework strictly enforces:
- **Calendar-Time Portfolio**: Primary inference approach aggregating overlapping multi-symbol events onto a uniform calendar grid.
- **Calendar-time Newey-West & Block Bootstrap**: Standard error and resampling methodologies explicitly tied to calendar grids.
- **Panel-HAC**: Secondary robustness check only.
- **Global Multiple-Testing Correction**: FDR applied across pre-registered hypothesis families.
- **Strict OOS Integrity**: Dev/OOS separation managed immutably by `ExperimentRunner`.
- **Feature Gates**: `CANDIDATE → LEAKAGE_PASS → DEV_PASS → OOS_PASS → COST_PASS → STABILITY_PASS → MULTIPLE_TESTING_PASS → PRODUCTION_CANDIDATE`. Failure leads permanently to `REJECTED`.

## 7. Current Feature Registry Status
Initialized in `research/phase6/feature_registry.json`.
- `fvg_confirmation_v1`: `PRODUCTION_CANDIDATE`
- `pool_confirmation_v1`: `PRODUCTION_CANDIDATE`
- `liquidity_sweep_v1`: `PRODUCTION_CANDIDATE`
- `flow_price_divergence_v1`: `REJECTED`

## 8. Current Test Status
- **PASSING TESTS**: `pytest research/phase6/tests/test_framework.py` (3/3 passed). Validates OOS integrity, FDR correction, and CalendarTimePortfolio aggregation.
- *Note*: Other historical test suites exist but were not run in the final execution step of this session.

## 9. Current Git Status
- **Branch**: `main` (ahead of origin/main by 1 commit)
- **Latest Commit**: `ecfcff0412f6fafb9faa9ef174293026cda62069` (Phase 5D.3: finalize institutional data and websocket baseline)
- **Uncommitted Modifications**:
  - `data/trades.csv`
  - `external/Kronos`
  - `institutional/liquidity.py`
  - `institutional/normalization.py`
  - `institutional/open_interest.py`
  - `institutional/order_flow.py`
  - `logs/ophelia.log`
- **Untracked Research/Audit Files**: Numerous `PHASE6_*.md` audit reports, `research/` directory, `tests/test_phase6_*.py` files, and various temporary `.json`/`.csv` files.

## 10. Current Known Limitations
- The historical ML data engine is incomplete.
- OFI is unavailable; models must be built without it.
- Flow-Price Divergence was theoretically plausible but practically inert; the baseline structural setups currently lack documented independent predictive power edge.

## 11. Current Next Phase Recommendation
- **Next Step**: Define a new research hypothesis or feature definition under the hardened Phase 6.2 framework. The immediate goal is to discover predictive features that can survive the rigorous new OOS, cost, and multiple-testing gates. Do *not* optimize against historical results.

## 12. Exact Files/Directories Relevant to Resume
- `AGENTS.md` (Core rules)
- `OPHELIA_SESSION_CHECKPOINT.md` (This file)
- `research/PHASE6_2_VALIDATION_FRAMEWORK.md` (Methodological rules)
- `research/phase6/` (Framework source code: `experiment.py`, `statistics.py`, `costs.py`, `registry.py`)
- `research/experiments/` (Experiment scripts)

## 13. Any Unfinished Task
- Phase 6 is in progress; ML modeling and probability calibration have not started.
- No active implementation task was left mid-edit.

## 14. Any Running/Stopped Process
- `task-547`: `$env:PYTHONPATH="."; python -u research/phase6/empirical_validation.py` (Reported as running by the IDE task manager from earlier in the session).

## 15. Temporary Files (Do Not Mistake for Production)
- Files inside `scratch/`
- `.log` files in `logs/`
- `temp_test_metrics_2.csv`
- `capture_output.txt`
- Assorted untracked ad-hoc diagnostic scripts (e.g., `audit_script.py`, `smoke_test.py`, `analyze_depth.py`).

***
**GOVERNING PRINCIPLE (EVIDENCE > SOPHISTICATION):**
"If a feature, model, indicator, mathematical estimator, timeframe, data source, or research technique does not demonstrate incremental out-of-sample predictive value, remove it regardless of how sophisticated, institutional, academic, or technically impressive it sounds."
