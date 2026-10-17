# PHASE 8.1 COST MODEL AUDIT

## 1. Execution Timing
The backtest specifically models `t+1` entry for signals generated at `t`. Same-bar ambiguity is treated pessimistically (stop hit before target).

## 2. Research Scenario Costs
Assumption: 4 bps taker + 2 bps slippage (12 bps round trip).
- **BTCUSDT Gross Return**: 0.0058%
- **BTCUSDT Net Return**: -0.1142%

The negative net return proves that even the marginal non-significant edge is immediately swallowed by execution costs.
