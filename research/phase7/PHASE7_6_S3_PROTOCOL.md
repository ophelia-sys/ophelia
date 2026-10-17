# Phase 7.6: EXP-S3 Protocol - Crowded Leverage Reversal (Corrected)

## 1. Hypothesis
When Open Interest (OI) sharply expands while Funding Rates reach polarized extremes in the direction of the recent price trend, the market is crowded with highly leveraged directional positions. Such crowded states are statistically prone to aggressive mean-reversion following a localized price shock.

## 2. Exact Formulas
- **Price Feature ($R_t$):** The logarithmic return over the lookback window $k$: $R_t = \ln(P_t / P_{t-k})$
- **Observable Funding Feature ($Z_{F,t}$):** Rolling Z-score of the **most recent historically available** funding rate $F$ over a trailing window $w$. A future funding settlement must never be used prior to its exact timestamp. We distinguish explicitly between `OBSERVABLE_FUNDING` (the lagged, known rate used to compute features) and `REALIZED_FUNDING` (the rate applied to PnL at boundary crossing). If the archive only contains the previous settled funding rate, it will be classified strictly as a lagged observable-funding formulation. $Z_{F,t} = \frac{F_t - \mu_{F,w}}{\sigma_{F,w}}$
- **Open Interest Feature ($\Delta OI_t$):** Percentage change in Open Interest over lookback window $k$: $\Delta OI_t = \frac{OI_t - OI_{t-k}}{OI_{t-k}}$
- **Interaction Signal ($S_t$):**
  $$ S_t = -\text{sign}(R_t) \times \mathbf{1}_{\{|Z_{F,t}| > \theta_F\}} \times \mathbf{1}_{\{\Delta OI_t > \theta_{OI}\}} \times \mathbf{1}_{\{\text{sign}(R_t) == \text{sign}(F_t)\}} $$
  *Interpretation:* If recent price is up ($R_t > 0$), funding is highly positive and aligned with price ($Z_{F,t} > \theta_F$), and OI is surging ($\Delta OI_t > \theta_{OI}$), the market is in a Crowded Long state. We issue a Short signal (-1). Conversely, down price + highly negative funding + surging OI triggers a Long signal (+1).

## 3. Pre-Registered Parameters
A strictly constrained parameter family:
- **Lookback ($k$):** [1h, 4h] (shared for both $R_t$ and $\Delta OI_t$)
- **Funding Window ($w$):** [7d] (168 hours)
- **Funding Threshold ($\theta_F$):** [1.5, 2.0] standard deviations
- **OI Threshold ($\theta_{OI}$):** Rolling 14-day 90th percentile of $\Delta OI_t$
- **Price Threshold ($\theta_R$):** 0 (Sign-based constraint only, requiring alignment with funding).

## 4. Label Selection
- **Pre-Registered Candidates:** {15m, 30m, 1h} forward raw log return.
- **Selection Rule:** We will evaluate the three candidate horizons purely on the chronological **DEVELOPMENT** fold data. The label will be selected based on:
  - Calendar-time excess return
  - Cost-aware expectancy
  - Fold stability
  - Sample sufficiency
- **Freeze Condition:** Exactly ONE label will be frozen after DEV analysis. OOS must remain completely untouched.

## 5. Baselines
- **BASELINE A (Unconditional Market Drift):** Constant long equal-weight allocation to the eligible point-in-time universe.
- **BASELINE B (Raw Short-Term Mean Reversion):**
  - **Signal ($S_{B,t}$):** $-\text{sign}(R_t)$ (Threshold = 0).
  - **Holding Period:** Exact same horizon $H$ as chosen for S3.
  - **Entry Rule:** Enter at close of $t$.
  - **Exit Rule:** Exit at close of $t+H$.
  - **Cost Model:** Same decomposed 12 bps execution cost framework as S3.

## 6. Cost Decomposition
Net Economics evaluated per simulated position will strictly decompose into:
- **gross_pnl:** Raw mark-to-market return.
- **fee_entry / fee_exit:** 4.0 bps per side.
- **slippage_entry / slippage_exit:** 2.0 bps per side.
- **funding_paid_received:** Applied *only* if the position bridges the exact 8h realized funding settlement boundary.
**Net PnL = gross_pnl - 0.0004 - 0.0004 - 0.0002 - 0.0002 $\pm$ funding_realized**
*Funding will not be double-counted or uniformly subtracted.*

## 7. Point-in-Time Universe
- **RESEARCH_UNIVERSE** derived directly from the hashed `universe_artifact_v1.parquet`. Evaluated strictly daily at $T-1$.

## 8. Statistical Framework
- **Folds:** Chronological split (e.g., DEV: 2021-2022, OOS: 2023-2024).
- **Aggregation:** Calendar-Time Portfolio return to control for cross-sectional correlation.
- **Significance:** HAC (Newey-West) t-statistic on calendar-time portfolio returns.
- **Multiple Testing:** Global FDR control over the 4 combinations of $k$ and $\theta_F$.
- **Diagnostics:** Symbol-level hit rates, dispersion, and cross-sectional consistency checks to ensure BTC does not unilaterally drive the strategy.

## 9. OOS Rules
- OOS data remains blinded until DEV results pass the multiple-testing threshold.
- No parameters, thresholds, or label definitions may be adjusted after OOS evaluation begins.

## 10. Success Criteria
To promote S3 to `PRODUCTION_CANDIDATE`:
1. Positive OOS gross expectancy.
2. Positive OOS net expectancy.
3. Statistically outperforms BASELINE B (Incremental vs baseline).
4. Stable performance across time and market regimes.
5. Not dominated by a single symbol (e.g. BTC).
6. Survives FDR multiple-testing correction.
7. Passes automated causal look-ahead audits for Funding and OI alignment.

*(Note: $t > 2.0$ may be used as a statistical criterion, but not an economic one).*
