# PHASE 5.3 REPORT: Economic Event Prediction and Microstructure Edge Audit

## 1. Executive Summary

Phase 5.3 transitioned the Ophelia research pipeline from unconstrained directional prediction (target_X) to deterministic event-driven classification using Triple-Barrier Labeling (Target, Stop, Timeout). Furthermore, we audited and integrated historical microstructure features to evaluate their incremental economic value.

### Final Verdict: REJECTED FOR PRODUCTION
- **Statistical Edge**: YES (Validation AUC ~0.5700)
- **Economic Edge**: NO (Net expected value remains negative under all realistic cost assumptions)
- **Production Eligibility**: NO

Despite robust statistical significance in predicting Target-Hit before Stop-Hit, the probability skew is insufficient to overcome the 12 bps execution friction in the baseline scenario. The introduction of microstructure features (such as `taker_buy_ratio` and `delta_oi_z`) failed to provide meaningful incremental economic value.

---

## 2. OFI and Microstructure Provenance Audit

### 2.1 Canonical Order Flow Imbalance (OFI)
- **Status**: **UNAVAILABLE / UNVERIFIED**
- **Provenance**: The historical K-line `v2_fixed_timestamp` parquet dataset does not contain canonical Level-2 order book snapshots. In the normalization layer (`normalize_parquet.py`), the `ofi` field is explicitly zeroed out (`np.nan`). 
- **Constraint Enforcement**: Canonical OFI has been completely removed from this phase's experiments.

### 2.2 OFI Proxy (`ofi_proxy_z`)
- **Status**: **AVAILABLE FOR RESEARCH ONLY**
- **Formula**: `(delta_v - rolling_mean(delta_v, 60)) / rolling_std(delta_v, 60)` where `delta_v = 2 * taker_buy_volume - total_volume`.
- **Constraint Enforcement**: A static codebase search confirms no alias exists that conflates `ofi_proxy_z` with `ofi`. This metric must not influence production Math engines.

### 2.3 Other Verified Microstructure Features
- **`taker_buy_volume`**: Verified deterministic mapping from Binance historical public K-lines.
- **`sum_open_interest`**: Verified via causal backward `merge_asof` from discrete 5-minute Binance API metrics snapshots.

---

## 3. Barrier Threshold Discovery

A grid search was executed over a pre-declared candidate set on the Development partition (Jan 2022 - Mar 2023):
- Targets: +10, +15, +20, +30 bps
- Stops: -10, -15, -20 bps
- Timeouts: 15m, 30m, 60m

**Baseline Outcomes (Unconditional):**
The highest unconditional probability of Target Hit without excessive Timeout was observed in tighter ranges (e.g., +20/-10, +15/-10). We selected **+20 bps TP / -15 bps SL at 60m** for the core ablation, representing a structurally favorable risk/reward ratio that demands a genuine edge to overcome standard market noise.

---

## 4. Ambiguity Policies

We implemented deterministic evaluation for OHLCV bars that penetrated both the Target and the Stop in the same minute:
1. **CONSERVATIVE_EXCLUSION**: Ambiguous events are ignored in EV calculations.
2. **WORST_CASE**: Ambiguous events are immediately booked as `STOP_HIT`.

For a +20/-15 barrier at 60m, ambiguous events constituted less than `0.32%` of the total bars.
Under both policies, the net EV remained practically identical and profoundly negative (approx -10.8 bps net), confirming that the lack of profitability is not an artifact of optimistic ambiguity handling.

---

## 5. Cost Sensitivity Analysis

Holding the ML model (trained on baseline features) constant over the Validation set (Apr 2023 - Jun 2023), we evaluated expected value under varying execution cost assumptions for the Top 10% highest confidence signals:

| Cost (bps) | Net EV (bps) | Gross EV (bps) | P(Net > 0) | Avg Hold (m) |
|------------|--------------|----------------|------------|--------------|
| 6          | -4.81        | 1.19           | 0.4550     | 11.4         |
| 8          | -6.81        | 1.19           | 0.4547     | 11.4         |
| 10         | -8.81        | 1.19           | 0.4545     | 11.4         |
| **12**     | **-10.81**   | **1.19**       | **0.4543** | **11.4**     |
| 15         | -13.81       | 1.19           | 0.4537     | 11.4         |
| 20         | -18.81       | 1.19           | 0.0070     | 11.4         |

*(Results shown under WORST_CASE ambiguity policy)*

**Conclusion**: The model possesses a very slight gross positive expected value (+1.19 bps). However, the break-even execution cost is roughly `1.19 bps`, which is structurally impossible for a taker strategy on BingX.

---

## 6. Microstructure Ablation Results

We ran an ablation study to determine if the local microstructure features could improve the expected net value (using a fixed 12 bps cost). 

| Model Configuration                   | Val AUC | Net EV (12 bps cost) |
|---------------------------------------|---------|----------------------|
| BASELINE EVENT MODEL                  | 0.5699  | -10.81 bps           |
| BASELINE + taker_buy_ratio            | 0.5700  | -10.70 bps           |
| BASELINE + ofi_proxy_z                | 0.5699  | -10.81 bps           |
| BASELINE + delta_oi_z                 | 0.5700  | -10.85 bps           |
| BASELINE + ALL MICROSTRUCTURE         | 0.5699  | -10.76 bps           |

**Conclusion**: The inclusion of `taker_buy_ratio`, `ofi_proxy_z`, and `delta_oi_z` provides virtually zero incremental predictive power or economic value over the baseline (momentum, volatility, trend, volume).

---

## 7. Locked OOS Protection
Per the strict protocol, the newly declared OOS window (July 2023 - Dec 2023) was completely untouched during this phase. Because the models failed to demonstrate economic viability in the validation window, there is no justification for proceeding to an OOS lock validation.

## 8. Final Research Directive
Because the models cannot overcome realistic execution friction even with advanced event labeling and verified microstructure proxies, Phase 5.3 strictly prohibits deploying these models or features to the live `TradingEngine`. The mathematical requirements of `EVIDENCE > SOPHISTICATION` demand this rejection.
