import numpy as np
import statsmodels.api as sm
from sklearn.metrics import log_loss, brier_score_loss

def calculate_logloss(y, p):
    p = np.clip(p, 1e-15, 1 - 1e-15)
    return -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))

def dm_test(y, p1, p2, max_lag=59):
    """
    Diebold-Mariano test using Newey-West HAC variance.
    p1 = BASE model predictions
    p2 = AUG (Augmented) model predictions
    Positive DM t-stat means AUG is better (loss1 > loss2, meaning base loss > aug loss).
    """
    loss1 = np.array([-np.log(max(p, 1e-15)) if y_ == 1 else -np.log(max(1 - p, 1e-15)) for y_, p in zip(y, p1)])
    loss2 = np.array([-np.log(max(p, 1e-15)) if y_ == 1 else -np.log(max(1 - p, 1e-15)) for y_, p in zip(y, p2)])
    d = loss1 - loss2  # positive means AUG is better
    
    if np.all(d == 0):
        return 0.0, 1.0
        
    model = sm.OLS(d, np.ones_like(d))
    res = model.fit(cov_type='HAC', cov_kwds={'maxlags': max_lag})
    return res.tvalues[0], res.pvalues[0]

def block_bootstrap(loss1, loss2, block_length=60, replications=1000):
    """
    Standard non-overlapping block bootstrap.
    """
    np.random.seed(42)
    n = len(loss1)
    if n < block_length:
        return 0.0, (0.0, 0.0)
    num_blocks = n // block_length
    
    boot_diffs = []
    blocks1 = [loss1[i*block_length:(i+1)*block_length] for i in range(num_blocks)]
    blocks2 = [loss2[i*block_length:(i+1)*block_length] for i in range(num_blocks)]
    
    for _ in range(replications):
        idx = np.random.randint(0, num_blocks, num_blocks)
        sample1 = np.concatenate([blocks1[i] for i in idx])
        sample2 = np.concatenate([blocks2[i] for i in idx])
        boot_diffs.append(np.mean(sample1) - np.mean(sample2))
        
    boot_diffs = np.array(boot_diffs)
    ci_lower = np.percentile(boot_diffs, 2.5)
    ci_upper = np.percentile(boot_diffs, 97.5)
    
    return np.mean(boot_diffs), (ci_lower, ci_upper)

def block_permutation(y, p_base, p_aug, block_length=60, iterations=1000):
    """
    Block permutation test. Shuffles the non-overlapping blocks of the Augmented 
    model's predictions while preserving the Target and Base alignment.
    Empirical p-value uses the exact formula: (better_count + 1) / (iterations + 1).
    """
    np.random.seed(42)
    n = len(y)
    if n < block_length:
        return 1.0
    num_blocks = n // block_length
    
    actual_diff = calculate_logloss(y, p_base) - calculate_logloss(y, p_aug)
    
    better_count = 0
    blocks_aug = [p_aug[i*block_length:(i+1)*block_length] for i in range(num_blocks)]
    tail_aug = p_aug[num_blocks*block_length:]
    
    for _ in range(iterations):
        idx = np.random.permutation(num_blocks)
        shuffled_aug = np.concatenate([blocks_aug[i] for i in idx])
        if len(tail_aug) > 0:
            shuffled_aug = np.concatenate([shuffled_aug, tail_aug])
            
        diff = calculate_logloss(y, p_base) - calculate_logloss(y, shuffled_aug)
        if diff >= actual_diff:
            better_count += 1
            
    return (better_count + 1) / (iterations + 1)
