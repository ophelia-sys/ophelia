# PHASE 7 VPS DEPLOYMENT MANIFEST

**Status:** APPROVED FOR VPS DEPLOYMENT
**Purpose:** Minimal code required to execute Phase 7 Shadow Observation Window.

## 1. Frozen Model Artifacts
These exact hashes MUST match between local environment and the VPS.
- `PHASE7_MODEL_FROZEN_BTCUSDT.pkl`
- `PHASE7_MODEL_FROZEN_ETHUSDT.pkl`
- `PHASE7_MODEL_FROZEN_SOLUSDT.pkl`
- `PHASE7_MODEL_FROZEN_XRPUSDT.pkl`
- `PHASE7_MODEL_FROZEN_BNBUSDT.pkl`
- `PHASE7_MODEL_FROZEN_ADAUSDT.pkl`
- `PHASE7_DECISION_THRESHOLDS.json`

## 2. Core Python Application
- `main.py`
- `config.py`
- `core/` (TradingEngine, Validatior, Errors, PositionManager, etc.)
- `models/` (Typed dataclasses)
- `exchange/` (BingXClient, PublicBingXClient)
- `institutional/` (Data Engine, Probability Engine, Feature generation)
- `utils/` (Logger, helpers)
- `brokers/` (ShadowBroker, null execution paths)
- `requirements.txt`

## 3. Infrastructure and Operations
- `deploy/ophelia-shadow.service` (systemd daemon definition)
- `scripts/deploy_vps_shadow.sh` (rsync transfer script)
- `scripts/vps_health_monitor.py` (shadow log parser and heartbeat)

## 4. Excluded Assets (DO NOT DEPLOY)
- `.env` containing live secrets
- `research/` notebooks and raw historical `.csv` files
- `test.zip` / bulky data archives
- `tests/` except when required for deployment validation
- Obsolete model artifacts (`LogisticRegression`, `PHASE5_*`, `PHASE6_*`)
