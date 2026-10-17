# DATA REQUIREMENTS

## 1. Context and Execution Venue
- **Execution Venue:** BingX Perpetual Futures. Execution-sensitive features (spread, order-book imbalance, microprice, visible impact) MUST be sourced exclusively from BingX.
- **Research Source:** Binance futures data may be used strictly for historical volume/price regimes or cross-exchange lag features, pending transferability tests.

## 2. Horizon and Granularity Requirements
The system requires multi-horizon historical data to test Triple-Barrier targets at:
- `15m`
- `30m`
- `1h`
- `4h`

Base resolution required: **1m OHLCV** (to accurately resolve barrier touches within larger horizons).
Assets: `BTC-USDT`, `ETH-USDT`, `SOL-USDT`, `XRP-USDT`, `BNB-USDT`.

## 3. Dataset Size and Empirical Feasibility
The minimum historical period required cannot be hard-coded to arbitrary values (e.g., 2 years). It must be determined empirically by investigating:
- Number of labels
- Class balance
- Overlapping labels
- Effective sample size
- Autocorrelation
- Volatility regime diversity (bull/bear/range regimes)
- Number of independent events
- Number of OOS observations
- Number of trades after filtering

Do not download massive datasets before determining the actual data requirement based on the factors above.

At ~50 columns (features), historical data easily fits in RAM as Parquet/Pandas DataFrame for standard model training.
- **VPS Feasibility:** A standard VPS can handle inference and periodic lightweight training. Before deploying complex models, calculate expected storage, RAM, CPU usage, inference latency, training duration, and database size.

## 4. Continuous Learning Requirements
Instead of retraining every candle, the system will append mature outcomes to an SQLite/Parquet dataset. 
Retraining triggers (e.g., weekly or when Brier score degrades) will occur asynchronously via a shadow challenger model.
