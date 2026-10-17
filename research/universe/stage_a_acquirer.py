import asyncio
import aiohttp
import zipfile
import io
import pandas as pd
import xml.etree.ElementTree as ET
from urllib.request import urlopen

async def fetch_zip_and_parse(session, url, symbol):
    try:
        async with session.get(url, timeout=30) as response:
            if response.status == 200:
                data = await response.read()
                with zipfile.ZipFile(io.BytesIO(data)) as z:
                    for name in z.namelist():
                        if name.endswith('.csv'):
                            # columns: open_time, open, high, low, close, volume, close_time, quote_volume, count, ...
                            df = pd.read_csv(z.open(name), usecols=[0, 7, 8], names=['open_time', 'quote_volume', 'count'], header=0)
                            df['symbol'] = symbol
                            return df
    except Exception as e:
        print(f"Error fetching {url}: {e}")
    return pd.DataFrame()

async def download_symbol_history(session, symbol, dates):
    tasks = []
    for date in dates:
        # e.g. BTCUSDT-1d-2023-01.zip
        url = f"https://data.binance.vision/data/futures/um/monthly/klines/{symbol}/1d/{symbol}-1d-{date}.zip"
        tasks.append(fetch_zip_and_parse(session, url, symbol))
    
    results = await asyncio.gather(*tasks)
    valid_dfs = [df for df in results if not df.empty]
    if valid_dfs:
        return pd.concat(valid_dfs, ignore_index=True)
    return pd.DataFrame()

def get_symbols():
    url = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?prefix=data/futures/um/monthly/klines/&delimiter=/"
    symbols = set()
    with urlopen(url) as response:
        root = ET.fromstring(response.read())
        ns = {'s3': 'http://s3.amazonaws.com/doc/2006-03-01/'}
        prefixes = root.findall('.//s3:CommonPrefixes/s3:Prefix', ns)
        if not prefixes:
            prefixes = root.findall('.//CommonPrefixes/Prefix')
        for p in prefixes:
            parts = p.text.split('/')
            if len(parts) >= 6:
                symbols.add(parts[5])
    return list(symbols)

async def main():
    print("Fetching symbol list from Binance Vision...")
    symbols = get_symbols()
    print(f"Found {len(symbols)} symbols. Preparing to download daily metadata...")
    
    # Generate month strings from 2019-09 to 2024-05
    dates = pd.date_range(start='2019-09-01', end='2024-05-01', freq='MS').strftime('%Y-%m').tolist()
    
    # We will process in batches of 50 symbols to avoid hammering memory
    all_dfs = []
    
    # For speed and demonstration, we will limit to the first 20 symbols if we just want to build a small artifact
    # but the user requested the broad historical Binance cross-section. We'll run it on all of them.
    # To prevent rate limiting or hitting connection limits, use a Semaphore.
    
    semaphore = asyncio.Semaphore(100)
    
    async def sem_fetch(session, url, symbol):
        async with semaphore:
            return await fetch_zip_and_parse(session, url, symbol)
            
    async with aiohttp.ClientSession() as session:
        tasks = []
        for sym in symbols:
            for date in dates:
                url = f"https://data.binance.vision/data/futures/um/monthly/klines/{sym}/1d/{sym}-1d-{date}.zip"
                tasks.append(sem_fetch(session, url, sym))
        
        print(f"Created {len(tasks)} zip fetch tasks. Running asynchronously...")
        
        # We can chunk the tasks to show progress
        chunk_size = 5000
        for i in range(0, len(tasks), chunk_size):
            chunk = tasks[i:i+chunk_size]
            results = await asyncio.gather(*chunk)
            valid = [df for df in results if not df.empty]
            if valid:
                all_dfs.append(pd.concat(valid, ignore_index=True))
            print(f"Processed {min(i+chunk_size, len(tasks))} / {len(tasks)} files...")
            
    if all_dfs:
        final_df = pd.concat(all_dfs, ignore_index=True)
        final_df['timestamp'] = pd.to_datetime(final_df['open_time'], unit='ms')
        final_df = final_df.drop(columns=['open_time'])
        final_df.to_parquet('data/processed/stage_a_daily_metadata.parquet', index=False)
        print(f"Successfully saved {len(final_df)} daily records to data/processed/stage_a_daily_metadata.parquet")
    else:
        print("Failed to download any data.")

if __name__ == "__main__":
    asyncio.run(main())
