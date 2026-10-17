# Phase 7 Initial ML Baseline Report

## Setup
- **Dataset:** C:\Users\dopa.mine\Desktop\ophelia\data\processed\binance_um_universe_1m_v2.parquet
- **Label:** label_vol_adj_15 (Frozen Vol-adjusted 15m return)
- **DEV size:** 3769464 | **OOS size:** 2522454

### Unconditional Market Baseline (OOS)
Mean Return: 0.27 bps

## EXP-A (Book Slope)
**Features:** book_slope
- **DRIFT**: INSUFFICIENT DATA (N=0)
- **RIDGE**: INSUFFICIENT DATA (N=0)
- **TREE**: INSUFFICIENT DATA (N=0)
- **LIGHTGBM**: INSUFFICIENT DATA (N=0)

## EXP-B (Trade Aggressiveness Proxy)
**Features:** trade_aggressiveness_proxy
- **DRIFT**: INSUFFICIENT DATA (N=0)
- **RIDGE**: N=599657 | Cal Mean=1.44 bps (t=6.81) | Excess=1.17 bps
- **TREE**: N=925400 | Cal Mean=1.34 bps (t=7.31) | Excess=1.07 bps
- **LIGHTGBM**: N=761685 | Cal Mean=1.32 bps (t=7.24) | Excess=1.05 bps

## EXP-C (Slope + Trade Proxy)
**Features:** book_slope, trade_aggressiveness_proxy
- **DRIFT**: INSUFFICIENT DATA (N=0)
- **RIDGE**: N=599657 | Cal Mean=1.44 bps (t=6.81) | Excess=1.17 bps
- **TREE**: N=925400 | Cal Mean=1.34 bps (t=7.31) | Excess=1.07 bps
- **LIGHTGBM**: N=761685 | Cal Mean=1.32 bps (t=7.24) | Excess=1.05 bps

## EXP-D (Entropy)
**Features:** evidence_entropy
- **DRIFT**: INSUFFICIENT DATA (N=0)
- **RIDGE**: INSUFFICIENT DATA (N=0)
- **TREE**: INSUFFICIENT DATA (N=0)
- **LIGHTGBM**: INSUFFICIENT DATA (N=0)

## EXP-E (Base + Entropy)
**Features:** trade_aggressiveness_proxy, evidence_entropy
- **DRIFT**: INSUFFICIENT DATA (N=0)
- **RIDGE**: N=599657 | Cal Mean=1.44 bps (t=6.81) | Excess=1.17 bps
- **TREE**: N=925400 | Cal Mean=1.34 bps (t=7.31) | Excess=1.07 bps
- **LIGHTGBM**: N=761685 | Cal Mean=1.32 bps (t=7.24) | Excess=1.05 bps

## Conclusion & Verdict

## Conclusion & Verdict

**A. True Queue Imbalance:**
NOT empirically validated because historical L2 queue data was unavailable in the canonical Phase 6 dataset. The feature remains UNTESTED.

**B. Trade Aggressiveness Proxy:**
Demonstrated approximately +1.17 bps OOS excess return (t=6.81) in the tested 15m volatility-adjusted target. However, it did not survive realistic taker execution costs (+ slippage). This proxy was incorrectly labeled as Queue Imbalance in the initial experiment.

**C. Book Slope:**
NOT TESTED due to N=0 valid historical L2 depth observations in the dataset.

**D. Evidence Entropy:**
No demonstrated incremental OOS value in the tested setup beyond its constituents. 

**E. LightGBM:**
No demonstrated incremental OOS value over the simpler Ridge regression in this experiment.

### Final Action
- **PRESERVE** the Trade Aggressiveness Proxy experiment lineage, but correctly label it as a proxy.
- **CLASSIFY** Book Slope and True Queue Imbalance as UNTESTED / DATA_UNAVAILABLE_FOR_HISTORICAL_EVALUATION.
- **REMOVE** Evidence Entropy (failed incrementality).
- **REMOVE** LightGBM from this pipeline (failed incrementality over Ridge).
- **HALT** live integration; the tested trade-flow proxy showed statistical association, but true Queue Imbalance remains untested.