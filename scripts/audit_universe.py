import urllib.request
import concurrent.futures
import datetime
import calendar
import json
import os

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT", "XRPUSDT"]
START_DATE = datetime.date(2022, 1, 1)
END_DATE = datetime.date(2023, 12, 31)

BASE_KLINES = "https://data.binance.vision/data/futures/um/monthly/klines"
BASE_METRICS = "https://data.binance.vision/data/futures/um/daily/metrics"

def generate_monthly_urls(symbol):
    urls = []
    curr = START_DATE.replace(day=1)
    while curr <= END_DATE:
        period = f"{curr.year}-{curr.month:02d}"
        url = f"{BASE_KLINES}/{symbol}/1m/{symbol}-1m-{period}.zip"
        urls.append(('kline', symbol, period, url))
        
        # Advance month
        if curr.month == 12:
            curr = curr.replace(year=curr.year+1, month=1)
        else:
            curr = curr.replace(month=curr.month+1)
    return urls

def generate_daily_urls(symbol):
    urls = []
    curr = START_DATE
    while curr <= END_DATE:
        period = f"{curr.year}-{curr.month:02d}-{curr.day:02d}"
        url = f"{BASE_METRICS}/{symbol}/{symbol}-metrics-{period}.zip"
        urls.append(('metric', symbol, period, url))
        curr += datetime.timedelta(days=1)
    return urls

def check_url(item):
    type_, symbol, period, url = item
    req = urllib.request.Request(url, method='HEAD')
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                length = int(response.getheader('Content-Length', 0))
                return (item, True, length)
    except Exception:
        pass
    return (item, False, 0)

def main():
    print("Generating URLs...")
    all_urls = []
    for s in SYMBOLS:
        all_urls.extend(generate_monthly_urls(s))
        all_urls.extend(generate_daily_urls(s))
        
    print(f"Checking {len(all_urls)} URLs concurrently...")
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(check_url, u): u for u in all_urls}
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            results.append(future.result())
            if (i+1) % 500 == 0:
                print(f"Processed {i+1}/{len(all_urls)}...")

    print("Aggregating results...")
    
    report = []
    report.append("# Phase 6 Perpetual Universe Selection")
    report.append("")
    report.append("## Dry-Run Audit Results")
    report.append("Date Range: 2022-01-01 to 2023-12-31")
    report.append("")
    
    total_zip_size = 0
    total_parquet_size = 0
    total_rows = 0
    
    for symbol in SYMBOLS:
        k_results = [r for r in results if r[0][1] == symbol and r[0][0] == 'kline']
        m_results = [r for r in results if r[0][1] == symbol and r[0][0] == 'metric']
        
        k_found = [r for r in k_results if r[1]]
        k_missing = [r for r in k_results if not r[1]]
        
        m_found = [r for r in m_results if r[1]]
        m_missing = [r for r in m_results if not r[1]]
        
        k_size = sum(r[2] for r in k_found)
        m_size = sum(r[2] for r in m_found)
        
        symbol_zip_size = k_size + m_size
        symbol_parquet_size = symbol_zip_size * 0.8 # Rough heuristic
        
        symbol_rows = sum(calendar.monthrange(int(r[0][2].split('-')[0]), int(r[0][2].split('-')[1]))[1] * 1440 for r in k_found)
        
        total_zip_size += symbol_zip_size
        total_parquet_size += symbol_parquet_size
        total_rows += symbol_rows
        
        k_coverage = len(k_found) / len(k_results) * 100 if k_results else 0
        m_coverage = len(m_found) / len(m_results) * 100 if m_results else 0
        
        report.append(f"### {symbol}")
        report.append(f"- **Listing / Range Checked**: {START_DATE} to {END_DATE}")
        report.append(f"- **Kline (Monthly) Coverage**: {len(k_found)} / {len(k_results)} ({k_coverage:.1f}%)")
        report.append(f"- **Metrics (Daily) Coverage**: {len(m_found)} / {len(m_results)} ({m_coverage:.1f}%)")
        report.append(f"- **Missing Kline Archives**: {len(k_missing)}")
        if k_missing:
            report.append(f"  - e.g., {', '.join([r[0][2] for r in k_missing[:5]])}")
        report.append(f"- **Missing Metrics Archives**: {len(m_missing)}")
        if m_missing:
            report.append(f"  - e.g., {', '.join([r[0][2] for r in m_missing[:5]])}")
        report.append(f"- **Expected Rows**: ~{symbol_rows:,}")
        report.append(f"- **Estimated ZIP Size**: {symbol_zip_size / 1024 / 1024:.2f} MB")
        report.append(f"- **Estimated Parquet Size**: {symbol_parquet_size / 1024 / 1024:.2f} MB")
        
        if k_coverage == 100 and m_coverage >= 99:
            report.append("- **Selection Status**: ACCEPTED")
        else:
            report.append(f"- **Selection Status**: REJECTED (Insufficient historical coverage)")
        report.append("")

    report.append("## Overall Resource Estimation")
    report.append(f"- **Total Target Symbols**: {len(SYMBOLS)}")
    report.append(f"- **Total Expected Rows**: ~{total_rows:,}")
    report.append(f"- **Total Estimated ZIP Download Size**: {total_zip_size / 1024 / 1024 / 1024:.2f} GB")
    report.append(f"- **Total Estimated Normalized Parquet Size**: {total_parquet_size / 1024 / 1024 / 1024:.2f} GB")
    report.append(f"- **Total Estimated Storage Requirement**: {(total_zip_size + total_parquet_size) / 1024 / 1024 / 1024:.2f} GB")
    report.append("")
    report.append("Storage footprint is highly manageable.")

    with open("PHASE6_PERPETUAL_UNIVERSE_SELECTION.md", "w") as f:
        f.write("\n".join(report))
        
    print("Audit complete. Written to PHASE6_PERPETUAL_UNIVERSE_SELECTION.md")

if __name__ == '__main__':
    main()
