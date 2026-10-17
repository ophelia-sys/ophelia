# MODEL SELECTION PROTOCOL

## 1. Core Principle (Model Complexity Gate)
Prefer the simplest model that produces the best calibrated after-cost result. 
Do NOT permanently ban neural/deep models, but establish a strict **Model Complexity Gate**. 
A more complex model may only proceed if it demonstrates:
- Lower OOS Log Loss
- Better Brier Score
- Better calibration
- Positive incremental economic value after costs
- Robustness across time periods and assets
- Acceptable computational requirements

The simplest model wins unless complexity produces measurable additional value. If it does not beat Logistic Regression sufficiently, discard it.

## 2. Candidate Models (Evaluated in Order)
1. **Regularized Logistic Regression:** The ultimate baseline. Easy to interpret, fast to infer.
2. **LightGBM:** Fast, gradient-boosted trees.
3. **Other Models (e.g., Deep Learning):** Only if justified by passing the Model Complexity Gate against the current champion on genuine OOS data.

## 3. Feature Ablation Process
Models are trained incrementally to prove feature value:
- **Step 1:** Base Model (`Price + Volatility`)
- **Step 2:** Add `Order Flow` -> Measure $\Delta$ Brier Score / EV
- **Step 3:** Add `Derivatives` -> Measure $\Delta$ Brier Score / EV
- **Step 4:** Add `Microstructure` -> Measure $\Delta$ Brier Score / EV

Any group (or specific feature) failing to improve Out-Of-Sample metrics after transaction costs is **removed**.

## 4. Kronos Evaluation
Kronos is treated as a sophisticated external time-series feature. It must prove its worth.
- Base Model with Kronos vs Base Model without Kronos.
- If Kronos does not provide statistically significant incremental predictive power, it is excluded from the automated pipeline.
