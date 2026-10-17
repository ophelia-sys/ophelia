# PHASE 6.3 P4 - RESULT INTEGRITY AUDIT (FINAL EXHAUSTIVE)

## 1. Symbol Level Independent Reproduction

### BTCUSDT
- Samples: 155456
- LogLoss: Base 0.67664 | Test 0.67651 | Diff 1.36 bps
- Brier: Base 0.24188 | Test 0.24182
- ECE: Base 0.0074 | Test 0.0068
- Calib Slope/Int: Base (0.1759, 0.4795) | Test (0.1815, 0.4819)
- ENR(0): Base 0.34bps | Test 1.94bps
- ENR(5): Base -4.66bps | Test -3.06bps
- ENR(10): Base -9.66bps | Test -8.06bps
- ENR(15): Base -14.66bps | Test -13.06bps
- ENR(20): Base -19.66bps | Test -18.06bps
- ENR(25): Base -24.66bps | Test -23.06bps
- DM p-val (Lag 59): 0.2432
- Bootstrap 1000-Block Diff: 0.00015
- Permutation 1000-Block p-val: 0.0010
- BH-FDR q-val: 0.3745

### ETHUSDT
- Samples: 155671
- LogLoss: Base 0.68377 | Test 0.68345 | Diff 3.19 bps
- Brier: Base 0.24535 | Test 0.24519
- ECE: Base 0.0114 | Test 0.0077
- Calib Slope/Int: Base (0.1827, 0.4838) | Test (0.1989, 0.4886)
- ENR(0): Base 3.30bps | Test 3.86bps
- ENR(5): Base -1.70bps | Test -1.14bps
- ENR(10): Base -6.70bps | Test -6.14bps
- ENR(15): Base -11.70bps | Test -11.14bps
- ENR(20): Base -16.70bps | Test -16.14bps
- ENR(25): Base -21.70bps | Test -21.14bps
- DM p-val (Lag 59): 0.0394
- Bootstrap 1000-Block Diff: 0.00032
- Permutation 1000-Block p-val: 0.0010
- BH-FDR q-val: 0.1182

### SOLUSDT
- Samples: 142540
- LogLoss: Base 0.69211 | Test 0.69211 | Diff -0.04 bps
- Brier: Base 0.24943 | Test 0.24944
- ECE: Base 0.0112 | Test 0.0122
- Calib Slope/Int: Base (0.0422, 0.4682) | Test (0.0417, 0.4684)
- ENR(0): Base 3.91bps | Test -2.26bps
- ENR(5): Base -1.09bps | Test -7.26bps
- ENR(10): Base -6.09bps | Test -12.26bps
- ENR(15): Base -11.09bps | Test -17.26bps
- ENR(20): Base -16.09bps | Test -22.26bps
- ENR(25): Base -21.09bps | Test -27.26bps
- DM p-val (Lag 59): 0.9875
- Bootstrap 1000-Block Diff: -0.00001
- Permutation 1000-Block p-val: 0.0909
- BH-FDR q-val: 0.9875

### XRPUSDT
- Samples: 155239
- LogLoss: Base 0.68828 | Test 0.68814 | Diff 1.47 bps
- Brier: Base 0.24751 | Test 0.24745
- ECE: Base 0.0138 | Test 0.0124
- Calib Slope/Int: Base (0.1547, 0.4904) | Test (0.1596, 0.4910)
- ENR(0): Base 2.09bps | Test 5.74bps
- ENR(5): Base -2.91bps | Test 0.74bps
- ENR(10): Base -7.91bps | Test -4.26bps
- ENR(15): Base -12.91bps | Test -9.26bps
- ENR(20): Base -17.91bps | Test -14.26bps
- ENR(25): Base -22.91bps | Test -19.26bps
- DM p-val (Lag 59): 0.3490
- Bootstrap 1000-Block Diff: 0.00015
- Permutation 1000-Block p-val: 0.0010
- BH-FDR q-val: 0.4188

### BNBUSDT
- Samples: 155455
- LogLoss: Base 0.68633 | Test 0.68597 | Diff 3.57 bps
- Brier: Base 0.24656 | Test 0.24639
- ECE: Base 0.0068 | Test 0.0076
- Calib Slope/Int: Base (0.1560, 0.4820) | Test (0.1670, 0.4832)
- ENR(0): Base 6.90bps | Test 5.51bps
- ENR(5): Base 1.90bps | Test 0.51bps
- ENR(10): Base -3.10bps | Test -4.49bps
- ENR(15): Base -8.10bps | Test -9.49bps
- ENR(20): Base -13.10bps | Test -14.49bps
- ENR(25): Base -18.10bps | Test -19.49bps
- DM p-val (Lag 59): 0.0262
- Bootstrap 1000-Block Diff: 0.00036
- Permutation 1000-Block p-val: 0.0010
- BH-FDR q-val: 0.1182

### ADAUSDT
- Samples: 155455
- LogLoss: Base 0.68886 | Test 0.68871 | Diff 1.44 bps
- Brier: Base 0.24784 | Test 0.24778
- ECE: Base 0.0062 | Test 0.0060
- Calib Slope/Int: Base (0.1437, 0.4808) | Test (0.1537, 0.4817)
- ENR(0): Base 8.28bps | Test 8.00bps
- ENR(5): Base 3.28bps | Test 3.00bps
- ENR(10): Base -1.72bps | Test -2.00bps
- ENR(15): Base -6.72bps | Test -7.00bps
- ENR(20): Base -11.72bps | Test -12.00bps
- ENR(25): Base -16.72bps | Test -17.00bps
- DM p-val (Lag 59): 0.2497
- Bootstrap 1000-Block Diff: 0.00015
- Permutation 1000-Block p-val: 0.0010
- BH-FDR q-val: 0.3745

## 2. Temporal Slices (Pooled)

### 2022
- Samples: 308710 | LL Diff: 4.75 bps | DM p-val: 0.0045
- ENR(0): Base -4.78bps | Test -6.25bps

### 2023
- Samples: 611106 | LL Diff: 0.40 bps | DM p-val: 0.4046
- ENR(0): Base 11.48bps | Test 11.18bps

## 3. Fold Slices (Pooled)

### Fold 0
- Samples: 306603 | LL Diff: 4.95 bps | DM p-val: 0.0035
- ENR(0): Base -4.95bps | Test -6.22bps
### Fold 1
- Samples: 306603 | LL Diff: -0.05 bps | DM p-val: 0.9386
- ENR(0): Base 11.23bps | Test 11.80bps
### Fold 2
- Samples: 306610 | LL Diff: 0.68 bps | DM p-val: 0.2684
- ENR(0): Base 11.08bps | Test 10.11bps

## 4. Aggregate Performance

### Pooled Aggregate
- Samples: 919816 | LL Diff: 1.86 bps | DM p-val: 0.0040
- ENR(0): Base 4.29bps | Test 3.95bps
- ENR(5): Base -0.71bps | Test -1.05bps
- ENR(10): Base -5.71bps | Test -6.05bps
- ENR(15): Base -10.71bps | Test -11.05bps
- ENR(20): Base -15.71bps | Test -16.05bps
- ENR(25): Base -20.71bps | Test -21.05bps

### Equal-Weighted Aggregate
- Equal-Weighted LL Diff: 1.83 bps
- EW ENR(0): Base 4.14bps | Test 3.80bps
- EW ENR(5): Base -0.86bps | Test -1.20bps
- EW ENR(10): Base -5.86bps | Test -6.20bps
- EW ENR(15): Base -10.86bps | Test -11.20bps
- EW ENR(20): Base -15.86bps | Test -16.20bps
- EW ENR(25): Base -20.86bps | Test -21.20bps