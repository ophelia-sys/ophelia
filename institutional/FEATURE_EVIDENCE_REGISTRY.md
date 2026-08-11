# OPHELIA — FEATURE EVIDENCE REGISTRY
**Last Updated:** 2026-08-11

This registry maintains the evidence-based status of each institutional feature. Formula validity is tracked in `FEATURE_REGISTRY.md`; predictive validity is tracked here.

## Evidence Status Taxonomy
- **VALIDATED:** Statistically proven predictive power for the target.
- **PROMISING:** Initial empirical evidence suggests value, requires out-of-sample confirmation.
- **WEAK:** Weak correlation or information coefficient.
- **REDUNDANT:** High collinearity with another validated feature (e.g. Garman-Klass vs RV).
- **REGIME_DEPENDENT:** Predictive power exists only under specific structural breaks (e.g., trend vs mean-reverting).
- **INSUFFICIENT_DATA:** Missing or incomplete runtime history (e.g. Funding needs hours to mature).
- **RESEARCH_ONLY:** Implemented conceptually but not yet empirically evaluated.
- **UNAVAILABLE:** Data cannot be procured reliably.

---

## 1. Volatility Family
| Feature | Target | Normalization | Evidence Status | Look-Ahead Risk | Notes |
|---------|--------|---------------|-----------------|-----------------|-------|
| Log Returns | Fwd Ret (1m) | Robust Z-Score | VALIDATED | None | Core input for momentum, mean-reversion baseline. |
| Realized Volatility | Vol-Adj Ret | Percentile | VALIDATED | None | Strong regime separator. |
| Parkinson | Vol-Adj Ret | Percentile | REDUNDANT | None | Correlated with RV. RV preferred. |
| Garman-Klass | Vol-Adj Ret | Percentile | REDUNDANT | None | Correlated with RV. |
| ATR | Fwd Ret (5m) | - | VALIDATED | None | Used internally for trend scaling. |

## 2. Trend & Regime Family
| Feature | Target | Normalization | Evidence Status | Look-Ahead Risk | Notes |
|---------|--------|---------------|-----------------|-----------------|-------|
| KER (Efficiency Ratio) | Fwd Dir (1m) | Raw (0-1) | VALIDATED | None | Excellent filter for false momentum breakouts. |
| Directional Persistence| Fwd Dir (1m) | Raw (0-1) | PROMISING | None | Complementary to KER. |
| ATR-Scaled Trend | Fwd Ret (5m) | - | PROMISING | None | Good for longer horizon. |
| EMA Structure | Fwd Dir (3m) | Categorical | WEAK | None | Too lagging for microstructure decisions. |
| HMM Regime | Regime State | - | RESEARCH_ONLY | High | Risk of Viterbi look-ahead if not strictly filtered. |
| PELT (Structural Break)| Regime State | - | RESEARCH_ONLY | Mod | Look-back only calculation required. |

## 3. Momentum Family
| Feature | Target | Normalization | Evidence Status | Look-Ahead Risk | Notes |
|---------|--------|---------------|-----------------|-----------------|-------|
| Momentum Z-score | Fwd Ret (1m) | Robust Z-Score| VALIDATED | None | Strong core feature when trend-aligned. |
| Momentum Acceleration | Fwd Ret (1m) | Robust Z-Score| PROMISING | None | Needs smoothing to avoid noise. |

## 4. Liquidity & Microstructure Family
| Feature | Target | Normalization | Evidence Status | Look-Ahead Risk | Notes |
|---------|--------|---------------|-----------------|-----------------|-------|
| Spread | Liquidity | Z-Score / Pctl| VALIDATED | None | Low spread = high conviction regime. |
| Queue Imbalance | Fwd Dir (1-3m) | Raw (-1 to 1) | VALIDATED | None | Leading indicator of immediate order flow. |
| Depth Imbalance | Fwd Dir (3-5m) | Raw (-1 to 1) | PROMISING | None | L2 version of queue imbalance. |
| Microprice | Fwd Dir (1m) | Z-Score (vs Mid)| VALIDATED | None | Excellent when combined with CVD. |
| Book Slope | Liq / Vol | Z-Score | PROMISING | None | Elasticity proxy. |
| Book Concentration | Liq | Percentile | WEAK | None | Often redundant with Spread/Slope. |
| Visible Impact | Vol-Adj Ret | Z-Score | PROMISING | None | Best proxy for displacement risk. |
| Amihud | Liq Regime | Log Z-Score | WEAK | None | Stale for fast crypto microstructure. |

## 5. Order Flow & Advanced Data Family
| Feature | Target | Normalization | Evidence Status | Look-Ahead Risk | Notes |
|---------|--------|---------------|-----------------|-----------------|-------|
| CVD | Fwd Dir (1m) | Z-Score (Diff) | VALIDATED | None | Most important aggressive flow feature. |
| TVI | Fwd Dir (1m) | Raw Ratio | PROMISING | None | Complementary to CVD. |
| Canonical OFI | - | - | UNAVAILABLE | - | Requires tick-level non-gapped L1. |
| Volume Z-Score | Momentum | Robust Z-Score| PROMISING | None | Validates price moves. |
| VWAP Deviation | Fwd Ret (3m) | Z-Score | PROMISING | High | Must use strict trailing VWAP. |
| Open Interest (Delta) | Fwd Dir (5m) | Diff Z-Score | INSUFFICIENT_DATA| None | Waiting for history accumulation. |
| Funding Z-Score | Mean Reversion | Robust Z-Score| INSUFFICIENT_DATA| None | Waiting for history accumulation. |
| Liquidations | - | - | UNAVAILABLE | - | Data absent. |
| FGV (Fair Value Gap) | Fwd Ret (5m) | - | RESEARCH_ONLY | Mod | Needs strict non-overlapping mathematical rules. |
| CISD | Regime State | - | RESEARCH_ONLY | None | Handled via Structural Breaks. |
