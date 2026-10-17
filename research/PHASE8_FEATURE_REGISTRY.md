# PHASE 8 FEATURE REGISTRY

## Validated Features
- `ret_1`, `ret_5`, `ret_15`: Point-in-time safe price returns.
- `vol_60`: Rolling std dev of returns.
- `mom_15`, `mom_60`: Raw momentum differences.
- `vol_z`: Rolling Z-score of volume.
- `delta_v`: Derived volume delta.
- `delta_oi_z`: Robust MAD Z-score of Open Interest change.

## Historically Unavailable
- `ofi`, `microprice`: Excluded from all ML models as they require L1 depth.
