# Phase 6 Historical Validation Forensic Audit

## A. Event-Generation Verification
**Findings: VALID BUT NO EVENTS GENERATED (STRICT PARAMETERS).**
- **Raw Events Generated:** 7,866
- **FVG_CONFIRMATION:** 0
- **POOL_CONFIRMATION:** 7,866
- **LIQUIDITY_SWEEP:** 0
- **Total Unique Timestamps:** 7,866
- **Primary Events:** 7,866
- **Non-Primary Events:** 0

*Analysis:*
The pipeline generated 7,866 `POOL_CONFIRMATION` events. Zero `FVG_CONFIRMATION` or `LIQUIDITY_SWEEP` events were generated. In `detect_bullish_fvg`, the constraints `body > 1.0 * ATR` and `gap > 1.0 * ATR` are extremely strict on 1-minute candles. The event generator is not maliciously filtering them; it simply mathematically generates 0 events given the dataset and exploratory parameters (alpha=1.0, gamma=1.0).

## B. Cluster Verification
**Findings: BUG DETECTED in Clustering Window Unit.**
- **Clusters Created:** 7,866
- **Minimum Cluster Size:** 1
- **Maximum Cluster Size:** 1
- **Median Cluster Size:** 1
- **Clusters > 1 event:** 0

*Analysis:*
The clustering logic groups events if the time difference is `<= 300`. However, the timestamps are in **milliseconds**. `300` ms is `0.3` seconds. Since the dataset is 1-minute (60,000 ms), it is physically impossible for two distinct events to be `<= 300 ms` apart.
As a result, clustering is effectively DISABLED by this unit mismatch. Every single event is assigned its own cluster, meaning every event is retained as a "Primary Event" and 0 are discarded. 
To achieve a 300-second window, the threshold must be `300,000`. 

## C. Power-Analysis Verification
**Findings: VALID, BUT CONTEXT NEEDED.**
- **Effective N:** 2,398
- **Standard Deviation (Baseline):** 0.006394
- **Alpha:** 0.05
- **Target Power:** 0.80

The Minimum Detectable Effect (MDE) is reported as `0.000366`. This represents the smallest true mean excess return (in absolute decimal terms, i.e., 3.66 basis points) that the test can reliably detect 80% of the time, given the sample size of 2,398 and noise (std dev) of 0.006394.

The report also lists "Power at 0.05 effect" (etc.). These refer to arbitrarily large standardized effect sizes (Cohen's d). A Cohen's d of 0.05 means an effect of `0.05 * 0.006394 = 0.0003197`. Because this is near the MDE, the simulated power approaches 100%. The test is indeed ADEQUATELY POWERED for standard financial effect sizes.

## D. Cost Arithmetic Verification
**Findings: ARITHMETIC IS CORRECT, TERMINOLOGY CONFUSING.**
Tracing a BINGX_SIMULATION 60-minute average trade:
- **Mean Gross Return:** 0.000429 (4.29 bps)
- **Mean Entry/Exit Fee:** 0.000700 (7.00 bps) (Taker + Taker = 0.035% * 2)
- **Mean Slippage:** 0.000300 (3.00 bps)
- **Mean Funding:** 0.000000
- **Mean Net Return:** `0.000429 - 0.000700 - 0.000300 - 0.000000 = -0.000571` (-5.71 bps)

The report states:
`Net Expectancy: -1.367990`
This is not a per-trade expectancy. This is the **Sum of Net Returns** (`-0.000571 * 2394 events = -1.36697`). The arithmetic holds, but the label "Net Expectancy" is incorrectly used to describe the cumulative sum of returns across all test events instead of the per-trade mean net return.

## E. OOS Forensics
**Findings: CRITICAL BUG DETECTED in Purge/Embargo Timestamps.**
In `WalkForwardValidator`, the purge and embargo are added to the timestamp:
`purge_end = train_time + max_horizon_seconds` (where `max_horizon_seconds = 3600`)
`embargo_end = purge_end + embargo_seconds` (where `embargo_seconds = 86400`)

However, the dataset timestamps are in **milliseconds**. 
Therefore:
- **Purge:** 3600 ms (3.6 seconds) instead of 1 hour (3,600,000 ms).
- **Embargo:** 86,400 ms (86.4 seconds) instead of 24 hours (86,400,000 ms).

The test labels **do** overlap with the training labels because the purge boundary is mathematically near-zero. Train data absolutely influences the test statistics in this state.

## F. Statistical Reproduction
**Findings: REPRODUCTION MATCHES.**
Manually calculating the 60m horizon for `POOL_CONFIRMATION`:
- **N:** 2394
- **Mean:** 0.000429
- **Baseline Mean:** 0.000261
- **Excess Return:** `0.000429 - 0.000261 = 0.000168` (Reported: 0.000167 due to float precision)
- **HAC SE:** 0.000249
The statistical functions executed correctly on the data they were given.

## G. Multiple-Testing Verification
**Findings: VALID.**
The hypothesis family consisted of 6 tests (POOL_CONFIRMATION at 1m, 3m, 5m, 15m, 30m, 60m). 
FVG and LIQUIDITY_SWEEP were omitted from the family because they had `NaN` values (0 events).
The Benjamini-Hochberg FDR step-up procedure was applied to the 6 valid p-values correctly.
Example:
- Raw p = 0.0685 -> FDR q = 0.4110
- Raw p = 0.4009 -> FDR q = 0.7396

## H. Final Findings
The execution reported in `PHASE6_HISTORICAL_VALIDATION_RESULTS.md` contains fundamentally invalid test statistics due to timestamp unit mismatches.

1. **Clustering is Broken:** 300 ms instead of 300,000 ms window. All events are passed as primary.
2. **Purge/Embargo is Broken:** 3.6 seconds purge instead of 1 hour. Train and Test labels overlap.
3. **FVG/Sweep are INCONCLUSIVE / NO EVENTS:** Due to strict mathematical constraints on 1-minute candles.

**CONCLUSION: FAIL.** 
The report cannot be accepted. The OOS isolation was breached due to millisecond/second unit conflicts, and clustering failed for the same reason. These bugs must be resolved before a valid empirical result can be generated.
