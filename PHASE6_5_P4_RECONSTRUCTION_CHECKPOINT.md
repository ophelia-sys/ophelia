# PHASE 6.5 P4 RECONSTRUCTION CHECKPOINT

**STATUS:** P4 = READY FOR BLIND CONFIRMATION

## EXACT KNOWN METHODOLOGY
The P4 ingestion logic was successfully recovered and verified in Phase 6.3.
Source: `research/data/ingest_aggtrades_p4.py`

### Features:
- `large_buy_volume_5m`
- `large_sell_volume_5m`
- `large_trade_imbalance`
- `large_trade_share`
- `trade_size_zscore`
- `trade_size_concentration`

### Causal Threshold Methodology
- Threshold is strictly causal. The threshold for bar $T$ uses only observations from $(T-24h)$ up to $(T-5m)$.
- Exactly a 288-bar (24h) rolling history of total quote volumes.
- Threshold = 99th percentile of this causal history.
- Data from bar $T$ never influences the threshold used to classify trades in bar $T$.

### State
- Checkpointing successfully implemented to pickle the 288-bar history (`_p4_checkpoint.pkl`).
- The 2022-2023 run produced valid artifacts in `research/data/normalized/p4/`.
- 2024 generation is ready to run and will automatically resume from the 2023 checkpoint state to fulfill exact 24h padding on `2024-01-01 00:00:00`.
