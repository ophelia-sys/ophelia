# SAMPLE SIZE ANALYSIS

Hard-coding arbitrary dataset lengths (e.g., "2 years") is statistically invalid. The required historical duration must be calculated empirically.

## 1. Factors Dictating Sample Size
- **Label Count & Class Balance:** We require enough minor-class labels (e.g., successful Take-Profit hits) to prevent the model from learning a degenerate "always predict loss" baseline.
- **Overlapping Labels:** In a 4h Triple-Barrier setup on 1m candles, consecutive candles will share up to 239 minutes of overlapping future data. These are NOT independent events.
- **Effective Sample Size (ESS):** The number of truly non-overlapping, independent barrier events. $ESS \approx \frac{N}{Horizon\_Length}$.

## 2. Empirical Calculation Formula
To achieve statistical significance (e.g., 95% confidence interval on a binomial proportion with a 2% margin of error):
$N_{independent} = \frac{Z^2 \cdot p(1-p)}{E^2}$
Where:
- $Z = 1.96$
- $p \approx 0.5$ (assuming balanced win-rate)
- $E = 0.02$
Result: $N_{independent} \approx 2,400$ independent trades per asset.

## 3. Translating to Time Duration
If a strategy averages 2 independent non-overlapping trades per day:
- Required duration = 1,200 days $\approx$ **3.2 years** to achieve tight bounds on a single asset.
- If pooled across 5 highly-correlated assets, we divide by the effective degrees of freedom (accounting for cross-asset correlation). If correlation is 0.8, the pooled ESS is much lower than $5 \times 2400$.

## 4. Recommendation
The exact sample size will be recommended *after* downloading a pilot sample (e.g., 3 months), running the Triple-Barrier labeler, calculating the overlap-adjusted ESS, and projecting it forward. Do not download massive data blindly.
