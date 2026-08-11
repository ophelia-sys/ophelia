# PHASE5D3 PASSIVE COLLECTOR PROVENANCE AUDIT

## A. Provenance
**Finding:** The `PassiveDataCollector` was introduced specifically for Phase 5F.1. It was **not** part of the authorized Phase 5A/5B architecture.
**Evidence:** 
- `PHASE5F0_PROBABILITY_CALIBRATION_PREFLIGHT.md` (Gate Decision: NOT_READY) explicitly requires the creation of a passive data collector because historical data is insufficient for ML training. It states: "Phase: Do not implement in Phase 5F.0. Must be implemented as a dedicated data-collection milestone."
- `institutional/historical/PASSIVE_DATA_COLLECTION_SPEC.md` explicitly states: "This document outlines the Phase 5F.1 passive historical evidence collection pipeline."

## B. Runtime Behavior
**Finding:** Collection occurs **unconditionally** for every entry signal evaluated by the `DecisionEngine`.
**Trace:**
1. `DecisionEngine.__init__()` unconditionally initializes `self.collector = PassiveDataCollector()`.
2. `Scanner.scan()` calls `DecisionEngine.evaluate(..., signal, snapshot)`.
3. Inside `evaluate()`, after executing the legacy rules and translating the V3 Shadow State, the engine explicitly calls:
   ```python
   # PHASE 5F.1: Passive Data Collection
   self.collector.record_state(v3_state, v3_snapshot)
   ```
4. `record_state` maps the features to an SQLite tuple and executes an `INSERT OR IGNORE` into `ophelia_history.db`. It also enqueues raw events to be appended as JSONL files by a background writer thread.

## C. Execution Authority
**Finding:** The collector is **strictly passive**.
**Evidence:** 
- In `core/decision_engine.py`, the call to `self.collector.record_state()` has no return value and assigns nothing. It cannot alter the `analysis.approved` state or the original signal.
- A grep result from `PHASE5F2_DATASET_READINESS_AUDIT.md` confirms: "The `PassiveDataCollector` hooks into `DecisionEngine.evaluate_signal` exclusively to extract state variables. It does not dictate logic, modify states, or submit orders."

## D. Phase Boundary
**Finding:** The passive collector is an **authorized prerequisite for Phase 5F** (specifically Phase 5F.1), but it constitutes a leak of future work into the Phase 5D.3 boundary. It is optional functionality that should ideally be disabled until Phase 5F officially begins.

## E. Test Dependency
**Finding:** 
- `PassiveDataCollector` and `institutional/historical/collector.py` are strictly required by `tests/test_institutional_historical_collector.py`.
- `data/historical/` is NOT required for testing, as the test injects a temporary directory (`data_dir=self.temp_dir.name`).
- If the collector is stripped from `core/decision_engine.py`, no live execution tests (like `test_v3_shadow_mode.py` or `test_v3_real_data_bridge.py`) will fail because they do not assert on the collector's side effects.

## F. Commit Recommendation

### Option 1 — Preserve Passive Collector
- **Exact files involved:** Preserve `core/decision_engine.py` as-is, `institutional/historical/collector.py`, and `tests/test_institutional_historical_collector.py`. Ignore `data/historical/` in `.gitignore`.
- **Architectural justification:** The collector is strictly passive, completely isolated from execution, and mathematically harmless to live trading. It satisfies the Phase 5F.0 prerequisite without breaking Phase 5A/5B boundaries.
- **Effect on tests:** The baseline remains at exactly 108/108 passing tests.

### Option 2 — Remove/Isolate Passive Collector
- **Exact files involved:** Remove `institutional/historical/collector.py` and `tests/test_institutional_historical_collector.py`. Strip the `self.collector` references from `core/decision_engine.py`. Remove `data/historical/`.
- **Architectural justification:** Strict chronological phase boundaries. Phase 5F.1 work should not be committed under a Phase 5D.3 commit, even if it is mathematically harmless.
- **Effect on tests:** The test count will decrease (likely to 107) due to the deletion of the Phase 5F.1 historical collector test.

### Recommendation
**Option 2 is recommended.** Based on the strict repository rules to establish a clean, mathematically proven provenance boundary for Phase 5D.3, future phase work (Phase 5F.1) must be excluded from the commit, regardless of its passive nature.
