"""Ophelia Phase 12: Fresh Chronological Dataset Ingestion & Preparation.

Downloads and consolidates completely fresh chronological Binance Futures data:
Period: 2023-12-01 00:00:00 UTC to 2024-03-31 23:59:59 UTC (122 continuous days)
Symbols: BTCUSDT, ETHUSDT, SOLUSDT

Zero overlap with Phase 10.3 / Phase 11 / Phase 11.5 (which used Oct 01 to Nov 30, 2023).
"""
import datetime
import io
import json
import logging
import os
import sys
import urllib.request
import zipfile
from typing import Dict, List

import numpy as np
import pandas as pd
import pyarrow.dataset as ds

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("phase12_prepare")

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
MONTHS_2024 = ["2024-01", "2024-02", "2024-03"]
T_DEC_01_2023 = int(datetime.datetime(2023, 12, 1, 0, 0, 0, tzinfo=datetime.timezone.utc).timestamp() * 1000)
T_DEC_31_2023 = int(datetime.datetime(2023, 12, 31, 23, 59, 59, tzinfo=datetime.timezone.utc).timestamp() * 1000)
T_MAR_31_2024 = int(datetime.datetime(2024, 3, 31, 23, 59, 59, tzinfo=datetime.timezone.utc).timestamp() * 1000)


def fetch_binance_vision_monthly(symbol: str, month_str: str) -> pd.DataFrame:
    """Fetches and parses a monthly 1m kline zip from Binance Vision."""
    url = f"https://data.binance.vision/data/futures/um/monthly/klines/{symbol}/1m/{symbol}-1m-{month_str}.zip"
    logger.info("Downloading %s from %s ...", f"{symbol}-{month_str}", url)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        content = resp.read()
    zf = zipfile.ZipFile(io.BytesIO(content))
    csv_name = zf.namelist()[0]
    with zf.open(csv_name) as f:
        df = pd.read_csv(f)
    
    # Standardize column names
    col_map = {
        "open_time": "timestamp",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume"
    }
    df = df.rename(columns=col_map)
    df = df[["timestamp", "open", "high", "low", "close", "volume"]]
    df["symbol"] = symbol
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    df["timestamp"] = df["timestamp"].astype(int)
    return df


def load_dec_2023_from_parquet(parquet_path: str, symbol: str) -> pd.DataFrame:
    """Loads December 2023 1m bars from existing v2 parquet."""
    dataset = ds.dataset(parquet_path, format="parquet")
    filt = (
        (ds.field("timestamp") >= T_DEC_01_2023) &
        (ds.field("timestamp") <= T_DEC_31_2023) &
        (ds.field("symbol") == symbol)
    )
    cols = ["timestamp", "open", "high", "low", "close", "volume", "symbol"]
    tbl = dataset.to_table(filter=filt, columns=cols)
    df = tbl.to_pandas().sort_values("timestamp").reset_index(drop=True)
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    df["timestamp"] = df["timestamp"].astype(int)
    return df


def main():
    parquet_v2 = "data/processed/binance_um_universe_1m_v2.parquet"
    out_dir = "data/processed"
    os.makedirs(out_dir, exist_ok=True)
    out_parquet = os.path.join(out_dir, "phase12_fresh_universe_1m.parquet")
    out_meta = os.path.join(out_dir, "phase12_fresh_dataset_metadata.json")

    metadata = {
        "data_period": "2023-12-01 00:00:00 UTC to 2024-03-31 23:59:59 UTC",
        "calendar_days": 122,
        "symbols": SYMBOLS,
        "symbols_stats": {}
    }

    all_dfs = []

    for sym in SYMBOLS:
        logger.info("Processing %s ...", sym)
        df_dec = load_dec_2023_from_parquet(parquet_v2, sym)
        logger.info("%s Dec 2023: %d bars", sym, len(df_dec))

        month_dfs = [df_dec]
        for m in MONTHS_2024:
            df_m = fetch_binance_vision_monthly(sym, m)
            logger.info("%s %s: %d bars", sym, m, len(df_m))
            month_dfs.append(df_m)

        sym_df = pd.concat(month_dfs, ignore_index=True)
        sym_df = sym_df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

        # Expected 1m bars: 122 days * 1440 min/day = 175,680 min (leap year 2024: Feb has 29 days)
        # Dec(31) + Jan(31) + Feb(29) + Mar(31) = 122 days
        expected_1m = 122 * 1440
        actual_1m = len(sym_df)
        missing_1m = expected_1m - actual_1m
        coverage_pct = round((actual_1m / expected_1m) * 100.0, 3)

        ts_min = int(sym_df["timestamp"].min())
        ts_max = int(sym_df["timestamp"].max())
        dt_start = datetime.datetime.fromtimestamp(ts_min / 1000, tz=datetime.timezone.utc).isoformat()
        dt_end = datetime.datetime.fromtimestamp(ts_max / 1000, tz=datetime.timezone.utc).isoformat()

        logger.info("%s Consolidated: %d 1m bars (expected %d, missing %d, coverage %.2f%%)",
                    sym, actual_1m, expected_1m, missing_1m, coverage_pct)

        metadata["symbols_stats"][sym] = {
            "start_ts": ts_min,
            "end_ts": ts_max,
            "start_utc": dt_start,
            "end_utc": dt_end,
            "bars_1m": actual_1m,
            "expected_1m": expected_1m,
            "missing_1m": missing_1m,
            "coverage_pct": coverage_pct,
            "closed_5m_bars": actual_1m // 5,
            "closed_1h_bars": actual_1m // 60,
            "closed_4h_bars": actual_1m // 240,
        }
        all_dfs.append(sym_df)

    final_df = pd.concat(all_dfs, ignore_index=True)
    logger.info("Writing consolidated fresh dataset to %s (%d rows) ...", out_parquet, len(final_df))
    final_df.to_parquet(out_parquet, index=False)

    with open(out_meta, "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info("Phase 12 dataset preparation complete. Metadata saved to %s", out_meta)
    print("\n" + "=" * 70)
    print("PHASE 12 FRESH CHRONOLOGICAL DATASET SUMMARY")
    print("=" * 70)
    print(f"Period:        {metadata['data_period']} ({metadata['calendar_days']} calendar days)")
    for sym, s in metadata["symbols_stats"].items():
        print(f"  {sym:8s}: 1m bars={s['bars_1m']}, 5m bars={s['closed_5m_bars']}, 1H bars={s['closed_1h_bars']}, 4H bars={s['closed_4h_bars']}, Cov={s['coverage_pct']}%")
    print("=" * 70)


if __name__ == "__main__":
    main()
