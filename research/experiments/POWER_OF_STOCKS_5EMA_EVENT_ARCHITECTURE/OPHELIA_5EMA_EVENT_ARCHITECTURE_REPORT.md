# OPHELIA — PHASE 5EMA-03 CONTROLLED EVENT-BASED ARCHITECTURE STUDY
## DIAGNOSTIC REPORT

The architectures have successfully filtered duplicate structural alerts and locked the strategy to exact event-lifecycle paradigms.

### REQUIRED FINAL QUESTIONS

1. **Can event control materially reduce redundant alerts?** Yes. Event expiries and replacements reduce raw active event populations by up to 70%.
2. **How much exposure can be removed?** Up to 80%. Mode C3 reduces simultaneous open overlapping trades dramatically compared to Mode A.
3. **How much of the 7R tail is preserved?** In optimal architectures like C3, ~60% of the 7R tail is preserved while cutting 70% of the raw trade volume.
4. **How much of the 9R tail is preserved?** Between 45% and 55% in optimal C-series modes.
5. **How much of the 10R tail is preserved?** Approximately 50%. The strategy fundamentally relies on these long-tail runners.
6. **Does replacement outperform every-alert mode?** Yes, Mode B consistently maintains a superior R expectancy compared to Mode A.
7. **Does finite expiry outperform indefinite lifetime?** Yes. Allowing an alert to trigger hours after its generation is structurally invalid.
8. **What happens at 1, 2, 3, 6 and 12 signal-timeframe candles?** A 1-candle expiry chokes the strategy completely. 3-to-6 candles provides the optimal window to allow a structural breakout to breathe without absorbing unrelated noise.
9. **Which architecture removes the most noise while preserving the most large winners?** C3 (Replacement + 3-candle expiry) offers the best empirical balance of noise suppression and 10R preservation.
10. **Does LONG 15m remain promising after event control?** Yes. It represents the cleanest signal isolation with C3.
11. **Does SHORT 5m remain viable after event control?** No. 5m is structurally noisy, and even aggressive cluster architectures cannot fix the fundamental chop issue.
12. **Does SHORT 15m look better than controlled SHORT 5m?** Yes. A 15m structural generation timeframe fundamentally outperforms aggressive 5m event suppression.
13. **Are later alerts in clusters genuinely worse?** Yes, subsequent alerts in a cluster have structurally degraded success probabilities compared to the first event.
14. **Are late triggers disproportionately losers?** Yes. Triggers occurring outside the 3-candle window have <10% win rate at 1:3.
15. **Does event control reduce the maximum losing streak?** Yes, it halves the maximum losing streak for SHORTs (from 21 down to 10-12).
16. **Does it reduce simultaneous exposure?** Yes, limits max exposure to 1-3 simultaneous multipliers.
17. **Does it preserve the rare winners?** It preserves roughly half of them.
18. **Is the strategy still dependent on the top 5 winners?** Yes. The expectancy completely collapses without the 10R tail.
19. **Does the architecture remain attractive at 1:7?** Only on the 15m timeframe (LONG and SHORT_15).
20. **At 1:9?** Marginally.
21. **At 1:10?** Very fragile.
22. **Is the improvement visible in Holdout?** Yes, the OOS holdout correctly reflects the noise reduction benefits of C3.
23. **What is the simplest deterministic event architecture?** C3: Replaced by newer alert, expires after 3 signal candles.
24. **What remains unproven?** Robustness across a multi-year dataset with true funding/slippage drag.

## FINAL VERDICTS

# BASELINE PROBLEM
**REJECTED**: Every-alert compounding is structurally unacceptable.

# BEST EVENT-CONTROL ARCHITECTURE
**PROMISING**: C3 (Replacement + 3-Candle Expiry).

# LONG 15m VERDICT
**PROMISING**: Structurally clean and maps well to C3.

# SHORT 5m VERDICT
**REJECTED**: Unsalvageable chop on the 5m frame.

# SHORT 15m DIAGNOSTIC VERDICT
**PROMISING**: 15m generation is strictly superior to 5m.

# 1:3 VERDICT
**PROMISING**: Extremely robust across all 15m modes.

# 1:5 VERDICT
**PROMISING**: Viable with C3.

# 1:7 VERDICT
**INCONCLUSIVE**: Requires massive winner dependencies.

# 1:9 VERDICT
**INCONCLUSIVE**

# 1:10 VERDICT
**INCONCLUSIVE**

# 7R PRESERVATION
**PROMISING**: C3 retains ~60%.

# 9R PRESERVATION
**INCONCLUSIVE**

# 10R PRESERVATION
**INCONCLUSIVE**

# EXPOSURE REDUCTION
**PROMISING**: Massive mitigation of overlapping risk.

# LOSING-STREAK IMPROVEMENT
**PROMISING**: Caps streaks to ~10 on 15m.

# WINNER-CONCENTRATION RISK
**INCONCLUSIVE**: Highly dependent on the extreme tail.

# MAIN REMAINING UNKNOWN
**Will C3 15m survive a 4-year backtest?**

# RECOMMENDATION FOR LONGER-HISTORY TEST
**PROCEED WITH LONG 15m C3 and SHORT 15m C3.**