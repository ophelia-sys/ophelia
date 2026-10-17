# PHASE 7 FINAL FEATURE REGISTRY

> [!IMPORTANT]
> **STATE: FROZEN WITH POLICY AMENDMENT**
> Phase 7 alpha discovery is officially closed. The historical research verdict is IMMUTABLE.
> Rejected hypotheses are preserved for possible LIVE SHADOW EXPERIMENTATION but must NOT influence the Phase 8 Probability Engine, production confidence, position sizing, or trigger live orders.

---

## FEATURE REPOSITORY

### S1: Time-Series Momentum
- **Experiment ID**: EXP-S1
- **Original Economic Hypothesis**: Time-series momentum continuation on intraday horizons.
- **Original Formula**: Trailing return over aggregated $W$ windows.
- **Original Dataset**: `binance_um_universe_1m_v2.parquet`
- **Original Dataset Hash**: Canonical V2
- **Original Parameter Family**: 1m to 4h momentum lookbacks.
- **Original OOS Result**: < 12 bps gross, negative net expectancy.
- **Original Rejection Reason**: Failed to clear the 12 bps institutional execution friction hurdle. Naive momentum lacks sufficient alpha on 1m/1h horizons.
- **research_status**: REJECTED
- **live_experimental_status**: ELIGIBLE_FOR_SHADOW
- **production_status**: DISABLED
- **revalidation_version**: NONE

---

### S2: Residual Momentum
- **Experiment ID**: EXP-S2
- **Original Economic Hypothesis**: Beta-adjusted idiosyncratic momentum continuation.
- **Original Formula**: $R_{idio} = R_i - \beta_i \times R_{mkt}$
- **Original Dataset**: `binance_um_universe_1m_v2.parquet`
- **Original Dataset Hash**: Canonical V2
- **Original Parameter Family**: Beta estimation windows + momentum holding periods.
- **Original OOS Result**: < 12 bps gross, negative net expectancy.
- **Original Rejection Reason**: Failed execution friction hurdle. Beta neutralization did not yield actionable intraday edge.
- **research_status**: REJECTED
- **live_experimental_status**: ELIGIBLE_FOR_SHADOW
- **production_status**: DISABLED
- **revalidation_version**: NONE

---

### S3_CONDITIONAL_VOL_V1: OI/Funding Crowding Reversal
- **Experiment ID**: EXP-S3
- **Original Economic Hypothesis**: Extreme crowding (OI + Funding) + directional price extreme leads to structural reversal.
- **Original Formula**: $Z_{price} \times (OI > \theta) \times (Funding Extreme)$
- **Original Dataset**: `binance_um_universe_1m_v2.parquet` + `research_funding.parquet`
- **Original Dataset Hash**: Canonical V2
- **Original Parameter Family**: Volatility scaling + extreme thresholds.
- **Original OOS Result**: Positive net expectancy (Fragile).
- **Original Rejection Reason**: N/A
- **research_status**: FRAGILE_VALIDATED_ALPHA_CANDIDATE
- **live_experimental_status**: RUNNING
- **production_status**: DISABLED
- **revalidation_version**: NONE

---

### S4_TAKER_FLOW_EXHAUSTION_V1: Taker-Flow Exhaustion
- **Experiment ID**: EXP-S4
- **Original Economic Hypothesis**: Sustained, extreme taker flow dominance leads to liquidity absorption and eventual reversal.
- **Original Formula**: $TakerBuyVolume_W / TotalVolume_W > \theta$
- **Original Dataset**: `binance_um_universe_1m_v2.parquet`
- **Original Dataset Hash**: Canonical V2
- **Original Parameter Family**: 1h, 4h, 8h aggregation; 70%, 80%, 90% dominance thresholds.
- **Original OOS Result**: 0 valid signals (Event starvation).
- **Original Rejection Reason**: Aggregation windows completely eliminated the extreme conditions required to generate signals.
- **research_status**: REJECTED
- **live_experimental_status**: ELIGIBLE_FOR_SHADOW
- **production_status**: DISABLED
- **revalidation_version**: NONE

---

### S4_1_FLOW_PRICE_DISLOCATION_V1: Flow/Price Dislocation Proxy
- **Experiment ID**: EXP-S4.1
- **Original Economic Hypothesis**: High aggressive flow paired with unusually muted price response indicates flow exhaustion/absorption.
- **Original Formula**: Normalized aggressive flow shock + Inverse Normalized Price Response.
- **Original Dataset**: `binance_um_universe_1m_v2.parquet`
- **Original Dataset Hash**: Canonical V2
- **Original Parameter Family**: 5m, 15m windows. 
- **Original OOS Result**: -13.95 bps net expectancy.
- **Original Rejection Reason**: Combining extreme flow with muted price actively degraded independent baseline edges and failed the cost hurdle.
- **research_status**: REJECTED
- **live_experimental_status**: ELIGIBLE_FOR_SHADOW
- **production_status**: DISABLED
- **revalidation_version**: NONE

---

### S5_CS_DISPERSION_V1: Cross-Sectional Dispersion / Relative-Value
- **Experiment ID**: EXP-S5
- **Original Economic Hypothesis**: Extreme idiosyncratic cross-sectional deviations mean-revert to the market median.
- **Original Formula**: $Z_{Idio} = (R_i - Median_{CS}(R)) / MAD$
- **Original Dataset**: `binance_um_universe_1m_v2.parquet` + `universe_artifact_v1.parquet`
- **Original Dataset Hash**: Canonical V2
- **Original Parameter Family**: 4h, 12h, 24h lookback/holding periods, 2.0-3.0 threshold.
- **Original OOS Result**: 0.00 bps net.
- **Original Rejection Reason**: Failed to provide incremental value over raw reversal baseline. Failed execution costs.
- **research_status**: REJECTED
- **live_experimental_status**: ELIGIBLE_FOR_SHADOW
- **production_status**: DISABLED
- **revalidation_version**: NONE

---

## FINAL DISCOVERY AUDIT
**Result: NO ADDITIONAL HIGH-CONVICTION ALPHA FAMILY IDENTIFIED.**
After exhaustive review of canonical data, no other distinct economic mechanism demonstrated a plausible path to clearing the 12 bps execution hurdle. The registry is frozen with S3 as the sole candidate advancing to Phase 8.

> [!NOTE]
> If a rejected feature demonstrates interesting live behavior in shadow mode, its `research_status` remains `REJECTED`. A new version (e.g., `S4_V2_BINGX_LIVE_REVALIDATION`) must be explicitly created.