import pandas as pd
import os
import glob

def check_csv_headers(data_type, market_type='um', symbol='BTCUSDT'):
    base_dir = r"c:\Users\dopa.mine\Desktop\ophelia\data\raw\binance\futures"
    target_dir = os.path.join(base_dir, market_type, symbol, data_type)
    
    files = glob.glob(os.path.join(target_dir, "*.csv"))
    if not files:
        print(f"No files found for {data_type}")
        return
        
    df = pd.read_csv(files[0], nrows=5, header=None)
    print(f"--- {data_type} first file: {os.path.basename(files[0])} ---")
    print(df.head())

if __name__ == '__main__':
    check_csv_headers('bookTicker')
    check_csv_headers('aggTrades')
