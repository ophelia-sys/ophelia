# Phase 7.5: Point-In-Time Universe Specification

Based on the research and survivorship audits, the following specification is proposed for constructing the `RESEARCH_UNIVERSE`.

## 1. Distinction of Universes
- **RESEARCH_UNIVERSE:** A dynamic, point-in-time basket of 50 to 100+ highly liquid Binance USDT-M perpetuals. Used exclusively to discover and validate cross-sectional or idiosyncratic alpha (e.g., S2, S3, S4).
- **EXECUTION_UNIVERSE:** The static list of symbols intended for actual production trading on BingX (BTC, ETH, SOL, XRP, BNB).

## 2. Data Acquisition Target
To prevent survivorship bias, we will utilize the Binance Vision S3 archives to download 1-minute `klines` for **all 986 historical and active USDT-M symbols**. This ensures that catastrophic failures (LUNA, FTT) are accurately represented in historical risk models.

## 3. Point-In-Time Eligibility Filter
A python function `get_research_universe(timestamp=t)` will be implemented to return eligible symbols at time $t$. 

**Inclusion Criteria (evaluated at $T-1$):**
1. **History:** Symbol must have at least 30 days of continuous trading history prior to $T$.
2. **Liquidity:** Symbol must have a rolling 14-day median daily traded quote volume $\ge$ $25,000,000 USD.
3. **Continuity:** Symbol must have $\le$ 0.5% missing 1m bars over the trailing 14 days.

*Rationale:* The \$25M daily volume threshold guarantees that the asset is sufficiently liquid to handle a 12 bps institutional transaction cost model. Sorting by static thresholds rather than "Top N" prevents edge-case thrashing where the 100th and 101st coin swap places daily. 

## 4. Final Required Answers

1. **How many Binance USD-M symbols can we safely research?** 986 total historical symbols.
2. **How many have sufficient history?** ~600+
3. **How many have sufficient liquidity?** ~100-150 depending on the market cycle.
4. **Is a 30+, 50+, 100+ symbol universe achievable?** Yes, easily.
5. **What survivorship risks exist?** Excluding delisted coins, and using future liquidity to select historical symbols.
6. **What point-in-time universe methodology should be used?** Trailing 14-day median volume > \$25M USD, requiring 30 days of history.
7. **How large would the resulting dataset be?** ~15 GB raw / 3 GB Parquet for 100 symbols over 24 months.
8. **Should research remain on the workstation?** Yes, a ~30GB RAM footprint is required to safely manipulate cross-sectional matrices in Pandas.

## 5. Next Steps
Once this specification is approved, we will begin the batch acquisition of the full Binance Vision historical dataset for the 100+ most liquid (point-in-time) symbols, including delisted assets, to prepare for Phase 7.4 EXP-S3 (Crowded Leverage Reversal).
