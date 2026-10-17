# Phase 6.1 Gate 1 Results (EXP 037-039)

## Out-Of-Sample Validation (Folds 4-5)

### Feature: FVG_CONFIRMATION (Selected Tau = 2.0)
Horizon 1m | N=1 | Uncond Mean=2.38 bps | Cond Mean=0.00 bps | Excess=0.00 bps | Raw-P=1.0000 | FDR-P=1.0000 | CI=[0.00, 0.00] bps | Verdict: INCONCLUSIVE / INSUFFICIENT DATA
Horizon 3m | N=1 | Uncond Mean=-3.06 bps | Cond Mean=0.00 bps | Excess=0.00 bps | Raw-P=1.0000 | FDR-P=1.0000 | CI=[0.00, 0.00] bps | Verdict: INCONCLUSIVE / INSUFFICIENT DATA
Horizon 5m | N=1 | Uncond Mean=-3.51 bps | Cond Mean=0.00 bps | Excess=0.00 bps | Raw-P=1.0000 | FDR-P=1.0000 | CI=[0.00, 0.00] bps | Verdict: INCONCLUSIVE / INSUFFICIENT DATA
Horizon 15m | N=1 | Uncond Mean=-16.95 bps | Cond Mean=0.00 bps | Excess=0.00 bps | Raw-P=1.0000 | FDR-P=1.0000 | CI=[0.00, 0.00] bps | Verdict: INCONCLUSIVE / INSUFFICIENT DATA
Horizon 30m | N=1 | Uncond Mean=-24.94 bps | Cond Mean=0.00 bps | Excess=0.00 bps | Raw-P=1.0000 | FDR-P=1.0000 | CI=[0.00, 0.00] bps | Verdict: INCONCLUSIVE / INSUFFICIENT DATA
Horizon 60m | N=1 | Uncond Mean=-33.26 bps | Cond Mean=0.00 bps | Excess=0.00 bps | Raw-P=1.0000 | FDR-P=1.0000 | CI=[0.00, 0.00] bps | Verdict: INCONCLUSIVE / INSUFFICIENT DATA
  Economics (h=60): Gross=0.00 bps, Cost=12.00 bps, Net=-12.00 bps
### Feature: POOL_CONFIRMATION (Selected Tau = 3.0)
Horizon 1m | N=1184 | Uncond Mean=-0.18 bps | Cond Mean=1.10 bps | Excess=1.07 bps | Raw-P=0.0537 | FDR-P=0.3225 | CI=[0.07, 2.17] bps | Verdict: REMOVE
Horizon 3m | N=1184 | Uncond Mean=-0.16 bps | Cond Mean=0.24 bps | Excess=0.15 bps | Raw-P=0.8507 | FDR-P=0.9884 | CI=[-1.41, 1.72] bps | Verdict: REMOVE
Horizon 5m | N=1184 | Uncond Mean=0.01 bps | Cond Mean=0.33 bps | Excess=0.19 bps | Raw-P=0.8271 | FDR-P=0.9884 | CI=[-1.73, 1.93] bps | Verdict: REMOVE
Horizon 15m | N=1184 | Uncond Mean=-0.02 bps | Cond Mean=0.41 bps | Excess=-0.02 bps | Raw-P=0.9884 | FDR-P=0.9884 | CI=[-3.05, 2.93] bps | Verdict: REMOVE
Horizon 30m | N=1184 | Uncond Mean=0.86 bps | Cond Mean=2.99 bps | Excess=2.13 bps | Raw-P=0.2368 | FDR-P=0.7103 | CI=[-1.60, 6.00] bps | Verdict: REMOVE
Horizon 60m | N=1184 | Uncond Mean=1.92 bps | Cond Mean=2.81 bps | Excess=1.11 bps | Raw-P=0.6853 | FDR-P=0.9884 | CI=[-4.17, 6.44] bps | Verdict: REMOVE
  Economics (h=60): Gross=2.81 bps, Cost=12.00 bps, Net=-9.19 bps
### Feature: LIQUIDITY_SWEEP (Selected Tau = 2.0)
Horizon 1m | N=0 | Uncond Mean=0.00 bps | Cond Mean=0.00 bps | Excess=0.00 bps | Raw-P=1.0000 | FDR-P=1.0000 | CI=[0.00, 0.00] bps | Verdict: INCONCLUSIVE / INSUFFICIENT DATA
Horizon 3m | N=0 | Uncond Mean=0.00 bps | Cond Mean=0.00 bps | Excess=0.00 bps | Raw-P=1.0000 | FDR-P=1.0000 | CI=[0.00, 0.00] bps | Verdict: INCONCLUSIVE / INSUFFICIENT DATA
Horizon 5m | N=0 | Uncond Mean=0.00 bps | Cond Mean=0.00 bps | Excess=0.00 bps | Raw-P=1.0000 | FDR-P=1.0000 | CI=[0.00, 0.00] bps | Verdict: INCONCLUSIVE / INSUFFICIENT DATA
Horizon 15m | N=0 | Uncond Mean=0.00 bps | Cond Mean=0.00 bps | Excess=0.00 bps | Raw-P=1.0000 | FDR-P=1.0000 | CI=[0.00, 0.00] bps | Verdict: INCONCLUSIVE / INSUFFICIENT DATA
Horizon 30m | N=0 | Uncond Mean=0.00 bps | Cond Mean=0.00 bps | Excess=0.00 bps | Raw-P=1.0000 | FDR-P=1.0000 | CI=[0.00, 0.00] bps | Verdict: INCONCLUSIVE / INSUFFICIENT DATA
Horizon 60m | N=0 | Uncond Mean=0.00 bps | Cond Mean=0.00 bps | Excess=0.00 bps | Raw-P=1.0000 | FDR-P=1.0000 | CI=[0.00, 0.00] bps | Verdict: INCONCLUSIVE / INSUFFICIENT DATA
  Economics (h=60): Gross=0.00 bps, Cost=12.00 bps, Net=-12.00 bps

## Final Analysis and Verdict

**Feature Verdict:** `REMOVE`

### Justification:
The Flow-Price Divergence feature completely failed to demonstrate statistically and economically meaningful incremental out-of-sample predictive value.

1. **Statistical Failure:** Following the hyperparameter search (`tau` grid) on the Dev set, the most promising threshold for `POOL_CONFIRMATION` (`tau=3.0`) was evaluated on the Out-of-Sample holdout. Across all tested horizons (1m to 60m), the FDR-adjusted p-values failed to show any significance, with the lowest `Raw-P` reaching only 0.0537 at `h=1m`, which dissolved under multiple-testing correction (`FDR-P = 0.3225`).
2. **Economic Failure:** For `POOL_CONFIRMATION` (the only setup with a sufficient sample size, `N=1184`), the gross expectancy at `h=60` was merely `2.81 bps`. When adjusted for a conservative `12.0 bps` round-trip transaction cost, the net expectancy was severely negative (`-9.19 bps`).
3. **Data Scarcity for FVG/Sweep:** The divergence condition (extreme drops in Open Interest coinciding with specific structural setups) occurs too infrequently to construct a robust trading strategy. Out-of-Sample `FVG_CONFIRMATION` produced exactly `N=1` event, and `LIQUIDITY_SWEEP` produced `N=0` events.
4. **EXP 040-041 (Combined Modeling):** As the primary feature yields `0` predictive power and severely negative expectancy out-of-the-box, combining it with the baseline model is mathematically moot. Running combined model training on an inert feature violates the requirement to fail fast. 

**Conclusion:** 
The Phase 6 Flow-Price Divergence (`Z_DeltaOI` conditioned divergence) feature does not rescue the Phase 5 pure structural setups. It is structurally sound and mathematically sophisticated, but entirely inert in out-of-sample forward prediction. It is formally rejected.