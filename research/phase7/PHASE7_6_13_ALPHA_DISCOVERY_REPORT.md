# PHASE 7.6.13 ALPHA DISCOVERY REPORT

## 1. Current Phase 7 Ledger

| Feature / Hypothesis | Focus Area | Status | Data Dependency |
|---|---|---|---|
| **S1_TSMOM** | Time-Series Momentum | REJECTED | Price |
| **S2_RESIDUAL_MOM** | Beta-Adjusted Momentum | REJECTED | Price |
| **S3_COND_VOL** | Leverage Crowding Reversal | **FRAGILE_VALIDATED_ALPHA_CANDIDATE** | Open Interest, Price |
| **S4_TAKER_FLOW** | Micro-structure Flow Exhaustion | REJECTED | Taker Buy/Sell Volume |
| **S4.1_FLOW_PRICE** | Flow-Price Dislocation Proxy | REJECTED | Taker Buy/Sell Volume, Price |

**Surviving Candidates:** 1 (S3, currently in Live Shadow Validation).
**Available Data Artifacts:**
- `binance_um_universe_1m_v2.parquet` (OHLCV, Taker Volume)
- `research_oi_5m.parquet` (Open Interest)
- `research_funding.parquet` (Funding Rates)
- `universe_artifact_v1.parquet` (Membership)

---

## 2. Candidate Economic Mechanisms (Distinct from S1-S4)

We investigated the currently available data to identify fundamentally new mechanisms.

### Candidate A: Cross-Sectional Dispersion / Relative Value Reversal
- **Economic Hypothesis:** Cryptocurrencies share a massive common market beta. Extreme short-term idiosyncratic deviations (an asset moving violently while the rest of the market does not) are frequently driven by liquidity voids or retail speculative cascades rather than fundamental re-pricing. These relative dislocations revert as arbitrageurs and market makers reposition.
- **Available Raw Data:** Canonical 1m OHLCV price dataset.
- **Exact Measurable Variables:** 
  - `R_W(i)`: Return of asset *i* over window *W*.
  - `R_W(mkt)`: Cross-sectional median (or equal-weight mean) return over window *W*.
  - `Idio_R_W(i)` = `R_W(i) - R_W(mkt)`.
  - Signal condition: `Idio_R_W(i)` > Threshold (Short) / < -Threshold (Long).
- **Expected Horizon:** 4h to 24h.
- **Likely Execution Friction:** Moderate to low. The longer holding period (hours/days vs minutes) easily absorbs the canonical 12 bps friction.
- **Redundancy Analysis:** Completely orthogonal to S3. S3 trades time-series absolute OI extremes. Candidate A trades cross-sectional price relative-value. A market-neutral portfolio here would have near-zero correlation with S3.

### Candidate B: Cross-Sectional OI Crowding
- **Economic Hypothesis:** Instead of comparing an asset's OI against its own trailing 14-day history (S3), we compare its OI share against the entire market. If an altcoin suddenly absorbs 15% of all Binance UM Open Interest (up from a baseline of 2%), it is universally crowded and vulnerable to a systemic liquidation cascade.
- **Available Raw Data:** 5m OI dataset.
- **Exact Measurable Variables:**
  - `OI_Share(i)` = `OI_Value(i) / Sum(OI_Value(all_assets))`.
  - Signal condition: `OI_Share(i)` > `Rolling_Mean(OI_Share(i)) + Z * Std`.
- **Expected Horizon:** 12h to 48h.
- **Likely Execution Friction:** Low (similar holding period to S3).
- **Redundancy Analysis:** High risk of redundancy. While the normalization vector is cross-sectional rather than time-series, it isolates exactly the same underlying vulnerability as S3 (over-leveraged altcoins).

### Candidate C: Volume Capitulation / Volatility State Transition
- **Economic Hypothesis:** Extreme volume spikes following a sustained trend indicate capitulation (exhaustion of the last marginal buyer/seller). If followed immediately by a collapse in volatility (state transition), it signals the trend is dead and a mean-reversion is highly probable.
- **Available Raw Data:** Canonical 1m OHLCV.
- **Exact Measurable Variables:**
  - `Trend_W`: Directional price move over 24h.
  - `Vol_Shock`: Current 15m volume / 24h average 15m volume > Theta.
  - `Volat_Collapse`: Next 15m ATR < previous 15m ATR.
- **Expected Horizon:** 1h to 4h.
- **Likely Execution Friction:** High. Reverting immediately after extreme volume spikes involves trading into widening spreads and high slippage environments.
- **Redundancy Analysis:** Conceptually distinct, but heavily reliant on finding perfect micro-structure state transitions, overlapping somewhat with the failures of S4/S4.1.

---

## 3. Recommended S5 Hypothesis

**Selection:** `CANDIDATE A: CROSS-SECTIONAL DISPERSION / RELATIVE VALUE REVERSAL`

**Feature ID:** `S5_CS_DISPERSION_V1`

### Exact Reason for Selection:
1. **Unambiguous Distinctiveness:** S3 is a time-series, directional, leverage-based strategy. S5 will be a cross-sectional, market-neutral, price-based strategy. They share zero structural mechanics.
2. **Data Sufficiency:** The price dataset (`binance_um_universe_1m_v2.parquet`) is the most robust, deeply-populated, and clean artifact we possess.
3. **Execution Realism:** By extending the evaluation window out of the micro-structure noise (e.g., 4h-24h horizons) and focusing on large relative mispricings, the signal-to-noise ratio easily overcomes the 12 bps execution cost, bypassing the event-starvation and cost-collapse seen in S4.1.
4. **Portfolio Theory Value:** A validated market-neutral relative-value strategy provides the highest possible incremental OOS portfolio value when paired with a directional strategy like S3, maximizing the Sharpe ratio through non-correlation.

### Rejected Candidates
- **Candidate B (Cross-Sectional OI Crowding):** Rejected due to high mechanistic redundancy with the already-validated S3.
- **Candidate C (Volume Capitulation):** Rejected due to the high likelihood of insurmountable slippage friction (trading exactly at the point of maximum market chaos).

---

## 4. Next Steps
Awaiting authorization to define the exact DEV/OOS methodology and feature formulation for `S5_CS_DISPERSION_V1`. 

*S3 live shadow telemetry continues to run uninterrupted.*
*Live Execution remains DISABLED.*
