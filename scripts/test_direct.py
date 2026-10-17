import requests
import time

url = "http://127.0.0.1:11434/api/chat"
t0 = time.time()
r = requests.post(url, json={
    "model": "qwen3:4b-direct",
    "messages": [
        {
            "role": "system",
            "content": "You are a professional trading analyst. Return only JSON."
        },
        {
            "role": "user",
            "content": "Return a trading proposal for GOLD (XAU) matching: {\"direction\": \"LONG\", \"confidence\": 75, \"thesis\": \"VWAP hold\"}"
        }
    ],
    "stream": False
}, timeout=60)
elapsed = time.time() - t0
print(f"Elapsed: {elapsed:.2f}s")
print("Response:", r.json()["message"]["content"])
