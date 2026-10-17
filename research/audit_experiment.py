import requests
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss, precision_score
import json

def fetch_data():
    url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=5m&limit=1000"
    response = requests.get(url)
    data = response.json()
    
    df = pd.DataFrame(data, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "number_of_trades",
        "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
    ])
    df["close"] = df["close"].astype(float)
    df["open"] = df["open"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)
    df["volume"] = df["volume"].astype(float)
    return df

def run_experiment():
    df = fetch_data()
    
    # 1. Feature Engineering
    df["returns"] = np.log(df["close"] / df["close"].shift(1))
    df["volatility_20"] = df["returns"].rolling(window=20).std()
    df["momentum_10"] = df["close"] / df["close"].shift(10) - 1
    
    # Target: 1 if next candle is positive, 0 if negative
    df["target"] = (df["returns"].shift(-1) > 0).astype(int)
    
    # Drop NAs
    df.dropna(inplace=True)
    
    # 2. Train / Test Split (Chronological)
    split_idx = int(len(df) * 0.8)
    train_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:]
    
    features = ["returns", "volatility_20", "momentum_10"]
    X_train = train_df[features]
    y_train = train_df["target"]
    X_test = test_df[features]
    y_test = test_df["target"]
    
    # 3. Model Training
    model = LogisticRegression(class_weight='balanced')
    model.fit(X_train, y_train)
    
    # 4. Predictions
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    
    # 5. Metrics
    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    ll = log_loss(y_test, y_prob)
    
    results = {
        "experiment_id": "EXP_001_BASELINE",
        "dataset": "Binance BTCUSDT 5m (1000 candles)",
        "features": features,
        "model": "LogisticRegression",
        "validation_method": "Chronological (80/20)",
        "metrics": {
            "accuracy": round(acc, 4),
            "precision": round(prec, 4),
            "log_loss": round(ll, 4)
        }
    }
    
    with open("audit_experiment_results.json", "w") as f:
        json.dump(results, f, indent=4)
        
    print(json.dumps(results, indent=4))

if __name__ == "__main__":
    run_experiment()
