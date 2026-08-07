import requests

BASE_URL = "https://open-api.bingx.com"

endpoints = [
    "/openApi/swap/v2/quote/price",
    "/openApi/swap/v3/quote/price",
    "/openApi/swap/v2/quote/klines",
    "/openApi/swap/v3/quote/klines",
]

for endpoint in endpoints:

    url = f"{BASE_URL}{endpoint}?symbol=SOL-USDT"

    print("=" * 60)
    print(url)

    try:
        r = requests.get(url, timeout=10)

        print("Status:", r.status_code)

        print(r.text[:400])

    except Exception as e:
        print(e)