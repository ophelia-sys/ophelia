# OPHELIA — PHASE 13 EVENT UNIVERSE REPORT

**Document:** `docs/PHASE_13_EVENT_UNIVERSE_REPORT.md`  
**Layer:** Market Microstructure Discovery  
**Universe:** BTCUSDT, ETHUSDT, SOLUSDT (12 Months 2023, 423,130 Events, 3.38M Outcomes)  
**Safety Invariants:** `TRADING_AUTHORITY = FALSE`, `EXECUTION_MODE = SHADOW`  

---

## 1. PURPOSE & METHODOLOGY

Previous research in Phases 10–12 restricted its universe exclusively to `ENTRY_READY` 5m retest candidates. Phase 13 fundamentally expands this universe to **all causally observable closed bars/events** across Binance market microstructure, establishing baseline frequencies, unconditional base rates, and multi-horizon forward behavior.

Events were detected strictly on confirmed closed 5m bars, utilizing causal historical indicators (VWAP, ATR, CVD `delta_v`, RVOL, 4H EMA trend, 15m/1H swing fractals) with zero future information leakage.

---

## 2. EVENT CATALOG & BASE RATES

| Event Class | Definition / Selection Rule | Sample Size (N) | Base Rate (% of 5m bars) | Directional Bias |
| :--- | :--- | :---: | :---: | :---: |
| **`MOMENTUM_DISPLACEMENT`** | Closed 5m body $|C - O| \ge 1.5 \times \text{ATR}_{14}$ | 9,998 | 3.17% | 51.2% Long / 48.8% Short |
| **`RVOL_EXPANSION`** | Volume $\ge 2.0 \times \text{SMA}(\text{Vol}, 20)$ | 27,156 | 8.61% | 50.8% Long / 49.2% Short |
| **`CVD_ACCELERATION`** | Rolling 1h CVD $z$-score $|Z_{\text{CVD}}| \ge 2.0$ | 20,991 | 6.65% | 52.1% Long / 47.9% Short |
| **`VWAP_DEVIATION`** | $|P - \text{VWAP}| \ge 1.5 \times \sigma_{\text{VWAP}}$ | 309,091 | 98.01% | 50.2% Long / 49.8% Short |
| **`VWAP_RECLAIM`** | Prior close $< \text{VWAP}$ and current close $> \text{VWAP}$ (or inverse) | 21,167 | 6.71% | 50.1% Long / 49.9% Short |
| **`LIQUIDITY_SWEEP_SFP`** | 15m wick breaches swing by $\ge 0.1\%$ then closes back inside | 2,630 | 0.83% | 49.4% Long / 50.6% Short |
| **`VALUE_AREA_BOUNDARY`** | Test of 24h rolling 30th/70th quantile and rejection | 25,086 | 7.95% | 50.0% Long / 50.0% Short |
| **`RANGE_EXPANSION`** | Compression ($\text{ATR}_{14}/\text{ATR}_{50} \le 0.75$) + 20-bar breakout | 1,372 | 0.44% | 51.5% Long / 48.5% Short |
| **`HTF_ALIGNED_DISPLACEMENT`** | Displacement $\ge 1.5$ ATR in direction of 4H EMA20 > EMA50 | 4,669 | 1.48% | 54.2% Long / 45.8% Short |
| **`ORDER_FLOW_VWAP_CONFLUENCE`** | VWAP Reclaim with CVD acceleration $Z_{\text{CVD}} \ge 1.5$ | 970 | 0.31% | 51.8% Long / 48.2% Short |

---

## 3. FORWARD TRAJECTORY HORIZONS (1m TO 120m)

For each event, we measured causal trajectory progression across 8 horizons (1m, 3m, 5m, 10m, 15m, 30m, 60m, 120m):

### Key Observations Across Horizons

1. **Immediate Mean Reversion on Breakouts:**
   - For `MOMENTUM_DISPLACEMENT` and `RVOL_EXPANSION`, the 1m to 5m forward returns are immediately negative (mean $-0.025\%$ to $-0.038\%$).
   - High-volume displacement candles represent liquidity exhaustion points rather than fresh trend initiations. Entering at the close of an expansion candle consistently buys the top/sells the bottom of local microstructure noise.
2. **Time to MFE vs Time to MAE:**
   - Across momentum events (`MOMENTUM_DISPLACEMENT`, `CVD_ACCELERATION`), median time to MFE is **15 to 18 minutes**, whereas median time to MAE is **26 to 28 minutes**.
   - Favorable momentum moves happen early; if a setup does not move favorably within 15–20 minutes, adverse drift typically dominates thereafter.
3. **VWAP Deviation Dynamics:**
   - At extreme VWAP distance ($|Z| \ge 1.5$), win rate for mean reversion is **52.79%** at 60m. However, the average magnitude of return ($-0.007\%$) is too small to cover 7.0–9.1 bps friction.

---

## 4. BASELINE BENCHMARK COMPARISONS

In accordance with Section 13, all candidate event classes were benchmarked against four simple baselines:

| Strategy / Baseline | Description | 60m Win Rate | Mean Directional Return | Realized Net R (Fee+Slip) |
| :--- | :--- | :---: | :---: | :---: |
| **`PERSISTENCE_BASELINE`** | Prior 5m candle direction continuation | 48.20% | -0.011% | -0.620 R |
| **`VWAP_MEAN_REVERSION`** | Fade distance from rolling session VWAP | 52.79% | -0.007% | -0.587 R |
| **`MOMENTUM_BASELINE`** | 15m return momentum continuation | 46.10% | -0.018% | -0.685 R |
| **`CVD_ACCELERATION`** | Microstructure order flow imbalance ($Z \ge 2$) | 44.70% | -0.013% | -0.662 R |
| **`HTF_ALIGNED_DISP`** | 5m Displacement $\times$ 4H Trend Alignment | 43.37% | +0.012% | -0.612 R |

### Scientific Verdict

$$\mathbf{Complex\ Microstructure\ \approx\ Simple\ Baselines}$$

After realistic BingX execution costs (7.0 bps fee + 2.1 bps slippage), complex order flow variables (CVD, OFI, RVOL) do not outperform naive baselines. None of the tested microstructure features generate positive net alpha.
