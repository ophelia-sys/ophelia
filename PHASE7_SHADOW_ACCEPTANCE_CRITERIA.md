# PHASE 7 SHADOW ACCEPTANCE CRITERIA

## 1. Observation Window Requirement
Before any transition to PAPER or LIVE execution is authorized, the system must complete the following minimum observation requirements in Shadow Mode:

- **Minimum Elapsed Time:** 24 hours (1 full daily cycle)
- **Minimum Completed 5m Bars:** 288 continuous decision cycles per symbol
- **Minimum Decisions Logged:** 1,728 total observations (288 x 6 symbols)
- **Minimum LONG_CANDIDATE Events:** At least 5 `LONG_CANDIDATE` occurrences per symbol to verify signal generation threshold execution.

> [!IMPORTANT]
> **Interpretation Warning:** 24-hour Shadow validation is an operational validation window, not a full statistical performance validation. Do NOT claim that 24 hours proves profitability or long-term robustness. The purpose is to validate continuous data ingestion, 5m timing, CVD streaming, feature generation, LightGBM inference, threshold routing, logging, restart recovery, broker isolation, and fail-closed behavior. Do NOT tune the model or threshold using the 24-hour Shadow results.

## 2. Integrity and Failure Tolerances
Shadow Mode is primarily an operational verification phase. The following maximum acceptable error rates apply:

- **Data-Error Rate:** Max 0.1% (Incomplete 5m bars, missing OHLCV, missing snapshot)
- **Inference-Error Rate:** 0.0% (No LightGBM failures, no NaN/Inf predictions, no routing mismatches)
- **Stale-Data Rate:** Max 0.5% (Price or CVD feeds lagging the 5m decision boundary by more than 10 seconds)
- **Timestamp Anomaly Rate:** 0.0% (Decisions strictly bound to `ts % 300000 == 0`)
- **Unintended Broker/Order Calls:** 0
- **Duplicate Symbol+Timestamp Decisions:** 0
- **Model Hash Changes:** 0
- **Threshold Hash Changes:** 0
- **Model Version Mismatches:** 0

## 3. Fail-Closed Validation
During the shadow period, the system must intentionally intercept and correctly handle (via `HOLD` and safe recovery) the following edge cases:
- Missing feature / dropped stream
- Stale data / connection timeout
- NaN / Inf in base features or CVD
- Unavailable or mismatched threshold file

## 4. Next Stage Gate
If all conditions are met after the observation window closes, a transition to **PAPER EXECUTION** is authorized.
If any condition fails, the observation window resets. **No performance retuning or threshold modifications are permitted.**
