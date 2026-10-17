# PHASE 5.3.2 CVD PRODUCTION ARCHITECTURE

This document specifies the production architecture for the Phase 5.3 CVD Live Aggregation System.

## 1. COMPONENT: `LiveCVDEngine`
Located at: `institutional/cvd/live_engine.py`

### Design Philosophy
The engine strictly enforces **Read-Only / Execution-Isolation**. It operates solely as a consumer of trade streams and a producer of predictive probabilities. It maintains no dependency on `TradingEngine` or `DecisionEngine`.

### Data Acquisition & Aggregation
- **Input Stream**: Consumes `TradeEvent` dataclass instances.
- **Deduplication**: Maintains a `seen_trade_ids` set to ensure that rapid webhook retries or overlapping websocket frames do not double-count volume.
- **Aggregation Strategy**: 
  - Trades are buffered until a probability evaluation is requested (`get_features(T_decision)`).
  - T_decision strictly aligns to 5-minute boundaries (e.g. `1640995500000`).
  - Upon request, trades are sorted chronologically. All trades $< T_{decision}$ are bucketed into integer 5-minute bounded blocks $[T, T+5m)$.
  - Any empty blocks in the temporal sequence are explicitly initialized with 0.0 volume to correctly penalize momentum indicators if the market goes silent.

### History Buffer
To support the `cvd_zscore` calculations (which require a rolling 288-period 5-minute standard deviation), the engine maintains a bounded array `history_blocks` with a strict maximum capacity of 300 elements (288 blocks for z-score memory + 12 blocks for 1h acceleration).

## 2. CONTRACT: `CVDFeatureVector`
To guarantee strict type safety between the pipeline and the model, a frozen dataclass is implemented.

```python
@dataclass
class CVDFeatureVector:
    cvd_delta_5m: float
    cvd_delta_15m: float
    ...
    cvd_acceleration_1h: float
    calculated_at: int
    source_latest_trade_time: int
    feature_age_ms: int
    data_quality: DataQuality
```
This forces the production evaluation layer to fail compilation/execution if features drift, change names, or break order.

## 3. MODEL ARTIFACT: `PHASE5_3_MODEL_G_FROZEN.pkl`
A dictionary containing the `StandardScaler`, `LogisticRegression` classifier, and expected features list per symbol.
- Features are concatenated safely: Base Features + CVD Features.
- Strict NaNs rejection is enforced matching the Phase 5.3 rules (`valid_df.dropna`). Zero-variance rows gracefully return `None` (no probability generated) instead of failing or implicitly imputing.
