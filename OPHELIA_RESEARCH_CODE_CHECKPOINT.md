# OPHELIA RESEARCH CODE CHECKPOINT

## Active Experiment Scripts
- `research/experiments/exp_phase6_5_2024_confirmation.py`: Pending execution. Contains the strict logic to evaluate Experiment A (P4) and Experiment B (P7) on 2024 data using the frozen LightGBM benchmark.
- `research/experiments/audit_phase6_5_data.py`: Script to verify 2024 data availability and padding.

## Feature Modules (FROZEN - DO NOT ALTER)
- `research/ml4t_benchmark/features/p7_volume_acceptance.py`: Exact P7 volume/price acceptance proxy logic.
- `research/pipeline/features.py`: Base features.
- `research/experiments/exp_phase5_3_ml_ablation.py`: Contains `engineer_cvd_features`.

## P4 Ingestion Pipeline
- `research/data/ingest_aggtrades_p4.py`: Maintains `P4IngestionPipeline`. Required to process 2024 aggTrades. Contains automatic 24h rolling checkpoint saving (`_p4_checkpoint.pkl`).

## P7 Implementation
- Present in `research/ml4t_benchmark/features/p7_volume_acceptance.py`.

## Data Loaders
- `research/data/ingest_phase6_5_cvd.py`: Created for Phase 6.5 to ingest exactly the same 5-minute CVD as Phase 5.3.

## Modified Files
- `bot.py`
- `institutional/liquidity.py`, `institutional/normalization.py`, `institutional/open_interest.py`, `institutional/order_flow.py`
- *Note: These files were not modified during this research phase but show up in git status.*

## Temporary Scripts
- None running. (Tasks 5546 and 5495 were killed to honor the ABSOLUTE STOP directive).
