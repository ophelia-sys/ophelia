# Microstructure Horizon Research Framework

## Objective
To map the information-decay curve of microstructure features across high-frequency and mid-frequency horizons, moving away from a singular 15-minute assumption.

## Horizons to Evaluate
The research will evaluate predictive signal strength at the following horizons ($h$):

**Tick-Based (Event Time):**
- Next tick
- Next 5 ticks
- Next 10 ticks

**Time-Based (Clock Time):**
- 1 second
- 5 seconds
- 10 seconds
- 30 seconds
- 1 minute
- 3 minutes
- 5 minutes
- 15 minutes

## Methodology
For each true microstructure feature (e.g., True Queue Imbalance, Microprice, Book Slope), we will compute:
1. **Predictive Signal at $h$**: Rank correlation (IC) and predictive expectancy.
2. **Signal Decay**: The gradient of signal strength across sequential horizons.
3. **Stability**: Variance of signal strength across market regimes.
4. **Transaction-Cost Sensitivity**: The ratio of expected return at horizon $h$ to the estimated cost of crossing the spread at entry and exit.

## Computational Efficiency Design
Given the massive volume of tick data:
1. **Initial Probing**: Sub-sample data to 1 week of highly liquid history (e.g., BTCUSDT only) to generate the initial decay curves.
2. **Elimination**: Discard horizons where the signal approaches 0 or becomes completely economically sub-marginal (cost ratio < 0.1).
3. **Full Sample Validation**: Only run surviving combinations across the full multi-month dataset and full 5-symbol universe.
