import urllib.request
from urllib.error import URLError, HTTPError

def check_url(url):
    req = urllib.request.Request(url, method="HEAD")
    try:
        urllib.request.urlopen(req)
        print(f"[OK] {url}")
        return True
    except HTTPError as e:
        print(f"[FAIL {e.code}] {url}")
        return False
    except URLError as e:
        print(f"[FAIL] {url} - {e.reason}")
        return False

if __name__ == "__main__":
    symbol = "BTCUSDT"
    year = "2023"
    month = "01"
    
    urls = [
        f"https://data.binance.vision/data/futures/um/daily/metrics/{symbol}/{symbol}-metrics-{year}-{month}-01.zip",
        f"https://data.binance.vision/data/futures/um/monthly/premiumIndexKlines/{symbol}/5m/{symbol}-5m-{year}-{month}.zip",
        f"https://data.binance.vision/data/futures/um/monthly/fundingRate/{symbol}/{symbol}-fundingRate-{year}-{month}.zip"
    ]
    
    for u in urls:
        check_url(u)
