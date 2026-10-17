# Phase 7: Short Feature Analysis Report

**Test AUC**: 0.6812

### Feature Importance
| Feature | Importance |
|---|---|
| atr_pct_14 | 417 |
| vol_ratio | 384 |
| cvd_acceleration_1h | 225 |
| realized_vol_20 | 204 |
| cvd_zscore_1h | 195 |
| mom_10 | 183 |
| ret_5 | 177 |
| ret_1 | 147 |
| ret_3 | 138 |
| cvd_imbalance_1h | 123 |
| cvd_delta_1h | 111 |
| cvd_imbalance_15m | 104 |
| cvd_zscore_15m | 104 |
| cvd_imbalance_5m | 104 |
| cvd_acceleration_15m | 74 |
| cvd_delta_15m | 70 |
| cvd_zscore_5m | 70 |
| cvd_delta_5m | 51 |

**Conclusion**: The 18 standard Phase 7 features provide significant predictive power on the short side. We will train the short models using the exact same feature schema to preserve symmetry and parity.