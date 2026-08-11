# Institutional Math Formula Registry

This document formally defines the mathematical calculations used in the Ophelia Institutional Math Engine.

## Microstructure Metrics

### Mid Price
`mid = (best_bid + best_ask) / 2`
- **Units:** USDT
- **Status:** MEASURED

### Absolute Spread
`spread = best_ask - best_bid`
- **Units:** USDT
- **Status:** MEASURED

### Relative Spread
`relative_spread = (best_ask - best_bid) / mid`
- **Units:** Float (can be converted to BPS)
- **Status:** VALIDATED

### Queue Imbalance
`QI = (bid_qty_1 - ask_qty_1) / (bid_qty_1 + ask_qty_1)`
- **Units:** Dimensionless ratio [-1, 1]
- **Status:** MEASURED

### Depth Imbalance (20 Levels)
`DI = (Σ bid_qty - Σ ask_qty) / (Σ bid_qty + Σ ask_qty)`
- **Units:** Dimensionless ratio [-1, 1]
- **Status:** MEASURED
- **Note:** Explicitly NOT Canonical OFI.

### Canonical OFI (Cont-Kukanov-Stoikov)
- **Status:** UNAVAILABLE
- **Note:** Requires Level 3 (Tick-by-tick order placement/cancellation) data which is not available via standard WebSocket streams. Do not hallucinate this metric.

### Microprice
`microprice = (best_bid * ask_qty_1 + best_ask * bid_qty_1) / (bid_qty_1 + ask_qty_1)`
- **Units:** USDT
- **Status:** MEASURED

### Book Slope (USDT/BPS)
OLS Regression of Cumulative Quote Notional against Price Distance in Basis Points.
- **X (Independent):** `|P_i - P_mid| / P_mid * 10000` (Basis Points)
- **Y (Dependent):** `Σ(qty_j * P_j)` (Cumulative Quote Notional in USDT)
- **Units:** USDT / BPS (Dollars of liquidity per basis point of spread)
- **Status:** MEASURED
- **Note:** Explicitly classified as DEFENSIBLE_ENGINEERING_ESTIMATOR. Calculated separately for Bid (`book_slope_bid`) and Ask (`book_slope_ask`).

### Book Concentration
`concentration = Σ(qty_i^2) / (Σ qty_i)^2` (Herfindahl-Hirschman Index approach)
- **Units:** Dimensionless ratio (0, 1]
- **Status:** MEASURED

### Visible Impact (BPS)
Estimates the price impact of a theoretical market order.
- **Units:** Basis Points (BPS)
- **Status:** MEASURED

## Flow Metrics

### Delta CVD (Cumulative Volume Delta)
`CVD = Σ(buy_volume) - Σ(sell_volume)` over a defined window (1m/5m).
- **Units:** Contracts
- **Status:** VALIDATED

### TVI (Trade Volume Imbalance)
`TVI = (buy_volume - sell_volume) / (buy_volume + sell_volume)`
- **Units:** Dimensionless ratio [-1, 1]
- **Status:** MEASURED
