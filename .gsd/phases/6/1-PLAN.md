---
phase: 6
plan: 1
wave: 1
---

# Plan 6.1: Microstructure Research Suite

## Objective
Implement the microstructure research suite as a dedicated, decoupled market intelligence and regime layer (`control_plane/microstructure_engine.py`). Do not allow unvalidated formulas or synthetic scores to independently trigger trades. Structure Modules A through E, normalize all component scores to $[0, 100]$, and label experimental syntheses (such as the ADAOT score) explicitly as `RESEARCH / EXPERIMENTAL`.

## Context
- [.gsd/SPEC.md](file:///c:/Users/dopa.mine/Desktop/ophelia/.gsd/SPEC.md)
- [OPHELIA_CURRENT_STATE.md](file:///c:/Users/dopa.mine/Desktop/ophelia/OPHELIA_CURRENT_STATE.md)
- `institutional/microstructure.py`
- `institutional/market_state.py`
- `control_plane/db.py`

## Tasks

<task type="auto">
  <name>Task 6.1: Implement Modules A through E and Normalized Toxicity Engine</name>
  <files>control_plane/microstructure_engine.py, control_plane/db.py</files>
  <action>
    - In `control_plane/db.py`:
      * Create table `microstructure_metrics`:
        `symbol`, `timestamp_ms`, `flow_innovation`, `rho_calibrated`, `median_duration_ms`, `duration_anomaly`, `depth_imbalance`, `spread_bps`, `price_impact_bps`, `toxicity_score`, `regime`, `is_experimental`, `created_ms`.
    - Create `control_plane/microstructure_engine.py`:
      * Module A — Trade Flow Innovation:
        - Calculate signed trade volume $Q_t \in \{-1, +1\}$.
        - Fit autoregressive flow parameter $\rho$ dynamically: $E[Q_t | Q_{t-1}] = \rho Q_{t-1}$.
        - Flow innovation: $I_t = V_t \cdot (Q_t - \rho Q_{t-1})$.
        - Output: innovation value, sample size, lookback window, confidence.
      * Module B — Trade Duration:
        - Inter-trade duration $\Delta t_i = t_i - t_{i-1}$.
        - Rolling median duration, duration percentile, duration acceleration ratio.
        - Duration anomaly flag when trading clusters rapidly.
      * Module C — Order Book Dynamics:
        - Bid depth, ask depth, relative spread, order-book imbalance (OBI).
        - Depth depletion and replenishment tracking.
        - Invariant: Preserve directionality; never fabricate limit book levels when sequence gaps exist.
      * Module D — Price Impact Estimation:
        - Observed immediate response and temporary vs persistent price impact.
        - Hasbrouck-style autoregressive impact estimate when sufficient trade data exists.
      * Module E — Composite Toxicity & Regime:
        - Normalize all components to $[0, 100]$ using rolling percentiles.
        - Composite Toxicity Score: weighted combination of normalized flow innovation, duration compression, order book stress, and impact estimate.
        - Regime Classification: `NORMAL`, `ELEVATED`, `TOXIC_BUY_FLOW`, `TOXIC_SELL_FLOW`, `LIQUIDITY_STRESS`, `EXTREME_LIQUIDITY_STRESS`.
      * ADAOT Research Score:
        - Implement experimental combined score clearly labeled `ADAOT_RESEARCH_SCORE (RESEARCH / EXPERIMENTAL)`.
        - Contextual and advisory only. Does not place orders.
  </action>
  <verify>python -m pytest tests/test_microstructure_engine.py -v</verify>
  <done>Microstructure engine calculates Modules A through E, outputs normalized toxicity scores and regimes without crashing on missing feeds.</done>
</task>

<task type="auto">
  <name>Task 6.2: Implement Duration ACD and Behavioral Liquidity Research (Shadow Only)</name>
  <files>control_plane/microstructure_engine.py, tests/test_microstructure_engine.py</files>
  <action>
    - In `control_plane/microstructure_engine.py`:
      * Implement `ACDDurationModel`:
        - Computes expected trade duration $\psi_i = \omega + \alpha \Delta t_{i-1} + \beta \psi_{i-1}$.
        - Flags duration residuals to identify volatility/liquidity clustering.
      * Implement `BehavioralLiquidityResearch`:
        - Tracks disposition-effect proxies and volume-weighted reference prices.
        - Operates strictly in `SHADOW_ONLY`.
    - Create `tests/test_microstructure_engine.py`:
      * Verify mathematical formulas of Modules A-E.
      * Verify normalization guarantees outputs remain in $[0, 100]$.
      * Verify handling of incomplete or missing order book data (displays `NOT_AVAILABLE`, never crashes or hallucinates).
  </action>
  <verify>python -m pytest tests/test_microstructure_engine.py -v</verify>
  <done>All microstructure research tests pass; shadow modules operate isolated from execution gating.</done>
</task>

## Success Criteria
- [ ] Modules A through E implemented with genuine market data inputs.
- [ ] Autoregressive $\rho$ calibrated empirically, not hardcoded.
- [ ] Composite toxicity score normalized to $[0, 100]$ with valid regimes.
- [ ] ADAOT research score explicitly marked `RESEARCH / EXPERIMENTAL`.
- [ ] Microstructure layer remains purely advisory for market regime context.
