# PHASE 6.3 P4 - CONFIRMATION DATA AUDIT

## Objective
Determine whether a genuinely unseen historical period is available post-2023 to execute a blind confirmation of the P4 feature family. The target period is **2024-01-01 through Present**.

## Data Availability Audit (Local Storage)
An exhaustive scan of the local filesystem (`data/raw`, `data/normalized`, `data/processed`) yields the following inventory:

| Data Type | End of Local Coverage | 2024-01-01+ Available? |
|-----------|-----------------------|------------------------|
| **5m OHLCV** (`BASE`) | 2023-12-31 23:55:00 UTC | ❌ No |
| **CVD Data** (`CVD`) | 2023-12-31 23:55:00 UTC | ❌ No |
| **Raw aggTrades** (`P4`) | 2023-12-31 23:59:59 UTC | ❌ No |
| **Target Labels** (`target_60_up_10`) | 2023-12-31 23:55:00 UTC | ❌ No |

### Conclusion
**The local Ophelia environment does NOT currently contain any 2024 data.** 
To proceed with the blind chronological confirmation, a full data ingestion protocol must be authorized to pull 2024 data for the 6 primary symbols across all necessary modalities (Klines, Metrics, aggTrades).

---

## 2024 Confirmation Success Criteria (FROZEN)

Before running the confirmation, the quantitative criteria for success are strictly locked. No thresholds will be modified post-evaluation.

**Protocol:**
- **Formulas:** Exact identical P4 formulations (no hyperparameter adjustments).
- **Features:** Identical BASE + CVD + P4 stack.
- **Model:** Identical frozen LightGBM architecture.
- **Period:** 2024-01-01 through latest available 2024 data (chronological out-of-sample).

**Pass Gates (All Must Be Met):**
1. **Predictive Edge:** LogLoss improvement versus BASE+CVD (LogLoss diff > 0 bps).
2. **Probability Calibration:** Brier score non-deterioration (Brier diff >= 0).
3. **Economic Utility:** Positive pooled economic improvement (ENR) at realistic trading cost tiers (e.g., 0, 5 bps).
4. **Broad Generalization:** Incremental improvement must NOT be entirely driven by a single symbol (e.g., must be directionally consistent across multiple symbols).
5. **Drawdown Safety:** No catastrophic degradation in any major symbol's isolated metric profile.
6. **Robustness:** Statistical robustness confirmed under the exact same frozen testing framework (DM HAC, Bootstrapping).

**Future States:**
- **RETAIN:** P4 remains statistically and economically superior in 2024.
- **INCONCLUSIVE / RESEARCH SURVIVOR:** Predictive improvement holds, but economic evidence is weak/negative.
- **REMOVE:** Confirmation fails (predictive degradation).
