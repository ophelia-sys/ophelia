import numpy as np
from fractional_differencing import get_ffd_weights, apply_ffd
import time

def run_tests():
    print("=== 1. WEIGHT LENGTH CALCULATION ===")
    d = 0.55
    threshold = 1e-4
    weights = get_ffd_weights(d, threshold=threshold)
    w_len = len(weights)
    print(f"Parameters: d={d}, threshold={threshold}")
    print(f"Weight Count (w_len): {w_len}")
    warmup_bars = w_len - 1
    print(f"Warmup Bars: {warmup_bars}")
    warmup_mins = warmup_bars * 5
    print(f"Warmup Duration (minutes): {warmup_mins}")
    print(f"Warmup Duration (hours): {warmup_mins / 60.0:.2f}")
    
    print("\n=== 2. MATHEMATICAL PARITY TESTS ===")
    series = np.arange(10, dtype=float) ** 2
    
    # Test d=1 (First Difference)
    weights_d1 = get_ffd_weights(1.0, threshold=threshold)
    out_d1 = apply_ffd(series, weights_d1)
    expected_d1 = series - np.roll(series, 1)
    # The first row will be NaN in out_d1 because len(weights_d1) == 2 -> warmup is 1
    expected_d1[0] = np.nan
    np.testing.assert_array_almost_equal(out_d1[1:], expected_d1[1:])
    print("PASS: apply_ffd(d=1.0) matches first discrete difference exactly (after warmup)")
    
    # Test d=0 (Identity)
    weights_d0 = get_ffd_weights(0.0, threshold=threshold)
    out_d0 = apply_ffd(series, weights_d0)
    # No warmup (len=1 -> warmup=0)
    np.testing.assert_array_almost_equal(out_d0, series)
    print("PASS: apply_ffd(d=0.0) matches original series exactly")
    
    print("\n=== 3. CAUSALITY AND WARMUP AUDIT ===")
    # Test full-window masking (warmup)
    series_causal = np.random.randn(2000)
    out_causal = apply_ffd(series_causal, weights)
    nan_count = np.isnan(out_causal).sum()
    assert nan_count == warmup_bars
    print(f"PASS: output has exactly {nan_count} leading NaNs, matching warmup_bars.")
    
    # Test Causality: If we change a future value, current output shouldn't change
    series_mut = series_causal.copy()
    series_mut[1500] = 999.0
    out_mut = apply_ffd(series_mut, weights)
    
    np.testing.assert_array_almost_equal(out_causal[:1500], out_mut[:1500])
    print("PASS: Causality check. Future values do not affect past/current outputs.")

    print("\n=== 4. DETERMINISTIC REPEATABILITY TESTS ===")
    out1 = apply_ffd(series_causal, weights)
    out2 = apply_ffd(series_causal, weights)
    np.testing.assert_array_equal(out1, out2)
    print("PASS: Repeated calls yield identical results.")
    
if __name__ == "__main__":
    run_tests()
