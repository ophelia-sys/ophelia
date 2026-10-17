# OPHELIA DATA CHECKPOINT

## BASE Data
- **Location:** `data/normalized/v2/`
- **Universe:** BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT, ADAUSDT
- **Timeframe:** 5m
- **Coverage:** 2022-01-01 to 2025-01-31 (approx.)
- **Status:** Normalized, 2024 included. 

## CVD Data
- **Location:** `research/data/normalized/cvd/5m/`
- **Universe:** BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT, ADAUSDT
- **Timeframe:** 5m
- **Coverage:** 2022-01 to 2023-12 (Frozen)
- **2024 Status:** Ingestion process was killed pending Phase 6.5 explicit restart. 2024 data absent.

## P4 2022-2023 Features
- **Location:** `research/data/normalized/p4/`
- **Universe:** BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT, ADAUSDT
- **Coverage:** 2022-01 to 2023-12 (Frozen)
- **2024 Status:** Ingestion process was killed pending Phase 6.5 explicit restart. 2024 data absent/incomplete.

## P7 2022-2023 Features
- **Location:** No saved file. Dynamically generated from Base OHLCV via `engineer_p7_volume_acceptance_features`.

## OI Data
- **Location:** `data/raw/` (BingX)
- **Status:** SKIPPED/REJECTED due to gaps.

## Spot Data
- **Location:** `data/normalized/v2/` (Spot)
- **Status:** SKIPPED/REJECTED.

## Funding Data
- **Status:** REJECTED.

## target_60_up_10 Supporting Data
- Data exists in `data/normalized/v2/` spanning past 2024 into Jan 2025 to evaluate the 60-bar forward horizon for late 2024 signals.
