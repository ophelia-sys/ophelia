---
phase: 6D.1
plan: 1
wave: 1
gap_closure: false
---

# Plan 6D.1.1: Econometric Hardening — VECM Sample Governance, Gonzalo-Granger Out-of-Range Handling, Cumulative Impact Renaming & Hasbrouck Robustness

## Objective
Harden and mathematically discipline the Phase 6D econometric implementations before integrated evaluation:
1. Establish a mathematically defensible minimum sample threshold ($N_{\text{min}} \ge 300$) for VECM cointegration based on parameter degrees of freedom ($K=2$, lag $p$, deterministic constants, and Johansen asymptotic distribution requirements), returning `INSUFFICIENT_SAMPLE` for $N < 300$.
2. Preserve raw unbounded Gonzalo-Granger component shares (`gg_share_1_raw`, `gg_share_2_raw`), document denominator $|\alpha_2 - \alpha_1|$ behavior, flag `gg_share_in_range = False` when shares fall outside $[0, 1]$, and expose an explicit separately named bounded speed share `bounded_speed_share = |\alpha_2| / (|\alpha_1| + |\alpha_2|)`.
3. Rename the 20-step IRF summation to `cumulative_impact_H20`, and only populate `permanent_impact` when a documented spectral radius / convergence criterion is verified ($|\Theta_{21, H} - \Theta_{21, H-1}| < 10^{-6}$ and $|\lambda_{\text{max}}|^H < 10^{-4}$).
4. Add a size-aware signed-volume robustness specification ($x_t^{\text{vol}} = \text{sign}_t \cdot \sqrt{\text{volume}_t}$) for Hasbrouck VAR alongside primary $x_t \in \{-1, +1\}$.
5. Increment methodology versions to `HASBROUCK_STYLE_V1.1` and `VECM_STYLE_V1.1` preserving backward reproducibility.

## Context
Load these files for context:
- models/microstructure.py
- control_plane/microstructure_engine.py
- control_plane/db.py
- control_plane/api.py
- tests/test_microstructure_phase6d.py

## Tasks

<task type="auto">
  <name>Harden VECM sample size governance and raw/bounded Gonzalo-Granger share</name>
  <files>
    models/microstructure.py
    control_plane/microstructure_engine.py
    control_plane/db.py
    control_plane/api.py
  </files>
  <action>
    1. In models/microstructure.py and control_plane/microstructure_engine.py:
       - Update VecmEngine default min_sample_size to 300.
       - Document mathematical justification: K=2 variables, p lags (4 parameters per lag), 2 intercept terms, 2 alpha speeds, 1 beta vector, plus Johansen asymptotic rank test requires degrees of freedom T - K*p >> 250 for empirical size stability.
       - If sample_count < 300, set status = 'INSUFFICIENT_SAMPLE', cointegration_rank = None, and populate detail: {'minimum_required_sample': 300, 'actual_sample': N, 'sample_status': 'INSUFFICIENT_SAMPLE', 'justification': 'K=2 bivariate VECM with unrestricted constant requires T >= 300 for stable Johansen trace critical value evaluation'}.
       - Compute raw GG component shares: denom = alpha_2 - alpha_1. If abs(denom) < 1e-9: denom = 1e-9.
       - Store raw values as gg_share_1_raw and gg_share_2_raw.
       - Evaluate gg_share_in_range = bool(0.0 <= gg_share_1_raw <= 1.0 and 0.0 <= gg_share_2_raw <= 1.0).
       - When gg_share_in_range is False, set gg_share_1 = None, gg_share_2 = None, and record diagnostic reason: 'OUT_OF_RANGE_ALPHA_SAME_SIGN' (e.g. both alpha < 0 or both alpha > 0).
       - Add separate bounded estimator: bounded_speed_share_spot = abs(alpha_2) / (abs(alpha_1) + abs(alpha_2) + 1e-9) and bounded_speed_share_perp = abs(alpha_1) / (abs(alpha_1) + abs(alpha_2) + 1e-9).
       - Increment methodology_version to 'VECM_STYLE_V1.1'.
    2. In control_plane/db.py:
       - Update persist_microstructure_vecm and table schema to include minimum_required_sample, actual_sample, sample_status, gg_share_1_raw, gg_share_2_raw, gg_share_in_range, bounded_speed_share_1, bounded_speed_share_2.
    AVOID: Clipping raw GG shares into [0, 1].
    USE: Explicit out-of-range flag and separate bounded speed share.
  </action>
  <verify>
    .venv/Scripts/python.exe -c "from control_plane.microstructure_engine import VecmEngine; e = VecmEngine('S1', 'S2', min_sample_size=300); print('Min sample:', e.min_sample_size)"
  </verify>
  <done>
    VECM sample threshold enforced at 300; raw GG shares preserved with in-range boolean; bounded speed share exposed separately.
  </done>
</task>

<task type="auto">
  <name>Rename cumulative impact H20, implement permanent impact convergence check, and add Hasbrouck volume robustness</name>
  <files>
    models/microstructure.py
    control_plane/microstructure_engine.py
    control_plane/db.py
    control_plane/api.py
  </files>
  <action>
    1. In models/microstructure.py and control_plane/microstructure_engine.py:
       - Rename cumulative_impact to cumulative_impact_H20 on HasbrouckVarObservation.
       - Implement formal convergence evaluation over MA expansion up to horizon H=50:
         delta_irf = abs(irf_cum[h] - irf_cum[h-1])
         spectral_decay = max_eigenvalue_modulus ** h
         is_converged = (delta_irf < 1e-6 and spectral_decay < 1e-4)
       - If is_converged: permanent_impact = irf_cum[h], convergence_status = 'CONVERGED', convergence_tolerance = 1e-6.
       - If not converged: permanent_impact = None, convergence_status = 'NOT_CONVERGED'.
       - Add Hasbrouck flow-specification robustness comparison:
         primary_x_definition = 'SIGNED_INDICATOR' (x_t in {-1, +1})
         robustness_x_definition = 'SIGNED_SQRT_VOLUME' (x_t = sign * sqrt(volume))
         Fit secondary VAR on (r_t, x_t_robust) and store robustness metrics in diagnostics['robustness']:
         { 'robustness_x_definition': 'SIGNED_SQRT_VOLUME', 'is_stable': bool, 'selected_lag': int, 'cumulative_impact_H20': float, 'variance_share_flow': float, 'coefficient_direction_match': bool }
       - Increment methodology_version to 'HASBROUCK_STYLE_V1.1'.
    2. In control_plane/db.py and api.py:
       - Update database persistence and API serializers to store and expose cumulative_impact_H20, permanent_impact, convergence_status, convergence_tolerance, and methodology_version.
  </action>
  <verify>
    .venv/Scripts/python.exe -c "from control_plane.microstructure_engine import HasbrouckVarEngine; e = HasbrouckVarEngine('BTC-USDT'); print('Hasbrouck engine ready')"
  </verify>
  <done>
    Cumulative impact H20 distinguished from permanent impact; convergence status populated; signed-sqrt volume robustness comparison recorded.
  </done>
</task>

<task type="auto">
  <name>Update Unit Tests and Validate on Local and VPS with Live BingX Probes</name>
  <files>
    tests/test_microstructure_phase6d.py
    scratch/deploy_phase6d1_vps.py
  </files>
  <action>
    1. Update tests/test_microstructure_phase6d.py to reflect Phase 6D.1 governance:
       - Test VECM sample requirement (N=254 returns INSUFFICIENT_SAMPLE, N >= 300 passes).
       - Test Gonzalo-Granger out-of-range state (when alpha speeds have same sign, gg_share_in_range=False, raw preserved, bounded speed share populated).
       - Test cumulative_impact_H20 field presence and permanent impact convergence check.
       - Test Hasbrouck signed-sqrt volume robustness diagnostics.
    2. Run full local pytest suite:
       .venv/Scripts/python.exe -m pytest tests/test_microstructure_phase6d.py -v
       .venv/Scripts/python.exe -m pytest tests/test_microstructure_phase6a.py tests/test_microstructure_phase6b.py tests/test_microstructure_phase6c.py -v
    3. Deploy to VPS (15.235.193.47), run migrations, restart services, and verify live BingX probe.
    4. Verify zero trading orders placed and zero slot mutations.
  </action>
  <verify>
    .venv/Scripts/python.exe scratch/deploy_phase6d1_vps.py
  </verify>
  <done>
    100% tests passing on Local and VPS; live BingX probe reflects Phase 6D.1 governance fields; zero orders placed.
  </done>
</task>

## Must-Haves
After all tasks complete, verify:
- [ ] VECM sample threshold strictly enforces N >= 300 with mathematical justification recorded.
- [ ] Gonzalo-Granger component shares never clipped; raw values preserved; out-of-range flagged; bounded speed share exposed.
- [ ] Cumulative impact H20 accurately labeled; permanent impact populated only upon demonstrated mathematical convergence.
- [ ] Hasbrouck signed-sqrt volume robustness comparison recorded in diagnostics.
- [ ] Methodology versions updated to HASBROUCK_STYLE_V1.1 and VECM_STYLE_V1.1.
- [ ] All 95+ microstructure tests pass with zero regressions.
- [ ] VPS live probe reflects updated models and fields.

## Success Criteria
- [ ] All 3 tasks verified passing
- [ ] Must-haves confirmed
- [ ] Zero orders placed, zero slots mutated
