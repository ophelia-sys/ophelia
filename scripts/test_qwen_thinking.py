import requests
import time

url = "http://127.0.0.1:11434/api/chat"

# In Qwen 3, to prevent thinking tokens or get fast generation:
# We pass options with num_predict and stop tokens, or system prompt
t0 = time.time()
try:
    r = requests.post(url, json={
        "model": "qwen3:4b",
        "messages": [
            {
                "role": "system",
                "content": "You are a crypto trader. Respond ONLY with a JSON object. No reasoning or thinking."
            },
            {
                "role": "user",
                "content": "Analyze Gold price action and give LONG/SHORT bias. Output ONLY JSON: {\"direction\": \"LONG\", \"confidence\": 75, \"thesis\": \"Bullish vwap hold\"}"
            }
        ],
        "options": {
            "temperature": 0.1,
            "num_predict": 120
        },
        "stream": False
    }, timeout=45)
    elapsed = time.time() - t0
    print(f"Status: {r.status_code}, Elapsed: {elapsed:.2f}s")
    content = r.json()["message"]["content"]
    print("Content preview:", content[:300])
except Exception as e:
    print("Error:", e)
