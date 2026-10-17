import os
import json
import psutil
import time
from datetime import datetime

LOG_FILE = os.path.join(os.path.dirname(__file__), "../logs/ophelia.log")

def get_health_status():
    status = {
        "process_status": "DOWN",
        "last_market_data_timestamp": None,
        "last_completed_5m_bar": None,
        "last_inference_timestamp": None,
        "last_decision_timestamp": None,
        "cvd_stream_status": "UNKNOWN",
        "websocket_status": "UNKNOWN",
        "feature_validity": "UNKNOWN",
        "inference_errors": 0,
        "missing_data_rate": 0.0,
        "disk_usage_percent": 0.0,
        "memory_usage_percent": 0.0,
        "service_uptime_seconds": 0
    }

    # Check process
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
        if proc.info['cmdline'] and 'python' in proc.info['cmdline'][0] and 'main.py' in ' '.join(proc.info['cmdline']):
            status["process_status"] = "UP"
            status["service_uptime_seconds"] = int(time.time() - proc.info['create_time'])
            break

    # Disk and memory
    disk = psutil.disk_usage('/')
    status["disk_usage_percent"] = disk.percent
    mem = psutil.virtual_memory()
    status["memory_usage_percent"] = mem.percent

    if not os.path.exists(LOG_FILE):
        return status

    # Parse log for shadow decisions
    try:
        with open(LOG_FILE, "r") as f:
            # Read last 1000 lines efficiently
            lines = f.readlines()[-1000:]
            
            for line in reversed(lines):
                if "[SHADOW_JSON]" in line:
                    try:
                        json_str = line.split("[SHADOW_JSON]")[-1].strip()
                        data = json.loads(json_str)
                        if status["last_decision_timestamp"] is None:
                            status["last_decision_timestamp"] = data.get("timestamp")
                            status["last_inference_timestamp"] = data.get("timestamp")
                            status["feature_validity"] = data.get("feature_validity")
                            
                            # Calculate missing data rate over recent logs
                            total_decisions = sum(1 for l in lines if "[SHADOW_JSON]" in l)
                            holds = sum(1 for l in lines if "[SHADOW_JSON]" in l and '"decision": "HOLD"' in l)
                            # Simplified approximation for missing data rate based on holds, 
                            # in reality we'd look for specific missing feature logs.
                            status["missing_data_rate"] = holds / total_decisions if total_decisions > 0 else 0.0
                            
                            # Timestamp of the 5m bar is typically floor of timestamp to 300s
                            ts_ms = data.get("timestamp", 0)
                            status["last_completed_5m_bar"] = (ts_ms // 300000) * 300000
                            break
                    except json.JSONDecodeError:
                        continue
                        
                elif "ERROR" in line and "LightGBM" in line:
                    status["inference_errors"] += 1

    except Exception as e:
        status["health_monitor_error"] = str(e)

    return status

if __name__ == "__main__":
    print(json.dumps(get_health_status(), indent=4))
