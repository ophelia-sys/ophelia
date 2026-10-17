# PHASE 8.1 LEAKAGE & SPLIT AUDIT

## 1. Purged Walk-Forward
The pipeline was corrected to use `PurgedWalkForwardSplitter`. An explicit embargo of 60 periods (equal to the maximum label horizon) was strictly enforced between the train `label_end` and test `prediction_time`.

## 2. Overlap Management
The non-overlapping diagnostic subset confirmed that once autocorrelation is accounted for, the effective OOS sample size collapses drastically. The standard errors of the AUC metric widen significantly.
