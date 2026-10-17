# OPHELIA PHASE 10 METHODOLOGY CORRECTION & VERIFICATION
## Formal Audit of Phase 10 Screening Limitations

Date: 2026-10-02
Author: Antigravity AI & Ophelia Core Architecture
Layer: Phase 10 / Phase 10.1 Transition

---

### Explicit Verification of the 11 Methodological Flaws in Phase 10

Prior to implementing architectural corrections in Phase 10.1, the following findings are verified directly against the codebase:

1. **Breakout vs. Retest Candidate Generation Defect**:
   - **Verification**: In `scripts/run_multi_venue_candidate_study.py:90-98`, candidates were generated when `cur_px > max_h and cur_px > vwap` (at the close of the breakout bar).
   - **Flaw**: Ophelia's canonical lifecycle requires `IDENTIFIED -> WAITING_FOR_RETEST -> RETEST_TOUCHED -> CONFIRMING_REJECTION -> ENTRY_READY`. The screening candidates were generated at the peak of momentum expansion prior to retest pullback.

2. **Crude Binary Compatibility Filter Collapse**:
   - **Verification**: In `control_plane/trade_compatibility.py:160-170`, the rule evaluated `q50 > entry` for LONG and `q50 < entry` for SHORT.
   - **Flaw**: Because candidates were generated at overextended breakout highs, TimesFM's autoregressive distribution projected a mean-reverting pullback towards the rolling mean ($q_{50} < entry$). Consequently, all 203 candidates collapsed into `INCOMPATIBLE`.

3. **Zero Treated Population**:
   - **Verification**: Database query confirms `Compatible: 0, Incompatible: 203`.
   - **Flaw**: With zero compatible candidates, there was no treatment group. Therefore, no comparative trading outcome or empirical improvement can mathematically exist.

4. **Misleading Capital Preservation Claim**:
   - **Verification**: Previous summary stated "100% negative drift eliminated" and "6.78R capital preserved".
   - **Flaw**: In statistical and causal inference, a filter that rejects 100% of observations is degenerate. Zero trades taken is not a trading strategy or a realized improvement. Claiming capital preservation from a zero-sample treatment group is statistically invalid.

5. **Timeframe Misalignment (1m vs 5m)**:
   - **Verification**: Previous experimental scripts used 1m raw klines with 60 1m steps in certain paths, while the core specification requires a 5m primary architecture.
   - **Correction**: Phase 10.1 establishes `TIMESFM_PRIMARY_TIMEFRAME = 5m` with 12 future steps (+15m, +30m, +45m, +60m), while preserving the 1m 60-step implementation cleanly labeled as `TIMESFM_1M_RESEARCH`.

6. **Missing 12-Step Path Persistence**:
   - **Verification**: `candidate_forecasts` table stored only 4 sampled steps (`path_15m`, `30m`, `45m`, `60m`).
   - **Correction**: The full 12-step trajectory must be serialized and persisted.

7. **Uncalibrated Dispersion Buckets**:
   - **Verification**: `control_plane/trade_compatibility.py:137-142` partitioned dispersion into `<2.5% = LOW`, `2.5-6.0% = MODERATE`, `>6.0% = HIGH`.
   - **Flaw**: These thresholds were arbitrary heuristics. They must be reported as `raw_dispersion_pct` with an explicit `DISPERSION_BUCKET_UNCALIBRATED` label.

8. **Quantile Sorting Is Not Calibration**:
   - **Verification**: In `control_plane/timesfm_candidate.py:163-168`, `q10 = min(q10, q50)` and `q90 = max(q90, q50)` enforced monotonic ordering.
   - **Flaw**: Monotonic post-processing is a validity constraint, not empirical calibration. Post-processed quantiles must be logged alongside raw quantiles, and empirical coverage must be evaluated out-of-sample.

9. **Sample Window Limitation (4 Days)**:
   - **Verification**: Ingestion used 4 days (17,281 bars).
   - **Flaw**: 4 days is an initial local screening window. Robust trading evaluation requires materially longer historical datasets spanning diverse market regimes.

10. **Sample-Bound Basis Statistics**:
    - **Verification**: Cross-venue basis metrics were calculated strictly over the 4-day sample.
    - **Flaw**: Basis statistics must be recognized as sample-specific and continuously updated over extended windows.

11. **Inconsistent Terminology (Max vs 99th Percentile)**:
    - **Verification**: In `docs/PHASE_BINANCE_TIMESFM_COMPATIBILITY_REPORT.md:144`, 99th percentile was 0.0245% while table headers and text used "max basis" interchangeably.
    - **Correction**: Strict statistical terminology must distinguish between maximum observed value and distribution percentiles (95th, 99th).

---

### Invariants for Phase 10.1
- `TRADING_AUTHORITY = FALSE`
- `EXECUTION_MODE = SHADOW`
- `LIVE_ORDER_PLACEMENT = FORBIDDEN`
- `AUTONOMOUS_SLOT_RESERVATION = FORBIDDEN`
- Zero live orders, zero slot mutations, zero risk overrides.
