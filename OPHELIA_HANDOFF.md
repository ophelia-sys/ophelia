# OPHELIA_HANDOFF
**Date:** 2026-08-12

## A. PROJECT IDENTITY
- **Project Name:** Ophelia
- **Purpose:** Production-grade algorithmic cryptocurrency trading system.
- **Current Architecture:** Layered Python system (App -> TradingEngine -> Validator -> BingXClient). 
- **Current Execution Venue:** BingX Perpetual Swap Futures.
- **Current Research Venues:** Binance Vision (USD-M Futures) for historical microstructure.
- **Current Development Environment:** Python 3.11, Windows.

## B. CRITICAL ARCHITECTURAL RULES
**Data Flow:** DATA → NORMALIZATION → INSTITUTIONAL MATH → RESEARCH / ML → DECISION → RISK → EXECUTION
- **Institutional Math** does NOT execute trades.
- **Research** does NOT modify production.
- **ML** does NOT automatically enter DecisionEngine.
- **Canonical OFI** remains unavailable unless mathematically proven otherwise.
- **Core Mandate:** Evidence > sophistication.

## C. CURRENT PRODUCTION ARCHITECTURE
- **Strategy:** Signal generation. Returns typed trade signals, does not place orders or manage risk.
- **Institutional Math Engine:** Calculates advanced order-book and depth-based features (CVD, spread, imbalance).
- **Data Acquisition:** Retrieves market data (OHLCV, Funding, OI).
- **DecisionEngine:** Evaluates Strategy signals against logic/regimes.
- **RiskManager:** Calculates position sizing, leverage limits, and safety stops. Never generates signals.
- **TradingEngine:** Business orchestration. Coordinates Scanner, Strategies, Portfolio updates, and RiskManager.
- **Broker (PaperBroker):** Simulates BingX execution strictly for paper trading.
- **BingX:** The exclusive target exchange.
- **Kronos:** (Untracked external dependency) For latency/execution analysis.

## D. CURRENT INSTITUTIONAL MATH INVENTORY
- Realized Volatility (AVAILABLE)
- Parkinson (AVAILABLE)
- Garman-Klass (AVAILABLE)
- ATR (AVAILABLE)
- Kaufman Efficiency Ratio (AVAILABLE)
- ATR-scaled trend (AVAILABLE)
- Directional persistence (AVAILABLE)
- Momentum (AVAILABLE)
- MAD Z-score (AVAILABLE)
- ECDF/percentile (AVAILABLE)
- CVD (PROXY / RESEARCH_ONLY)
- TVI (PROXY / RESEARCH_ONLY)
- Spread (PROXY / RESEARCH_ONLY)
- Relative spread (PROXY / RESEARCH_ONLY)
- Queue imbalance (PROXY / RESEARCH_ONLY)
- Depth imbalance (PROXY / RESEARCH_ONLY)
- Microprice (PROXY / RESEARCH_ONLY)
- Visible impact (PROXY / RESEARCH_ONLY)
- Book slope (PROXY / RESEARCH_ONLY)
- Book concentration (PROXY / RESEARCH_ONLY)
- OI (AVAILABLE)
- Funding (AVAILABLE)

## E. OFI RULE
**Canonical OFI = UNAVAILABLE / UNVERIFIED**
BingX public depth snapshots were verified as gapped snapshots and do not provide sufficient information for canonical event-level OFI.
**Never alias:** `depth_imbalance`, `queue_imbalance`, `CVD`, or `snapshot_ofi_proxy` to canonical OFI.

## F. BINGX DATA FINDINGS
- **OHLCV:** Available
- **Trades:** Available
- **Aggressor side:** Available
- **Order book:** Available (gapped snapshots, not full event stream)
- **OI:** Available
- **Funding:** Available
- **Liquidations:** Available

## G. RESEARCH DATA FINDINGS
**Binance Vision (USD-M Futures, BTCUSDT, 1-minute data)** and relevant historical microstructure datasets are actively used. 
*Important:* Binance research data is NOT automatically equivalent to BingX execution data.

## H. PHASE HISTORY
See `/research/PHASE_INDEX.md` and `/research/RESEARCH_STATE.md` for a comprehensive historical record.

## I. IMPORTANT CORRECTIONS
**BTCUSDT.parquet is 1-minute data.**
Earlier reports incorrectly described it as 5-minute.
Correct interpretation: 1 candle = 1 minute, 60 candles = 60 minutes.

## J. RESEARCH RESULTS
- Directional ML had statistical signal but weak economics.
- Event prediction failed the cost hurdle.
- Microstructure validation improvement failed locked Out-of-Sample (OOS) testing.
- Regime conditioning found no robust candidate.
*(These are strictly research findings, not production results.)*

## K. CURRENT PHASE
- **Current Phase:** Phase 5.6 (Strategic Economic Feasibility Lab)
- **Status:** Complete.
- **Selected Branch:** Branch B (Higher-Timeframe Economics) + Branch C (Asset/Venue Economic Efficiency).
- **Additional Approval:** Required before implementing Phase 6 architecture.
- **Exact Next Task:** The new session must await user approval to begin Phase 6 implementation of High-Timeframe (1h+) models on SOLUSDT.

## L. EXACT NEXT ACTION
**READ THIS FILE FIRST.**
Then read `AGENTS.md`.
Then inspect `git status`.
Then inspect the files listed below.
Do not modify production code until the user approves the next plan.

## M. IMPORTANT FILES
- `AGENTS.md`
- `institutional/`
- `institutional/data/`
- `core/`
- `risk/`
- `strategies/`
- `research/`
- `tests/`
- `research/PHASE5_6_REPORT.md` (and older phase reports)

## N. TEST STATUS
- **Last full test command:** `pytest tests/`
- **Number passed/failed:** UNVERIFIED (Environment throws `ModuleNotFoundError` during pytest collection due to missing `numba` and module pathing). 
- **Last test date:** 2026-08-12

## O. DEPENDENCIES / ENVIRONMENT
- **Python Version:** 3.11.9
- **Major Packages:** pandas, numpy, scikit-learn, xgboost, lightgbm, numba (currently broken in env).

## P. GIT STATE
- **Current Branch:** main
- **Current Commit:** Ahead of origin/main by 1 commit.
- **Clean Working Tree:** FALSE. `institutional/liquidity.py`, `institutional/normalization.py` modified. Multiple untracked files in `research/` and `tests/`.

==================================================
# NEW SESSION STARTUP PROTOCOL
1. Read OPHELIA_HANDOFF.md
2. Read AGENTS.md
3. Run git status
4. Inspect current branch/commit
5. Read RESEARCH_STATE.md
6. Inspect current phase artifacts
7. Run relevant tests before changing code
8. Do not assume previous reports are correct
9. Preserve production/research boundaries
10. Ask the user before making a major architectural change
