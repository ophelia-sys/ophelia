import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def audit_datasets(data_dir, symbols):
    norm_dir = os.path.join(data_dir, 'normalized', 'positioning')
    
    start_dt = pd.to_datetime('2022-01-01 00:00:00')
    end_dt = pd.to_datetime('2023-12-31 23:55:00')
    expected_5m = pd.date_range(start=start_dt, end=end_dt, freq='5min')
    
    results = {}
    
    for sym in symbols:
        sym_u = sym.upper()
        print(f"Auditing {sym_u}...")
        results[sym_u] = {}
        
        # 1. METRICS AUDIT
        metrics_file = os.path.join(norm_dir, f"{sym_u}_metrics.parquet")
        if os.path.exists(metrics_file):
            df_m = pd.read_parquet(metrics_file)
            df_m['create_time'] = pd.to_datetime(df_m['create_time'])
            
            total_rows = len(df_m)
            dup_ts = df_m['create_time'].duplicated().sum()
            
            # For NaNs, check the required columns
            col_oi = 'sum_open_interest'
            col_oiv = 'sum_open_interest_value'
            col_lsr = 'count_long_short_ratio'
            
            nan_oi = df_m[col_oi].isna().sum() if col_oi in df_m.columns else total_rows
            nan_oiv = df_m[col_oiv].isna().sum() if col_oiv in df_m.columns else total_rows
            nan_lsr = df_m[col_lsr].isna().sum() if col_lsr in df_m.columns else total_rows
            
            required_cols = [c for c in [col_oi, col_oiv, col_lsr] if c in df_m.columns]
            any_nan = df_m[required_cols].isna().any(axis=1).sum() if required_cols else total_rows
            
            inf_count = np.isinf(df_m[required_cols].select_dtypes(include=np.number)).sum().sum()
            
            # Continuity
            ts = df_m['create_time']
            unexpected = (~ts.dt.minute.isin(range(0, 60, 5))) | (ts.dt.second != 0)
            unexp_count = unexpected.sum()
            
            valid_ts = ts[~unexpected].drop_duplicates()
            missing_ts = expected_5m.difference(valid_ts)
            
            results[sym_u]['metrics'] = {
                'total_rows': total_rows,
                'nan_oi': int(nan_oi),
                'nan_oiv': int(nan_oiv),
                'nan_lsr': int(nan_lsr),
                'any_nan': int(any_nan),
                'dup_ts': int(dup_ts),
                'unexp_ts': int(unexp_count),
                'missing_ts': len(missing_ts),
                'inf_count': int(inf_count),
                'missing_intervals': missing_ts
            }
        else:
            results[sym_u]['metrics'] = None
            
        # 2. PREMIUM INDEX AUDIT
        pi_file = os.path.join(norm_dir, f"{sym_u}_premiumIndex.parquet")
        if os.path.exists(pi_file):
            df_pi = pd.read_parquet(pi_file)
            df_pi['datetime'] = pd.to_datetime(df_pi['datetime'])
            
            total_rows_pi = len(df_pi)
            dup_ts_pi = df_pi['datetime'].duplicated().sum()
            
            ts_pi = df_pi['datetime']
            unexpected_pi = (~ts_pi.dt.minute.isin(range(0, 60, 5))) | (ts_pi.dt.second != 0)
            unexp_count_pi = unexpected_pi.sum()
            
            valid_ts_pi = ts_pi[~unexpected_pi].drop_duplicates()
            missing_ts_pi = expected_5m.difference(valid_ts_pi)
            
            results[sym_u]['premium'] = {
                'total_rows': total_rows_pi,
                'dup_ts': int(dup_ts_pi),
                'unexp_ts': int(unexp_count_pi),
                'missing_ts': len(missing_ts_pi),
                'missing_intervals': missing_ts_pi
            }
        else:
            results[sym_u]['premium'] = None
            
        # 3. FUNDING RATE AUDIT
        fr_file = os.path.join(norm_dir, f"{sym_u}_fundingRate.parquet")
        if os.path.exists(fr_file):
            df_fr = pd.read_parquet(fr_file)
            df_fr['datetime'] = pd.to_datetime(df_fr['datetime'])
            
            total_events = len(df_fr)
            dup_fr = df_fr['datetime'].duplicated().sum()
            
            ts_fr = df_fr['datetime'].sort_values()
            diffs = ts_fr.diff().dropna()
            
            if len(diffs) > 0:
                min_diff = diffs.min()
                max_diff = diffs.max()
                freq_dist = diffs.value_counts().to_dict()
            else:
                min_diff = pd.Timedelta(0)
                max_diff = pd.Timedelta(0)
                freq_dist = {}
                
            first_event = ts_fr.iloc[0] if len(ts_fr) > 0 else None
            last_event = ts_fr.iloc[-1] if len(ts_fr) > 0 else None
            
            results[sym_u]['funding'] = {
                'total_events': total_events,
                'dup_ts': int(dup_fr),
                'min_diff': str(min_diff),
                'max_diff': str(max_diff),
                'freq_dist': {str(k): int(v) for k, v in freq_dist.items()},
                'first_event': str(first_event),
                'last_event': str(last_event)
            }
        else:
            results[sym_u]['funding'] = None
            
    import json
    
    # We will format missing intervals for readability
    for sym in symbols:
        for k in ['metrics', 'premium']:
            if results[sym][k] is not None:
                miss_ts = results[sym][k]['missing_intervals']
                intervals = []
                if len(miss_ts) > 0:
                    start_i = miss_ts[0]
                    prev_i = miss_ts[0]
                    for t in miss_ts[1:]:
                        if t - prev_i > pd.Timedelta('5min'):
                            intervals.append((str(start_i), str(prev_i)))
                            start_i = t
                        prev_i = t
                    intervals.append((str(start_i), str(prev_i)))
                results[sym][k]['missing_intervals_compact'] = intervals
                del results[sym][k]['missing_intervals']
                
    with open('positioning_audit_results.json', 'w') as f:
        json.dump(results, f, indent=4)
        
if __name__ == '__main__':
    data_dir = 'c:/Users/dopa.mine/Desktop/ophelia/data'
    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT', 'ADAUSDT']
    audit_datasets(data_dir, symbols)
