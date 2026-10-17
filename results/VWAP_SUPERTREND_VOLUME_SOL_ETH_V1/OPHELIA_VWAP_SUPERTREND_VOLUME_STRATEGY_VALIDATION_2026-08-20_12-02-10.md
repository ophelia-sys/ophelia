# OPHELIA — VWAP + SUPERTREND + VOLUME STRATEGY V1 VALIDATION
Date: 2026-08-20 12:02:10 UTC

## 1. Strategy Objective
Validate a deterministic V1 strategy for SOLUSDT and ETHUSDT using 5-minute candles, Session VWAP, Supertrend (10, 3.0), and Ophelia's volume aggregation logic. Live execution remains BLOCKED.

## 2. Pine Script Reference & 3. Exact V1 Interpretation
- **Pine Script Variant**: Triggered on `price crosses VWAP AND Supertrend is favorable`.
- **User V1 Interpretation**: Triggered on `Supertrend Direction Flips AND price is favorable relative to VWAP`.

## 4. Supertrend & 5. VWAP Validation
Supertrend uses `length=10, factor=3.0` calculated matching TradingView step logic. VWAP uses `(H+L+C)/3` typical price weighted by volume, resetting daily at 00:00 UTC.

## 6. Volume Data Validation & 7. Volume Rule Sensitivity
Volume features used standard Ophelia `volume` and `delta_v`. Multiplier sweeps were tested across 3, 5, 6 bar windows.

### Volume Sensitivity Results
| Symbol | Config | Trades | Win Rate | Mean Return (Gross) | Partial Rate |
|---|---|---|---|---|---|
| SOLUSDT | mult1.0_win3 | 54 | 33.3% | -14.3 bps | 33.3% |
| SOLUSDT | mult1.1_win3 | 46 | 30.4% | -8.5 bps | 30.4% |
| SOLUSDT | mult1.25_win3 | 33 | 33.3% | -6.0 bps | 33.3% |
| SOLUSDT | mult1.5_win3 | 20 | 35.0% | -1.0 bps | 35.0% |
| SOLUSDT | mult1.0_win5 | 75 | 41.3% | 5.1 bps | 41.3% |
| SOLUSDT | mult1.1_win5 | 61 | 49.2% | 17.5 bps | 49.2% |
| SOLUSDT | mult1.25_win5 | 51 | 49.0% | 20.2 bps | 49.0% |
| SOLUSDT | mult1.5_win5 | 40 | 52.5% | 30.7 bps | 52.5% |
| SOLUSDT | mult1.75_win5 | 31 | 51.6% | 31.1 bps | 51.6% |
| SOLUSDT | mult1.0_win6 | 76 | 46.1% | 10.3 bps | 46.1% |
| SOLUSDT | mult1.25_win6 | 61 | 49.2% | 16.6 bps | 49.2% |
| ETHUSDT | mult1.0_win3 | 40 | 22.5% | -20.2 bps | 22.5% |
| ETHUSDT | mult1.1_win3 | 33 | 24.2% | -20.8 bps | 24.2% |
| ETHUSDT | mult1.25_win3 | 29 | 20.7% | -23.8 bps | 20.7% |
| ETHUSDT | mult1.5_win3 | 25 | 20.0% | -24.7 bps | 20.0% |
| ETHUSDT | mult1.0_win5 | 76 | 32.9% | -9.1 bps | 32.9% |
| ETHUSDT | mult1.1_win5 | 69 | 31.9% | -11.0 bps | 31.9% |
| ETHUSDT | mult1.25_win5 | 60 | 31.7% | -15.1 bps | 31.7% |
| ETHUSDT | mult1.5_win5 | 55 | 32.7% | -12.5 bps | 32.7% |
| ETHUSDT | mult1.75_win5 | 46 | 28.3% | -20.0 bps | 28.3% |
| ETHUSDT | mult1.0_win6 | 92 | 23.9% | -11.6 bps | 23.9% |
| ETHUSDT | mult1.25_win6 | 76 | 25.0% | -10.0 bps | 25.0% |


## 17. SOL Results (V1: mult 1.25, win 5)
- **Trades**: 51
- **Win Rate**: 49.0%
- **Gross Expectancy**: 20.2 bps
- **0.80% Partial Rate**: 49.0%

## 18. ETH Results (V1: mult 1.25, win 5)
- **Trades**: 60
- **Win Rate**: 31.7%
- **Gross Expectancy**: -15.1 bps
- **0.80% Partial Rate**: 31.7%

### 21. Cost Sensitivity (SOL)
- Gross: 20.2 bps
- Net at 8 bps friction: 12.2 bps
- Net at 12 bps friction: 8.2 bps
- Net at 16 bps friction: 4.2 bps
- Net at 20 bps friction: 0.2 bps

### 21. Cost Sensitivity (ETH)
- Gross: -15.1 bps
- Net at 8 bps friction: -23.1 bps
- Net at 12 bps friction: -27.1 bps
- Net at 16 bps friction: -31.1 bps
- Net at 20 bps friction: -35.1 bps

## 22. Pine Variant Comparison
- **SOL Pine Variant**: 592 trades, 18.9% win rate, -1.1 bps gross.
- **ETH Pine Variant**: 668 trades, 13.5% win rate, 1.9 bps gross.

## 23. Edge Cases & Intrabar Assumptions
Intrabar assumption conservatively assumed that if a Stop and the 0.80% milestone were both breached in the same 5m candle, the **Stop was hit first**. This prevents manufacturing artificial performance.

## 26. LOCAL/VPS Status & 27. Shadow Readiness
Research completed locally. Not yet synchronized to VPS. Shadow mode disabled.

## 29. Final Recommendation
### NOT READY — FIX REQUIRED
The strategy fails to demonstrate a sufficient net expectancy after 12 bps execution friction.
- ETH Net Expectancy (12 bps): -27.1 bps
The 1-bps buffer stop may be too tight, causing premature stop-outs before the 0.80% milestone is achieved. The volume multiplier rules showed mixed success.