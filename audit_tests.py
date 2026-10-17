import pandas as pd
import numpy as np

# Test 1: Realized Volatility
# RV = sqrt(sum(r_i^2))
returns = np.array([0.01, -0.02, 0.015, -0.005, 0.008])
expected_rv = np.sqrt(np.sum(returns**2))
print(f"Expected RV: {expected_rv}")

# Test 2: Parkinson Volatility
# sigma_P = sqrt( 1/(4*ln(2)) * sum(ln(H/L)^2) )
high = np.array([101, 102, 101.5])
low = np.array([100, 100, 99.5])
hl_log_sq = np.log(high/low)**2
factor = 1.0 / (4.0 * np.log(2.0))
expected_parkinson = np.sqrt(factor * np.sum(hl_log_sq))
print(f"Expected Parkinson: {expected_parkinson}")

# Test 3: Garman-Klass
# sigma_GK = sqrt( sum( 0.5*ln(H/L)^2 - (2ln2 - 1)*ln(C/O)^2 ) )
open_p = np.array([100.5, 101, 100])
high_p = np.array([101, 102, 101.5])
low_p = np.array([100, 100, 99.5])
close_p = np.array([100.8, 100.5, 101])

hl_term = 0.5 * (np.log(high_p/low_p)**2)
co_term = (2*np.log(2) - 1) * (np.log(close_p/open_p)**2)
gk_sq = np.sum(hl_term - co_term)
expected_gk = np.sqrt(max(0, gk_sq))
print(f"Expected Garman-Klass: {expected_gk}")

# Test 4: ATR
# TR = max(H-L, |H-Cp|, |L-Cp|)
high_a = np.array([105, 106, 107])
low_a = np.array([100, 102, 104])
close_prev = np.array([99, 104, 105]) # using previous close
tr1 = high_a - low_a
tr2 = np.abs(high_a - close_prev)
tr3 = np.abs(low_a - close_prev)
true_ranges = np.maximum(tr1, np.maximum(tr2, tr3))
expected_atr = np.mean(true_ranges)
print(f"Expected ATR: {expected_atr}")

# Test 5: Kaufman ER
close_k = np.array([100, 102, 101, 105])
direction = np.abs(close_k[-1] - close_k[0])
volatility = np.sum(np.abs(np.diff(close_k)))
expected_er = direction / volatility
print(f"Expected ER: {expected_er}")

# Test 6: MAD Z-score
series = np.array([1, 2, 3, 4, 100])
median = np.median(series)
mad = np.median(np.abs(series - median))
robust_std = mad * 1.4826
expected_mad_z = (100 - median) / robust_std
print(f"Expected MAD Z-Score (100): {expected_mad_z}")

# Test 7: ECDF
s = np.array([10, 20, 30, 40, 50])
val = 40
expected_ecdf = (np.sum(s < val) / len(s)) * 100
print(f"Expected ECDF (40): {expected_ecdf}")

# Test 8: Depth Imbalance
bid_v = 150.0
ask_v = 50.0
expected_depth = (bid_v - ask_v) / (bid_v + ask_v)
print(f"Expected Depth Imbalance: {expected_depth}")

# Test 9: Entropy
p = np.array([0.5, 0.25, 0.25])
expected_entropy = -np.sum(p * np.log2(p))
print(f"Expected Entropy: {expected_entropy}")
