# PHASE 5 TIMEFRAME CORRECTIVE REPORT

## 1. The Timeframe Mislabel Error

During the execution of Phase 5 (including 5.1, 5.2, and the initial 5.3 report), the core dataset `v2_fixed_timestamp/BTCUSDT.parquet` was repeatedly described as containing **5-minute** candles. 

**VERIFIED DATA FACT:** An independent audit of the dataset schema and timestamps confirms that `v2_fixed_timestamp/BTCUSDT.parquet` consists of **1-minute (1m)** candles. 

- **Row Count:** 1,051,200 rows.
- **Date Range:** 2022-01-01 to 2023-12-31.
- **Resolution:** 1 minute.

## 2. Old Interpretation vs Verified Fact

### Experiment 001 - 013 (Phases 5.1 & 5.2)
- **Old Interpretation:** "Baseline BTCUSDT (5m) Ablation."
- **Verified Fact:** The baseline ablation was performed on 1m data.
- **Old Interpretation:** `target_60` was interpreted as 60 candles = 300 minutes (5 hours).
- **Verified Fact:** `target_60` is exactly 60 minutes (1 hour).
- **Old Interpretation:** Horizons like 1, 3, 12, 60 were interpreted as 5m, 15m, 1h, 5h.
- **Verified Fact:** Horizons 1, 3, 12, 60 were exactly 1m, 3m, 12m, 60m.

### Phase 5.3 (Initial Report)
- **Old Interpretation:** Barrier timeout of 60 meant 60 * 5 = 300 minutes.
- **Verified Fact:** Barrier timeout of 60 meant exactly 60 minutes.

## 3. Which Conclusions Remain Valid?

The mathematical conclusions regarding statistical edge versus economic edge remain completely valid, albeit at different time horizons than originally believed:

1. **Statistical Edge is Present:** The models still demonstrate out-of-sample predictive power (AUC > 0.50). 
2. **Economic Edge is Negative:** Even at 1m to 60m horizons, the gross EV captured by the models is entirely consumed by the 12 bps execution cost. 
3. **Evidence > Sophistication:** The rejection of unconstrained ML models for production remains the correct scientific decision.

## 4. Which Conclusions Must Be Reconsidered?

1. **Feature Decay Rates:** In Phase 5.2, it was noted that "5-minute" features degrade rapidly. In reality, these were 1-minute features degrading rapidly. We do not yet have empirical evidence on how true 5-minute or 1-hour aggregated features perform.
2. **Holding Horizons:** The assumption that the model was holding trades for ~2.5 hours on average was false. The average holding time in Phase 5.3 was 11.4 *minutes* (11.4 candles). 

## 5. Protocol Update
From this point forward, the verified 1m timeframe is authoritative. All subsequent Phase 5.3 rerun experiments and metrics will correctly label 60 candles as 60 minutes.
