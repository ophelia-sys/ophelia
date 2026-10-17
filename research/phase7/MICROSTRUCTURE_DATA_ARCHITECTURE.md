# Microstructure Data Architecture & Resource Estimates

## 1. Target Data Architecture
High-frequency data requires a distinct pipeline separated from the current 1m bar/OI pipeline:

RAW MARKET DATA (WS/REST)
        ↓
VALIDATION (Sequence IDs, Timestamps)
        ↓
ORDER-BOOK / TRADE EVENT STORE (Parquet/ClickHouse)
        ↓
MICROSTRUCTURE FEATURE ENGINE (L2/L1 derivations)
        ↓
SHORT-HORIZON RESEARCH DATASET
        ↓
ALPHA / EXECUTION TESTS (Horizon framework)
        ↓
PHASE 6.2 PROMOTION GATES

## 2. Storage Analysis Estimates
Assuming 5 symbols (BTC, ETH, SOL, XRP, BNB) storing `depth@100ms` updates and tick-level `aggTrades`.

**Approximate sizing per symbol per day:**
- AggTrades: ~50-100 MB
- L2 Depth (Update Stream): ~500 MB - 1 GB (highly dependent on market volatility)
- Total per symbol: ~1 GB / day
- Total for 5 symbols: ~5 GB / day

| Period | Raw Event Storage | Compressed Columnar (Parquet) | Derived Feature Storage |
|--------|-------------------|-------------------------------|-------------------------|
| 1 Day  | 5 GB              | ~1 GB                         | ~100 MB                 |
| 7 Days | 35 GB             | ~7 GB                         | ~700 MB                 |
| 30 Days| 150 GB            | ~30 GB                        | ~3 GB                   |
| 90 Days| 450 GB            | ~90 GB                        | ~9 GB                   |

**Conclusion:** 90 days of raw data approaches 0.5 TB. This requires local high-capacity storage on a research workstation or dedicated VPS block storage. It is not suitable for Github or standard low-tier cloud VMs.

## 3. Resource / Compute Estimates

1. **Historical Ingestion**: Low CPU, Moderate RAM. Bottleneck is Network/Disk I/O.
2. **Feature Generation**: High CPU (order book reconstruction). Requires efficient C++/Cython or optimized Pandas/Polars logic to replay sequence IDs. 16-32 GB RAM recommended to process 1 month of tick data in memory batches.
3. **Microstructure Feature Calculation**: Moderate CPU. Highly parallelizable across symbols.
4. **Short-Horizon Labeling**: Low CPU. Fast vectorized Pandas shifts.
5. **Walk-Forward Testing**: Very High CPU. Requires evaluating ML models on millions of rows. LightGBM on 100M+ rows requires 32GB+ RAM.

**Recommendation:** A dedicated research workstation with 32-64GB RAM and a 1TB+ NVMe SSD is required for efficient full-history L2 microstructure research.
