import pandas as pd
import os

path = r"c:\Users\dopa.mine\Desktop\ophelia\data\raw\binance\futures\um\BTCUSDT\aggTrades\BTCUSDT-aggTrades-2023-01-01.csv"

if os.path.exists(path):
    try:
        # Check if headers exist
        df = pd.read_csv(path, nrows=5)
        print("COLUMNS FOUND IN BTCUSDT-aggTrades-2023-01-01.csv:")
        print(df.columns.tolist())
        print(df.head())
    except Exception as e:
        print("Error reading CSV:", e)
else:
    print(f"File not found: {path}")

# Check monthly file
monthly_path = r"c:\Users\dopa.mine\Desktop\ophelia\data\raw\binance\futures\um\BTCUSDT\aggTrades\BTCUSDT-aggTrades-2023-01.csv"
if os.path.exists(monthly_path):
    try:
        df_monthly = pd.read_csv(monthly_path, nrows=5)
        print("\nCOLUMNS FOUND IN MONTHLY BTCUSDT-aggTrades-2023-01.csv:")
        print(df_monthly.columns.tolist())
    except Exception as e:
        print("Error reading monthly CSV:", e)
