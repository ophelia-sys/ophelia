# RESEARCH DATA SCHEMA

All historical research datasets must adhere to the following schema. Missing data must be explicitly represented as `NULL` (or `np.nan` in Pandas/Parquet), NEVER as `0`.

## 1. Core Schema (Parquet / DuckDB)

| Column Name | Type | Description |
| :--- | :--- | :--- |
| `timestamp` | `int64` | Unix timestamp in milliseconds (Candle Close) |
| `symbol` | `string` | Asset pair (e.g., "BTC-USDT") |
| `exchange` | `string` | Source exchange (e.g., "BINANCE", "BINGX") |
| `open` | `float64` | Open price |
| `high` | `float64` | High price |
| `low` | `float64` | Low price |
| `close` | `float64` | Close price |
| `volume` | `float64` | Volume (Base asset) |

## 2. Derivative Fields (Nullable)

| Column Name | Type | Description |
| :--- | :--- | :--- |
| `open_interest` | `float64` | Open interest at `timestamp` (`NULL` if unavailable) |
| `funding_rate` | `float64` | Funding rate at `timestamp` (`NULL` if unavailable) |

## 3. Target / Label Fields

| Column Name | Type | Description |
| :--- | :--- | :--- |
| `label_15m` | `int8` | Triple-barrier label: `1`, `-1`, `0`, or `NULL` (Ambiguous) |
| `label_30m` | `int8` | Triple-barrier label: `1`, `-1`, `0`, or `NULL` (Ambiguous) |
| `label_1h` | `int8` | Triple-barrier label: `1`, `-1`, `0`, or `NULL` (Ambiguous) |
| `label_4h` | `int8` | Triple-barrier label: `1`, `-1`, `0`, or `NULL` (Ambiguous) |
| `time_to_barrier_15m` | `int32` | Milliseconds until a barrier was hit |
| `realized_return_15m` | `float64` | Exact return before costs |
| `mfe_15m` | `float64` | Maximum Favorable Excursion |
| `mae_15m` | `float64` | Maximum Adverse Excursion |

## 4. Feature Space
Computed features will append to this schema (e.g., `feature_rv_20`, `feature_mom_z`).
If a feature requires data that is `NULL`, the feature itself must evaluate to `NULL`.
