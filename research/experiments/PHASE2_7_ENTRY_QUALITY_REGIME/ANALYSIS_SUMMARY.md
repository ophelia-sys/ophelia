# OPHELIA — PHASE 2.7 ENTRY QUALITY REPORT
## OVERVIEW
Analysis of pre-entry structural features distinguishing successful 1R continuation trades from failures.

### Top Feature Differences (COMBINED)
| Feature | Cont Mean | Fail Mean | Cont Med | Fail Med | Diff |
|---|---:|---:|---:|---:|---:|
| hour_utc | 11.303 | 10.872 | 11.000 | 10.000 | +1.000 |
| htf_1h_dist_200ma | -1.317 | -0.898 | -1.401 | -0.635 | -0.766 |
| htf_1h_dist_50ma | -0.404 | -0.056 | -0.329 | 0.241 | -0.571 |
| htf_1h_ret_3 | -0.017 | -0.035 | 0.170 | -0.057 | +0.227 |
| ret_6 | -0.152 | -0.050 | -0.277 | -0.172 | -0.105 |
| ret_3 | -0.129 | -0.043 | -0.228 | -0.131 | -0.097 |
| ret_1 | -0.010 | -0.025 | 0.004 | -0.039 | +0.043 |
| st_slope_1 | -0.026 | -0.004 | -0.067 | -0.029 | -0.038 |
| price_vwap_dist | 0.840 | 0.889 | 0.768 | 0.739 | +0.029 |
| body_pct | 0.453 | 0.478 | 0.446 | 0.425 | +0.021 |
| htf_1h_atr | 0.688 | 0.677 | 0.690 | 0.670 | +0.020 |
| body_atr | 0.611 | 0.582 | 0.466 | 0.484 | -0.017 |
| risk_pct | 0.791 | 0.839 | 0.762 | 0.745 | +0.017 |
| price_st_dist | 0.779 | 0.831 | 0.749 | 0.735 | +0.014 |
| atr_pct | 0.201 | 0.206 | 0.185 | 0.173 | +0.012 |
| st_slope_3 | -0.027 | 0.004 | -0.018 | -0.029 | +0.011 |
| sep_pct | 0.061 | 0.058 | 0.048 | 0.039 | +0.009 |
| range_atr | 1.334 | 1.192 | 1.096 | 1.089 | +0.007 |
| vwap_slope_3 | -0.013 | 0.001 | -0.006 | -0.006 | +0.000 |
| vwap_slope_1 | -0.005 | 0.000 | -0.003 | -0.003 | -0.000 |
| vwap_crosses_12 | 0.970 | 0.744 | 1.000 | 1.000 | +0.000 |

### Top Feature Differences (LONG)
| Feature | Cont Mean | Fail Mean | Cont Med | Fail Med | Diff |
|---|---:|---:|---:|---:|---:|
| htf_1h_dist_200ma | -1.991 | -0.426 | -1.656 | -0.079 | -1.576 |
| htf_1h_dist_50ma | -0.003 | 0.595 | 0.272 | 0.821 | -0.549 |
| hour_utc | 12.214 | 10.706 | 11.500 | 11.000 | +0.500 |
| price_vwap_dist | 0.722 | 0.930 | 0.610 | 0.903 | -0.293 |
| risk_pct | 0.678 | 0.882 | 0.569 | 0.830 | -0.261 |
| price_st_dist | 0.669 | 0.873 | 0.559 | 0.819 | -0.260 |
| body_atr | 0.550 | 0.491 | 0.505 | 0.275 | +0.230 |
| ret_6 | 0.432 | 0.518 | 0.358 | 0.534 | -0.176 |
| ret_3 | 0.240 | 0.348 | 0.139 | 0.296 | -0.156 |
| htf_1h_ret_3 | 0.571 | 0.477 | 0.354 | 0.202 | +0.152 |
| body_pct | 0.473 | 0.404 | 0.445 | 0.302 | +0.143 |
| htf_1h_atr | 0.610 | 0.681 | 0.623 | 0.730 | -0.107 |
| atr_pct | 0.178 | 0.220 | 0.144 | 0.227 | -0.082 |
| st_slope_3 | 0.110 | 0.176 | 0.092 | 0.153 | -0.060 |
| ret_1 | 0.048 | 0.069 | 0.061 | 0.020 | +0.041 |
| range_atr | 1.450 | 1.116 | 1.046 | 1.017 | +0.030 |
| st_slope_1 | 0.081 | 0.107 | 0.050 | 0.078 | -0.028 |
| vwap_slope_3 | 0.013 | 0.022 | 0.009 | 0.015 | -0.006 |
| sep_pct | 0.054 | 0.057 | 0.042 | 0.036 | +0.006 |
| vwap_slope_1 | 0.005 | 0.009 | 0.003 | 0.006 | -0.003 |
| vwap_crosses_12 | 1.286 | 1.235 | 1.000 | 1.000 | +0.000 |

### Top Feature Differences (SHORT)
| Feature | Cont Mean | Fail Mean | Cont Med | Fail Med | Diff |
|---|---:|---:|---:|---:|---:|
| hour_utc | 10.632 | 11.000 | 11.000 | 9.000 | +2.000 |
| price_vwap_dist | 0.926 | 0.857 | 0.939 | 0.704 | +0.235 |
| htf_1h_dist_200ma | -0.811 | -1.203 | -1.167 | -0.954 | -0.213 |
| risk_pct | 0.874 | 0.806 | 0.856 | 0.696 | +0.160 |
| body_atr | 0.656 | 0.652 | 0.408 | 0.560 | -0.152 |
| price_st_dist | 0.861 | 0.799 | 0.820 | 0.686 | +0.134 |
| htf_1h_dist_50ma | -0.695 | -0.552 | -0.565 | -0.456 | -0.109 |
| htf_1h_atr | 0.745 | 0.673 | 0.733 | 0.644 | +0.089 |
| body_pct | 0.437 | 0.536 | 0.459 | 0.547 | -0.088 |
| ret_6 | -0.583 | -0.489 | -0.434 | -0.360 | -0.074 |
| htf_1h_ret_3 | -0.451 | -0.431 | -0.345 | -0.405 | +0.060 |
| range_atr | 1.249 | 1.250 | 1.160 | 1.103 | +0.057 |
| ret_1 | -0.053 | -0.098 | -0.032 | -0.083 | +0.051 |
| atr_pct | 0.218 | 0.194 | 0.196 | 0.155 | +0.041 |
| st_slope_3 | -0.128 | -0.129 | -0.150 | -0.115 | -0.035 |
| st_slope_1 | -0.105 | -0.090 | -0.096 | -0.073 | -0.024 |
| sep_pct | 0.066 | 0.059 | 0.059 | 0.047 | +0.011 |
| vwap_slope_3 | -0.033 | -0.016 | -0.016 | -0.012 | -0.004 |
| vwap_slope_1 | -0.012 | -0.006 | -0.006 | -0.004 | -0.002 |
| ret_3 | -0.401 | -0.344 | -0.298 | -0.299 | +0.001 |
| vwap_crosses_12 | 0.737 | 0.364 | 0.000 | 0.000 | +0.000 |

### OOS Bin Monotonicity
| Direction | Feature | Split | Bin 0 (1R %) | Bin 1 (1R %) | Bin 2 (1R %) |
|---|---|---|---:|---:|---:|
| LONG | risk_pct | DEV | 63.6% | 50.0% | 20.0% |
| LONG | risk_pct | VAL | 85.7% | 20.0% | 100.0% |
| LONG | risk_pct | HOLDOUT | 50.0% | 66.7% | 100.0% |
| LONG | sep_pct | DEV | 36.4% | 60.0% | 40.0% |
| LONG | sep_pct | VAL | 75.0% | 40.0% | 75.0% |
| LONG | sep_pct | HOLDOUT | 57.1% | 80.0% | 100.0% |
| LONG | vwap_slope_1 | DEV | 63.6% | 40.0% | 30.0% |
| LONG | vwap_slope_1 | VAL | 50.0% | 100.0% | 50.0% |
| LONG | vwap_slope_1 | HOLDOUT | 33.3% | 100.0% | 100.0% |
| LONG | vwap_slope_3 | DEV | 72.7% | 30.0% | 30.0% |
| LONG | vwap_slope_3 | VAL | 57.1% | 100.0% | 50.0% |
| LONG | vwap_slope_3 | HOLDOUT | 33.3% | 100.0% | 100.0% |
| LONG | st_slope_1 | DEV | 54.5% | 50.0% | 30.0% |
| LONG | st_slope_1 | VAL | 66.7% | 75.0% | 50.0% |
| LONG | st_slope_1 | HOLDOUT | 66.7% | 60.0% | 100.0% |
| LONG | st_slope_3 | DEV | 54.5% | 40.0% | 40.0% |
| LONG | st_slope_3 | VAL | 100.0% | 60.0% | 40.0% |
| LONG | st_slope_3 | HOLDOUT | 60.0% | 60.0% | 100.0% |
| LONG | body_pct | DEV | 45.5% | 40.0% | 50.0% |
| LONG | body_pct | VAL | 33.3% | 75.0% | 66.7% |
| LONG | body_pct | HOLDOUT | 66.7% | 71.4% | 75.0% |
| LONG | range_atr | DEV | 36.4% | 40.0% | 60.0% |
| LONG | range_atr | VAL | 33.3% | 0.0% | 85.7% |
| LONG | range_atr | HOLDOUT | 33.3% | 100.0% | 66.7% |
| LONG | body_atr | DEV | 27.3% | 60.0% | 50.0% |
| LONG | body_atr | VAL | 50.0% | 25.0% | 83.3% |
| LONG | body_atr | HOLDOUT | 60.0% | 100.0% | 71.4% |
| LONG | ret_1 | DEV | 36.4% | 50.0% | 50.0% |
| LONG | ret_1 | VAL | 50.0% | 33.3% | 75.0% |
| LONG | ret_1 | HOLDOUT | 33.3% | 80.0% | 80.0% |
| LONG | ret_3 | DEV | 45.5% | 60.0% | 30.0% |
| LONG | ret_3 | HOLDOUT | 50.0% | 62.5% | 100.0% |
| LONG | ret_6 | DEV | 54.5% | 50.0% | 30.0% |
| LONG | ret_6 | VAL | 57.1% | 75.0% | 50.0% |
| LONG | ret_6 | HOLDOUT | 57.1% | 75.0% | 100.0% |
| LONG | price_st_dist | DEV | 63.6% | 50.0% | 20.0% |
| LONG | price_st_dist | VAL | 85.7% | 20.0% | 100.0% |
| LONG | price_st_dist | HOLDOUT | 50.0% | 66.7% | 100.0% |
| LONG | price_vwap_dist | DEV | 72.7% | 30.0% | 30.0% |
| LONG | price_vwap_dist | VAL | 85.7% | 20.0% | 100.0% |
| LONG | price_vwap_dist | HOLDOUT | 62.5% | 50.0% | 100.0% |
| LONG | atr_pct | DEV | 63.6% | 40.0% | 30.0% |
| LONG | atr_pct | VAL | 85.7% | 0.0% | 100.0% |
| LONG | atr_pct | HOLDOUT | 66.7% | 50.0% | 100.0% |
| LONG | hour_utc | DEV | 36.4% | 45.5% | 55.6% |
| LONG | hour_utc | VAL | 71.4% | 50.0% | 50.0% |
| LONG | hour_utc | HOLDOUT | 100.0% | 50.0% | 100.0% |
| LONG | htf_1h_dist_200ma | DEV | 57.1% | 66.7% | 14.3% |
| LONG | htf_1h_dist_200ma | VAL | 100.0% | 100.0% | 44.4% |
| LONG | htf_1h_dist_50ma | DEV | 60.0% | 55.6% | 20.0% |
| LONG | htf_1h_dist_50ma | VAL | 100.0% | 33.3% | 66.7% |
| LONG | htf_1h_dist_50ma | HOLDOUT | 100.0% | 33.3% | 100.0% |
| LONG | htf_1h_ret_3 | DEV | 27.3% | 70.0% | 40.0% |
| LONG | htf_1h_ret_3 | VAL | 0.0% | 75.0% | 66.7% |
| LONG | htf_1h_ret_3 | HOLDOUT | 50.0% | 70.0% | 100.0% |
| LONG | htf_1h_atr | DEV | 63.6% | 50.0% | 20.0% |
| SHORT | risk_pct | DEV | 28.6% | 61.5% | 50.0% |
| SHORT | risk_pct | VAL | 20.0% | 66.7% | 100.0% |
| SHORT | risk_pct | HOLDOUT | 75.0% | 0.0% | 0.0% |
| SHORT | sep_pct | DEV | 35.7% | 53.8% | 50.0% |
| SHORT | sep_pct | VAL | 0.0% | 50.0% | 50.0% |
| SHORT | sep_pct | HOLDOUT | 33.3% | 33.3% | 33.3% |
| SHORT | vwap_slope_1 | DEV | 64.3% | 38.5% | 35.7% |
| SHORT | vwap_slope_1 | VAL | 0.0% | 57.1% | 33.3% |
| SHORT | vwap_slope_1 | HOLDOUT | 50.0% | 33.3% | 0.0% |
| SHORT | vwap_slope_3 | DEV | 64.3% | 38.5% | 35.7% |
| SHORT | vwap_slope_3 | VAL | 50.0% | 50.0% | 0.0% |
| SHORT | vwap_slope_3 | HOLDOUT | 50.0% | 25.0% | 0.0% |
| SHORT | st_slope_1 | DEV | 57.1% | 53.8% | 28.6% |
| SHORT | st_slope_1 | VAL | 100.0% | 25.0% | 40.0% |
| SHORT | st_slope_1 | HOLDOUT | 0.0% | 100.0% | 40.0% |
| SHORT | st_slope_3 | DEV | 57.1% | 46.2% | 35.7% |
| SHORT | st_slope_3 | VAL | 0.0% | 57.1% | 33.3% |
| SHORT | st_slope_3 | HOLDOUT | 0.0% | 100.0% | 28.6% |
| SHORT | body_pct | DEV | 57.1% | 46.2% | 35.7% |
| SHORT | body_pct | VAL | 33.3% | 0.0% | 80.0% |
| SHORT | body_pct | HOLDOUT | 33.3% | 50.0% | 33.3% |
| SHORT | range_atr | DEV | 50.0% | 30.8% | 57.1% |
| SHORT | range_atr | VAL | 33.3% | 50.0% | 0.0% |
| SHORT | range_atr | HOLDOUT | 0.0% | 50.0% | 50.0% |
| SHORT | body_atr | DEV | 50.0% | 46.2% | 42.9% |
| SHORT | body_atr | VAL | 0.0% | 75.0% | 66.7% |
| SHORT | body_atr | HOLDOUT | 0.0% | 75.0% | 50.0% |
| SHORT | ret_1 | DEV | 50.0% | 23.1% | 64.3% |
| SHORT | ret_1 | VAL | 100.0% | 50.0% | 0.0% |
| SHORT | ret_1 | HOLDOUT | 0.0% | 66.7% | 0.0% |
| SHORT | ret_3 | DEV | 50.0% | 53.8% | 35.7% |
| SHORT | ret_3 | VAL | 50.0% | 50.0% | 40.0% |
| SHORT | ret_3 | HOLDOUT | 0.0% | 0.0% | 57.1% |
| SHORT | ret_6 | DEV | 50.0% | 61.5% | 28.6% |
| SHORT | ret_6 | VAL | 100.0% | 50.0% | 20.0% |
| SHORT | ret_6 | HOLDOUT | 0.0% | 50.0% | 40.0% |
| SHORT | price_st_dist | DEV | 28.6% | 61.5% | 50.0% |
| SHORT | price_st_dist | VAL | 33.3% | 50.0% | 100.0% |
| SHORT | price_st_dist | HOLDOUT | 75.0% | 0.0% | 0.0% |
| SHORT | price_vwap_dist | DEV | 21.4% | 69.2% | 50.0% |
| SHORT | price_vwap_dist | VAL | 20.0% | 66.7% | 100.0% |
| SHORT | price_vwap_dist | HOLDOUT | 50.0% | 0.0% | 0.0% |
| SHORT | atr_pct | DEV | 14.3% | 76.9% | 50.0% |
| SHORT | atr_pct | VAL | 37.5% | 100.0% | 50.0% |
| SHORT | hour_utc | DEV | 57.1% | 38.5% | 42.9% |
| SHORT | hour_utc | VAL | 50.0% | 33.3% | 66.7% |
| SHORT | hour_utc | HOLDOUT | 50.0% | 0.0% | 50.0% |
| SHORT | htf_1h_dist_200ma | DEV | 40.0% | 44.4% | 40.0% |
| SHORT | htf_1h_dist_50ma | DEV | 38.5% | 61.5% | 38.5% |
| SHORT | htf_1h_dist_50ma | VAL | 0.0% | 50.0% | 60.0% |
| SHORT | htf_1h_ret_3 | DEV | 57.1% | 30.8% | 50.0% |
| SHORT | htf_1h_ret_3 | VAL | 50.0% | 37.5% | 100.0% |
| SHORT | htf_1h_ret_3 | HOLDOUT | 0.0% | 66.7% | 0.0% |
| SHORT | htf_1h_atr | DEV | 28.6% | 69.2% | 42.9% |