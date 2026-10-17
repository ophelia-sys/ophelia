import os
import pandas as pd
import numpy as np
import zipfile
import glob

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DATASET_PATH = os.path.join(BASE_DIR, 'data', 'processed', 'binance_um_universe_1m_v2.parquet')
RAW_DIR = os.path.join(BASE_DIR, 'data', 'raw')

def independent_robust_z(series_window, current_val):
    valid_x = series_window[~np.isnan(series_window)]
    if len(valid_x) == 0:
        return np.nan, np.nan, np.nan, np.nan
        
    med = np.median(valid_x)
    mad = np.median(np.abs(valid_x - med))
    
    mad_scaled = mad * 1.4826
    denominator = 1.0 if mad_scaled == 0 else mad_scaled
    z = (current_val - med) / denominator
    
    if mad_scaled == 0:
        if current_val == med:
            z = 0.0
        else:
            z = np.nan
            
    return z, med, mad, denominator

def load_symbol_raw_metrics(symbol):
    print(f"Loading raw metrics for {symbol}...")
    metric_files = glob.glob(os.path.join(RAW_DIR, symbol, f"{symbol}-metrics-*.zip"))
    metric_dfs = []
    for mf in sorted(metric_files):
        try:
            with zipfile.ZipFile(mf, 'r') as z:
                csv_name = z.namelist()[0]
                with z.open(csv_name) as f:
                    raw_df = pd.read_csv(f)
                    raw_dt = pd.to_datetime(raw_df['create_time'], errors='coerce', format='mixed', utc=True)
                    raw_dt_naive = raw_dt.dt.tz_convert(None)
                    raw_df['timestamp'] = ((raw_dt_naive - pd.Timestamp("1970-01-01")) // pd.Timedelta('1ms')).astype('int64')
                    raw_df = raw_df.drop_duplicates(subset=['timestamp'], keep='last')
                    metric_dfs.append(raw_df)
        except:
            pass
    if metric_dfs:
        df = pd.concat(metric_dfs, ignore_index=True)
        df = df.sort_values('timestamp').reset_index(drop=True)
        df['delta_oi'] = df['sum_open_interest'].diff()
        return df
    return pd.DataFrame()

def reconcile_extreme_events():
    print(f"Loading {DATASET_PATH}...")
    df = pd.read_parquet(DATASET_PATH)
    
    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'ADAUSDT', 'XRPUSDT']
    results = []
    
    for symbol in symbols:
        sym_df = df[df['symbol'] == symbol].copy()
        
        sym_df['returns'] = sym_df['close'].pct_change()
        sym_df['volatility_60m'] = sym_df['returns'].rolling(60).std()
        sym_df['volume_mean_60m'] = sym_df['volume'].rolling(60).mean()
        
        sym_df['abs_Z'] = sym_df['Z_DeltaOI'].abs()
        top_10 = sym_df.nlargest(10, 'abs_Z')  # Top 10 to speed up output
        
        raw_df = load_symbol_raw_metrics(symbol)
        
        for idx, row in top_10.iterrows():
            candle_ts = row['timestamp']
            oi_ts = row['oi_timestamp']
            canonical_oi = row['sum_open_interest']
            canonical_z = row['Z_DeltaOI']
            
            raw_confirmed = False
            is_market_corroborated = False
            numerical_cause = "UNKNOWN"
            
            if not raw_df.empty and pd.notna(oi_ts):
                # find the index in raw_df of this oi_ts
                matches = raw_df.index[raw_df['timestamp'] == int(oi_ts)].tolist()
                if matches:
                    raw_idx = matches[0]
                    raw_current_oi = raw_df.loc[raw_idx, 'sum_open_interest']
                    raw_delta = raw_df.loc[raw_idx, 'delta_oi']
                    
                    if raw_idx >= 100:
                        window_vals = raw_df.loc[raw_idx-100:raw_idx-1, 'delta_oi'].values
                        
                        z, med, mad, denom = independent_robust_z(window_vals, raw_delta)
                        
                        if np.isclose(canonical_oi, raw_current_oi) and (pd.isna(canonical_z) and pd.isna(z) or np.isclose(canonical_z, z)):
                            raw_confirmed = True
                        
                        ret = row['returns']
                        vol_sd = row['volatility_60m']
                        vol = row['volume']
                        vol_mean = row['volume_mean_60m']
                        
                        if pd.notna(ret) and pd.notna(vol_sd) and pd.notna(vol_mean):
                            if abs(ret) > (3 * vol_sd) or vol > (3 * vol_mean):
                                is_market_corroborated = True
                        
                        if abs(raw_delta) > 100 * mad:
                            numerical_cause = "GENUINELY_LARGE_NUMERATOR"
                        elif denom < 1e-3:
                            numerical_cause = "ABNORMALLY_SMALL_DISPERSION"
                        else:
                            numerical_cause = "BOTH"
                            
                        results.append({
                            'symbol': symbol,
                            'candle_ts': candle_ts,
                            'Z': canonical_z,
                            'DeltaOI': raw_delta,
                            'med': med,
                            'mad': mad,
                            'denom': denom,
                            'raw_confirmed': raw_confirmed,
                            'class': "MARKET_CORROBORATED" if raw_confirmed and is_market_corroborated else ("RAW_DATA_CONFIRMED_NO_MARKET_CORROBORATION" if raw_confirmed else "DATA_OR_NUMERICAL_ANOMALY"),
                            'numerical_cause': numerical_cause
                        })
    
    res_df = pd.DataFrame(results)
    print("\n==========================================")
    print("EXTREME EVENT CLASSIFICATIONS")
    print("==========================================")
    print(res_df['class'].value_counts())
    print("\nNUMERICAL CAUSES:")
    print(res_df['numerical_cause'].value_counts())
    
    print("\nSAMPLE EXTREME EVENTS:")
    print(res_df.head(10).to_string())
    
    res_df.to_csv(os.path.join(BASE_DIR, 'research', 'phase6', 'extreme_event_audit.csv'), index=False)

if __name__ == "__main__":
    reconcile_extreme_events()
