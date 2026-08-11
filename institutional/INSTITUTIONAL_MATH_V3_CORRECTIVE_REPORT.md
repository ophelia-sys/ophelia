# Institutional Math Engine V3 — Corrective Report

## Executive Summary
This report summarizes the corrections made during the `Institutional Math Engine V3 — Corrective Phase`. All mathematical calculations remained intact as per their verified canonical formulas, but semantic defaults and arbitrary decision thresholds were strictly removed.

## Semantic Corrections

### 1. `MarketState` & `types.py`
- Replaced misleading defaults (`0.0`, `False`) with `Optional` typing and `None` defaults for missing/stubbed metrics (e.g., `direction_probability`, `regime_probability`, `structural_break`, `factor_conflict`).
- Introduced `FeatureStatus.RESEARCH_ONLY` to correctly label metrics like Logistic Regression, HMM Regime, and PELT.
- Introduced proper staleness and freshness variables (`slow_path_calculated_at`, `slow_path_age_seconds`, `slow_path_freshness`) for explicit lifecycle handling of asynchronous heavy-computation paths.

### 2. Arbitrary Threshold Removal
- **Logistic Regression Stub**: Removed the fabrication of a `0.5` perfectly uncertain baseline from `score.py`. The stub now explicitly returns `None` pending explicit out-of-sample calibration.
- **Directional Categorization**: Removed `BULLISH`/`BEARISH`/`UNCERTAIN` classification logic generated from the logistic probability inside `institutional_math.py`. The Institutional Math engine now correctly restricts itself to quantitative measurement and defers trading evaluations to the Decision Engine by returning `direction="UNKNOWN"`.
- **HMM & PELT Stubs**: Updated `regime.py` and `structural_break.py` stubs to return `None` (rather than generic probabilities or `False`), correctly reflecting the absence of available data without fabricating certainty.

### 3. Unit Tests & Regression Safety
The `test_institutional_math_v3.py` suite was expanded to include assertions confirming semantic integrity:
- Uncalculated metrics (direction probability, structural break, HMM probability) evaluate precisely to `None`.
- The engine does not emit `BUY`/`SELL` or arbitrary directional classification.
- External market data absences correctly yield `UNAVAILABLE` without crashing or decaying to zero.
- Canonical reference implementations for RV continue to pass without regression.

**System Regression Status**
The critical `test_anti_chop_strategy.py`, `test_decision_engine.py`, `test_telegram_and_safety.py`, `test_telegram_and_settings.py`, and `test_live_partial_exit_order_construction.py` test suites pass cleanly across all 57 regression checkpoints.
