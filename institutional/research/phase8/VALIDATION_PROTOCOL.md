# VALIDATION PROTOCOL

## 1. Walk-Forward Time-Series Validation
Standard randomized k-fold Cross-Validation is completely banned. All models must be evaluated using strict rolling walk-forward validation (e.g., Purged K-Fold or contiguous block walk-forward).

## 2. Information Leakage Controls

### A. Purging and Embargo
- **Purging:** Drop training samples whose outcome horizons overlap with the test set's input window.
- **Embargo:** Drop training samples immediately following the test set to account for serial correlation in market regimes.

### B. Scaler & Normalization Leakage
- Feature scalers (`RobustScaler`, `StandardScaler`, rolling Z-scores) must be fit **only on the training split**. 
- The validation/test split must be transformed using the historical parameters.

### C. Calibration Leakage
- Model calibration (Platt scaling / Isotonic regression) must be fit on a separate validation split (or derived cross-validated predictions), **never** on the test set.

### D. Hyperparameter Leakage
- Hyperparameter tuning must happen strictly within the bounds of the training splits. The final out-of-sample (OOS) test period must remain untouched until the model configuration is finalized.

## 3. Mandatory Evaluation Metrics
A model is only valid if it excels in the following out-of-sample metrics:
1. **Log Loss / Brier Score:** Primary targets for proper scoring rules.
2. **Expected Calibration Error (ECE):** Assesses how close the predicted probability is to the empirical frequency.
3. **Expected Value After Costs:** 
   `EV = [P(win) * Reward] - [P(loss) * Risk] - (Spread + Fees)`
4. **Maximum Drawdown (MDD) & Turnover:** Checks for economic viability in a simulated run.
