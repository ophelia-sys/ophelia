# PHASE 7.6.8 — BINGX FEATURE PARITY AUDIT (HARDENED)

**Target Version:** `S3_CONDITIONAL_VOL_V1`

## 1. Feature Parity Matrix

| Feature | Research Source (Binance) | Research Cadence & Timestamp | Live Source (BingX) | Live Cadence & Timestamp | Classification |
|---------|---------------------------|------------------------------|---------------------|--------------------------|----------------|
| **1m close** | `monthly/klines` | 1m (`open_time`) | REST `/openApi/swap/v3/quote/klines` | 1m (`time`) | **MATCH** |
| **4h log return** | Computed from 1m close | 4h | Computed from 1m close | 4h | **MATCH** |
| **14d ATR (Vol State)** | Computed from 1m close | 14d | Computed from 1m close | 14d | **MATCH_WITH_ADAPTATION** (Historical API fetch) |
| **Funding Rate** | `monthly/fundingRate` | 8h (`calc_time`) | REST `/openApi/swap/v2/quote/premiumIndex` | 8h (`nextFundingTime`) | **MATCH** |
| **Funding Z-Score** | Computed | 14d rolling | Computed | 14d rolling | **MATCH_WITH_ADAPTATION** (Local accumulation or historical API fetch) |
| **Open Interest (OI)** | `daily/metrics` | 5m (`create_time`) | REST `/openApi/swap/v2/quote/openInterest` | Current Snapshot only | **MATCH_WITH_SEMANTIC_ADAPTATION** (Local Poller required) |
| **Delta OI (4h)** | Computed from 5m OI | 4h lag | Computed | 4h lag | **MATCH_WITH_SEMANTIC_ADAPTATION** |
| **14d OI Percentile** | Computed from 5m OI | 14d rolling | Computed | 14d rolling | **MATCH_WITH_SEMANTIC_ADAPTATION** |

## 2. BingX Open Interest Semantics Audit (Critical)
- **Binance Research OI Semantics:** Represents the total outstanding derivative contracts at the `create_time`. Notional value is calculated based on the contract price.
- **BingX Live OI Semantics:** BingX `openInterest` represents the total outstanding contracts. 
- **Equivalence Analysis:** 
  - **Units:** Both report in base asset (e.g., BTC for BTC-USDT). **MATCH**.
  - **Notional:** Both derive notional dynamically. **MATCH**.
  - **Update Frequency:** Binance provides a 5m historical interval snapshot. BingX provides instantaneous REST state.
  - **Timestamp Meaning:** BingX does not return a historical timestamp for its REST OI snapshot. It represents `time_of_request`. 
- **Status:** **MATCH_WITH_SEMANTIC_ADAPTATION**. BingX OI is structurally equivalent in units and meaning, but the temporal mechanism (REST snapshots vs historical aggregates) necessitates a rigorous local institutional archival layer. No unit conversions are required.

## 3. Exact Warmup Requirement Calculation
To compute `S3_CONDITIONAL_VOL_V1` live, the system requires sufficient history for all components.

- **14d ATR & 90d Historical Percentile:** Requires $90 + 14 = 104$ days of Kline history. (Can be immediately backfilled via BingX REST Kline history).
- **14d Funding Z-Score:** Requires 14 days of 8h funding rates. (Can be backfilled via BingX REST funding history).
- **14d OI Percentile of 4h Delta OI:** Requires $14 \text{ days} + 4 \text{ hours}$ of 5m OI snapshots. 
  - *Because BingX does not provide historical OI via REST, this data must be locally polled.*
- **LIVE_WARMUP_REQUIRED:** **14 days + 4 hours** of active local OI polling.

## 4. Signal Gating & Staleness Policy
A live S3 signal evaluates strictly to `UNAVAILABLE` if *any* required input is missing, stale, or lacks sufficient warmup history.
- **Price Freshness:** Max 1 minute old.
- **Funding Freshness:** Max 8 hours + 1 minute (accounting for rollover jitter).
- **OI Freshness:** `STALENESS_CUTOFF = 60 minutes`. If the local institutional archive has not recorded a successful OI poll within 60 minutes, the OI metric explicitly transitions to `UNAVAILABLE`, immediately masking the S3 signal. No synthetic approximation is permitted.
