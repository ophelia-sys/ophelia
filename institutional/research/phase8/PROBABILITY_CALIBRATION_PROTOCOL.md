# PROBABILITY CALIBRATION PROTOCOL

## 1. The Calibration Mandate
The core function of the Probability Engine is not to emit scores (e.g., 0-100), but to output true empirical probabilities.
If the engine states a trade has a `0.78` probability of hitting the take-profit before the stop-loss, historical OOS testing must confirm that ~78% of trades in that bucket were successful.

## 2. Calibration Methods to Evaluate
1. **Platt Scaling (Logistic Calibration):** Parametric. Assumes the relationship between raw model scores and true probabilities is sigmoidal. Suitable for small validation sets.
2. **Isotonic Regression:** Non-parametric. Fits a piecewise constant non-decreasing function. Powerful, but requires a larger calibration set to avoid overfitting.

## 3. Distinguishing Score from Calibrated Probability
- **Model Score:** The raw output margin of a Logistic Regression or the raw tree sum of LightGBM.
- **Calibrated Probability:** The output of the calibration layer (`predict_proba` after calibration).
- **Ophelia UI / Telemetry:** Must clearly label outputs as `Calibrated Probability`. Raw scores are purely diagnostic.

## 4. Evaluation via Calibration Curves
Calibration must be plotted and quantified using:
- **Reliability Diagrams (Calibration Curves):** Binned predicted probabilities vs. actual fraction of positives. The ideal model follows the `y=x` diagonal.
- **Brier Score:** The mean squared difference between predicted probability and the actual outcome (0 or 1).
- **Expected Calibration Error (ECE):** Weighted average of the difference between predicted and empirical probability across bins.
