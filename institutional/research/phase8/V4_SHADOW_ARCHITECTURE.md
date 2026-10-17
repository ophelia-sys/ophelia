# V4 SHADOW ARCHITECTURE

## 1. Purpose
The V4 Shadow pipeline allows the Calibrated Probability Engine to be developed, deployed, and tested in a production environment WITHOUT disrupting or replacing the existing `DecisionEngine`.

## 2. Independence of Execution
- The existing `DecisionEngine` handles current live flow (or simulated live flow) and its heuristic output remains operational and untouched.
- The V4 pipeline forks off the `MarketState`.
- It executes independently and logs to a **V4 Shadow Opportunity** database.
- It MUST NOT execute trades.

## 3. The "Unavailable" Probability Mandate
Before a real model is trained and validated:
- `probability = UNAVAILABLE`
- Do not fabricate placeholders like `0.5`, `0`, `0.01`, or `0.99`.

The shadow telemetry must distinguish between:
- `MODEL_UNAVAILABLE` (No valid model exists)
- `LOW_PROBABILITY` (Model evaluated, but probability < threshold)
- `REJECTED_BY_EV` (Probability OK, but EV < 0 after costs)
- `INSUFFICIENT_DATA` (Missing critical features preventing model inference)

## 4. Telemetry Collection
The V4 Shadow system serves as the primary data collection vehicle for future model training. It records:
**Opportunity Generation:**
- timestamp, symbol, timeframe
- complete feature vector
- feature availability and data quality
- candidate direction
- `entry`, `stop`, `T1`, `T2`, `T3`
- estimated costs
- model status, probability, expected value
- decision / rejection reason

**Outcome Resolution (Later):**
- actual outcome (which barrier was reached)
- realized return
- MFE (Maximum Favorable Excursion)
- MAE (Maximum Adverse Excursion)
- time to outcome
