# PHASE 5.3 TARGET/PURGE AUDIT

**Date:** 2026-08-14

## 1. Target Label Construction
- **Target Definition:** `target_60_up_10` (Cost-Adjusted Triple Barrier)
- **Time Horizon:** 60 periods (5 hours on 5m data)
- **Label Resolution:** For an observation at time $t$, the label evaluates the price path from $t+1$ to $t+60$.
- **Information Span:** The label $y_t$ is a function of $\{P_{t+1}, P_{t+2}, ..., P_{t+60}\}$.

## 2. Purged Walk-Forward Configuration
- **Proposed Purge:** 12 observations
- **Proposed Embargo:** 12 observations

## 3. Mathematical Overlap Proof
Let the training partition end at index $T_{train\_end}$.
Let the validation/test partition begin at index $T_{val\_start}$.

Under a 12-bar purge configuration:
$T_{val\_start} = T_{train\_end} + 12 + 1$

The label for the final training observation $y_{T_{train\_end}}$ is evaluated using future prices up to $T_{train\_end} + 60$.
Since $T_{val\_start} < T_{train\_end} + 60$, the training label $y_{T_{train\_end}}$ is actively utilizing future prices that occur *within* the out-of-sample validation period (specifically, 48 bars of validation data leak into the training label). 

If a model learns to predict this target, the training partition has "seen" future market regimes/volatility states that exist inside the validation set.

Similarly, an **Embargo** of 12 bars means that after the validation set ends at $T_{val\_end}$, the subsequent training partition begins at $T_{val\_end} + 12 + 1$. The validation label $y_{T_{val\_end}}$ depends on prices up to $T_{val\_end} + 60$, causing 48 bars of overlap into the next training period.

## 4. Conclusion and Minimum Safe Boundary
> [!CAUTION]
> **PROTOCOL CONFLICT — PURGE/HORIZON**
> A 12-bar purge and 12-bar embargo are **mathematically unsafe** and violate the strict non-overlapping requirement for out-of-sample ML evaluation. 
> 
> **Minimum Safe Boundary Required:**
> Both the Purge and Embargo must be **$\ge 60$ observations** to completely clear the 60-bar label horizon. 
> 
> *Recommendation:* Set Purge = 60 and Embargo = 60.

**STATUS: FAIL** (Do not run ML until the purge/embargo configuration is updated to at least 60).
