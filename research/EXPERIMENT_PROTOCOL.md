# EXPERIMENT PROTOCOL

The Ophelia Research Lab rigorously tests incremental feature improvements and ML model complexity against strict evaluation criteria. No mathematical transformation or complex ML algorithm can be deployed into Ophelia without satisfying these tests.

## 1. Incremental Ablation

Instead of throwing large feature sets at models in bulk, experiments use incremental ablation (e.g., baseline -> +volatility -> +trend -> +momentum). This determines exactly which features contribute to predictive edge and which are noise.

## 2. Statistical Baseline Validation

For every prediction model run, predictions must demonstrate statistical significance:
- Evaluated via stationary block bootstrap cross-validation.
- Must produce AUC significantly above 0.50 (the 95% CI lower bound must strictly exceed 0.50).

## 3. Net Economic Requirement

Statistical significance is NOT sufficient. The predictions must demonstrate an economic edge.
- Net Economic Return must be positive across independent folds when evaluated under standard institutional cost parameters.
- Standard Assumption: 12 bps round-trip cost (4 bps taker fee + 2 bps slippage per side).

## 4. Rejection

If an ablation run yields a net return <= 0 (e.g., `STATISTICALLY_SIGNIFICANT_NOT_ECONOMIC`), the feature or model architecture under consideration is REJECTED for production.
