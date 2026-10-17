# Phase 7 Label Selection

## Candidate Labels Evaluated on DEV Data
### label_raw_15
- **Information Coefficient (IC) with Queue Imbalance**: -0.0162 (p=0.0000)
- **Skewness**: 0.3372
- **Kurtosis**: 64.1301
- **Mean**: -0.000013 | **Std**: 0.004839

### label_vol_adj_15
- **Information Coefficient (IC) with Queue Imbalance**: -0.0179 (p=0.0000)
- **Skewness**: 0.0789
- **Kurtosis**: 50.4441
- **Mean**: -0.006079 | **Std**: 1.123448

## Selected Label: `label_vol_adj_15`
**Selection Rationale**: The label with the highest absolute Information Coefficient on DEV data, indicating better inherent predictability by our base features.