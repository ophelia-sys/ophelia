# Binance Historical Level-2 Data Feasibility

## 1. Data Types & True Capabilities

| DATA TYPE | TRUE CAPABILITY | SUFFICIENT FOR |
|---|---|---|
| **aggTrades** | Tick-by-tick trade execution events | Trade flow, Aggressive Volume, short-horizon CVD, TVI |
| **bookTicker** | Level 1 Snapshot (Best Bid/Ask updates) | Level-1 True Queue Imbalance, Microprice, BBA volatility |
| **bookDepth** | Periodic Level 2/3 Snapshot (via Binance Vision) | Static depth analysis, macroscopic liquidity shifts |
| **S_DEPTH** | Full Level 2 Snapshot Data | Book initialization, gap-filling, resting liquidity analysis |
| **T_DEPTH** | Tick-by-tick Level 2 Event Stream (incremental depth) | Book Slope, Depth Imbalance, OFI, order replenishment |
| **T_DEPTH_BACKFILL** | Tick-level depth stream for backfilling gaps | Reconstructing continuous sequences when WS disconnects |

**Critical Distinction:**
- `bookDepth` and `S_DEPTH` are **snapshots**. They cannot accurately model queue position, exact order addition/cancellation flow, or canonical OFI.
- `T_DEPTH` is the **incremental event stream** necessary for true high-frequency L2 reconstruction.

## 2. Historical Availability

### T_DEPTH Availability
- **Existence:** `T_DEPTH` (tick-level depth) is technically logged by Binance but is heavily gated for historical retrieval. It typically requires institutional whitelisting for direct API download of deep history.
- **Alternatives:** Reliable historical `T_DEPTH` streams are commonly sourced from third-party archival services like **Tardis.dev** or **Databento**, which record the live WebSocket streams continuously.
- **Coverage:** Readily available for BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT across major third-party vendors for years of history.

### Volume & Storage Estimates (BTCUSDT only)
- **T_DEPTH (Raw JSON/CSV):** ~1.5 GB to 3 GB per day (highly dependent on volatility).
- **Compressed (Parquet/Zstd):** ~300 MB to 600 MB per day.
- **30 Days:** ~15 GB compressed.
- **90 Days:** ~45 GB compressed.
- **180 Days:** ~90 GB compressed.

Extrapolating to 5 symbols for 180 days results in ~450 GB of strictly L2 compressed event data, before derived features are calculated.

## 3. Workstation vs VPS Architecture

Due to the massive disk and memory requirements for reconstructing tick-by-tick L2 limit order books:
- **Research Workstation (Local/Dedicated Big Compute):** MUST be used for bulk historical ingestion, L2 book reconstruction, feature generation, model training, and long-horizon backtesting.
- **Production VPS:** MUST be restricted to incremental live data consumption (WebSocket), lightweight feature updates in memory, opportunity detection, and execution routing. 

Attempting to process 6+ months of `T_DEPTH` on a lightweight execution VPS will result in catastrophic memory limits and CPU throttling.
