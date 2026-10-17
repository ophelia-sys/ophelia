import os
import json
import hashlib
import pandas as pd
import numpy as np
from datetime import datetime, timezone

def compute_sha256(filepath):
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def dataset_lock_audit():
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    DATASET_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'binance_um_universe_1m_v2.parquet')
    MANIFEST_PATH = os.path.join(BASE_DIR, 'research', 'phase6', 'CANONICAL_DATASET_MANIFEST.json')
    
    print(f"Loading {DATASET_PATH}...")
    
    if not os.path.exists(DATASET_PATH):
        raise FileNotFoundError(f"Dataset not found at {DATASET_PATH}")
        
    file_size = os.path.getsize(DATASET_PATH)
    print("Computing SHA-256 hash...")
    file_hash = compute_sha256(DATASET_PATH)
    print(f"Hash: {file_hash}")
    
    df = pd.read_parquet(DATASET_PATH)
    
    symbols = sorted(df['symbol'].unique().tolist())
    total_rows = len(df)
    min_ts = df['timestamp'].min()
    max_ts = df['timestamp'].max()
    
    symbol_counts = df['symbol'].value_counts().to_dict()
    
    schema_types = {col: str(dtype) for col, dtype in df.dtypes.items()}
    columns = list(df.columns)
    
    manifest = {
        "dataset_name": "binance_um_universe_1m_v2",
        "phase": "Phase 6",
        "file_path": DATASET_PATH,
        "sha256": file_hash,
        "file_size_bytes": file_size,
        "row_count": total_rows,
        "min_timestamp": int(min_ts),
        "max_timestamp": int(max_ts),
        "symbols": symbols,
        "symbol_counts": symbol_counts,
        "columns": columns,
        "schema": schema_types,
        "creation_verification_timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    with open(MANIFEST_PATH, 'w') as f:
        json.dump(manifest, f, indent=4)
        
    print(f"Manifest written to {MANIFEST_PATH}")
    
    print("\n==========================================")
    print("DISTRIBUTION AUDIT: Z_DeltaOI")
    print("==========================================")
    
    quantiles = [0.01, 0.05, 0.25, 0.50, 0.75, 0.95, 0.99, 0.995, 0.999]
    
    for sym in symbols:
        print(f"\n--- Symbol: {sym} ---")
        sym_df = df[df['symbol'] == sym]
        z = sym_df['Z_DeltaOI']
        z_valid = z.dropna()
        
        nan_rate = z.isna().mean()
        
        # zero dispersion rate (strictly zero Z)
        zero_rate = (z == 0.0).mean()
        
        print(f"Count valid: {len(z_valid)} / {len(z)}")
        print(f"NaN Rate: {nan_rate*100:.4f}%")
        print(f"Zero-dispersion Rate (Z=0): {zero_rate*100:.4f}%")
        
        if not z_valid.empty:
            mean_z = z_valid.mean()
            median_z = z_valid.median()
            std_z = z_valid.std()
            mad_z = np.median(np.abs(z_valid - median_z))
            
            print(f"Mean: {mean_z:.4f} | Median: {median_z:.4f} | Std: {std_z:.4f} | MAD: {mad_z:.4f}")
            print(f"Min: {z_valid.min():.4f} | Max: {z_valid.max():.4f}")
            
            for q in quantiles:
                print(f"p{int(q*1000)/10.0}: {z_valid.quantile(q):.4f}")
                
            print("Extreme Counts:")
            abs_z = z_valid.abs()
            print(f"  |Z| > 3: {(abs_z > 3).sum()} ({(abs_z > 3).mean()*100:.4f}%)")
            print(f"  |Z| > 5: {(abs_z > 5).sum()} ({(abs_z > 5).mean()*100:.4f}%)")
            print(f"  |Z| > 10: {(abs_z > 10).sum()} ({(abs_z > 10).mean()*100:.4f}%)")
            print(f"  |Z| > 20: {(abs_z > 20).sum()} ({(abs_z > 20).mean()*100:.4f}%)")

if __name__ == "__main__":
    dataset_lock_audit()
