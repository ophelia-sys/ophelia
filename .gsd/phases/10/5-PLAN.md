---
phase: 10
plan: 5
wave: 3
---

# Plan 10.5: Candidate-Level Empirical Utility Study & Binance vs BingX Comparative Research

## Objective
Execute empirical research answering the two central architectural questions:
1. "Does TimesFM add useful information for deciding whether an already-valid Ophelia `ENTRY_READY` trade candidate is worth pursuing?"
2. "Does Binance provide better or more useful market intelligence than BingX for constructing that candidate?"

Evaluate candidate-level outcomes across real historical data:
- Track: future returns (+15m, +30m, +45m, +60m), MFE (Maximum Favorable Excursion), MAE (Maximum Adverse Excursion), TP1 hit before SL, TP2 hit before SL, SL hit before TP1, time to exit.
- Compare:
  - Base Strategy alone vs Base Strategy + TimesFM Compatibility Evidence.
  - Candidate generation on Mode A (Binance data) vs Mode B (BingX data): candidate count, entry timing, retest zone fidelity, outcome differences.
- Feature ablations: Condition A (Price only) vs B (+Volume) vs C (+Volatility/VWAP) vs D (+Selected Flow) vs E (+Regime).
- Statistical rigor: Chronological walk-forward splits, Purge + Embargo, Diebold-Mariano tests, Benjamini-Hochberg FDR control.
- Persist results in dedicated experiment tables (`multi_venue_candidate_outcomes`, `multi_venue_experiments`).

## Context
- `control_plane/binance_data.py`
- `control_plane/timesfm_candidate.py`
- `control_plane/trade_compatibility.py`
- `control_plane/cross_venue_basis.py`
- `control_plane/retest_engine.py`

## Tasks

<task type="auto">
  <name>Implement Candidate Outcome Evaluator & Comparative Harness</name>
  <files>control_plane/candidate_research.py</files>
  <action>
    - Create `control_plane/candidate_research.py`:
      - `CandidateOutcomeTracker`: Takes frozen candidate at $T$ and future closed candles $(T, T+60m]$, computes:
        - `mfe`, `mae`, `tp1_hit`, `tp2_hit`, `sl_hit`, `time_to_tp1_min`, `time_to_sl_min`, `realized_r_multiple`, `future_returns` (15m, 30m, 45m, 60m).
      - `ComparativeMarketEngine`: Runs identical structural candidate detector on:
        - Stream A: Binance 5m closed candles.
        - Stream B: BingX 5m closed candles.
        - Computes: candidate count delta, entry price delta, timestamp delta, retest zone accuracy delta.
      - Persistence: Stores full candidate study rows in `candidate_research_outcomes` table with explicit experiment lineage.
  </action>
  <verify>python -c "from control_plane.candidate_research import CandidateOutcomeTracker; tracker = CandidateOutcomeTracker(); cand = {'direction': 'LONG', 'entry_price': 100, 'suggested_sl': 95, 'suggested_tp1': 110, 'suggested_tp2': None}; future_bars = [{'high': 108, 'low': 98, 'close': 105, 'ts': 1000+i*60000} for i in range(15)]; out = tracker.evaluate_outcome(cand, future_bars); assert out['mfe'] == 8.0; assert out['mae'] == -2.0"</verify>
  <done>CandidateOutcomeTracker accurately calculates MFE, MAE, and barrier hit states.</done>
</task>

<task type="auto">
  <name>Execute Historical Candidate Study Across BTC, ETH, and SOL</name>
  <files>scripts/run_multi_venue_candidate_study.py</files>
  <action>
    - Author and execute research runner:
      - Ingest historical Binance USD-M 1m candles for BTCUSDT, ETHUSDT, SOLUSDT.
      - Aggregate into causal 5m candles.
      - Detect structural breakout/retest candidates transitioning to `ENTRY_READY`.
      - Generate frozen TimesFM candidate forecasts and compatibility evaluations at $T$.
      - Trace forward outcomes out to 60 minutes.
      - Run BingX comparative stream.
      - Compute metrics: Win rate, Profit Factor, Expectancy, Net R, Mean MFE, Mean MAE, FDR q-values.
  </action>
  <verify>python scripts/run_multi_venue_candidate_study.py --symbols BTCUSDT,ETHUSDT,SOLUSDT --dry-run</verify>
  <done>Empirical study executes cleanly, populating research tables with verifiable outcome statistics.</done>
</task>

<task type="auto">
  <name>Author Unit Tests for Candidate Research Harness</name>
  <files>tests/test_candidate_research.py</files>
  <action>
    - Test outcome evaluation under LONG and SHORT setups.
    - Test barrier hit order (SL hit before TP1, TP1 hit before SL).
    - Test comparative Binance vs BingX candidate alignment.
    - Verify zero future data enters candidate features or forecast generation.
  </action>
  <verify>pytest tests/test_candidate_research.py -v</verify>
  <done>All candidate research tests pass with 100% assertions.</done>
</task>

## Success Criteria
- [ ] Candidate outcome study executed on real market data across BTC, ETH, SOL.
- [ ] Empirical metrics computed for Base Strategy vs Base Strategy + TimesFM Compatibility.
- [ ] Binance vs BingX candidate quality differences quantified without speculation.
