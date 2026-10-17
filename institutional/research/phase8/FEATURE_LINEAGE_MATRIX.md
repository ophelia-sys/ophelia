# FEATURE LINEAGE MATRIX

## GROUP A — PRICE & VOLATILITY (Baseline)
- **OHLCV:** Base candles (1m, 5m).
- **Realized Volatility:** Standard deviation of log returns.
- **ATR:** True range average for stop/target scaling.
- **Parkinson / Garman-Klass:** High-low and open-close volatility estimators.
- **Trend Distance:** Distance to VWAP / EMAs.
- **Kaufman Efficiency Ratio:** Noise vs direction.
- **Robust Momentum:** Z-scored rate of change.

## GROUP B — ORDER FLOW
- **CVD (Cumulative Volume Delta):** Net taker volume.
- **TVI (Taker Volume Imbalance):** Normalized buy vs sell volume.
- **CVD Acceleration:** Second derivative of CVD.
- **Price/CVD Divergence:** Disconnects between price trend and flow trend.

## GROUP C — VOLUME PROFILE
*(Only included if computationally viable on VPS without massive tick data overhead)*
- **POC Distance:** Price relative to Point of Control.
- **VAH / VAL Distance:** Position relative to Value Area High/Low.

## GROUP D — DERIVATIVES
- **Open Interest:** Absolute aggregate OI.
- **ΔOI (Change in OI):** Over specific windows (e.g., 4h).
- **Funding Rate & Z-Score:** Cost of holding perpetual positions.
- **Basis:** Futures premium over spot (if supported).

## GROUP E — MICROSTRUCTURE
- **Spread / Relative Spread:** Cost of market taking.
- **Queue Imbalance:** Top-of-book bid vs ask sizes.
- **Depth Imbalance:** Deeper book liquidity asymmetry.
- **Microprice Skew:** Volume-weighted mid price vs geometric mid.
- **Book Slope:** Density of liquidity deeper in the book.
- **Visible-Book Price Impact:** Simulated market order slippage.

### Strict Non-Mapping Rules
- `depth_imbalance` -> NEVER mapped to OFI.
- `queue_imbalance` -> NEVER mapped to OFI.
- `CVD` -> NEVER mapped to OFI.
- `Canonical OFI` -> **REMAINS UNAVAILABLE**.
