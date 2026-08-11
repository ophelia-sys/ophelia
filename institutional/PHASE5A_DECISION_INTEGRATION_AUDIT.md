# Phase 5A: Decision Integration Audit

## 1. Architecture Diagram

```mermaid
flowchart TD
    subgraph Data Generation
        BXC[BingXClient] --> MD[MarketData]
        MD --> df[df_1m / df_5m]
    end

    subgraph Strategy Layer
        df --> S[Strategy: AntiChopEMA]
        S --> Sig[Signal: BUY/SELL/HOLD]
    end

    subgraph Decision Pipeline
        Sig --> DE[DecisionEngine]
        df --> DE
        
        DE --> |LEGACY CALL| OIM[core.institutional_math]
        OIM --> MA[MathAnalysis: Legacy]
        MA --> DE
        
        DE --> KP[KronosProvider]
    end
    
    subgraph Risk & Execution
        DE --> |Approved Signal| TE[TradingEngine]
        TE --> RM[RiskManager]
        RM --> OM_EXEC[OrderManager]
        OM_EXEC --> API[BingX API]
    end
    
    subgraph V3 Architecture (Currently Isolated)
        Snap[MarketDataSnapshot] --> V3[institutional.institutional_math]
        V3 --> MS[MarketState]
        MS -.-> |DISCONNECTED| DE
    end
```

## 2. Feature Lineage Matrix

| Feature | Source | Calculation | Target Field | Consumer | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Volatility | `core.institutional_math` | BBS + RVOL | `volatility_score` | `DecisionEngine` | LEGACY |
| Momentum | `core.institutional_math` | nslope + nes | `momentum_score` | `DecisionEngine` | LEGACY |
| Trend | `core.institutional_math` | er10 * 10 | `trend_persistence_score` | `DecisionEngine` | LEGACY |
| Regime | `core.institutional_math` | er10 thresholds | `market_regime` | Ignored | IGNORED |
| V3 Volatility | `institutional_math` v3 | Realized Vol + Percentile | `volatility_score` | None | UNUSED |
| V3 Momentum | `institutional_math` v3 | Robust MAD Z-score | `momentum_score` | None | UNUSED |
| V3 Trend | `institutional_math` v3 | Directional Persistence | `trend_persistence` | None | UNUSED |
| V3 Microstructure | `MarketDataSnapshot` | Orderbook parsing | `microstructure` | None | UNUSED |

**Conclusion:** The entire V3 Institutional Math architecture is currently disconnected from the live trading pipeline. `DecisionEngine` imports and consumes a legacy duplicate file: `core/institutional_math.py`.

## 3. Critical Safety Audit

- **Are Execution boundaries bypassed?** No. 
- **Can Institutional Math trigger a trade?** No. `InstitutionalMathEngine` (both legacy and V3) is strictly observational. Signals exclusively originate in the Strategy layer (`AntiChopEMAStrategy`).
- **Can Risk Manager be bypassed?** No. The `DecisionEngine` only passes approved signals to the `TradingEngine`, which rigidly passes them through `RiskManager` before execution.
- **P0 Safety Violations:** **NONE**. The system is completely secure from math-induced hallucinated trades.

## 4. Legacy vs V3 Semantic Contract

`DecisionEngine` uses the legacy `MathAnalysis` outputs to compute a 1-10 `overall_market_score`. This score influences `suggested_leverage` and `suggested_tp_buffer` (observational advisory flags). 

If we swap V3 in, we face these semantic mismatches:

| Legacy Expectation | V3 Output | Compatible? | Action Required |
| :--- | :--- | :--- | :--- |
| `volatility_score` (0-10 float) | Z-score / Percentile | **NO** | Must translate V3 percentiles into the 0-10 advisory scale. |
| `momentum_score` (0-10 float) | MAD Z-Score | **NO** | Must translate Z-scores to the 0-10 magnitude scale. |
| `trend_persistence_score` (0-10) | Raw float / ATR Scaled | **NO** | Must normalize to 0-10. |
| `market_regime` (Strings) | HMM states | **NO** | Need mapping between HMM output and CHOPPY/TRENDING labels. |

## 5. Microstructure Consumption Matrix

| Metric | Status | Note |
| :--- | :--- | :--- |
| `queue_imbalance` | **IGNORED** | Present in V3 `MarketState`, but V3 is disconnected. |
| `depth_imbalance` | **IGNORED** | Verified safely separate from OFI. Not reaching `DecisionEngine`. |
| `microprice` | **IGNORED** | Present but unused. |
| `book_slope` | **IGNORED** | Present but unused. |
| `cvd` / `tvi` | **IGNORED** | Present but unused. |
| **`ofi`** | **UNAVAILABLE** | Correctly assigned `np.nan` with no aliasing. |

## 6. Decision Logic Audit

The `DecisionEngine` approves signals based on:
1. **Advisory Scores:** Computes `overall_market_score` using Legacy Math + Kronos. This affects suggested leverage/TP.
2. **Strict Gates:** Checks `1m` and `5m` candle sizes.
   - `1m` <= 0.20% (Pass)
   - `1m` > 0.20% & <= 0.40% (Requires Kronos > 0.77 Override)
   - `1m` > 0.40% (Hard Reject)
   - Similar gates for `5m` (0.35%, 0.60%).

**Impact of V3 Integration:** Replacing the Legacy math with V3 will alter the calculation of `overall_market_score`. We must ensure V3 metrics are accurately scaled (0-10) so the advisory leverage/TP suggestions behave as expected.

## 7. Risk / Execution Audit

The boundary is flawless:
`Signal -> DecisionEngine -> TradingEngine -> RiskManager -> OrderManager`
There are no shortcuts or bypasses.

## 8. Test Coverage Audit

- **DecisionEngine:** Well covered for boundary conditions (candle sizes, Kronos overrides).
- **InstitutionalMath (V3):** Well covered for nan handling, valid calculations, and microstructure logic.
- **MISSING:** We lack integration tests that verify `Scanner` -> `MarketDataSnapshot` -> `InstitutionalMathEngine V3` -> `DecisionEngine`. Currently, tests mock or use the legacy engine.

## 9. P0 / P1 / P2 Findings

- **[P0 - Critical Safety]**: None.
- **[P1 - Architectural Debt]**: V3 is entirely disconnected. `core.institutional_math.py` is a duplicate legacy system currently running the live logic.
- **[P2 - Semantic Mismatch]**: V3 features use true statistical outputs (Z-scores, probability), but `DecisionEngine` expects 0-10 scaled floats.

## 10. Recommended Phase 5B Implementation Order

1. **Adapter / Translation Layer:** Update `institutional/score.py` (or create a translation layer) to convert V3 robust statistical outputs into the 0-10 legacy scale expected by `DecisionEngine`.
2. **Integration:** Update `core/decision_engine.py` to import `institutional.institutional_math.InstitutionalMathEngine`.
3. **Plumbing:** Ensure `Scanner` or `DecisionEngine` constructs the `MarketDataSnapshot` correctly before passing it to V3.
4. **Deprecation:** Delete `core/institutional_math.py`.
5. **Testing:** Write end-to-end integration tests proving V3 safely feeds the decision pipeline without breaking strict candle gates.
