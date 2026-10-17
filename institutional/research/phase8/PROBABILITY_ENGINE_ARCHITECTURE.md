# PROBABILITY ENGINE ARCHITECTURE

## 1. Purpose

The Calibrated Probability Engine replaces the heuristic `DecisionEngine` scoring with an empirical, machine-learning-driven pipeline. It answers one specific question:

> "What is the empirically calibrated probability that this opportunity reaches its predefined outcome before its adverse barrier, AFTER trading costs?"

## 2. Real-Time Execution Architecture (V4 Shadow Pipeline)

The new pipeline must run **independently** alongside the existing `DecisionEngine`. It must NOT replace the `DecisionEngine` or execute live trades. Until a model is fully trained, it produces `MODEL_UNAVAILABLE`.

```text
REAL-TIME DATA (InstitutionalDataEngine)
      ↓
FEATURE ENGINE (InstitutionalMathEngine)
      ↓
(V4 Shadow Fork - Independent of DecisionEngine)
      ↓
TRADE GEOMETRY MODULE (Dynamic Entry, SL, T1, T2, T3)
      ↓
LOCAL PROBABILITY MODEL (e.g., Logistic Regression / LightGBM)
      ↓
CALIBRATION LAYER (Platt Scaling / Isotonic Regression)
      ↓
EXPECTED VALUE CALCULATOR (EV = [P(Win) * Reward] - [P(Loss) * Risk] - Costs)
      ↓
OPPORTUNITY GATE (Deterministic Thresholds)
      ↓
V4 SHADOW OPPORTUNITY (Logged for telemetry, never executed)
```

## 3. The Triple-Barrier Target

The engine trains on the **Triple-Barrier Method**, parameterized as follows (and configurable for research):
- **Upper Barrier:** `+ATR-scaled target + estimated spread/fee costs` (configurable)
- **Lower Barrier:** `-ATR-scaled stop loss - estimated spread/fee costs` (configurable)
- **Vertical Barrier:** Configurable Horizons (`15m`, `30m`, `1h`, `4h`)

**Label Definition:** 
`y = 1` if Upper Barrier is touched first.
`y = 0` if Lower Barrier or Vertical Barrier is touched first.
Target variable: `P(TAKE_PROFIT BEFORE STOP | FEATURES)`

## 4. Expected Output Schema

The engine must produce a detailed, deterministic opportunity object:

```json
{
  "symbol": "BTC-USDT",
  "direction": "LONG",
  "calibrated_probability": 0.674,
  "prediction_horizon_minutes": 60,
  "expected_value_r_multiple": 0.42,
  "trade_geometry": {
    "entry_price": 60000.0,
    "stop_loss": 59500.0,
    "take_profit": 61500.0,
    "estimated_cost_usdt": 1.50
  },
  "evidence": {
    "order_flow": "strong positive",
    "volume_profile": "positive",
    "open_interest": "moderately positive",
    "microstructure": "positive",
    "momentum": "neutral",
    "funding": "negative"
  },
  "data_quality": "VALID",
  "missing_features": []
}
```

## 5. Deployment & Continuous Learning (Champion/Challenger)

- **No Auto-Training:** The live model is statically serialized.
- **Champion / Challenger Setup:** A Challenger model can replace a Champion ONLY after passing explicit gates on identical OOS periods. Never silently replace a model.
- **V4 Shadow Telemetry:** The shadow system logs the full feature vector, availability, probability, EV, geometry, and eventually the actual outcome and barrier hit (MFE/MAE/time to outcome) to collect training data without altering historical records.
