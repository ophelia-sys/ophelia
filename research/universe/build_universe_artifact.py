import pandas as pd
import hashlib
import json
from point_in_time import compute_historical_eligibility

def print_breadth_report(df: pd.DataFrame):
    # Filter to only eligible symbols
    eligible = df[df['eligible'] == True]
    
    # Count N eligible symbols per timestamp
    daily_counts = eligible.groupby('timestamp')['symbol'].count()
    
    if daily_counts.empty:
        print("NO ELIGIBLE SYMBOLS FOUND.")
        return

    median_n = daily_counts.median()
    min_n = daily_counts.min()
    max_n = daily_counts.max()
    
    total_days = len(daily_counts)
    pct_10 = (daily_counts >= 10).sum() / total_days * 100
    pct_20 = (daily_counts >= 20).sum() / total_days * 100
    pct_30 = (daily_counts >= 30).sum() / total_days * 100
    pct_50 = (daily_counts >= 50).sum() / total_days * 100
    pct_100 = (daily_counts >= 100).sum() / total_days * 100
    
    print("\n==========================================")
    print("UNIVERSE BREADTH REPORT")
    print("==========================================")
    print(f"Total Evaluated Days: {total_days}")
    print(f"Median N Eligible:    {median_n:.0f}")
    print(f"Minimum N Eligible:   {min_n}")
    print(f"Maximum N Eligible:   {max_n}")
    print("------------------------------------------")
    print(f"% Timestamps with N >= 10:  {pct_10:.1f}%")
    print(f"% Timestamps with N >= 20:  {pct_20:.1f}%")
    print(f"% Timestamps with N >= 30:  {pct_30:.1f}%")
    print(f"% Timestamps with N >= 50:  {pct_50:.1f}%")
    print(f"% Timestamps with N >= 100: {pct_100:.1f}%")
    print("==========================================\n")

def main():
    try:
        metadata_df = pd.read_parquet('data/processed/stage_a_daily_metadata.parquet')
    except Exception as e:
        print(f"Could not load stage_a_daily_metadata.parquet: {e}")
        return

    print(f"Loaded {len(metadata_df)} daily metadata records. Computing eligibility...")
    universe_df = compute_historical_eligibility(metadata_df)
    
    # Save the canonical artifact
    out_path = 'data/processed/universe_artifact_v1.parquet'
    universe_df.to_parquet(out_path, index=False)
    
    # Compute SHA-256
    sha256_hash = hashlib.sha256()
    with open(out_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
            
    hex_hash = sha256_hash.hexdigest()
    print(f"Saved canonical universe artifact to: {out_path}")
    print(f"SHA-256 Hash: {hex_hash}")
    
    # Update feature registry with the hash (we will just print it here, but in practice we log it)
    print_breadth_report(universe_df)

if __name__ == '__main__':
    main()
