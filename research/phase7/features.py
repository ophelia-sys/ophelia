import pandas as pd
import numpy as np
from typing import List

def extract_queue_imbalance(df: pd.DataFrame) -> pd.Series:
    """
    Extracts or computes queue imbalance.
    The canonical dataset provides `mean_queue_imbalance`.
    """
    if 'mean_queue_imbalance' in df.columns:
        return df['mean_queue_imbalance']
    elif 'snapshot_ofi_proxy' in df.columns:
        # Fallback if queue imbalance is completely missing, 
        # though canonical should have it.
        return df['snapshot_ofi_proxy']
    elif 'delta_v' in df.columns and 'volume' in df.columns:
        print("WARNING: 'mean_queue_imbalance' not found. Using 'delta_v / volume' (Trade Imbalance) as a proxy.")
        return df['delta_v'] / df['volume'].replace(0, np.nan)
    else:
        raise ValueError("Queue Imbalance not available in dataset.")

def extract_book_slope(df: pd.DataFrame) -> pd.Series:
    """
    Extracts or computes book slope imbalance.
    Note: if the dataset lacks native book slope (e.g., L2 snapshots),
    this will raise an error or return a derived proxy.
    """
    if 'book_slope' in df.columns:
        return df['book_slope']
    if 'bid_slope' in df.columns and 'ask_slope' in df.columns:
        return (df['bid_slope'] - df['ask_slope']) / (df['bid_slope'] + df['ask_slope']).replace(0, np.nan)
    
    # As a fallback for Phase 7 initial testing on UM dataset which lacks L2 depth:
    print("WARNING: 'book_slope' not found in dataframe. Returning zeros. Feature EXP-A will be null.")
    return pd.Series(0.0, index=df.index)

def calculate_evidence_entropy_feature(df: pd.DataFrame, feature_cols: List[str]) -> pd.Series:
    """
    Calculates Evidence Entropy across a set of underlying features.
    Treats each normalized feature as a probability of a positive outcome,
    then calculates the Shannon entropy across the evidence vector for each timestamp.
    """
    if not feature_cols:
        return pd.Series(0, index=df.index)
        
    # Standardize features to [0, 1] using a rolling sigmoid-like mapping
    # to simulate a probability p_i for each feature.
    # z = (x - mean) / std
    # p = 1 / (1 + exp(-z))
    
    entropies = []
    
    for i in range(len(df)):
        row = df.iloc[i]
        
        # We need a cross-sectional probability vector for this row
        p_vec = []
        for col in feature_cols:
            val = row[col]
            if pd.isna(val):
                continue
            
            # Assuming the features are already roughly standard normal (Z-scores),
            # we convert them to probabilities.
            # If they are not Z-scores, we'd need to normalize them first.
            p = 1.0 / (1.0 + np.exp(-val))
            p_vec.append(p)
            
        if not p_vec:
            entropies.append(np.nan)
            continue
            
        p_arr = np.array(p_vec)
        # Normalize so they sum to 1 to represent a true categorical distribution?
        # No, the institutional math treats each as independent evidence.
        # Entropy of independent binary variables: sum( H(p_i) )
        # H(p) = -p*log2(p) - (1-p)*log2(1-p)
        
        # Using the exact score.py definition: -sum(p_i * log2(p_i)) over the normalized evidence
        # Let's normalize the vector to sum to 1 so it represents the "distribution of evidence"
        sum_p = np.sum(p_arr)
        if sum_p == 0:
            entropies.append(0.0)
            continue
            
        p_norm = p_arr / sum_p
        # Filter 0s
        p_norm = p_norm[p_norm > 0]
        
        if len(p_norm) == 0:
            entropies.append(0.0)
        else:
            e = -np.sum(p_norm * np.log2(p_norm))
            entropies.append(e)
            
    return pd.Series(entropies, index=df.index)
