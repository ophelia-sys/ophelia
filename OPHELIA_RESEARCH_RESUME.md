============================================
OPHELIA RESEARCH — NEXT SESSION RESUME POINT
============================================

CURRENT BENCHMARK:
BASE + CVD + LightGBM

NEXT PHASE:
PHASE 6.5 — BLIND 2024 CONFIRMATION

SURVIVORS:
P4
P7

PRODUCTION:
NOT AUTHORIZED

---

### NEXT STEPS IN ORDER:
1. **Audit 2024 data availability.** (Use `audit_phase6_5_data.py`).
2. **Determine required historical padding.** Calculate how many 2023 rows are needed to satisfy P4 (24h causal) and P7 (1d VWAP) starting exactly at `2024-01-01 00:00:00 UTC`.
3. **Determine required future label-support data.** Ensure data extends 60 bars past `2024-12-31 23:55:00 UTC` into early 2025 for `target_60_up_10`.
4. **Reconstruct the exact frozen P4 feature-generation methodology.** Read `PHASE6_5_P4_RECONSTRUCTION_CHECKPOINT.md`.
5. **Ingest required 2024 data from the approved source.** (Execute `ingest_aggtrades_p4.py` and `ingest_phase6_5_cvd.py`).
6. **Run P4 and P7 as SEPARATE blind confirmation experiments.** (Execute `exp_phase6_5_2024_confirmation.py`).
7. **Perform independent result-integrity audits.**
8. **Produce final Phase 6.5 decision.**
