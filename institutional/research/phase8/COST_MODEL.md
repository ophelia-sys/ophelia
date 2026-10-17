# COST MODEL

Evaluating an ML model simply on "Did the price go up or down?" is insufficient. A model must be evaluated on its ability to generate positive Expected Value (EV) after realistic trading frictions.

Every model candidate must be evaluated across the following Cost Scenarios. A model only qualifies for production if it survives the `Realistic` scenario with positive EV.

## 1. Optimistic Scenario
- **Maker/Taker Fee:** 0.02% / 0.05%
- **Spread Assumption:** 1 tick
- **Slippage Assumption:** 0 ticks
- **Use Case:** Best-case baseline to see if the model has *any* gross edge at all.

## 2. Realistic Scenario (Default Target)
- **Maker/Taker Fee:** 0.045% (Typical blended rate)
- **Spread Assumption:** Historical spread (if available) or 2 ticks average.
- **Slippage Assumption:** 1 tick on entry (market order), 0 ticks on limit exit.
- **Funding:** Accounted for if holding over 8-hour boundaries.

## 3. Conservative Scenario
- **Maker/Taker Fee:** 0.05% (Full Taker)
- **Spread Assumption:** 3 ticks
- **Slippage Assumption:** 2 ticks (Simulating slight adverse selection).

## 4. Stress Scenario
- **Maker/Taker Fee:** 0.05%
- **Spread Assumption:** 5 ticks (Simulating low liquidity/high volatility environments).
- **Slippage Assumption:** 3 ticks.
- **Use Case:** Ensuring the model isn't hyper-fitted to ultra-tight microstructure regimes that disappear during market shocks.

## Implementation in Labeling
Rather than modifying the raw Triple-Barrier label ($y \in \{1, -1\}$), the Cost Model is applied to the **Expected Value** calculation during model evaluation:
$EV = (P(Win) \times (Reward - Costs)) - (P(Loss) \times (Risk + Costs))$
