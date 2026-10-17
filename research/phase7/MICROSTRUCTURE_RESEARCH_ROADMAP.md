# Microstructure Research Roadmap (Phase 7.3+)

This document defines the strict, linear experimental framework required before any new high-frequency L2 feature can be considered a Production Candidate.

## 1. Feature Role Mapping
Features must be evaluated strictly against their designated roles.

| Feature | Data Required | Role | Status |
|---|---|---|---|
| True Queue Imbalance | `bookTicker` / `T_DEPTH` | BOTH | UNTESTED |
| Microprice | `bookTicker` | EXECUTION | UNTESTED |
| Depth Imbalance | `T_DEPTH` | BOTH | UNTESTED |
| Book Slope (Bid/Ask) | `T_DEPTH` | ALPHA | UNTESTED |
| Book Concentration | `T_DEPTH` | EXECUTION | UNTESTED |
| Visible Impact | `T_DEPTH` | EXECUTION | UNTESTED |
| OFI (Strict) | `T_DEPTH` | ALPHA | UNTESTED |
| Liquidity Add/Withdraw | `T_DEPTH` | ALPHA | UNTESTED |
| Trade Aggressiveness Proxy| `aggTrades` | EXECUTION | VALIDATED (Proxy) |

## 2. Horizon Framework
Microstructure features decay rapidly. We must evaluate them across multiple short horizons ($h$) rather than assuming 15m viability.

**Short-Horizon Targets:**
- 1s, 5s, 10s, 30s, 1m, 3m, 5m

**Slow-Alpha Target:**
- 15m Volatility-Adjusted (Existing Phase 6/7 baseline)

## 3. Experimental Pipeline

The following pipeline must be executed for any L2 feature:

1. **RAW L2:** Acquire a 1-month high-quality slice of `T_DEPTH` + `S_DEPTH` for BTCUSDT (e.g., via Tardis/Databento).
2. **BOOK RECONSTRUCTION:** Build a C++/Cython/Polars book builder that enforces sequence ID checks.
3. **VALIDATED EVENT STREAM:** Emit a sanitized tick stream (or 100ms sampled stream) with gaps flagged as `NaN`.
4. **MICROSTRUCTURE FEATURES:** Compute OFI, Slope, True Imbalance strictly on valid sequences.
5. **SHORT-HORIZON LABELS:** Generate the $h$-sec forward returns.
6. **BASELINE:** Evaluate predictability (IC, Rank IC, univariate regression t-stats).
7. **FEATURE ABLATION:** Combine with existing slow-alpha baseline (e.g. Phase 6 baseline) to prove *incremental* value.
8. **OOS:** Validate on holdout data.
9. **COST / EXECUTION TEST:** Measure expected return against 10-12 bps taker costs (for Alpha) or against passive limit slippage (for Execution).
10. **PROMOTION GATES:** Strict rejection if cost-adjusted expectancy is negative or incrementality is zero.

Do not implement this pipeline in Phase 7.2. This serves as the blueprint for subsequent L2 efforts.
