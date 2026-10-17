# PHASE 5.2 - ECONOMIC EDGE DISCOVERY REPORT

**Date**: 2026-08-12
**Status**: COMPLETE (SCIENTIFIC REJECTION)

## 1. Executive Summary

Phase 5.2 subjected the statistically valid (but economically negative) model identified in Phase 5.1 to a systematic, multi-stage economic discovery process. The goal was to determine if specific holding horizons, entry timing techniques (delays/pullbacks), or fixed barrier structures (targets/stops) could extract an economic edge (defined against a 12 bps execution cost baseline) using strictly out-of-sample walk-forward methodology on the discovery dataset (2022-2023, 1-minute candles).

**Conclusion**: The hypothesis is definitively **REJECTED**.
While the base features exhibit strong short-term statistical predictive power (AUC > 0.80 at 5-minute horizons), the gross return captured by the top decile of predictions remains strictly bounded between -1.0 bps and +2.1 bps across all parameter configurations. No tested variation approaches the 12 bps cost boundary, nor even a theoretical 6 bps cost boundary.

---

## 2. Experiment Results

### Exp 007: Feature Quality Review
An ablation study of the feature families identified significant dead weight in the model.
*   **Baseline Model**: AUC 0.5854, Gross return -0.11 bps (60m horizon).
*   **Negative Contributors**: Dropping `vol_60` *increased* AUC by 0.0087 and gross return by +1.45 bps. Dropping `mom_60` increased AUC by 0.0048 and gross return by +0.34 bps.
*   **Result**: Several higher-timeframe features are actively degrading the model on 1-minute data and should be reviewed or discarded.

### Exp 008: Cost Sensitivity
Evaluated the top decile predictions against hypothetical execution costs ranging from 6 bps to 20 bps.
*   **Top Decile Gross Return**: 0.00 bps (Base model).
*   **Break-Even Cost**: 0.00 bps.
*   **Result**: The model is economically unviable at any realistic execution cost tier.

### Exp 009: Holding Horizon
Evaluated fixed time-based exits from 5m (Horizon 1) to 5h (Horizon 60).
*   **5m Horizon**: Highest predictive power (AUC = 0.8094), but slightly negative gross return (-0.02 bps).
*   **1h Horizon**: Peak gross return (+0.13 bps), AUC degrades to 0.6622.
*   **5h Horizon**: AUC degrades further (0.5929), gross return flatlines (0.00 bps).
*   **Result**: AUC decays monotonically with time. The signal is highly short-term but lacks the magnitude required to cover the spread/fees.

### Exp 010: Entry Timing
Evaluated delayed entries (1-3 candles) and pullback limit orders (3 candle expiration).
*   **Delays**: Delaying entry by 2-3 candles marginally improved gross return (from 0.54 bps to 0.61 bps).
*   **Pullbacks**: Limit orders at 5 bps and 10 bps pullbacks suffered from severe adverse selection. Fill rates dropped (73.6% and 56.3%), and the gross return of filled trades turned strictly negative (-0.44 bps and -0.06 bps).
*   **Result**: Limit orders only get filled when the market is accelerating against the prediction.

### Exp 011: Target / Stop Structure
Evaluated fixed asymmetric and symmetric barrier exits.
*   **T1 (10bps) vs SL (10bps)**: 46.6% hit target, 45.2% hit stop. EV = +0.13 bps.
*   **T2 (20bps) vs SL (10bps)**: 33.3% hit target, 63.7% hit stop. Peak EV = +0.28 bps. Avg hold: 3.1 candles.
*   **Result**: While asymmetric barriers (2:1 reward-to-risk) slightly outperformed symmetric barriers, the absolute expected value (+0.28 bps) is an order of magnitude smaller than execution costs.

### Exp 012: Kronos Lineage
*   **Status**: Pending external data delivery.

### Exp 013: Cross-Asset Validation
Evaluated the BTCUSDT-trained parameters identically on major altcoins.
*   **ETHUSDT**: AUC 0.5679 | Gross +2.10 bps
*   **BNBUSDT**: AUC 0.5613 | Gross +0.59 bps
*   **SOLUSDT & XRPUSDT**: AUC < 0.55 | Gross < 0 bps
*   **Result**: The model exhibits varying statistical transferability, performing slightly better on ETHUSDT in gross terms, but strictly failing the economic viability threshold on all evaluated assets.

---

## 3. Final Scientific Verdict

The Phase 5 Quantitative Research Lab has successfully demonstrated its utility by aggressively identifying and rejecting a statistically attractive but economically toxic model configuration. 

**Summary of Rejection**:
1. The model identifies directional tendencies (AUC > 0.50), but the magnitude of the predicted moves is dwarfed by the bid-ask spread and taker fees.
2. Attempting to bypass fees via limit-order pullbacks results in classical adverse selection.
3. The features designed for 5-minute candles are actively degrading the 1-minute prediction space.

**Status**: The model, features, and target horizon evaluated in Phase 5.1/5.2 are hereby **REJECTED** for production use. 
