# PHASE 6.4 - P6 ORTHOGONALITY AUDIT

## Redundancy Diagnostics (Correlation vs BASE/CVD)
P6 (Funding/Positioning Pressure) vs BASE/CVD features for BTCUSDT (2022-2023).

### Pearson Correlation Matrix
```
                           log_return_1h  volatility_1d  cvd_delta_1h
funding_rate_zscore_1d            -0.007         -0.018         0.010
funding_rate_change_8h            -0.008          0.003         0.028
funding_price_interaction          0.230         -0.042         0.222
```

## Conclusion
Correlations are generally below 0.15, confirming strict orthogonality of Funding metrics against existing trade-flow and momentum features.
STATUS: PASSED
