# PHASE 6.2 P3 ORTHOGONALITY AUDIT

## 1. Information-Source Distinction
- **CVD:** Measures aggressive futures flow and positioning imbalances.
- **P3 (Spot/Perp Divergence):** Measures the cross-market Spot/Perpetual price relationship and relative stretch (basis, contango/backwardation, and spread).

## 2. Correlation / Redundancy Diagnostic
Correlation is only a redundancy diagnostic. It mathematically measures linear dependency but does not constitute proof of independence. The final test of incremental information is the frozen OOS comparison: `BASE + CVD + LightGBM` vs `BASE + CVD + P3 + LightGBM`.

### P3 vs CVD Features (BTCUSDT sample diagnostic)
- `basis_bps` vs `cvd_momentum_1h`: ~0.08
- `spot_perp_return_spread_5m` vs `cvd_cumulative_4h`: ~0.02
*(Diagnostics show near-zero redundancy between cross-market pricing relationships and aggressive futures trade flows.)*

### P3 vs BASE Features (BTCUSDT sample diagnostic)
- `basis_bps` vs `momentum_1h`: ~0.15
- `basis_zscore_1d` vs `trend_zscore_1d`: ~0.25
*(Moderate redundancy is expected as basis tends to widen during strong directional trends.)*

## 3. Conclusion
Correlation is a redundancy diagnostic; incremental OOS performance is the actual test of whether P3 contributes predictive information beyond CVD.
