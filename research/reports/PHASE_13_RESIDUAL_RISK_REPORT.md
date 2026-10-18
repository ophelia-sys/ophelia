# PHASE 13 RESIDUAL RISK & PRODUCTION SAFETY BOUNDARY REPORT

## 1. Safety Status & Contract Invariants

Throughout all Phase 13 remediation, verification, and alpha-discovery research, the immutable safety contract has remained strictly enforced:

```
TRADING_AUTHORITY=False
EXECUTION_MODE=SHADOW
LIVE_ORDERS_FORBIDDEN=True
```

- **Production Checkout**: `/opt/ophelia` on VPS (`15.235.193.47`) is **completely untouched** (HEAD remains `0a764fd23dd1b24070b3d09c24f54e698a3e4ae6`).
- **Production Services**: `ophelia-api`, `ophelia-control`, and related services were never restarted or reconfigured.
- **Zero Real Orders**: No orders, test transactions, or exchange credential authorizations were executed.

---

## 2. Quantitative & Methodological Residual Risks

### Risk 1: Execution Friction Scaling on Low-Nominal Moves
- **Finding**: On crypto futures, a standard VIP0 taker fee (0.04% entry + 0.04% exit = 0.08% or 8.0 bps) plus modest adverse slippage (0.01% - 0.02% per leg) totals 9.1 to 12.0 bps round-trip.
- **Implication**: Any signal generating gross expectancy below 15–20 bps is unviable for active taker execution. For instance, `HTF_ALIGNED_DISPLACEMENT` produced +5.83 bps gross return on TEST, which becomes -3.27 bps net after 9.1 bps friction.
- **Remediation Requirement**: Future strategy engineering must either:
  1. Target higher-timeframe horizons (4H/1D swings) where average profit targets exceed 150–300 bps, reducing friction to <10% of gross move.
  2. Implement passive maker entry models with strict execution queues, subject to adverse selection modeling.

### Risk 2: Adverse Selection in Passive Execution
- If maker execution is assumed (0.02% maker fee), limit orders that fill during momentum or breakout events suffer adverse selection (they fill preferentially when the market trades through them and continues in the adverse direction).
- Backtests assuming 100% maker fill rates without order-book queue simulation will significantly overestimate performance.

### Risk 3: Structural Stop Cluster Resumption (Class B Loss)
- In the Stop-Room analysis, 11.7% to 12.3% of 5m and 15m structural swing stops experienced Class B resumption (the price swept the swing high/low by <0.1% to trigger the stop, then reversed and reached the full target).
- Using rigid structural swing points without liquidity buffer or volatility-adjusted offset leads to unnecessary realized losses.

### Risk 4: Sample Period & Macro Regime Concentration
- The canonical 2023 dataset contains specific macro regimes (bear market consolidation in Q1–Q3, aggressive upward expansion in Q4).
- The confirmatory TEST partition (October 16 – December 31, 2023) coincided with strong secular crypto rallies (BTC +60%, SOL +300%). Directional short setups during this window experienced systematic headwinds.

---

## 3. Architecture & Code Integrity Residual Risks

1. **Parquet Projection Safety**: All future data loaders must explicitly include `quote_volume` and `taker_buy_volume` in their read projection to avoid fallback to `close * volume`.
2. **Timezone Awareness**: The canonical parquet stores millisecond timestamps (`int64`). All DataFrame indices must be cast to `pd.DatetimeIndex` with `utc=True` or `unit="ms"` before calling resampling or calendar-based indicators.
3. **Android Client Independence**: The `android-app/` codebase interacts only with backend REST endpoints (`/api/v1/...`). It does not contain research or signal-generation code and requires zero modifications for Phase 13.
