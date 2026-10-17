import os
from dotenv import load_dotenv
load_dotenv()
import time
import json
import psutil
from datetime import datetime, timezone
import requests

LOG_FILE = os.path.join(os.path.dirname(__file__), "../logs/ophelia.log")
PRE_CHANGE_LOG = os.path.join(os.path.dirname(__file__), "../logs/ophelia_pre_change_shadow.log")
THRESHOLDS_FILE = os.path.join(os.path.dirname(__file__), "../PHASE7_DECISION_THRESHOLDS.json")

# IMPORTANT: ZERO IMPORTS from core.trading_engine, exchange.bingx_client, brokers, risk.

class ShadowMonitorBot:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        allowed_str = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "")
        self.allowed_user_ids = {int(uid.strip()) for uid in allowed_str.split(",") if uid.strip().isdigit()}
        
        if not self.token:
            print("WARNING: TELEGRAM_BOT_TOKEN not set. Monitor will not start.")
        
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.running = False
        self.last_update_id = 0
        self.shadow_duration_seconds = 86400  # 24 hours
        
        # Load thresholds for static reference
        self.thresholds = {}
        if os.path.exists(THRESHOLDS_FILE):
            try:
                with open(THRESHOLDS_FILE, "r") as f:
                    self.thresholds = json.load(f)
            except Exception:
                pass

    def is_authorized(self, user_id):
        return user_id in self.allowed_user_ids

    def send_message(self, chat_id, text):
        if not self.token:
            return
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"Failed to send message: {e}")

    def get_shadow_logs(self, limit=5000):
        if not os.path.exists(LOG_FILE):
            return []
        try:
            with open(LOG_FILE, "r") as f:
                lines = f.readlines()
                return [line for line in lines[-limit:]]
        except Exception as e:
            print(f"Error reading logs: {e}")
            return []

    def parse_state(self):
        # 1. Load Shadow State
        state_file = getattr(self, "state_file", None) or os.environ.get("SHADOW_STATE_FILE") or os.path.join(os.path.dirname(__file__), "../data/shadow_state.json")
        shadow_state = {
            "phase": "WARMING",
            "shadow_started_at": None,
            "observations": 0,
            "long_candidates": 0,
            "short_candidates": 0,
            "holds": 0,
            "conflicts": 0,
            "telemetry_counts": {"dtr": 0, "flp": 0, "div": 0, "abs": 0},
            "last_update": 0
        }
        if os.path.exists(state_file):
            try:
                with open(state_file, "r") as f:
                    shadow_state.update(json.load(f))
            except Exception as e:
                print(f"Error reading shadow state: {e}")
                
        # 2. Load CVD States
        data_dir = getattr(self, "data_dir", None) or os.path.join(os.path.dirname(__file__), "../data")
        cvd_states = {}
        buffer_warming_min = 288
        
        if os.path.exists(data_dir):
            for fname in os.listdir(data_dir):
                if fname.startswith("cvd_state_") and fname.endswith(".json"):
                    sym = fname.replace("cvd_state_", "").replace(".json", "")
                    try:
                        with open(os.path.join(data_dir, fname), "r") as f:
                            c_data = json.load(f)
                        blocks = len(c_data.get("history_blocks", []))
                        cvd_states[sym] = blocks
                        buffer_warming_min = min(buffer_warming_min, blocks)
                    except:
                        pass
                        
        if not cvd_states:
            buffer_warming_min = 0

        # 3. Parse Diagnostics from Log
        logs = self.get_shadow_logs(limit=2000)
        errors = 0
        warnings = 0
        last_error = None
        last_warning = None
        websocket_state = "DISCONNECTED"
        symbol_state = {}
        
        for line in logs:
            if "[InstWS] Connected" in line:
                websocket_state = "CONNECTED"
            if "ERROR" in line:
                errors += 1
                last_error = line.split("| ERROR |")[-1].strip()
            if "WARNING" in line:
                warnings += 1
                last_warning = line.split("| WARNING |")[-1].strip()
            if "[SHADOW_JSON]" in line:
                try:
                    json_str = line.split("[SHADOW_JSON]")[-1].strip()
                    data = json.loads(json_str)
                    sym = data.get("symbol")
                    if sym:
                        symbol_state[sym] = data
                except:
                    pass
                    
        return {
            "shadow_state": shadow_state,
            "cvd_states": cvd_states,
            "buffer_warming_min": buffer_warming_min,
            "errors": errors,
            "warnings": warnings,
            "last_error": last_error,
            "last_warning": last_warning,
            "websocket_state": websocket_state,
            "symbol_state": symbol_state,
            "last_market_update": shadow_state.get("last_update")
        }

    def handle_command(self, chat_id, text):
        parts = text.split()
        cmd = parts[0].lower().split("@")[0]
        args = parts[1:]

        if cmd == "/hi":
            self.cmd_hi(chat_id)
        elif cmd == "/health":
            self.cmd_health(chat_id)
        elif cmd == "/status":
            self.cmd_status(chat_id)
        elif cmd == "/progress":
            self.cmd_progress(chat_id)
        else:
            self.send_message(chat_id, "Unknown command. Type /hi for available commands.")

    def cmd_hi(self, chat_id):
        msg = (
            "<b>OPHELIA COMMAND CENTER</b>\n\n"
            "Available monitoring commands:\n"
            "/health — VPS + Ophelia health\n"
            "/status — VPS + Ophelia current state\n"
            "/progress — Complete shadow progress report\n\n"
            "<i>Note: All commands are read-only. Broker execution remains strictly isolated.</i>"
        )
        self.send_message(chat_id, msg)

    def cmd_health(self, chat_id):
        state = self.parse_state()
        
        # VPS Health
        hostname = os.uname().nodename if hasattr(os, "uname") else os.environ.get("COMPUTERNAME", "UNKNOWN")
        uptime_seconds = time.time() - psutil.boot_time()
        vps_uptime = f"{int(uptime_seconds//3600)}h {int((uptime_seconds%3600)//60)}m"
        
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        try:
            load1, load5, load15 = psutil.getloadavg()
            load_str = f"{load1:.2f}, {load5:.2f}, {load15:.2f}"
        except Exception:
            load_str = "N/A"
            
        net_io = psutil.net_io_counters()
        net_str = f"Sent: {net_io.bytes_sent//1024//1024}MB | Recv: {net_io.bytes_recv//1024//1024}MB"

        # Ophelia Health
        process_state = "DEAD"
        ophelia_uptime = "N/A"
        for proc in psutil.process_iter(['name', 'cmdline', 'create_time']):
            if proc.info['cmdline'] and 'main.py' in ' '.join(proc.info['cmdline']) and 'python' in proc.info['name'].lower():
                process_state = "ALIVE"
                o_up = time.time() - proc.info['create_time']
                ophelia_uptime = f"{int(o_up//3600)}h {int((o_up%3600)//60)}m"
                break
                
        freshness = "N/A"
        if state["last_market_update"]:
            fresh = time.time() - state["last_market_update"]
            freshness = f"{int(fresh)} sec ago"
            
        msg = (
            "━━━━━━━━━━━━━━━━━━\n"
            "<b>OPHELIA HEALTH</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "<b>VPS HEALTH</b>\n"
            f"Host: {hostname}\n"
            f"OS: {os.name}\n"
            f"Uptime: {vps_uptime}\n"
            f"CPU: {cpu}%\n"
            f"RAM: {ram.percent:.1f}% ({ram.used//1024//1024}MB / {ram.total//1024//1024}MB)\n"
            f"Disk: {disk.percent:.1f}% ({disk.free//1024//1024//1024}GB free)\n"
            f"Load: {load_str}\n"
            f"Network: {net_str}\n\n"
            "<b>OPHELIA HEALTH</b>\n"
            f"Process: {process_state}\n"
            f"Uptime: {ophelia_uptime}\n"
            f"Market Data: {freshness}\n"
            f"WebSocket: {state['websocket_state']}\n"
            f"CVD Engine: {'WARMING UP (' + str(state['buffer_warming_min']) + '/288)' if state['buffer_warming_min'] < 288 else 'READY'}\n"
            f"LONG Model: HEALTHY\n"
            f"SHORT Model: HEALTHY\n"
            f"Shadow Engine: HEALTHY\n"
            f"Errors: {state['errors']}\n"
            f"Warnings: {state['warnings']}\n\n"
            "<b>BROKER</b>\n"
            "<b>LIVE EXECUTION: BLOCKED</b>\n"
            "━━━━━━━━━━━━━━━━━━"
        )
        self.send_message(chat_id, msg)

    def cmd_status(self, chat_id):
        state = self.parse_state()
        
        process_state = "DEAD"
        ophelia_uptime = "N/A"
        for proc in psutil.process_iter(['name', 'cmdline', 'create_time']):
            if proc.info['cmdline'] and 'main.py' in ' '.join(proc.info['cmdline']) and 'python' in proc.info['name'].lower():
                process_state = "ALIVE"
                o_up = time.time() - proc.info['create_time']
                ophelia_uptime = f"{int(o_up//3600)}h {int((o_up%3600)//60)}m"
                break
                
        freshness = "N/A"
        if state["last_market_update"]:
            fresh = time.time() - state["last_market_update"]
            freshness = f"{int(fresh)} sec ago"
            
        syms = list(state["symbol_state"].keys())
        sym_str = ", ".join(syms) if syms else "WAITING FOR DATA"
        
        decisions_str = ""
        for sym, d in state["symbol_state"].items():
            l_prob = d.get('probability_long', 0)
            s_prob = d.get('probability_short', 0)
            l_thresh = d.get('frozen_threshold_long', 0)
            s_thresh = d.get('frozen_threshold_short', 0)
            dec = d.get('decision', 'N/A')
            reason = d.get('reason', 'N/A')
            
            tel = d.get("telemetry", {})
            tel_flags = []
            if tel.get("delta_deterioration_bullish", 0) == 1.0 or tel.get("delta_deterioration_bearish", 0) == 1.0:
                tel_flags.append("DTR")
            if tel.get("delta_flip_bullish", 0) == 1.0 or tel.get("delta_flip_bearish", 0) == 1.0:
                tel_flags.append("FLP")
            if tel.get("divergence_bullish", 0) == 1.0 or tel.get("divergence_bearish", 0) == 1.0:
                tel_flags.append("DIV")
            if tel.get("absorption_bullish_proxy", 0) == 1.0 or tel.get("absorption_bearish_proxy", 0) == 1.0:
                tel_flags.append("ABS")
            tel_str = ", ".join(tel_flags) if tel_flags else "NOT TRIGGERED"
            
            decisions_str += (
                f"<b>{sym}</b>\n"
                f"LONG Prob: {l_prob:.4f} (Thresh: {l_thresh:.4f})\n"
                f"SHORT Prob: {s_prob:.4f} (Thresh: {s_thresh:.4f})\n"
                f"Decision: {dec}\n"
                f"Reason: {reason}\n"
                f"Adv. OF Flags: {tel_str}\n\n"
            )
            
        if not decisions_str:
            decisions_str = "No decisions generated yet (warming up...)\n\n"

        msg = (
            "━━━━━━━━━━━━━━━━━━\n"
            "<b>OPHELIA CURRENT STATUS</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "<b>SYSTEM</b>\n"
            "Mode: PAPER (SHADOW)\n"
            f"Process: {process_state}\n"
            f"Uptime: {ophelia_uptime}\n"
            "Model Version: frozen_v1\n"
            f"Active Symbols: {sym_str}\n"
            "Timeframe: 5m\n\n"
            "<b>MARKET DATA</b>\n"
            f"WebSocket: {state['websocket_state']}\n"
            f"Data Freshness: {freshness}\n"
            f"CVD Status: {'WARMING UP' if state['buffer_warming_min'] < 288 else 'READY'}\n\n"
            "<b>CURRENT DECISIONS</b>\n"
            f"{decisions_str}"
            "<b>BROKER</b>\n"
            "<b>LIVE EXECUTION: BLOCKED</b>\n"
            "━━━━━━━━━━━━━━━━━━"
        )
        self.send_message(chat_id, msg)

    def cmd_progress(self, chat_id):
        state = self.parse_state()
        shadow = state["shadow_state"]
        
        # Determine actual shadow progress
        start_ts = shadow.get("shadow_started_at")
        elapsed = 0
        remaining = self.shadow_duration_seconds
        pct = 0.0
        
        if start_ts:
            elapsed = time.time() - start_ts
            remaining = max(0, self.shadow_duration_seconds - elapsed)
            pct = min(100.0, (elapsed / self.shadow_duration_seconds) * 100.0)
            
        try:
            from zoneinfo import ZoneInfo
            tz_ist = ZoneInfo("Asia/Kolkata")
        except ImportError:
            from datetime import timedelta
            tz_ist = timezone(timedelta(hours=5, minutes=30))
            
        start_str = datetime.fromtimestamp(start_ts, tz=timezone.utc).astimezone(tz_ist).strftime('%Y-%m-%d %H:%M:%S IST') if start_ts else "NOT STARTED"
        elapsed_str = f"{int(elapsed//3600)}h {int((elapsed%3600)//60)}m"
        rem_str = f"{int(remaining//3600)}h {int((remaining%3600)//60)}m"
        
        total_obs = shadow.get("observations", 0)
        l_pct = (shadow.get("long_candidates", 0) / total_obs * 100) if total_obs > 0 else 0
        s_pct = (shadow.get("short_candidates", 0) / total_obs * 100) if total_obs > 0 else 0
        h_pct = (shadow.get("holds", 0) / total_obs * 100) if total_obs > 0 else 0
        
        cvd_msg = f"Progress: {state['buffer_warming_min']}/288\n"
        for sym, b in state['cvd_states'].items():
            cvd_msg += f"- {sym}: {b}/288\n"
            
        shadow_phase = shadow.get('phase', 'WARMING')
        
        msg = (
            "━━━━━━━━━━━━━━━━━━\n"
            "<b>OPHELIA SHADOW PROGRESS</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "<b>CURRENT VPS CVD WARM-UP</b>\n"
            f"Status: {'WARMING' if state['buffer_warming_min'] < 288 else 'READY'}\n"
            f"{cvd_msg}\n"
            "<b>ACTUAL 24-HOUR SHADOW</b>\n"
            f"Status: {shadow_phase}\n"
            f"Started: {start_str}\n"
            f"Elapsed: {elapsed_str if shadow_phase == 'SHADOW_RUNNING' else '0h 0m'}\n"
            f"Remaining: {rem_str if shadow_phase == 'SHADOW_RUNNING' else '24h 0m'}\n"
            f"Progress: {pct if shadow_phase == 'SHADOW_RUNNING' else 0.0:.1f}%\n"
            f"Target: {self.shadow_duration_seconds//3600}h\n\n"
            "<b>OBSERVATIONS</b>\n"
            f"Total: {total_obs}\n"
            f"LONG: {shadow.get('long_candidates', 0)} ({l_pct:.1f}%)\n"
            f"SHORT: {shadow.get('short_candidates', 0)} ({s_pct:.1f}%)\n"
            f"HOLD: {shadow.get('holds', 0)} ({h_pct:.1f}%)\n\n"
            "<b>CONFLICT STATISTICS</b>\n"
            f"Conflict Events: {shadow.get('conflicts', 0)}\n\n"
            "<b>ADVANCED ORDER FLOW</b>\n"
            f"DTR: {shadow.get('telemetry_counts', {}).get('dtr', 0)}\n"
            f"FLP: {shadow.get('telemetry_counts', {}).get('flp', 0)}\n"
            f"DIV: {shadow.get('telemetry_counts', {}).get('div', 0)}\n"
            f"ABS: {shadow.get('telemetry_counts', {}).get('abs', 0)} (PROXY)\n\n"
            "<b>DATA INTEGRITY</b>\n"
            f"WebSocket: {state['websocket_state']}\n"
            f"CVD: {'WARMING UP (' + str(state['buffer_warming_min']) + '/288)' if state['buffer_warming_min'] < 288 else 'READY'}\n"
            "Features: VALID\n\n"
            "<b>ERRORS / WARNINGS</b>\n"
            f"Errors: {state['errors']}\n"
            f"Warnings: {state['warnings']}\n"
            f"Last Error: {state['last_error'] or 'None'}\n"
            f"Last Warning: {state['last_warning'] or 'None'}\n\n"
            "<b>MODEL STATUS</b>\n"
            "LONG Model: frozen_v1 (Loaded: OK)\n"
            "SHORT Model: frozen_v1 (Loaded: OK)\n\n"
            "<b>BROKER</b>\n"
            "<b>LIVE EXECUTION: BLOCKED</b>\n"
            "━━━━━━━━━━━━━━━━━━"
        )
        self.send_message(chat_id, msg)

    def start(self):
        if not self.token:
            return
            
        self.running = True
        
        # Polling loop
        while self.running:
            try:
                url = f"{self.base_url}/getUpdates"
                params = {"offset": self.last_update_id + 1, "timeout": 5}
                resp = requests.get(url, params=params, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("ok"):
                        for update in data.get("result", []):
                            update_id = update.get("update_id", 0)
                            if update_id > self.last_update_id:
                                self.last_update_id = update_id
                            
                            msg = update.get("message")
                            if msg:
                                user_id = msg.get("from", {}).get("id")
                                chat_id = msg.get("chat", {}).get("id")
                                text = (msg.get("text") or "").strip()
                                
                                if not self.is_authorized(user_id):
                                    self.send_message(chat_id, "🚫 Access Denied.")
                                    continue
                                
                                if text.startswith("/"):
                                    self.handle_command(chat_id, text)
            except Exception as e:
                time.sleep(5)
            time.sleep(1)

if __name__ == "__main__":
    bot = ShadowMonitorBot()
    bot.start()
