# PHASE 8 LABEL VALIDATION REPORT

## Labels Tested
- `target_15`: Direction of forward 15m return.
- `target_60`: Direction of forward 60m return.

## Integrity
Labels are strictly constructed using `shift(-horizon)` on closing prices, avoiding any future leakage. The distributions are balanced (~50/50).
