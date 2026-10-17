import os
import json
import time
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any

from research.pipeline.data_loader import ResearchDataLoader
from research.pipeline.labels import LabelGenerator
from utils.logger import logger

FORWARD_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'forward'))
MANIFEST_FILE = os.path.join(FORWARD_DATA_DIR, "manifest.json")
FORWARD_METRICS_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'results', 'phase5_3_4_forward_metrics.json'))

class ForwardDataStore:
    def __init__(self, data_dir=FORWARD_DATA_DIR):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self.manifest_path = os.path.join(self.data_dir, "manifest.json")
        self._load_manifest()
        
    def _load_manifest(self):
        if os.path.exists(self.manifest_path):
            with open(self.manifest_path, "r") as f:
                self.manifest = json.load(f)
        else:
            self.manifest = {
                "symbols": {}
            }
            
    def _save_manifest(self):
        with open(self.manifest_path, "w") as f:
            json.dump(self.manifest, f, indent=4)
            
    def append_data(self, df: pd.DataFrame, source: str, data_version: str):
        if df.empty:
            return
            
        symbol = df['symbol'].iloc[0]
        df = df.sort_values("timestamp")
        
        file_path = os.path.join(self.data_dir, f"{symbol}.parquet")
        
        if os.path.exists(file_path):
            existing_df = pd.read_parquet(file_path)
            new_df = df[~df['timestamp'].isin(existing_df['timestamp'])]
            if new_df.empty:
                return
            combined_df = pd.concat([existing_df, new_df]).sort_values("timestamp").reset_index(drop=True)
        else:
            combined_df = df.reset_index(drop=True)
            new_df = combined_df
            
        combined_df.to_parquet(file_path)
        
        if symbol not in self.manifest["symbols"]:
            self.manifest["symbols"][symbol] = {}
            
        sym_manifest = self.manifest["symbols"][symbol]
        sym_manifest["latest_source_event_timestamp"] = int(pd.to_datetime(combined_df['timestamp'].max()).timestamp() * 1000)
        sym_manifest["latest_ingestion_timestamp"] = int(time.time() * 1000)
        sym_manifest["data_version"] = data_version
        sym_manifest["source_exchange"] = source
        sym_manifest["timeframe"] = "5m"
        
        self._save_manifest()
        
    def get_data(self, symbol: str) -> pd.DataFrame:
        file_path = os.path.join(self.data_dir, f"{symbol}.parquet")
        if not os.path.exists(file_path):
            return pd.DataFrame()
        return pd.read_parquet(file_path)

class ForwardPaperTracker:
    def __init__(self, signals_file: str, forward_store: ForwardDataStore):
        self.signals_file = signals_file
        self.forward_store = forward_store
        
        self.historical_stats = {}
        
    def calculate_historical_drift_baseline(self, symbol: str):
        if symbol in self.historical_stats:
            return
            
        loader = ResearchDataLoader()
        try:
            hist_df = loader.load_symbol(symbol)
            hist_df = hist_df[hist_df['timestamp'] < pd.to_datetime('2024-01-01')]
            stats = {}
            for col in hist_df.columns:
                if col.startswith('cvd_'):
                    stats[col] = {
                        "mean": float(hist_df[col].mean()),
                        "std": float(hist_df[col].std())
                    }
            self.historical_stats[symbol] = stats
        except Exception as e:
            logger.warning(f"Could not load historical data for {symbol}: {e}")

    def evaluate_signals(self) -> Dict[str, Any]:
        if not os.path.exists(self.signals_file):
            return {"status": "NO_FORWARD_DATA"}
            
        signals = []
        with open(self.signals_file, "r") as f:
            for line in f:
                rec = json.loads(line)
                if not rec.get("suppressed", False):
                    signals.append(rec)
                    
        if not signals:
            return {"status": "NO_FORWARD_DATA"}
            
        sym_signals = {}
        for s in signals:
            sym = s["symbol"]
            sym_signals.setdefault(sym, []).append(s)
            
        outcomes = []
        pending_count = 0
        completed_count = 0
        
        for symbol, sig_list in sym_signals.items():
            self.calculate_historical_drift_baseline(symbol)
            
            fwd_df = self.forward_store.get_data(symbol)
            if fwd_df.empty:
                pending_count += len(sig_list)
                for s in sig_list:
                    s["outcome_status"] = "OUTCOME_PENDING"
                    outcomes.append(s)
                continue
                
            fwd_df['timestamp_ms'] = (pd.to_datetime(fwd_df['timestamp']) - pd.Timestamp("1970-01-01")) // pd.Timedelta('1ms')
            fwd_df = LabelGenerator.generate_labels(fwd_df, horizons=[1, 3, 6, 12, 60], thresholds_bps=[10])
            
            for s in sig_list:
                t_decision = s["decision_timestamp"]
                row = fwd_df[fwd_df['timestamp_ms'] == t_decision]
                if row.empty:
                    s["outcome_status"] = "OUTCOME_PENDING"
                    pending_count += 1
                else:
                    idx = row.index[0]
                    if idx + 60 >= len(fwd_df):
                        s["outcome_status"] = "OUTCOME_PENDING"
                        pending_count += 1
                    else:
                        r_row = row.iloc[0]
                        s["outcome_status"] = "OUTCOME_COMPLETE"
                        s["returns"] = {
                            "5m": r_row.get("R_1", np.nan),
                            "15m": r_row.get("R_3", np.nan),
                            "30m": r_row.get("R_6", np.nan),
                            "60m": r_row.get("R_12", np.nan),
                            "5h": r_row.get("R_60", np.nan)
                        }
                        s["target_60_up_10"] = r_row.get("target_60_up_10", np.nan)
                        
                        window = fwd_df.iloc[idx+1:idx+61]
                        entry = r_row['close']
                        s["MFE"] = float(np.log(window['high'].max() / entry))
                        s["MAE"] = float(np.log(window['low'].min() / entry))
                        
                        completed_count += 1
                outcomes.append(s)
                
        metrics = {
            "evaluation_timestamp": int(time.time() * 1000),
            "total_signals": len(signals),
            "pending_count": pending_count,
            "completed_count": completed_count,
            "status": "FORWARD VALIDATION COMPLETE" if pending_count == 0 else "OBSERVATION IN PROGRESS"
        }
        
        self._append_metrics(metrics)
        
        return metrics

    def _append_metrics(self, metrics: dict):
        os.makedirs(os.path.dirname(FORWARD_METRICS_FILE), exist_ok=True)
        if os.path.exists(FORWARD_METRICS_FILE):
            with open(FORWARD_METRICS_FILE, "r") as f:
                data = json.load(f)
        else:
            data = {"snapshots": []}
            
        data["snapshots"].append(metrics)
        
        with open(FORWARD_METRICS_FILE, "w") as f:
            json.dump(data, f, indent=4)
