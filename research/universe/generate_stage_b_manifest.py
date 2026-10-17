import pandas as pd
import numpy as np
import calendar
from datetime import datetime
from dateutil.relativedelta import relativedelta
import os

def generate_manifest():
    print("Loading universe artifact...")
    # Load frozen point-in-time universe
    universe = pd.read_parquet('data/processed/universe_artifact_v1.parquet')
    
    # We only care about rows where eligible == True
    eligible_universe = universe[universe['eligible'] == True].copy()
    
    # Extract year_month
    eligible_universe['year_month'] = eligible_universe['timestamp'].dt.strftime('%Y-%m')
    
    # Find unique symbol-months required
    symbol_months = eligible_universe.groupby(['symbol', 'year_month']).size().reset_index(name='eligible_days')
    
    # Convert year_month to datetime for easy shifting
    symbol_months['ym_dt'] = pd.to_datetime(symbol_months['year_month'], format='%Y-%m')
    
    # Determine the warmup months
    # For each symbol, we find continuous blocks of eligibility. 
    # If a month is the first in a continuous block, we need the PREVIOUS month for the 14-day warmup.
    # To be safe and simple, for any required month, if the previous month is NOT in the list, we add it as warmup.
    
    all_required = []
    
    symbols = symbol_months['symbol'].unique()
    for sym in symbols:
        sym_data = symbol_months[symbol_months['symbol'] == sym].copy()
        sym_data = sym_data.sort_values('ym_dt')
        
        existing_months = set(sym_data['ym_dt'])
        
        for _, row in sym_data.iterrows():
            # Add the primary eligible month
            all_required.append({
                'symbol': sym,
                'year_month': row['year_month'],
                'ym_dt': row['ym_dt'],
                'eligible_days': row['eligible_days'],
                'reason_required': 'ELIGIBLE_UNIVERSE',
                'warmup_start': pd.NaT,
                'warmup_days': 0
            })
            
            # Check if previous month exists
            prev_month = row['ym_dt'] - relativedelta(months=1)
            if prev_month not in existing_months:
                # Add previous month as warmup
                # We need exactly 14 days, but Binance gives us monthly zips. 
                # So we acquire the whole previous month.
                prev_month_str = prev_month.strftime('%Y-%m')
                # Avoid duplicate warmup entries if we somehow triggered it multiple times
                all_required.append({
                    'symbol': sym,
                    'year_month': prev_month_str,
                    'ym_dt': prev_month,
                    'eligible_days': 0,
                    'reason_required': 'WARMUP',
                    'warmup_start': prev_month + relativedelta(months=1) - relativedelta(days=14),
                    'warmup_days': 14
                })
                existing_months.add(prev_month) # prevent adding it twice if a gap of 1 month occurs

    manifest = pd.DataFrame(all_required)
    
    # Drop duplicates just in case
    manifest = manifest.drop_duplicates(subset=['symbol', 'year_month'])
    
    # Calculate exact required timestamps and row counts
    def get_month_stats(ym_dt):
        year = ym_dt.year
        month = ym_dt.month
        days_in_month = calendar.monthrange(year, month)[1]
        
        first_ts = datetime(year, month, 1)
        last_ts = datetime(year, month, days_in_month, 23, 59, 59)
        
        req_klines = days_in_month * 1440
        req_oi = days_in_month * 288
        req_funding = days_in_month * 3
        
        return first_ts, last_ts, req_klines, req_oi, req_funding, days_in_month

    stats = manifest['ym_dt'].apply(get_month_stats)
    manifest[['first_required_timestamp', 'last_required_timestamp', 'required_klines', 'required_OI', 'required_funding', 'total_days_in_month']] = pd.DataFrame(stats.tolist(), index=manifest.index)
    
    # Save the parquet
    manifest = manifest.drop(columns=['ym_dt', 'total_days_in_month'])
    os.makedirs('research/phase7', exist_ok=True)
    manifest.to_parquet('research/phase7/stage_b_acquisition_manifest.parquet', index=False)
    
    # Generate exact summary counts
    unique_symbols = manifest['symbol'].nunique()
    total_symbol_months = len(manifest)
    total_klines = manifest['required_klines'].sum()
    total_oi = manifest['required_OI'].sum()
    total_funding = manifest['required_funding'].sum()
    
    # Estimates
    # 1m kline zip is ~1.5MB. Monthly. -> 1.5MB * symbol_months
    # OI zip is ~2KB. Daily. -> 2KB * symbol_months * 30 
    # Funding zip is ~1KB. Monthly. -> 1KB * symbol_months
    
    monthly_zips = total_symbol_months * 2 # kline + funding
    daily_zips = int(manifest['required_OI'].sum() / 288)
    total_requests = monthly_zips + daily_zips
    
    # Rough estimate of compressed size downloaded
    est_kline_size_mb = total_symbol_months * 1.5
    est_oi_size_mb = daily_zips * 0.002
    est_funding_size_mb = total_symbol_months * 0.001
    
    total_compressed_gb = (est_kline_size_mb + est_oi_size_mb + est_funding_size_mb) / 1024
    
    # Rough estimate of uncompressed / final Parquet footprint
    # Klines: ~25 bytes per row in Parquet
    # OI: ~10 bytes per row
    # Funding: ~10 bytes per row
    total_parquet_gb = ((total_klines * 25) + (total_oi * 10) + (total_funding * 10)) / (1024**3)

    summary = {
        "exact_job_count": total_requests,
        "exact_symbol_count": unique_symbols,
        "exact_symbol_month_count": total_symbol_months,
        "expected_kline_rows": int(total_klines),
        "expected_oi_rows": int(total_oi),
        "expected_funding_rows": int(total_funding),
        "expected_download_gb": round(total_compressed_gb, 2),
        "expected_final_parquet_gb": round(total_parquet_gb, 2),
        "http_requests_required": total_requests
    }
    
    print("Manifest generation complete.")
    for k, v in summary.items():
        print(f"{k}: {v}")
        
if __name__ == "__main__":
    generate_manifest()
