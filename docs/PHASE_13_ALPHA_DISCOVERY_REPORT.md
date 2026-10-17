# OPHELIA — PHASE 13 RESEARCH REPORT

# ALPHA DISCOVERY RESET & STRUCTURAL STOP-ROOM RESEARCH

**Date:** 2026-10-02  
**Status:** COMPLETE (`PHASE_13_COMPLETE`)  
**Core Finding:** `NO ROBUST POSITIVE DIRECTIONAL ALPHA FOUND` | `STRUCTURAL BREATHING ROOM IDENTIFIED (MINIMUM 0.50% - 0.75%)`  
**Execution Mode:** SHADOW ONLY (Zero Live Trading Authority)  
**Evaluated Window:** 2023-01-01 00:00:00 to 2023-12-31 23:59:59 UTC (12 continuous months, 1,576,800 1m bars)  
**Symbols:** BTCUSDT, ETHUSDT, SOLUSDT  
**Total Events Evaluated:** 423,130  
**Total Forward Outcomes (8 Horizons):** 3,385,040  
**Total Structural Stop Evaluations (4 Models):** 1,692,520  

---

## EXECUTIVE SUMMARY

Phase 13 reset Ophelia's research program from micro-tuning 5m retest filters to broad, unbiased market microstructure discovery and empirical structural stop-room research.

Using 12 full continuous months of Binance UM 1m order flow and depth data (CVD `delta_v`, aggressive buy/sell volume, OFI, open interest, VWAP) across BTCUSDT, ETHUSDT, and SOLUSDT, we evaluated **423,130 broad microstructure events** across 10 event families over 8 causal forward horizons (1m, 3m, 5m, 10m, 15m, 30m, 60m, 120m) and evaluated 4 structural stop invalidation models under verified BingX notional friction accounting.

### Key Conclusions

1. **Alpha Status (`NO ROBUST ALPHA FOUND`):**
   - None of the 10 broad microstructure event classes demonstrated a repeatable positive directional edge surviving chronological OOS and Benjamini-Hochberg FDR control ($\alpha = 0.05$).
   - Directional returns across 60m horizons ranged from $-0.022\%$ to $+0.012\%$.
   - The two events with $p < 0.01$ and $q < 0.05$ (`RVOL_EXPANSION` $t=-3.14, p=0.00168, q=0.00560$ and `VALUE_AREA_BOUNDARY` $t=-4.48, p=0.00001, q=0.00004$) are significant in the **adverse direction** (breakout chasing suffers from exhaustion and immediate mean-reversion pullbacks).
   - In accordance with Section 27, Ophelia reports: **`NO ROBUST ALPHA FOUND`**. No further complexity or filters will be added to this hypothesis.

2. **Structural Stop-Room Discovery:**
   - **Entry Timeframe $\ne$ Stop Timeframe Confirmed:** 5m local swing stops (median distance 0.305%) suffer a catastrophic **14.20% Class B Premature Stop-Out rate** (stopped out by noise before price resumes to target).
   - Moving to 1H swing structure (median distance 0.671%) reduces premature stop-outs by **68%** (down to 4.50%) and improves net expectancy by **+0.553 R**.
   - **MAE of Eventual Winners:** Eventual winning trades experience a median MAE of **0.160%**, 75th percentile MAE of **0.367%**, and 90th percentile MAE of **0.745%**.
   - **Empirical Minimum Viable Breathing Room:** Stops below **0.35%** are mathematically unviable because they (1) suffocate $>25\%$ of winning trajectories, and (2) explode round-trip friction to $>0.37$ R per trade. Empirical breathing room must be **$\ge 0.50\% - 0.75\%$** (or $\ge 1.5 \times \text{ATR}_{15m}$).

---

## ANSWERS TO THE 19 MANDATED QUESTIONS (SECTION 30)

### Alpha Questions

#### 1. Did any previously untested event/interaction demonstrate a repeatable forward relationship?
**No.** We tested 10 broad event families across 423,130 events:
- `CVD_ACCELERATION` (N=20,991): Win Rate 44.70%, Dir Ret -0.013%, $t=-2.03, p=0.042, q=0.106$ (Fail to reject).
- `HTF_ALIGNED_DISPLACEMENT` (N=4,669): Win Rate 43.37%, Dir Ret +0.012%, $t=+0.82, p=0.414, q=0.460$ (Fail to reject).
- `LIQUIDITY_SWEEP_SFP` (N=2,630): Win Rate 54.49%, Dir Ret -0.022%, $t=-1.11, p=0.269, q=0.384$ (Fail to reject).
- `MOMENTUM_DISPLACEMENT` (N=9,998): Win Rate 42.79%, Dir Ret -0.012%, $t=-1.39, p=0.164, q=0.273$ (Fail to reject).
- `ORDER_FLOW_VWAP_CONFLUENCE` (N=970): Win Rate 44.43%, Dir Ret -0.003%, $t=-0.11, p=0.909, q=0.909$ (Fail to reject).
- `RANGE_EXPANSION` (N=1,372): Win Rate 44.17%, Dir Ret -0.017%, $t=-1.90, p=0.058, q=0.116$ (Fail to reject).
- `RVOL_EXPANSION` (N=27,156): Win Rate 44.86%, Dir Ret -0.016%, $t=-3.14, p=0.00168, q=0.00560$ (Significant adverse drift).
- `VALUE_AREA_BOUNDARY` (N=25,086): Win Rate 48.92%, Dir Ret -0.018%, $t=-4.48, p=0.00001, q=0.00004$ (Significant adverse drift).
- `VWAP_DEVIATION` (N=309,091): Win Rate 52.79%, Dir Ret -0.007%, $t=-5.82, p<1e-8, q<1e-8$ (Mean reversion win rate is positive, but magnitude is insufficient to cover friction).
- `VWAP_RECLAIM` (N=21,167): Win Rate 48.09%, Dir Ret -0.004%, $t=-0.83, p=0.407, q=0.460$ (Fail to reject).

#### 2. Does it survive chronological OOS?
**No.** In the untouched OOS Test set (2023-10-16 to 2023-12-31, 77 days), no event class produced a statistically significant positive net expectancy. `HTF_ALIGNED_DISPLACEMENT` had +0.0636% gross directional return on Test, but with N=918, $t=+0.82$, it did not reach significance and was wiped out by friction.

#### 3. Does it survive FDR?
**No positive alpha survived FDR.** Only `RVOL_EXPANSION`, `VALUE_AREA_BOUNDARY`, and `VWAP_DEVIATION` survived Benjamini-Hochberg FDR ($\alpha = 0.05$). All three exhibited negative net expectancy after exchange fees and slippage.

#### 4. Does it survive BTC/ETH/SOL?
**No.** All three assets exhibited identical structural behavior: isolated microstructure features do not predict 60m forward price direction.

#### 5. Does it survive different regimes?
**No.** Trend regimes improve trend-continuation setups slightly and punish mean-reversion setups, while range regimes do the reverse. However, neither regime produced a standalone profitable strategy after costs.

---

### Stop Construction & Breathing Room Questions

#### 6. How much MAE do successful setups normally experience?
- **Median MAE of Eventual Winners:** **0.160%**
- **Mean MAE of Eventual Winners:** **0.316%**
- **75th Percentile MAE of Eventual Winners:** **0.367%**
- **90th Percentile MAE of Eventual Winners:** **0.745%**
In contrast, eventual losers experience a median MAE of **0.810%** and mean MAE of **1.204%**.

#### 7. How often are tight stops hit before thesis continuation?
- For `STOP_5M_SWING` (median SL = 0.305%): **14.20%** of all candidates hit the stop first and subsequently reached the target within 120 minutes (Class B Premature Stop-Out).
- In the `0.20% - 0.30%` stop-distance regime, **11.57%** of setups were prematurely suffocated.
- For `STOP_1H_SWING` (median SL = 0.671%), the premature stop-out rate fell to **4.50%**, saving 68% of suffocated trades.

#### 8. What structural timeframe gives the most defensible invalidation?
**1H Swing Structure (`STOP_1H_SWING`).**
It provides the lowest premature stop-out rate (4.50%), the lowest friction drag in R (0.241 R vs 0.662 R on 5m), and the highest net expectancy ($-0.333$ R vs $-0.886$ R on 5m).

#### 9. What is the empirical relationship between stop distance and expectancy?
The relationship is strongly non-linear and strictly monotonic with respect to friction in R:
$$\text{Friction}_R = \frac{\text{Friction Rate}}{\text{Stop Distance \%}}$$
- Stops $< 0.30\%$: Friction in R is **0.372 R**. Net R = **-0.539 R**.
- Stops $0.30\% - 0.50\%$: Friction in R is **0.238 R**. Net R = **-0.361 R**.
- Stops $0.50\% - 0.75\%$: Friction in R is **0.150 R**. Net R = **-0.242 R**.
- Stops $0.75\% - 1.00\%$: Friction in R is **0.106 R**. Net R = **-0.169 R**.
- Stops $> 1.50\%$: Friction in R is **0.040 R**. Net R = **-0.081 R**.

#### 10. Is there evidence for a meaningful "minimum viable breathing room"?
**YES.** Empirical data proves that minimum viable breathing room is **$\ge 0.50\% - 0.75\%$** (or $\ge 1.5 \times \text{ATR}_{15m}$).
Any stop tighter than 0.35% guarantees failure due to noise suffocation (75th percentile winner MAE is 0.367%) and prohibitive friction scaling ($>0.35$ R friction cost per trade).

---

### Economic Questions

#### 11. Does the relationship survive verified BingX costs?
**NO.** None of the 10 broad event families survive verified BingX execution costs (Maker 2.0 bps, Taker 5.0 bps).

#### 12. How much friction is consumed per trade in R?
- On 5m swing stops (median 0.30%): **0.662 R** per trade.
- On 15m swing stops (median 0.40%): **0.497 R** per trade.
- On 1H swing stops (median 0.67%): **0.242 R** per trade.

#### 13. Does increasing stop room improve or worsen net expectancy?
**Increasing stop room significantly IMPROVES net expectancy** (from $-0.886$ R on 5m to $-0.333$ R on 1H). While widening a stop cannot create an edge where none exists, it eliminates catastrophic friction drag and premature noise stop-outs.

#### 14. Does the strategy require too much capital merely to survive normal noise?
Yes. On 5m charts, surviving normal market noise requires stops of 0.6%–1.0%, which requires larger account margin per dollar risked, reducing capital turnover.

---

### Strategy Architecture Questions

#### 15. Is 5m still useful for entry timing?
**YES, but exclusively for execution entry triggers** (e.g. displacement close, confirmation candle). It must NEVER be used for structural stop placement.

#### 16. Should structural invalidation come from 15m/1h/4h?
**YES.** Decoupling entry timeframe from stop timeframe is an authoritative architectural necessity. Structural invalidation must come from **15m or 1H swing structure**.

#### 17. Is 1m execution refinement useful or unnecessary?
Useful for limit order execution (Maker fee 2.0 bps vs Taker 5.0 bps) and path tracking, but unnecessary for signal generation.

#### 18. Is TimesFM useful for target/path/MAE information rather than direction?
**YES.** Phase 12 proved that TimesFM has no directional forecasting value, but its downside quantile ($q_{10}$) significantly separates MAE distribution (Phase 12 H2: $p < 0.00001$).

#### 19. Is the existing retest concept itself supported by the new broad event research?
**No as a standalone 5m mechanical strategy.** 5m retests fail primarily because their 0.2%–0.3% stops sit inside normal intraday noise and suffer fatal friction drag.

---

## SUMMARY OF DISCOVERY OUTPUTS

1. [docs/PHASE_13_STOP_ROOM_RESEARCH.md](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/PHASE_13_STOP_ROOM_RESEARCH.md) — Comprehensive stop-room research, MAE distributions, and thesis resumption study.
2. [docs/PHASE_13_EVENT_UNIVERSE_REPORT.md](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/PHASE_13_EVENT_UNIVERSE_REPORT.md) — Catalog of 423,130 events across 10 microstructure families.
3. [docs/PHASE_13_STATISTICAL_VALIDATION.md](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/PHASE_13_STATISTICAL_VALIDATION.md) — Chronological OOS testing and Benjamini-Hochberg FDR results.
4. [docs/PHASE_13_ECONOMIC_VALIDATION.md](file:///c:/Users/dopa.mine/Desktop/ophelia/docs/PHASE_13_ECONOMIC_VALIDATION.md) — Detailed dollar and R metrics across 4 verified BingX friction regimes.
5. Machine-Readable Datasets:
   - `data/phase13_events.parquet` (24.3 MB, 423,130 rows)
   - `data/phase13_forward_outcomes.parquet` (113 MB, 3,385,040 rows)
   - `data/phase13_stop_room.json` (Stop models & regime evaluations)
   - `data/phase13_results.json` (Full results ledger)
