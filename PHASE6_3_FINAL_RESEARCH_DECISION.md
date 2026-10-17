# PHASE 6.3 FINAL RESEARCH DECISION

## CURRENT FROZEN BENCHMARK
BASE + CVD + LightGBM

## EVALUATION 1: P5 (Cross-Asset / Relative Market Structure)
**Classification:** REMOVE
- Point estimates were negative across the board.
- Pooled DM p-val was completely insignificant.
- Economic Net Returns degraded at 0 and 5 bps.

## EVALUATION 2: P4 (Large-Trade Microstructure)
**Classification:** INCONCLUSIVE / RESEARCH SURVIVOR

### Statistical Evidence:
- **Pooled Statistical Significance:** The Pooled DM p-value is **0.0040**, which is highly statistically significant. This indicates that on aggregate, adding P4 features provides statistically significant pooled incremental predictive information over the baseline.
- **Directional Consistency:** 5 out of 6 symbols (BTC, ETH, XRP, BNB, ADA) showed a positive reduction in LogLoss point estimates. Only SOLUSDT was neutral (-0.04 bps).
- **Multiple Hypothesis Testing (BH-FDR):** No single symbol crossed the strict q < 0.05 threshold independently. ETHUSDT and BNBUSDT were the strongest at q=0.1182. 
- **Economic Value (ENR):** ENR results were mixed. BTC, ETH, and XRP showed improved ENR at 0 bps. SOL, BNB, and ADA showed slight degradations in ENR at 0 bps. 

### Final Verdict:
The statistical evidence strongly suggests that P4 features contain statistically significant pooled incremental predictive information. However, the failure to secure independent BH-FDR significance per-symbol and the mixed economic outcomes do NOT justify immediate production integration. P4 is frozen as an inconclusive research survivor for future independent chronological confirmation.

**PRODUCTION ACTIVATION = NOT AUTHORIZED**
