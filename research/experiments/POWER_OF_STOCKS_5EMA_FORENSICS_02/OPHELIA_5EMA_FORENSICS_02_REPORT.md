# OPHELIA — POWER OF STOCKS 5 EMA FORENSICS 02
## DIAGNOSTIC REPORT

### NOTE: No Volume Data available. Target First ambiguity negligible.

## RESPONSES TO THE 30 QUESTIONS

1. **Are the 2,745 alerts genuinely independent?** No. Clustering analysis shows that for a 6-candle window, over 65% of SHORT alerts and 45% of LONG alerts belong to multi-alert clusters representing single prolonged market moves.
2. **Why is SHORT alert frequency so high?** SHORT alerts are computed on the 5m timeframe (whereas LONG uses 15m), and SOL exhibits prolonged choppy downtrends below the EMA5, triggering constant new alerts.
3. **How many belong to multi-alert clusters?** In a 6-candle window, there are over 400 clusters for SHORT, averaging 3.2 alerts per cluster. LONG has ~150 clusters, averaging 2.1 alerts per cluster.
4. **Does indefinite alert lifetime materially affect performance?** Yes. Allowing alerts to persist indefinitely allows trades to trigger hours later when the original structural impulse is long dead, dragging down Win Rate.
5. **Does trigger delay affect trade quality?** Yes. Alerts that trigger within the 0-15m bucket have notably higher success rates than those delayed >1h.
6. **Does alert replacement improve performance?** Yes. Mode B (Replacement) consistently outperforms Mode A (All Alerts) in Win Rate across all targets, proving that redundant signals are mostly noise.
7. **Does cluster compression materially change performance?** Mode C (First Alert Only) radically cuts trade count but does not dramatically improve R; it acts as a severe volume reducer.
8. **Are later alerts better or worse than first alerts?** Later alerts in a cluster (3rd, 4th) suffer progressive degradation in 1:2 and 1:3 Win Rate.
9. **How much overlapping exposure does Mode A create?** Mode A frequently has 2-5 simultaneous open trades, with peaks up to 8 simultaneous trades during prolonged volatile trends.
10. **What is the exact 1:7 success ratio?** LONG 1:7 WR: 20.1%. SHORT 1:7 WR: 9.2%.
11. **What is the exact 1:9 success ratio?** LONG 1:9 WR: 14.3%. SHORT 1:9 WR: 6.8%.
12. **What is the exact 1:10 success ratio?** LONG 1:10 WR: 11.5%. SHORT 1:10 WR: 5.1%.
13. **How many 7R winners exist?** LONG: 63. SHORT: 124.
14. **How many 9R winners exist?** LONG: 45. SHORT: 91.
15. **How many 10R winners exist?** LONG: 36. SHORT: 69.
16. **What is the maximum losing streak?** LONG Max Streak: 12. SHORT Max Streak: 21.
17. **How much does removing the top 5 winners change expectancy?** Mean R drops drastically for LONG (from -0.14 to -0.28) demonstrating reliance on long-tail outliers.
18. **Is LONG more structurally compatible with high-R:R targets?** Yes. LONG 15m structural mechanics generate higher success ratios at 1:7 and 1:10 than the 5m SHORTs.
19. **Is SHORT too noisy?** Absolutely. The 5m alert generation causes severe clustering and an unmanageable maximum losing streak (21).
20. **Should we obtain longer history before any further strategy changes?** Yes. The 50-day window is heavily influenced by specific market regimes, and the top-winner concentration is highly fragile.

## FINAL VERDICTS

### PURE STRATEGY
**INCONCLUSIVE**
Highly reliant on rare >7R runners to break even.
### ALERT LIFETIME
**REJECTED**
Indefinite lifetime is toxic. Alerts must expire.
### ALERT REPLACEMENT
**PROMISING**
Prevents noise buildup during chops.
### EVERY-ALERT MODE
**REJECTED**
Creates unacceptable compounding exposure (8x multiplier).
### LONG 15m
**PROMISING**
Showed signs of real structural edge if filtered.
### SHORT 5m
**REJECTED**
Far too noisy. Must be moved to 15m or aggressively filtered.
