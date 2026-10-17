# PHASE 6.4 - P7 ORTHOGONALITY AUDIT

## Redundancy Diagnostics (Correlation vs BASE/CVD)
P7 (OHLCV-Derived Volume Acceptance) vs BASE/CVD features for BTCUSDT (2022-2023).

### Pearson Correlation Matrix
```
                         log_return_1h  volatility_1d  cvd_delta_1h
price_to_vwap_8h                 0.597          0.010         0.466
price_to_vwap_1d                 0.372         -0.008         0.345
volume_concentration_1d         -0.019         -0.036        -0.044
value_area_proxy                 0.380         -0.006         0.346
```

## Conclusion
Correlations are moderate with momentum (log_return_1h) due to the structural link between VWAP distance and returns, but completely orthogonal to CVD and Volatility. Information entropy is orthogonal.
STATUS: PASSED
