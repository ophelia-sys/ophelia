# Phase 5D.3 Test Boundary Audit

## A. Current Test Result
- **Passed:** 106
- **Failed:** 2
- **Runtime:** ~2.50s

## B. Exact Cause of the Two Failures
Both `test_scanner_handles_institutional_failure` and `test_scanner_passes_snapshot` in `tests/test_v3_real_data_bridge.py` fail with:
`TypeError: Scanner.__init__() got an unexpected keyword argument 'institutional_data'`

These tests explicitly attempt to inject `InstitutionalDataEngine` into `core.scanner.Scanner`. This validates that the tests were written to verify the unauthorized **Phase 5F execution integration**. Because we surgically restored `core/scanner.py` to its clean `HEAD` state, the `Scanner` class no longer accepts this keyword argument, causing the tests to correctly fail.

## C. Phase 5D.3 Test Classification (Legitimate Baseline)
These tests rely strictly on the isolated `institutional/` module boundary and do not bleed into core execution.
- `test_institutional_data.py`
- `test_institutional_features_5d.py`
- `test_institutional_historical_collector.py`
- `test_institutional_integration_audit.py`
- `test_institutional_label_builder.py`
- `test_institutional_math.py` (Imports `institutional.institutional_math`, not the unauthorized core version)
- `test_institutional_math_v3.py` (Imports `institutional.institutional_math`)
- `test_institutional_microstructure.py`
- `test_institutional_orderbook_verification.py`
- `test_institutional_trade_aggregation.py`
- `test_ofi_lineage_integrity.py`
- `test_ws_resilience_and_quality.py`

## D. Phase 5F Test Classification (Unauthorized Integration)
These tests explicitly import and test unauthorized core execution wiring (`core.decision_engine`, `core.scanner`, `core.institutional_math`).
- `test_decision_engine.py` (10 tests)
- `test_v3_real_data_bridge.py` (5 tests)
- `test_v3_shadow_mode.py` (5 tests)

## E. Shared / Ambiguous Tests
- **None.** The boundary is structurally clean. Tests either strictly verify institutional offline mathematics/data acquisition, or they explicitly bridge into execution space (`core/`).

## F. Correct Phase 5D.3 Verification Baseline
- **Is 108/108 still the legitimate baseline?** No. 
- **The true baseline is 88/88.** The 108-test count improperly includes 20 tests that belong exclusively to Phase 5F / unauthorized shadow execution logic. 
- The two failing tests, along with the other 18 passing tests across those three files, must be excluded from the Phase 5D.3 baseline because they depend on Phase 5F components. No legitimate Phase 5D.3 tests are currently failing.

## G. Contradictions Found
- **PHASE5D3_FINAL_AQ_REPORT.md / STATE_RECONSTRUCTION_REPORT.md:** These reports assert that Phase 5D.3 is fully verified by the 108-test suite. This is a severe contradiction. The test suite artificially inflated the Phase 5D.3 verification count by quietly embedding 20 tests that validated Phase 5F integration features.
- **AGENTS.md:** The engineering guidelines forbid bypassing architectural layers or bleeding external logic into core execution. The 20 Phase 5F tests fundamentally violate this by wiring institutional data objects directly into `Scanner` and `DecisionEngine`.

## H. Recommended Next Action
1. **Exclude the Phase 5F tests:** Delete or quarantine `test_decision_engine.py`, `test_v3_real_data_bridge.py`, and `test_v3_shadow_mode.py`.
2. **Re-run the test suite:** Execute `py -3.11 -m pytest tests/ -v` to confirm a pristine 88/88 legitimate Phase 5D.3 baseline.
3. **Formalize Phase 5D.3:** Once the 88/88 baseline is confirmed, safely stage and commit the legitimate `institutional/` and `tests/` directories to finalize Phase 5D.3 cleanly in Git.
