"""Telegram control-plane bot: deterministic slash-command layer + NL via LLM.

ARCHITECTURE (mandatory):
  slash command -> direct deterministic router -> core/account/data subsystem
  natural language -> Qwen3 4B intent -> same deterministic subsystem

Slash commands NEVER call the LLM, the news engine, or any analysis beyond
what they need. Execution stays behind explicit confirmation and the
SHADOW/LIVE mode gate; this module exposes no direct exchange access.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.parse
import urllib.request

from . import account, analytics, config, core, db, llm, nlg

API = "https://api.telegram.org/bot{token}/{method}"

CONTEXT_KEYS = ("strategy", "symbol", "timeframe_min", "direction_preference",
                "margin_usage_pct", "leverage")

_AFFIRMATIVE = {"YES", "Y", "CONFIRM", "CONFIRMED", "ARM", "ARM IT", "ARMIT",
                "DO IT", "GO", "GO AHEAD", "SEND IT", "EXECUTE", "PROCEED"}
_NEGATIVE = {"NO", "N", "NOPE", "CANCEL", "CANCEL IT", "CANCELLED", "CANCELED",
             "SKIP", "SKIP IT", "STOP", "ABORT", "FORGET IT"}

_SYMBOL_ALIASES = {
    "btc": "BTCUSDT", "bitcoin": "BTCUSDT",
    "eth": "ETHUSDT", "ethereum": "ETHUSDT",
    "sol": "SOLUSDT", "solana": "SOLUSDT",
    "xrp": "XRPUSDT", "ripple": "XRPUSDT",
    "bnb": "BNBUSDT", "ada": "ADAUSDT", "doge": "DOGEUSDT",
    "gold": "PAXGUSDT", "paxg": "PAXGUSDT",
}

_HELP_TEXT = (
    "OPHELIA COMMAND TREE (all deterministic, no LLM):\n"
    "/hi - master operator menu\n"
    "/status | /health | /progress - system\n"
    "/download - get Android APKs (prompts /user or /admin)\n"
    "/user - get Ophelia User APK directly\n"
    "/admin - get Ophelia Admin APK directly\n"
    "\n/trade - trading setup wizard\n"
    "  /strategy [st_vwap|ema|both]\n"
    "  /choose_symbol [one|multi|all]\n"
    "  /sl [manual 0.8 | vwap 0.5 | supertrend 0.2 | multi | show]\n"
    "  /target 1:2 | /partial 50@0.8 25@1.2 [trail 0.8]\n"
    "  /margin 50% | 10usdt   /leverage 20\n"
    "\n/setup - full deterministic setup view\n"
    "/position - ALL open positions (exchange + Ophelia)\n"
    "/edit - edit setup/position (stop, targets, qty, trailing, BE)\n"
    "/closeall - emergency close (double confirm)\n"
    "/live - enable or disable LIVE mode\n"
    "/watchlist | /bingx\n\n"
    "Natural language reaches the same functions through Qwen3 4B - e.g. "
    "\"Set a buy on Supertrend/VWAP cross, book 50% at 0.8%, rest trailing "
    "0.8%.\"")

_MENU_KB = {
    "inline_keyboard": [
        [{"text": "TRADE", "callback_data": "/trade"},
         {"text": "STRATEGY", "callback_data": "/strategy"},
         {"text": "SYMBOL", "callback_data": "/choose_symbol"}],
        [{"text": "POSITION", "callback_data": "/position"},
         {"text": "SETUP", "callback_data": "/setup"},
         {"text": "EDIT", "callback_data": "/edit"}],
        [{"text": "WATCHLIST", "callback_data": "/watchlist"},
         {"text": "ACCOUNT", "callback_data": "/bingx"},
         {"text": "LIVE MODE", "callback_data": "/live"}],
        [{"text": "STATUS", "callback_data": "/status"},
         {"text": "HEALTH", "callback_data": "/health"},
         {"text": "PROGRESS", "callback_data": "/progress"}],
        [{"text": "📱 GET APK", "callback_data": "/download"},
         {"text": "CLOSE ALL", "callback_data": "/closeall"},
         {"text": "HELP", "callback_data": "/help"}],
    ]}

_TRADE_KB = {
    "inline_keyboard": [
        [{"text": "1. CHOOSE STRATEGY", "callback_data": "/strategy"}],
        [{"text": "2. CHOOSE SYMBOL", "callback_data": "/choose_symbol"}],
        [{"text": "3. SET MARGIN/LEV", "callback_data": "/margin"}],
        [{"text": "4. SET STOPS/TARGETS", "callback_data": "/sl"}],
        [{"text": "LIFECYCLE (TOGGLE)", "callback_data": "/lifecycle"}],
        [{"text": "EXECUTE AUTOMATION", "callback_data": "/execute"}],
        [{"text": "cancel", "callback_data": "/cancel"}],
    ]}

_STRATEGY_KB = {
    "inline_keyboard": [
        [{"text": "SUPERTREND + VWAP", "callback_data": "/st_vwap"}],
        [{"text": "EMA 9/20", "callback_data": "/ema"}],
        [{"text": "BOTH", "callback_data": "/strategy both"}],
        [{"text": "SHOW CURRENT", "callback_data": "/setup"}],
    ]}

_SYMBOL_KB = {
    "inline_keyboard": [
        [{"text": "ONE SYMBOL (BTC)", "callback_data": "/choose_symbol btc"}],
        [{"text": "ONE SYMBOL (ETH)", "callback_data": "/choose_symbol eth"}],
        [{"text": "MULTIPLE (BTC, ETH, SOL)", "callback_data": "/choose_symbol btc eth sol"}],
        [{"text": "ALL WATCHLIST", "callback_data": "/choose_symbol all"}],
        [{"text": "cancel", "callback_data": "/cancel"}],
    ]}

_SL_KB = {
    "inline_keyboard": [
        [{"text": "MANUAL (1%)", "callback_data": "/sl manual 1.0"},
         {"text": "VWAP (0.2%)", "callback_data": "/sl vwap 0.2"},
         {"text": "SUPERTREND (0.2%)", "callback_data": "/sl supertrend 0.2"}],
        [{"text": "MULTI-STOP", "callback_data": "/sl multi"},
         {"text": "SHOW CURRENT", "callback_data": "/sl show"}],
    ]}

_MARGIN_KB = {
    "inline_keyboard": [
        [{"text": "10%", "callback_data": "/margin 10%"},
         {"text": "25%", "callback_data": "/margin 25%"},
         {"text": "45%", "callback_data": "/margin 45%"},
         {"text": "100%", "callback_data": "/margin 100%"}],
    ]}

_LEVERAGE_KB = {
    "inline_keyboard": [
        [{"text": "5x", "callback_data": "/leverage 5"},
         {"text": "10x", "callback_data": "/leverage 10"},
         {"text": "20x", "callback_data": "/leverage 20"},
         {"text": "50x", "callback_data": "/leverage 50"}],
    ]}

_TARGET_KB = {
    "inline_keyboard": [
        [{"text": "1R / 2R / 3R", "callback_data": "/target r 1 2 3"}],
        [{"text": "+2% / +5%", "callback_data": "/target pct 2 5"},
         {"text": "NONE", "callback_data": "/target none"}],
    ]}

_PARTIAL_KB = {
    "inline_keyboard": [
        [{"text": "25% at TP1", "callback_data": "/partial 25"},
         {"text": "50% at TP1", "callback_data": "/partial 50"}],
        [{"text": "100% (No partials)", "callback_data": "/partial 100"}],
    ]}


def _norm(text: str) -> str:
    return text.upper().strip().rstrip(".!?, ").strip()


def _verify_binance_pair(pair: str) -> bool:
    """Check a futures pair actually exists on the data-source exchange."""
    try:
        url = ("https://fapi.binance.com/fapi/v1/exchangeInfo"
               f"?symbol={urllib.parse.quote(pair)}")
        req = urllib.request.Request(url, headers={"User-Agent": "ophelia-cp/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            info = json.loads(r.read().decode())
        syms = info.get("symbols")
        if isinstance(syms, list):
            return any(s.get("symbol") == pair for s in syms)
        return False
    except Exception:                                             # noqa: BLE001
        return False


class Bot:
    def __init__(self):
        self.token = config.TELEGRAM_BOT_TOKEN
        self.offset = 0
        # chat_id -> {"context", "pending", "history", "trade": draft}
        self.sessions: dict[int, dict] = {}

    # ---------------- transport ----------------
    def _call(self, method: str, payload: dict) -> dict:
        url = API.format(token=self.token, method=method)
        data = urllib.parse.urlencode(payload).encode()
        req = urllib.request.Request(url, data=data,
                                     headers={"Content-Type":
                                              "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=35) as r:
            return json.loads(r.read().decode())

    def send(self, chat_id: int, text: str, keyboard: dict | None = None):
        payload = {"chat_id": chat_id, "text": text[:4000]}
        if keyboard:
            payload["reply_markup"] = json.dumps(keyboard)
        self._call("sendMessage", payload)
        print(f"[tg->] {str(text)[:90]!r}", flush=True)

    def send_document(self, chat_id: int, file_path: str, caption: str = "") -> bool:
        """Send an APK or document directly via Telegram Bot API."""
        url = f"https://api.telegram.org/bot{self.token}/sendDocument"
        try:
            import requests
            if not os.path.exists(file_path):
                print(f"[tg] send_document error: file not found {file_path}", flush=True)
                return False
            fname = os.path.basename(file_path)
            with open(file_path, "rb") as f:
                files = {"document": (fname, f, "application/vnd.android.package-archive")}
                data = {"chat_id": chat_id}
                if caption:
                    data["caption"] = caption[:1024]
                r = requests.post(url, data=data, files=files, timeout=90)
                res = r.json()
                if not res.get("ok"):
                    print(f"[tg] sendDocument API error: {res}", flush=True)
                    return False
                print(f"[tg] sendDocument success: {fname} sent to {chat_id}", flush=True)
                return True
        except Exception as e:
            print(f"[tg] send_document exception: {e}", flush=True)
            return False

    def poll(self):
        d = self._call("getUpdates",
                       {"offset": self.offset, "timeout": 25,
                        "allowed_updates": json.dumps(
                            ["message", "callback_query"])})
        for u in d.get("result", []):
            self.offset = max(self.offset, u["update_id"] + 1)
            if cb := u.get("callback_query"):
                self._on_callback(cb)
                continue
            msg = u.get("message") or {}
            chat_id = msg.get("chat", {}).get("id")
            text = (msg.get("text") or "").strip()
            uid = msg.get("from", {}).get("id")
            if chat_id is None or not text:
                continue
            if config.TELEGRAM_ALLOWED_USER_IDS and \
                    uid not in config.TELEGRAM_ALLOWED_USER_IDS:
                self.send(chat_id, "Unauthorized user.")
                continue
            if uid == 9781404533 or str(chat_id) == "9781404533":
                self._send_user_apk(chat_id)
                continue
            try:
                self.handle(chat_id, text)
            except Exception as e:                                # noqa: BLE001
                print(f"[tg] handle error: {e}", flush=True)
                try:
                    self.send(chat_id, f"Handler error (safe-stop): {str(e)[:160]}")
                except Exception as send_err:                     # noqa: BLE001
                    print(f"[tg] send failure: {send_err}", flush=True)

    def _on_callback(self, cb: dict):
        """Inline-button presses route through the SAME deterministic router."""
        chat_id = (cb.get("message") or {}).get("chat", {}).get("id")
        uid = cb.get("from", {}).get("id")
        data = (cb.get("data") or "").strip()
        if chat_id is None or not data:
            return
        try:
            self._call("answerCallbackQuery", {"callback_query_id": cb["id"]})
        except Exception:                                          # noqa: BLE001
            pass
        if config.TELEGRAM_ALLOWED_USER_IDS and \
                uid not in config.TELEGRAM_ALLOWED_USER_IDS:
            self.send(chat_id, "Unauthorized user.")
            return
        try:
            self.handle(chat_id, data)
        except Exception as e:                                    # noqa: BLE001
            print(f"[tg] callback error: {e}", flush=True)
            self.send(chat_id, f"Handler error (safe-stop): {str(e)[:160]}")

    # ---------------- confirmation handling ----------------
    def try_confirmation(self, chat_id: int, text: str) -> bool:
        """Handle explicit YES/NO replies against any pending item."""
        s = self.sessions.get(chat_id) or {}
        pend = s.get("pending")
        if not pend:
            return False
        up = _norm(text)
        kind = pend["kind"]

        if kind == "LIVE_CONFIRM_2":
            s["pending"] = None
            if up in ("CONFIRM LIVE", "CONFIRMLIVE"):
                db.set_mode("LIVE")
                db.audit("telegram", "MODE_LIVE", {})
                self.send(chat_id, "LIVE trading ENABLED. Real orders will be "
                                   "placed for confirmed signals. Use /live off "
                                   "to stop.")
            else:
                self.send(chat_id, "Live mode NOT enabled (needed the exact "
                                   "words 'CONFIRM LIVE'). Staying in "
                                   f"{db.get_mode()}.")
            return True

        is_affirm = up in _AFFIRMATIVE or up.startswith(("YES ", "ARM", "DO IT"))
        is_reject = (up in _NEGATIVE
                     or up.startswith(("SKIP", "CANCEL", "NO ", "DONT", "DON'T")))
        if not (is_affirm or is_reject):
            return False

        if kind == "LIVE_CONFIRM_1":
            if up in ("YES", "Y"):
                s["pending"] = {"kind": "LIVE_CONFIRM_2"}
                self.send(chat_id, "FINAL CONFIRMATION: Are you absolutely sure? "
                                   "If you enable this, Ophelia will place real "
                                   "market orders. Reply with EXACTLY "
                                   "'CONFIRM LIVE' to proceed.")
            else:
                s["pending"] = None
                self.send(chat_id, "Live mode activation aborted.")
            return True

        if kind == "LIVE_OFF_CONFIRM":
            if is_affirm:
                db.set_mode("SHADOW")
                db.audit("telegram", "MODE_SHADOW", {})
                s["pending"] = None
                self.send(chat_id, "Ophelia is back in SHADOW mode. No live "
                                   "orders will be placed.")
            else:
                s["pending"] = None
                self.send(chat_id, "Staying in LIVE mode.")
            return True

        if kind == "CLOSEALL_CONFIRM":
            if is_affirm:
                s["pending"] = None
                try:
                    if db.get_mode() == "LIVE":
                        out = core.live_close_all()
                        self.send(chat_id, f"LIVE CLOSE-ALL executed.\n"
                                           f"BingX Response: {out['exchange_resp']}")
                    else:
                        n = core.shadow_close_all()
                        self.send(chat_id, f"SHADOW CLOSE-ALL executed. Closed {n} "
                                           "positions/trades.")
                except Exception as e:
                    self.send(chat_id, f"Close-all error: {e}")
            else:
                s["pending"] = None
                self.send(chat_id, "Close-all aborted.")
            return True

        if kind == "EDIT_CONFIRM":
            if is_affirm:
                apply_fn = pend.get("apply")
                s["pending"] = None
                if apply_fn:
                    try:
                        msg = apply_fn()
                        self.send(chat_id, f"Applied.\n{msg}")
                    except core.CoreReject as e:
                        self.send(chat_id, f"Rejected by risk layer: {e}")
                else:
                    self.send(chat_id, "Nothing to apply.")
            else:
                s["pending"] = None
                self.send(chat_id, "Edit cancelled - nothing changed.")
            return True

        if kind == "AUTOMATION_CONFIRM":
            if is_affirm:
                try:
                    out = core.register_condition(pend["spec"])
                except core.CoreReject as e:
                    s["pending"] = None
                    self.send(chat_id, f"I couldn't arm that - the risk layer "
                                       f"rejected it: {e}\nNothing was armed.")
                    return True
                s["pending"] = None
                s["trade"] = None
                self.send(chat_id, nlg.armed_confirmation(out))
            else:
                spec = pend["spec"]
                s["pending"] = None
                self.send(chat_id, f"Dropped the {spec.get('symbol', '')} "
                                   f"{spec.get('timeframe_min', '')}m proposal. "
                                   "Nothing was armed.")
            return True

        if kind == "TRADE_CONFIRM":
            tnum = up.replace("#", "").strip()
            if is_reject:
                core.cancel_shadow_trade(int(pend["trade_id"]))
                s["pending"] = None
                self.send(chat_id, f"Skipped proposal #{pend['trade_id']}. The "
                                   "condition can be re-armed whenever you want.")
                return True
            if tnum.isdigit() or is_affirm:
                tid = int(tnum) if tnum.isdigit() else pend["trade_id"]
                try:
                    out = core.confirm_shadow_trade(tid)
                except core.CoreReject as e:
                    s["pending"] = None
                    self.send(chat_id, f"Couldn't execute: {e}")
                    return True
                s["pending"] = None
                if out.get("status") == "OPEN_LIVE":
                    self.send(chat_id,
                              f"LIVE order submitted for proposal #{tid} "
                              f"(position #{out['position_id']}, id "
                              f"{out['client_order_id']}).\nVerify with "
                              "/position and /bingx.")
                else:
                    self.send(chat_id, f"Recorded shadow trade #{out['trade_id']} "
                                       "(OPEN_SHADOW). No live order exists.")
                return True
            return False

        if kind == "LIVE_CONFIRM_1":
            s["pending"] = None
            if is_reject:
                self.send(chat_id, "Live mode switch cancelled. Staying in "
                                   f"{db.get_mode()}.")
                return True
            s["pending"] = {"kind": "LIVE_CONFIRM_2"}
            self.send(chat_id,
                      "FINAL CONFIRMATION: this enables REAL exchange orders on "
                      "BingX with real funds at risk. Risk checks stay active.\n"
                      "Type 'CONFIRM LIVE' to enable, or 'no' to abort.")
            return True

        if kind == "LIVE_OFF_CONFIRM":
            s["pending"] = None
            if is_affirm:
                db.set_mode("SHADOW")
                db.audit("telegram", "MODE_SHADOW", {})
                self.send(chat_id, "Live trading STOPPED. Mode is now SHADOW - "
                                   "no live orders will be placed. Open exchange "
                                   "positions (if any) are NOT auto-closed; use "
                                   "/closeall if you want them closed.")
            else:
                self.send(chat_id, f"Still in {db.get_mode()}.")
            return True

        if kind == "CLOSEALL_CONFIRM":
            s["pending"] = None
            if not is_affirm:
                self.send(chat_id, "Close-all aborted. Nothing was touched.")
                return True
            try:
                if db.get_mode() == "LIVE":
                    out = core.live_close_all()
                    self.send(chat_id, f"Close-all sent to BingX: "
                                       f"{out.get('exchange_resp', 'ok')[:140]}")
                else:
                    n = core.shadow_close_all()
                    self.send(chat_id, f"Closed {n} shadow position(s)/trade(s). "
                                       "No live order was sent.")
            except Exception as e:                                # noqa: BLE001
                self.send(chat_id, f"Close-all FAILED: {str(e)[:180]}\n"
                                   "Check /bingx - do not assume it worked.")
                db.audit("telegram", "CLOSEALL_FAILED", {"error": str(e)[:180]})
            return True

        return False

    # ---------------- trade draft (deterministic wizard state) --------------
    def _symbol_kb(self) -> dict:
        wl = db.watchlist_symbols()
        rows = []
        single_row = []
        for sym in wl[:6]:
            alias = sym.replace("-USDT", "").lower()
            single_row.append({"text": sym, "callback_data": f"/choose_symbol {alias}"})
            if len(single_row) == 2:
                rows.append(single_row)
                single_row = []
        if single_row:
            rows.append(single_row)
        if len(wl) >= 2:
            preset = " ".join(s.replace("-USDT", "").lower() for s in wl[:3])
            rows.append([{"text": f"MULTIPLE ({', '.join(wl[:3])})", "callback_data": f"/choose_symbol {preset}"}])
        rows.append([{"text": f"ALL WATCHLIST ({len(wl)} symbols)", "callback_data": "/choose_symbol all"}])
        rows.append([{"text": "cancel", "callback_data": "/cancel"}])
        return {"inline_keyboard": rows}

    def _update_risk(self, d: dict, key: str, value: any, target_strat: str = "BOTH"):
        d[key] = value
        strats = ["VWAP_SUPERTREND", "EMA_CROSSOVER"]
        if target_strat and target_strat.lower() != "both":
            if target_strat.lower() in ("st_vwap", "stvwap", "supertrend", "vwap", "vwap_supertrend"):
                strats = ["VWAP_SUPERTREND"]
            elif target_strat.lower() in ("ema", "ema_crossover", "crossover"):
                strats = ["EMA_CROSSOVER"]
        for st in strats:
            d.setdefault("strategy_risk", {}).setdefault(st, {})[key] = value

    def _get_risk(self, d: dict, key: str, target_strat: str = None) -> any:
        st = target_strat or "VWAP_SUPERTREND"
        if st.lower() in ("st_vwap", "stvwap", "supertrend", "vwap", "vwap_supertrend"):
            st = "VWAP_SUPERTREND"
        elif st.lower() in ("ema", "ema_crossover", "crossover"):
            st = "EMA_CROSSOVER"
        val = d.get("strategy_risk", {}).get(st, {}).get(key)
        if val is not None:
            return val
        return d.get(key)

    def _draft(self, s: dict) -> dict:
        d = s.get("trade")
        if not d:
            d = {"strategy": None, "symbol": None, "symbols": None,
                 "symbol_scope": None, "timeframe_min": 3,
                 "direction_preference": None, "margin_usage_pct": 45.0,
                 "margin_usdt": None, "leverage": 20.0, "stops": None,
                 "targets": None, "trailing_pct": None, "breakeven": None,
                 "expiry_hours": None, "lifecycle": "CONTINUOUS",
                 "strategy_timeframes": {"VWAP_SUPERTREND": 3, "EMA_CROSSOVER": 1},
                 "strategy_risk": {
                     "VWAP_SUPERTREND": {},
                     "EMA_CROSSOVER": {}
                 }}
            s["trade"] = d
        return d

    def _missing_fields(self, d: dict) -> list[str]:
        missing = []
        if not d.get("strategy"):
            missing.append("strategy")
        if not d.get("symbol") and not d.get("symbols"):
            missing.append("symbol")
            
        strats = ["VWAP_SUPERTREND", "EMA_CROSSOVER"] if d.get("strategy") == "BOTH" else [d.get("strategy")] if d.get("strategy") else []
        for st in strats:
            tf = d.get("strategy_timeframes", {}).get(st) if d.get("strategy") == "BOTH" else (d.get("timeframe_min") or d.get("strategy_timeframes", {}).get(st))
            if not tf:
                missing.append(f"timeframe for {st}")
            risk = d.get("strategy_risk", {}).get(st) if d.get("strategy") == "BOTH" else d
            stops = (risk.get("stops") if risk else None) or d.get("stops")
            if not stops:
                missing.append(f"stop for {st}")
            targets = (risk.get("targets") if risk else None) or d.get("targets")
            trailing = (risk.get("trailing_pct") if risk else None) or d.get("trailing_pct")
            if not targets and not trailing:
                missing.append(f"target/exit for {st}")

        if not d.get("direction_preference"):
            missing.append("direction")
        if d.get("margin_usage_pct") is None and d.get("margin_usdt") is None:
            missing.append("margin")
        if d.get("leverage") is None:
            missing.append("leverage")
        return missing

    def _resolve_symbols(self, s: dict, arg: str) -> list[str] | None:
        if arg:
            clean_arg = arg.lower().strip()
            if clean_arg.startswith("single "):
                clean_arg = clean_arg[7:].strip()
            elif clean_arg.startswith("multi "):
                clean_arg = clean_arg[6:].strip()
            tokens = clean_arg.replace(",", " ").split()
            if "all" in tokens:
                return ["ALL_WATCHLIST"]
            syms = []
            wl = db.watchlist_symbols()
            for token in tokens:
                first = token.lower()
                pair = _SYMBOL_ALIASES.get(first, first.upper())
                
                if pair.endswith("USDT") and not pair.endswith("-USDT"):
                    pair = pair[:-4] + "-USDT"
                elif not pair.endswith("USDT"):
                    pair += "-USDT"
                    
                if pair in config.SYMBOLS or pair in wl or _verify_binance_pair(pair.replace("-", "")):
                    if pair not in syms:
                        syms.append(pair)
            return syms if syms else None
        ctx = s.get("context", {}).get("symbol")
        if ctx:
            return [ctx]
        wl = db.watchlist_symbols()
        return [wl[0]] if wl else None

    # ---------------- deterministic command router ----------------
    def _command(self, chat_id: int, text: str) -> bool:
        low = text.lower().strip()
        if not low.startswith("/"):
            return False
        parts = low.split(maxsplit=1)
        cmd = parts[0]
        arg = parts[1].strip() if len(parts) > 1 else ""
        s = self.sessions.setdefault(chat_id, {"context": {}, "pending": None,
                                               "history": []})

        if cmd in ("/cancel",):
            s["pending"] = None
            s["trade"] = None
            self.send(chat_id, "Cleared the pending proposal and trade draft. "
                               "Armed automations are unaffected.")
            return True

        if cmd in ("/start", "/stop"):
            self.send(chat_id,
                      "Use /live on to enable live trading or /live off to stop "
                      "it (each guarded). /start and /stop are aliases.")
            return True

        if cmd == "/help":
            self.send(chat_id, _HELP_TEXT)
            return True

        if cmd == "/hi":
            self._cmd_hi(chat_id)
            return True

        if cmd == "/status":
            t0 = time.time()
            self.send(chat_id, nlg.status_report(core.system_status()))
            print(f"[cmd] /status {time.time() - t0:.2f}s", flush=True)
            return True

        if cmd in ("/health",):
            self.send(chat_id, nlg.health_summary(core.health()))
            return True

        if cmd == "/progress":
            self.send(chat_id, self._progress_report())
            return True

        if cmd == "/position":
            t0 = time.time()
            self.send(chat_id, self._position_view())
            print(f"[cmd] /position {time.time() - t0:.2f}s", flush=True)
            return True

        if cmd == "/setup":
            self.send(chat_id, self._setup_view(s))
            return True

        if cmd in ("/marketstate", "/microstructure"):
            sym = arg.upper().strip() if arg else "BTC-USDT"
            if not sym.endswith("-USDT"):
                sym = sym.replace("USDT", "") + "-USDT"
            self.send(chat_id, self._cmd_marketstate(sym))
            return True

        if cmd == "/watchlist":
            self.send(chat_id, nlg.watchlist_report(self._watchlist_rows()))
            return True

        if cmd == "/bingx":
            t0 = time.time()
            self.send(chat_id, nlg.bingx_account_view(account.account_view()))
            print(f"[cmd] /bingx {time.time() - t0:.2f}s", flush=True)
            return True

        if cmd == "/trade":
            if arg:
                # /trade st_vwap 3m long 50% 20x -> preset then show wizard
                sub = arg.split()[0]
                if sub in ("st_vwap", "stvwap", "supertrend"):
                    return self._cmd_stvwap(chat_id, s,
                                            " ".join(arg.split()[1:]))
                if sub in ("ema",):
                    return self._cmd_ema(chat_id, s, " ".join(arg.split()[1:]))
            d = self._draft(s)
            self.send(chat_id,
                      "Trade Setup Wizard:\n"
                      "SUPERTREND + VWAP\n"
                      "EMA 9/20\n"
                      "Follow the steps below to configure your trade. "
                      "You can view the full draft at any time using /setup.",
                      _TRADE_KB)
            return True

        if cmd == "/strategy":
            if arg:
                sub = arg.lower().strip()
                if sub in ("both", "multi") or sub.startswith("both"):
                    d = self._draft(s)
                    d["strategy"] = "BOTH"
                    if "strategy_timeframes" not in d or not isinstance(d["strategy_timeframes"], dict):
                        d["strategy_timeframes"] = {}
                    st_tf = d["strategy_timeframes"].get("VWAP_SUPERTREND", 3)
                    ema_tf = d["strategy_timeframes"].get("EMA_CROSSOVER", 1)
                    m_tfs = re.findall(r"(\d+)\s*m\b", sub)
                    if len(m_tfs) >= 2:
                        st_tf = int(m_tfs[0])
                        ema_tf = int(m_tfs[1])
                    elif len(m_tfs) == 1:
                        st_tf = int(m_tfs[0])
                    d["strategy_timeframes"]["VWAP_SUPERTREND"] = st_tf
                    d["strategy_timeframes"]["EMA_CROSSOVER"] = ema_tf
                    self.send(chat_id, self._draft_view(s, f"BOTH strategies selected:\n"
                                                           f"• VWAP_SUPERTREND: {st_tf}m\n"
                                                           f"• EMA_CROSSOVER: {ema_tf}m\n"
                                                           f"Use /st_vwap <min>m and /ema <min>m to configure timeframes."), _TRADE_KB)
                    return True
                if sub in ("st_vwap", "stvwap", "supertrend", "vwap"):
                    return self._cmd_stvwap(chat_id, s, " ".join(arg.split()[1:]))
                if sub in ("ema", "ema_crossover", "crossover"):
                    return self._cmd_ema(chat_id, s, " ".join(arg.split()[1:]))
            self.send(chat_id, "Choose strategy:", _STRATEGY_KB)
            return True
            
        if cmd == "/choose_symbol":
            if arg:
                d = self._draft(s)
                low_arg = arg.lower().strip()
                if low_arg == "all":
                    wl = db.watchlist_symbols() or db.ensure_seed_watchlist() or list(config.SYMBOLS)
                    d["symbol"] = "ALL_WATCHLIST"
                    d["symbols"] = wl
                    d["symbol_scope"] = {"mode": "ALL_WATCHLIST", "symbols": wl}
                    self.send(chat_id, self._draft_view(s, f"Symbol scope set to ALL WATCHLIST ({len(wl)} symbols: {', '.join(wl)})"), _TRADE_KB)
                    return True
                syms = self._resolve_symbols(s, arg)
                if syms:
                    if len(syms) == 1 and not low_arg.startswith("multi"):
                        d["symbol"] = syms[0]
                        d["symbols"] = [syms[0]]
                        d["symbol_scope"] = {"mode": "SINGLE", "symbols": [syms[0]]}
                        self.send(chat_id, self._draft_view(s, f"Symbol set to {syms[0]} (SINGLE)"), _TRADE_KB)
                    else:
                        d["symbol"] = "MULTIPLE"
                        d["symbols"] = syms
                        d["symbol_scope"] = {"mode": "MULTIPLE", "symbols": syms}
                        self.send(chat_id, self._draft_view(s, f"Symbols set to MULTIPLE ({', '.join(syms)})"), _TRADE_KB)
                    return True
                self.send(chat_id, f"Could not resolve any symbols from '{arg}'. Watchlist: {', '.join(db.watchlist_symbols())}")
                return True
            self.send(chat_id, "Choose symbol scope:", self._symbol_kb())
            return True

        if cmd in ("/timeframe", "/tf"):
            return self._cmd_timeframe(chat_id, s, arg)

        if cmd in ("/st_vwap", "/stvwap"):
            return self._cmd_stvwap(chat_id, s, arg)

        if cmd in ("/ema",):
            return self._cmd_ema(chat_id, s, arg)

        if cmd == "/sl":
            return self._cmd_sl(chat_id, s, arg)

        if cmd == "/target":
            return self._cmd_target(chat_id, s, arg)

        if cmd == "/partial":
            return self._cmd_partial(chat_id, s, arg)

        if cmd == "/margin":
            return self._cmd_margin(chat_id, s, arg)

        if cmd == "/leverage":
            return self._cmd_leverage(chat_id, s, arg)

        if cmd in ("/arm", "/execute"):
            return self._cmd_arm(chat_id, s)

        if cmd == "/lifecycle":
            return self._cmd_lifecycle(chat_id, s, arg)

        if cmd == "/edit":
            return self._cmd_edit(chat_id, s, arg)

        if cmd == "/closeall":
            if db.get_mode() == "LIVE":
                n = len(account.exchange_snapshot()[1])
            else:
                n = len(core.db.open_positions(mode="SHADOW")) + \
                    len(core.db.open_shadow_trades())
            if n == 0 and db.get_mode() == "SHADOW":
                self.send(chat_id, "No open positions to close.")
                return True
            s["pending"] = {"kind": "CLOSEALL_CONFIRM"}
            self.send(chat_id, nlg.closeall_warning(db.get_mode(), n))
            return True

        if cmd == "/live":
            if arg.startswith(("on", "start")):
                if db.get_mode() == "LIVE":
                    self.send(chat_id, "Live trading is already ON.")
                    return True
                s["pending"] = {"kind": "LIVE_CONFIRM_1"}
                self.send(chat_id,
                          "Switch Ophelia to LIVE mode? This enables REAL "
                          "exchange orders on BingX.\nType YES to continue or "
                          "no to abort.")
                return True
            if arg.startswith(("off", "stop")):
                if db.get_mode() == "SHADOW":
                    self.send(chat_id, "Live trading is already OFF (SHADOW).")
                    return True
                s["pending"] = {"kind": "LIVE_OFF_CONFIRM"}
                self.send(chat_id, "Stop LIVE trading and return to SHADOW? "
                                   "(yes / no)")
                return True
            self.send(chat_id, nlg.live_mode_message(db.get_mode()))
            return True

        if cmd in ("/download", "/update", "/apk", "/app"):
            sub = arg.lower().strip()
            if sub in ("user", "client"):
                return self._send_user_apk(chat_id)
            elif sub in ("admin", "master", "operator"):
                return self._send_admin_apk(chat_id)
            else:
                return self._show_download_menu(chat_id)

        if cmd in ("/user", "/ophelia_user"):
            return self._send_user_apk(chat_id)

        if cmd in ("/admin", "/ophelia_admin"):
            return self._send_admin_apk(chat_id)

        return False

    # ---------------- /download & APK distribution ----------------
    def _show_download_menu(self, chat_id: int) -> bool:
        kb = {
            "inline_keyboard": [
                [{"text": "📱 OPHELIA USER (v1.2.0)", "callback_data": "/user"}],
                [{"text": "⚡ OPHELIA ADMIN (v2.8.0)", "callback_data": "/admin"}],
                [{"text": "🔙 BACK TO MENU", "callback_data": "/hi"}]
            ]
        }
        msg = (
            "📱 OPHELIA ANDROID FLEET DISTRIBUTION\n\n"
            "Choose which application package to download:\n\n"
            "1️⃣ OPHELIA USER (v1.2.0 Build 3)\n"
            "• Client app for traders & followers\n"
            "• Global ML Intelligence across Crypto, US Equities & Gold\n"
            "• Dynamic ML Slots (1–N) with custom margin & leverage\n"
            "• Manual AUTO Order Terminal with live unified search\n"
            "• Master Copy Trading (1-click follow with own slot capital)\n"
            "• Autonomous Position Manager (TP1 50%, Breakeven, Monotonic Trailing)\n"
            "👉 Tap button below or type /user\n\n"
            "2️⃣ OPHELIA ADMIN (v2.8.0 Build 28)\n"
            "• Operator control plane interface\n"
            "• God Eye 360° Fleet Audit (genuine registered fleet users)\n"
            "• Global System Limits, Live/Shadow Gate, Emergency Close All\n"
            "• Master Trade Broadcasting & Replication Orchestration\n"
            "👉 Tap button below or type /admin"
        )
        self.send(chat_id, msg, kb)
        return True

    def _send_user_apk(self, chat_id: int) -> bool:
        apk_candidates = [
            "/opt/ophelia/static/ophelia-user-latest.apk",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "android-app/app/build/outputs/apk/user/debug/app-user-debug.apk"),
            "/opt/ophelia/control_data/apk/ophelia-user.apk"
        ]
        apk_path = next((p for p in apk_candidates if os.path.exists(p)), None)
        sha256 = "unknown"
        size_mb = 11.4
        if apk_path:
            try:
                with open(apk_path, "rb") as f:
                    b = f.read()
                    sha256 = hashlib.sha256(b).hexdigest()
                    size_mb = len(b) / (1024 * 1024)
            except Exception:
                pass

        direct_url = "https://15.235.193.47/download/user"
        self.send(chat_id, f"⏳ Uploading Ophelia User APK ({size_mb:.2f} MB) directly to this chat...")

        sent_doc = False
        if apk_path:
            caption = (
                f"📱 Ophelia User Client v1.2.0 (Build 3)\n"
                f"• Package: com.ophelia.user\n"
                f"• Size: {size_mb:.2f} MB\n"
                f"• SHA256: {sha256[:16]}...{sha256[-8:]}"
            )
            sent_doc = self.send_document(chat_id, apk_path, caption=caption)

        kb = {
            "inline_keyboard": [
                [{"text": "⚡ DOWNLOAD ADMIN APP", "callback_data": "/admin"}],
                [{"text": "🔙 DOWNLOAD MENU", "callback_data": "/download"}],
                [{"text": "🏠 MAIN MENU", "callback_data": "/hi"}]
            ]
        }

        msg = (
            "✨ *Welcome to Ophelia — Global Autonomous Trading & Replication* ✨\n\n"
            "📱 *Ophelia User App (v1.2.0 • Build 3)* is ready for installation.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🚀 *WHAT'S NEW IN V1.2.0*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "• **Global Autonomous Trading Core**: Unified opportunity engine across Crypto, US Equities & Gold.\n"
            "• **Dynamic ML Slots (1–N)**: Scale beyond 2 slots with custom asset scopes, margin caps & max loss %.\n"
            "• **Manual AUTO Terminal**: Fast unified live search across all markets with direct order submission.\n"
            "• **Autonomous Position Manager**: Server-side TP1 50% partial execution, mathematical net breakeven, and monotonic dynamic trailing.\n"
            "• **Master Copy Trading**: Replicate master trades using your own slot capital and BingX account with strict isolation.\n"
            "• **Collapsible Market & ML Views**: Seamless 3-domain structure (Crypto, US Market, Commodities/Gold).\n\n"
            f"🌐 *Direct HTTPS Download Link*:\n{direct_url}\n\n"
            "ℹ️ *Setup Instructions*:\n"
            "1. Tap the uploaded APK above to install (or open the HTTPS link in your browser).\n"
            "2. Allow install from unknown sources when prompted.\n"
            "3. Sign in with Google.\n"
            "4. Connect your BingX account or trade with simulation.\n"
            "5. Configure your dynamic ML slots or enable Copy Ophelia."
        )
        self.send(chat_id, msg, kb)
        return True

    def _send_admin_apk(self, chat_id: int) -> bool:
        apk_candidates = [
            "/opt/ophelia/static/ophelia-admin-latest.apk",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "android-app/app/build/outputs/apk/admin/debug/app-admin-debug.apk"),
            "/opt/ophelia/control_data/apk/ophelia-admin.apk"
        ]
        apk_path = next((p for p in apk_candidates if os.path.exists(p)), None)
        sha256 = "unknown"
        size_mb = 11.4
        if apk_path:
            try:
                with open(apk_path, "rb") as f:
                    b = f.read()
                    sha256 = hashlib.sha256(b).hexdigest()
                    size_mb = len(b) / (1024 * 1024)
            except Exception:
                pass

        direct_url = "https://15.235.193.47/download/admin"
        self.send(chat_id, f"⏳ Uploading Ophelia Admin APK ({size_mb:.2f} MB) directly to this chat...")

        sent_doc = False
        if apk_path:
            caption = (
                f"⚡ Ophelia Admin v2.8.0 (Build 28)\n"
                f"• Package: com.ophelia.admin\n"
                f"• Size: {size_mb:.2f} MB\n"
                f"• SHA256: {sha256[:16]}...{sha256[-8:]}"
            )
            sent_doc = self.send_document(chat_id, apk_path, caption=caption)

        kb = {
            "inline_keyboard": [
                [{"text": "📱 DOWNLOAD USER APP", "callback_data": "/user"}],
                [{"text": "🔙 DOWNLOAD MENU", "callback_data": "/download"}],
                [{"text": "🏠 MAIN MENU", "callback_data": "/hi"}]
            ]
        }

        msg = (
            "✅ OPHELIA ADMIN APK READY FOR DOWNLOAD\n\n"
            "• App: Ophelia Admin\n"
            "• Package: com.ophelia.admin\n"
            "• Version: 2.8.0 (Build 28)\n"
            f"• File Size: {size_mb:.2f} MB\n"
            f"• SHA-256: {sha256}\n\n"
            f"🌐 Direct HTTPS Download Link:\n{direct_url}\n\n"
            "ℹ️ Features:\n"
            "1. God Eye 360° Fleet Monitoring of genuine registered users.\n"
            "2. Global Autonomous Opportunity Engine and Dynamic Slots control.\n"
            "3. Manual AUTO order terminal with multi-market search.\n"
            "4. Master Trade Replication Bus and system-wide risk limits."
        )
        self.send(chat_id, msg, kb)
        return True

    # ---------------- /hi master menu ----------------
    def _cmd_hi(self, chat_id: int):
        t0 = time.time()
        st = core.system_status()
        rec = None
        if db.get_mode() == "LIVE":
            try:
                rec = account.reconcile()
            except Exception:                                      # noqa: BLE001
                rec = None
        attn = []
        if not st.get("llm", {}).get("available"):
            attn.append("LLM down")
        if (st.get("data_age_min") or 0) > 5:
            attn.append("market data stale")
        if st.get("blackout"):
            attn.append("new-entry blackout")
        if rec and rec.get("reconciliation_required"):
            attn.append(f"{len(rec['issues'])} reconciliation issue(s)")
        lines = [
            "OPHELIA",
            f"Mode: {st.get('mode')}",
            f"Market: LIVE data ({st.get('data_age_min', '?')} min old)",
            f"Automations: {st.get('active_automations', 0)} | "
            f"Positions: {st.get('open_positions', 0)}",
            f"News bias: {st.get('news_bias')}",
            f"Session: {', '.join(st.get('sessions') or []) or 'none'}",
            "Attention: " + (", ".join(attn) if attn else "none"),
            "",
            "Choose a command:",
        ]
        self.send(chat_id, "\n".join(lines), _MENU_KB)
        print(f"[cmd] /hi {time.time() - t0:.2f}s", flush=True)

    # ---------------- trade wizards ----------------
    def _cmd_stvwap(self, chat_id: int, s: dict, arg: str) -> bool:
        d = self._draft(s)
        is_both = d.get("strategy") == "BOTH"
        if not is_both:
            d["strategy"] = "VWAP_SUPERTREND"
        if arg:
            m = re.search(r"(\d+)\s*m\b", arg)
            if m and int(m.group(1)) in (1, 2, 3, 5, 10, 15, 30, 60):
                if is_both:
                    if "strategy_timeframes" not in d: d["strategy_timeframes"] = {}
                    d["strategy_timeframes"]["VWAP_SUPERTREND"] = int(m.group(1))
                else:
                    d["timeframe_min"] = int(m.group(1))
            if re.search(r"\blong\b|bullish", arg):
                d["direction_preference"] = "BULLISH"
            elif re.search(r"\bshort\b|bearish", arg):
                d["direction_preference"] = "BEARISH"
            elif re.search(r"\bany\b", arg):
                d["direction_preference"] = "ANY"
        syms = self._resolve_symbols(s, arg)
        if syms:
            d["symbols"] = syms
            d["symbol"] = syms[0] if len(syms) == 1 else "MULTIPLE"
        self.send(chat_id, self._draft_view(s, "SUPERTREND + VWAP wizard"), _TRADE_KB)
        return True

    def _cmd_ema(self, chat_id: int, s: dict, arg: str) -> bool:
        d = self._draft(s)
        is_both = d.get("strategy") == "BOTH"
        if not is_both:
            d["strategy"] = "EMA_CROSSOVER"
        if arg:
            m = re.search(r"(\d+)\s*m\b", arg)
            if m and int(m.group(1)) in (1, 2, 3, 5, 10, 15, 30, 60):
                if is_both:
                    if "strategy_timeframes" not in d: d["strategy_timeframes"] = {}
                    d["strategy_timeframes"]["EMA_CROSSOVER"] = int(m.group(1))
                else:
                    d["timeframe_min"] = int(m.group(1))
            if re.search(r"\blong\b|bullish", arg):
                d["direction_preference"] = "BULLISH"
            elif re.search(r"\bshort\b|bearish", arg):
                d["direction_preference"] = "BEARISH"
            elif re.search(r"\bany\b", arg):
                d["direction_preference"] = "ANY"
        syms = self._resolve_symbols(s, arg)
        if syms:
            d["symbols"] = syms
            d["symbol"] = syms[0] if len(syms) == 1 else "MULTIPLE"
        self.send(chat_id, self._draft_view(s, "EMA 9/20 wizard"), _TRADE_KB)
        return True

    def _cmd_sl(self, chat_id: int, s: dict, arg: str) -> bool:
        d = self._draft(s)
        toks = arg.split()
        target_strat = None
        if toks and toks[0].lower() in ("st_vwap", "stvwap", "vwap_supertrend", "ema", "ema_crossover", "both"):
            target_strat = toks[0].lower()
            toks = toks[1:]
            arg = " ".join(toks)
        
        if not arg or arg in ("show",):
            cur = self._get_risk(d, "stops", target_strat)
            cur_txt = ("; ".join(f"{x['value']}% {x['type']}"
                                 for x in cur) if cur else "none set")
            self.send(chat_id,
                      f"Stop configuration - current: {cur_txt}\n"
                      "Options:\n"
                      "- /sl manual 1.0        (X% beyond entry)\n"
                      "- /sl vwap 0.2          (X% beyond VWAP)\n"
                      "- /sl supertrend 0.2    (X% beyond Supertrend)\n"
                      "- /sl multi 0.8 vwap0.2 st0.2  (first trigger exits)\n"
                      "- /sl breakeven 0.8     (move stop to cost at +0.8%)\n"
                      "LONG: levels below entry; SHORT: above. Invalid sides "
                      "are rejected, never installed.", _SL_KB)
            return True
        toks = arg.split()
        sub = toks[0]
        try:
            if sub == "manual":
                v = float(toks[1]) if len(toks) > 1 else 1.0
                if not (0 < v <= 50):
                    raise ValueError
                self._update_risk(d, "stops", [{"type": "entry_pct", "value": v}], target_strat)
            elif sub == "vwap":
                v = float(toks[1]) if len(toks) > 1 else 0.20
                self._update_risk(d, "stops", [{"type": "vwap_pct", "value": v}], target_strat)
            elif sub in ("supertrend", "st"):
                v = float(toks[1]) if len(toks) > 1 else 0.20
                self._update_risk(d, "stops", [{"type": "supertrend_pct", "value": v}], target_strat)
            elif sub == "multi":
                stops = []
                for t in toks[1:]:
                    if t.startswith("vwap"):
                        stops.append({"type": "vwap_pct", "value": float(t[4:])})
                    elif t.startswith(("st", "supertrend")):
                        val = float(t.replace("st", "").replace("supertrend", ""))
                        stops.append({"type": "supertrend_pct", "value": val})
                    else:
                        stops.append({"type": "entry_pct", "value": float(t)})
                self._update_risk(d, "stops", stops, target_strat)
            elif sub == "breakeven":
                buf = float(toks[2]) if len(toks) > 2 else 0.0
                self._update_risk(d, "breakeven", {"trigger_pct": float(toks[1]), "buffer_pct": buf}, target_strat)
                self.send(chat_id, f"Break-even armed: stop moves to cost "
                                   f"(buffer {buf:g}%) after +{float(toks[1]):g}% "
                                   "favorable move. Applies to the position "
                                   "once opened.")
                return True
            else:
                raise ValueError(f"unknown stop model: {sub}")
        except (IndexError, ValueError) as e:
            self.send(chat_id, f"Couldn't parse stop config: {e}. See /sl show.")
            return True
        self.send(chat_id, self._draft_view(s, "Stop updated"), _TRADE_KB)
        return True

    def _cmd_target(self, chat_id: int, s: dict, arg: str) -> bool:
        d = self._draft(s)
        toks = arg.split()
        target_strat = None
        if toks and toks[0].lower() in ("st_vwap", "stvwap", "vwap_supertrend", "ema", "ema_crossover", "both"):
            target_strat = toks[0].lower()
            toks = toks[1:]
            arg = " ".join(toks)
        if not arg:
            self.send(chat_id,
                      "Target editor:\n"
                      "- /target 1:2            (single 2R target)\n"
                      "- /partial 50@0.8 25@1.2 trail 0.8  (partial exits)\n"
                      "R targets use the current stop distance at entry.",
                      reply_markup=_TARGET_KB)
            return True
        if arg.startswith("r "):
            r = float(arg.split()[1])
            self._update_risk(d, "targets", [{"pct_qty": 100, "r": round(r, 4)}], target_strat)
            self._update_risk(d, "trailing_pct", None, target_strat)
            self.send(chat_id, self._draft_view(s, "Target updated"), _TRADE_KB)
            return True
        if arg.startswith("pct "):
            p = float(arg.split()[1])
            self._update_risk(d, "targets", [{"pct_qty": 100, "move_pct": round(p, 4)}], target_strat)
            self._update_risk(d, "trailing_pct", None, target_strat)
            self.send(chat_id, self._draft_view(s, "Target updated"), _TRADE_KB)
            return True
        if arg == "none":
            self._update_risk(d, "targets", [], target_strat)
            self.send(chat_id, self._draft_view(s, "Targets cleared"), _TRADE_KB)
            return True
        m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)", arg)
        if not m:
            self.send(chat_id, "Format: /target 1:2  (risk:reward). For "
                               "partials use /partial.")
            return True
        r = float(m.group(2)) / float(m.group(1))
        # R-multiple target: resolved to a % at arm time from the live
        # stop distance (an R target is meaningless before the stop exists)
        self._update_risk(d, "targets", [{"pct_qty": 100, "r": round(r, 4)}], target_strat)
        self._update_risk(d, "trailing_pct", None, target_strat)
        self.send(chat_id, self._draft_view(s, "Target updated"), _TRADE_KB)
        return True

    def _cmd_partial(self, chat_id: int, s: dict, arg: str) -> bool:
        d = self._draft(s)
        toks = arg.split()
        target_strat = None
        if toks and toks[0].lower() in ("st_vwap", "stvwap", "vwap_supertrend", "ema", "ema_crossover", "both"):
            target_strat = toks[0].lower()
            toks = toks[1:]
            arg = " ".join(toks)
        if not arg:
            cur = self._get_risk(d, "targets", target_strat) or []
            cur_txt = "; ".join(f"TP{i + 1}: {t['pct_qty']}% @ +{t['move_pct']}%"
                                for i, t in enumerate(cur)) or "none"
            tr_pct = self._get_risk(d, "trailing_pct", target_strat)
            tr = (f", remaining {100 - sum(t['pct_qty'] for t in cur):g}% "
                  f"trailing {tr_pct}%" if tr_pct else "")
            self.send(chat_id,
                      f"Partial exits - current: {cur_txt}{tr}\n"
                      "Format: /partial 50@0.8 25@1.2 [trail 0.8]\n"
                      "Percentages must sum to 100 (or use trail for the "
                      "remainder).",
                      reply_markup=_PARTIAL_KB)
            return True
        targets = []
        trailing = self._get_risk(d, "trailing_pct", target_strat)
        m_trail = re.search(r"trail(?:ing)?\s+(\d+(?:\.\d+)?)", arg)
        if m_trail:
            trailing = float(m_trail.group(1))
        for m in re.finditer(r"(\d+(?:\.\d+)?)\s*@\s*(\d+(?:\.\d+)?)", arg):
            targets.append({"pct_qty": float(m.group(1)),
                            "move_pct": float(m.group(2))})
        if not targets:
            self.send(chat_id, "Couldn't parse partials. Example: /partial "
                               "50@0.8 25@1.2 trail 0.8")
            return True
        total = sum(t["pct_qty"] for t in targets)
        if trailing is not None:
            if total >= 100:
                self.send(chat_id, "With trailing, target percentages must "
                                   "sum to < 100 (remainder trails).")
                return True
        elif abs(total - 100.0) > 0.01:
            self.send(chat_id, f"Target percentages sum to {total:g}% - must "
                               "be exactly 100, or add 'trail X' for the "
                               "remainder.")
            return True
        self._update_risk(d, "targets", targets, target_strat)
        self._update_risk(d, "trailing_pct", trailing, target_strat)
        self.send(chat_id, self._draft_view(s, "Partial exits updated"), _TRADE_KB)
        return True

    def _cmd_margin(self, chat_id: int, s: dict, arg: str) -> bool:
        d = self._draft(s)
        if not arg:
            try:
                acc, _pos = account.exchange_snapshot()
                avail = acc["available_margin"]
            except Exception:                                     # noqa: BLE001
                avail = None
            self.send(chat_id,
                      "Margin editor:\n"
                      "- /margin 45%      (percent of available margin)\n"
                      "- /margin 10usdt   (fixed USDT amount)\n"
                      + (f"Available margin right now: {avail:g} USDT"
                         if avail else "Available margin: unavailable"), _MARGIN_KB)
            return True
        m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*%", arg)
        m2 = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(?:usdt|u)\b", arg)
        try:
            if m:
                v = float(m.group(1))
                if not (0 < v <= config.RISK_DEFAULTS["max_margin_pct"]):
                    raise ValueError("percent out of range")
                d["margin_usage_pct"] = v
                d["margin_usdt"] = None
            elif m2:
                v = float(m2.group(1))
                if v < config.RISK_DEFAULTS["min_margin_usdt"]:
                    raise ValueError(f"below min "
                                     f"{config.RISK_DEFAULTS['min_margin_usdt']} "
                                     "USDT")
                d["margin_usdt"] = v
                d["margin_usage_pct"] = None
            else:
                raise ValueError("format")
        except ValueError as e:
            self.send(chat_id, f"Invalid margin: {e}. Use /margin 50% or "
                               "/margin 10usdt.")
            return True
        self.send(chat_id, self._draft_view(s, "Margin updated"), _TRADE_KB)
        return True

    def _cmd_leverage(self, chat_id: int, s: dict, arg: str) -> bool:
        d = self._draft(s)
        if not arg:
            self.send(chat_id, "Leverage editor: /leverage 20  (1-"
                               f"{config.RISK_DEFAULTS['max_leverage']}x; "
                               "exchange max applies too)", _LEVERAGE_KB)
            return True
        m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*x?", arg)
        if not m:
            self.send(chat_id, "Leverage editor: /leverage 20  (1-"
                               f"{config.RISK_DEFAULTS['max_leverage']}x; "
                               "exchange max applies too)", _LEVERAGE_KB)
            return True
        v = float(m.group(1))
        if not (1 <= v <= config.RISK_DEFAULTS["max_leverage"]):
            self.send(chat_id, f"Leverage {v:g}x out of allowed range 1-"
                               f"{config.RISK_DEFAULTS['max_leverage']}x.")
            return True
        d["leverage"] = v
        self.send(chat_id, self._draft_view(s, "Leverage updated"), _TRADE_KB)
        return True

    def _cmd_timeframe(self, chat_id: int, s: dict, arg: str) -> bool:
        d = self._draft(s)
        if not arg:
            is_both = d.get("strategy") == "BOTH"
            if is_both:
                tfs = d.get("strategy_timeframes", {})
                st_tf = tfs.get("VWAP_SUPERTREND", 3)
                ema_tf = tfs.get("EMA_CROSSOVER", 1)
                self.send(chat_id, f"Current strategy timeframes:\n"
                                   f"• VWAP_SUPERTREND: {st_tf}m\n"
                                   f"• EMA_CROSSOVER: {ema_tf}m\n"
                                   f"Configure with /st_vwap <min>m, /ema <min>m, or /timeframe both 3m 1m.")
            else:
                self.send(chat_id, f"Current timeframe: {d.get('timeframe_min', 3)}m. Set with /timeframe <min>m (e.g. /timeframe 3m).")
            return True
        low = arg.lower().strip()
        m_both = re.findall(r"(\d+)\s*m\b", low)
        if low.startswith("both") or len(m_both) >= 2:
            if "strategy_timeframes" not in d:
                d["strategy_timeframes"] = {}
            st_val = int(m_both[0]) if len(m_both) >= 1 else 3
            ema_val = int(m_both[1]) if len(m_both) >= 2 else 1
            d["strategy_timeframes"]["VWAP_SUPERTREND"] = st_val
            d["strategy_timeframes"]["EMA_CROSSOVER"] = ema_val
            self.send(chat_id, self._draft_view(s, f"Timeframes updated: VWAP_SUPERTREND {st_val}m, EMA_CROSSOVER {ema_val}m"), _TRADE_KB)
            return True
        if low.startswith(("st", "supertrend", "vwap")):
            m = re.search(r"(\d+)\s*m\b", low)
            if m:
                tf = int(m.group(1))
                d.setdefault("strategy_timeframes", {})["VWAP_SUPERTREND"] = tf
                if d.get("strategy") != "BOTH":
                    d["timeframe_min"] = tf
                self.send(chat_id, self._draft_view(s, f"VWAP_SUPERTREND timeframe set to {tf}m"), _TRADE_KB)
                return True
        if low.startswith("ema"):
            m = re.search(r"(\d+)\s*m\b", low)
            if m:
                tf = int(m.group(1))
                d.setdefault("strategy_timeframes", {})["EMA_CROSSOVER"] = tf
                if d.get("strategy") != "BOTH":
                    d["timeframe_min"] = tf
                self.send(chat_id, self._draft_view(s, f"EMA_CROSSOVER timeframe set to {tf}m"), _TRADE_KB)
                return True
        if m_both:
            tf = int(m_both[0])
            d["timeframe_min"] = tf
            if "strategy_timeframes" not in d:
                d["strategy_timeframes"] = {}
            if d.get("strategy") == "BOTH":
                d["strategy_timeframes"]["VWAP_SUPERTREND"] = tf
                d["strategy_timeframes"]["EMA_CROSSOVER"] = tf
            elif d.get("strategy") == "EMA_CROSSOVER":
                d["strategy_timeframes"]["EMA_CROSSOVER"] = tf
            else:
                d["strategy_timeframes"]["VWAP_SUPERTREND"] = tf
            self.send(chat_id, self._draft_view(s, f"Timeframe set to {tf}m"), _TRADE_KB)
            return True
        self.send(chat_id, "Usage: /timeframe 3m (or /timeframe both 3m 1m)")
        return True

    def _cmd_arm(self, chat_id: int, s: dict) -> bool:
        d = s.get("trade")
        if not d:
            self.send(chat_id, "No trade draft. Start with /trade.")
            return True
        missing = self._missing_fields(d)
        if missing:
            self.send(chat_id, "SETUP INCOMPLETE\nMissing:\n" +
                      "\n".join(f"  • {m}" for m in missing))
            return True
        spec = {"strategy": d["strategy"], "symbol": d["symbol"],
                "symbols": d.get("symbols"),
                "symbol_scope": d.get("symbol_scope") or {"mode": "SINGLE" if d["symbol"] not in ("MULTIPLE", "ALL_WATCHLIST") else d["symbol"], "symbols": d.get("symbols") or [d["symbol"]]},
                "timeframe_min": int(d.get("timeframe_min") or (d.get("strategy_timeframes", {}).get("VWAP_SUPERTREND", 3))),
                "direction_preference": d["direction_preference"],
                "margin_usage_pct": d.get("margin_usage_pct"),
                "margin_usdt": d.get("margin_usdt"),
                "leverage": float(d["leverage"]),
                "stops": d.get("stops"), "targets": d.get("targets"),
                "trailing_pct": d.get("trailing_pct"),
                "breakeven": d.get("breakeven"),
                "expiry_hours": d.get("expiry_hours"),
                "lifecycle": d.get("lifecycle", "CONTINUOUS"),
                "strategy_timeframes": d.get("strategy_timeframes"),
                "strategy_risk": d.get("strategy_risk"),
                "mode": db.get_mode()}
        try:
            proposal = core.build_proposal(spec)
        except core.CoreReject as e:
            return self.send(chat_id, f"Risk layer rejected this setup before "
                                      f"anything was armed: {e}") or True
        # resolve R-multiple targets to % using the live stop distance
        entry_ref = float(proposal.get("entry_ref_price") or 0)
        stop_dist = float(proposal.get("stop_distance_ref") or 0)
        if entry_ref and stop_dist:
            for t in spec.get("targets") or []:
                if t.get("r") and not t.get("move_pct"):
                    t["move_pct"] = round(
                        t["r"] * stop_dist / entry_ref * 100, 4)
        s["pending"] = {"kind": "AUTOMATION_CONFIRM", "spec": spec}
        self.send(chat_id, nlg.proposal_summary(proposal))
        return True

    def _cmd_lifecycle(self, chat_id: int, s: dict, arg: str) -> bool:
        d = self._draft(s)
        curr = d.get("lifecycle", "CONTINUOUS")
        nxt = "ONE_SHOT" if curr == "CONTINUOUS" else "CONTINUOUS"
        d["lifecycle"] = nxt
        self.send(chat_id, self._draft_view(s, f"Lifecycle toggled to {nxt}"), _TRADE_KB)
        return True

    # ---------------- deterministic views ----------------
    def _draft_view(self, s: dict, title: str) -> str:
        d = self._draft(s)
        missing = self._missing_fields(d)
        lines = [title, ""]
        if d.get("strategy") == "BOTH":
            lines.append(f"Strategy: BOTH")
        else:
            lines.append(f"Strategy: {d.get('strategy') or '-'}")

        scope = d.get("symbol_scope", {}).get("mode") if isinstance(d.get("symbol_scope"), dict) else None
        if d.get("symbol") == "ALL_WATCHLIST" or scope == "ALL_WATCHLIST":
            lines.append(f"Symbols: ALL WATCHLIST ({len(d.get('symbols') or db.watchlist_symbols())} symbols)")
        elif d.get("symbol") == "MULTIPLE" or scope == "MULTIPLE" or (d.get("symbols") and len(d.get("symbols")) > 1):
            lines.append(f"Symbols: {', '.join(d.get('symbols') or [])} (MULTIPLE)")
        else:
            lines.append(f"Symbol: {d.get('symbol') or '-'}")

        if d.get("strategy") == "BOTH":
            tfs = d.get("strategy_timeframes", {})
            st_tf = tfs.get("VWAP_SUPERTREND", 3)
            ema_tf = tfs.get("EMA_CROSSOVER", 1)
            lines.append(f"Timeframes: ST/VWAP {st_tf}m | EMA {ema_tf}m")
        else:
            lines.append(f"Timeframe: {d.get('timeframe_min') or '-'}m")

        lines.append(f"Direction: {d.get('direction_preference') or '-'}")
        if d.get("margin_usdt") is not None:
            lines.append(f"Margin: {d['margin_usdt']:g} USDT fixed")
        elif d.get("margin_usage_pct") is not None:
            lines.append(f"Margin: {d['margin_usage_pct']:g}%")
        else:
            lines.append("Margin: -")
        lev = d.get("leverage")
        lines.append(f"Leverage: {f'{float(lev):g}x' if lev else '-'}")
        strats = ["VWAP_SUPERTREND", "EMA_CROSSOVER"] if d.get("strategy") == "BOTH" else [d.get("strategy")] if d.get("strategy") else []
        for st in strats:
            if len(strats) > 1:
                tf_st = d.get("strategy_timeframes", {}).get(st) or (3 if st == "VWAP_SUPERTREND" else 1)
                lines.append(f"-- {st} ({tf_st}m) --")
            risk = d.get("strategy_risk", {}).get(st, d) if d.get("strategy") == "BOTH" else d
            stops = risk.get("stops") or d.get("stops")
            lines.append("Stops: " + ("; ".join(f"{x['value']:g}% {x['type']}" for x in stops) if stops else "-") + " (first trigger exits)")
            be = risk.get("breakeven") or d.get("breakeven")
            if be:
                lines.append(f"Break-even: at +{be['trigger_pct']:g}% (buffer {be.get('buffer_pct', 0):g}%)")
            targets = risk.get("targets") or d.get("targets")
            if targets:
                tparts = []
                for i, t in enumerate(targets):
                    if t.get("r"):
                        tparts.append(f"TP{i + 1}: {t['pct_qty']:g}% @ {t['r']:g}R")
                    else:
                        tparts.append(f"TP{i + 1}: {t['pct_qty']:g}% @ +{t['move_pct']:g}%")
                lines.append("Targets: " + "; ".join(tparts))
            else:
                lines.append("Targets: -")
            tr = risk.get("trailing_pct") or d.get("trailing_pct")
            lines.append(f"Trailing: {(str(tr) + '% buffer') if tr else '-'}")
        lines.append(f"Mode: {db.get_mode()}")
        if missing:
            lines.append("\nSETUP INCOMPLETE - Missing:")
            lines.extend(f"  â€¢ {m}" for m in missing)
            lines.append("Configure with /sl /target /partial /margin "
                         "/leverage, then /arm.")
        else:
            lines.append("\nComplete. /arm to arm (asks final YES), or keep "
                         "editing with /edit.")
        return "\n".join(lines)

    def _position_view(self) -> str:
        """ALL open positions: exchange truth + Ophelia management state."""
        sections: list[str] = []
        rec: dict = {"ok": False, "issues": [], "reconciliation_required": False}
        try:
            _acc, ex = account.exchange_snapshot()
        except Exception as e:                                    # noqa: BLE001
            ex = []
            sections.append(f"Exchange positions unavailable: {str(e)[:120]}")
        try:
            rec = account.reconcile()
        except Exception:                                          # noqa: BLE001
            pass
        local_by_key: dict = {}
        for p in core.db.open_positions():
            key = (p["symbol"] or "").replace("-USDT", "USDT")
            local_by_key.setdefault(f"{key}|{p['direction']}", p)
        shown_keys = set()
        for p in ex:
            key = f"{p['symbol']}|{p['side']}"
            shown_keys.add(key)
            lp = local_by_key.get(key)
            managed = (f"Ophelia-managed (position #{lp['id']}, "
                       f"strategy {(lp.get('detail') or {}).get('strategy', 'n/a')})"
                       if lp else "UNTRACKED (not created by Ophelia)")
            stop_txt = "-"
            targets_txt = "-"
            trail_txt = "-"
            be_txt = "disabled"
            if lp:
                stops = lp.get("stops") or []
                stop_txt = "; ".join(
                    f"{s['value']:g}% {s['type']}" for s in stops) or "-"
                if lp.get("stop_current"):
                    stop_txt += f" | armed stop {nlg._usd(lp['stop_current'])}"
                tg = lp.get("targets") or []
                targets_txt = ("; ".join(f"{t['pct_qty']:g}% @ +{t['move_pct']:g}%"
                                         for t in tg) or "-")
                done = (lp.get("detail") or {}).get("targets_done", [])
                if done:
                    targets_txt += f" (hit: {len(done)})"
                trail_txt = (f"{lp['trailing_pct']:g}% (ref "
                             f"{nlg._usd(lp.get('trailing_ref'))})"
                             if lp.get("trailing_pct") else "-")
                be = (lp.get("detail") or {}).get("breakeven")
                if be:
                    be_txt = (f"at +{be['trigger_pct']:g}%"
                              f"{' DONE' if (lp.get('detail') or {}).get('breakeven_done') else ''}")
            sections.append(
                f"{p['symbol']} {p['side']}  [{managed}]\n"
                f"- qty {p['qty']:g} | entry {nlg._usd(p['entry'])} | mark "
                f"{nlg._usd(p['mark'])} | lev {p['leverage']:g}x\n"
                f"- margin/notional: notional {p['notional']:,.2f} USDT\n"
                f"- liquidation: {nlg._usd(p['liquidation_price'])}\n"
                f"- unrealized PnL: {p['unrealized_pnl']:+.4f} USDT "
                f"({nlg._pct(p['unrealized_pnl_pct'])}) | move from entry "
                f"{nlg._pct(p['move_from_entry_pct'])}\n"
                f"- stops: {stop_txt}\n"
                f"- targets: {targets_txt} | trailing: {trail_txt} | "
                f"break-even: {be_txt}\n"
                f"- mode: {db.get_mode()}")
        # local LIVE positions with no exchange counterpart
        for key, lp in local_by_key.items():
            if key not in shown_keys:
                sections.append(
                    f"{lp['symbol']} {lp['direction']}  [LOCAL ONLY - "
                    "RECONCILIATION_REQUIRED]\n"
                    f"- qty {lp['qty']:g} @ {nlg._usd(lp['entry'])}\n"
                    "- exchange shows no such position - do not trust local "
                    "state; check /bingx.")
        for t in core.db.open_shadow_trades():
            sections.append(
                f"Shadow trade #{t['id']}: {t['direction']} {t.get('qty', '?')} "
                f"@ {nlg._usd(t['entry'])} | stop {nlg._usd(t['stop'])} | "
                f"target {nlg._usd(t['target'])} (simulated)")
        if rec.get("reconciliation_required"):
            sections.append("RECONCILIATION_REQUIRED: " + "; ".join(
                f"{i.get('kind')} {i.get('symbol')}" for i in rec["issues"]))
        if not sections:
            return "No active position."
        return "\n\n".join(sections)

    def _setup_view(self, s: dict) -> str:
        pend = s.get("pending")
        if pend and pend.get("kind") == "AUTOMATION_CONFIRM":
            return nlg.setup_report(pend["spec"], "WAITING_CONFIRMATION",
                                    db.get_mode())
        d = s.get("trade")
        if d and (d.get("strategy") or d.get("symbol")):
            return self._draft_view(s, "OPHELIA SETUP (draft)")
        autos = db.list_automations(status="ACTIVE")
        if not autos:
            return ("No armed setup or draft. Create one with /trade "
                    "(deterministic) or natural language.")
        a = autos[0]
        params = a.get("params") or {}
        spec = {"symbol": a["symbol"], "timeframe_min": a["timeframe"],
                "direction_preference": a["direction_pref"],
                "margin_usage_pct": a["margin_usage_pct"],
                "leverage": a["leverage"], "strategy": a["strategy"],
                "stops": params.get("stops"), "targets": params.get("targets"),
                "trailing_pct": params.get("trailing_pct"),
                "expiry_hours": params.get("expiry_hours")}
        return nlg.setup_report(spec, "ARMED", db.get_mode())

    def _cmd_edit(self, chat_id: int, s: dict, arg: str) -> bool:
        """Deterministic editor for pending drafts and open positions.

        Every material edit shows old -> new and asks confirmation before
        being applied.
        """
        if not arg:
            self.send(chat_id, self._edit_menu(s))
            return True
        toks = arg.split()
        sub = toks[0].lower()
        positions = core.db.open_positions()

        # draft edits route to the wizard editors
        d = s.get("trade")
        if d and (d.get("strategy") or d.get("symbol")) and \
                sub in ("stop", "target", "partial", "margin", "leverage",
                        "sl", "trail", "trailing", "breakeven"):
            if sub in ("stop", "sl"):
                return self._cmd_sl(chat_id, s, " ".join(toks[1:]) or "show")
            if sub in ("target",):
                return self._cmd_target(chat_id, s, " ".join(toks[1:]))
            if sub in ("partial",):
                return self._cmd_partial(chat_id, s, " ".join(toks[1:]))
            if sub in ("margin",):
                return self._cmd_margin(chat_id, s, " ".join(toks[1:]))
            if sub in ("leverage",):
                return self._cmd_leverage(chat_id, s, " ".join(toks[1:]))
            if sub in ("trail", "trailing"):
                try:
                    v = float(toks[1])
                    d["trailing_pct"] = v
                except (IndexError, ValueError):
                    self.send(chat_id, "Format: /edit trailing 0.8")
                    return True
                self.send(chat_id, self._draft_view(s, "Trailing updated"))
                return True
            if sub == "breakeven":
                try:
                    buf = float(toks[2]) if len(toks) > 2 else 0.0
                    d["breakeven"] = {"trigger_pct": float(toks[1]),
                                      "buffer_pct": buf}
                except (IndexError, ValueError):
                    self.send(chat_id, "Format: /edit breakeven 0.8 [buffer]")
                    return True
                self.send(chat_id, self._draft_view(s, "Break-even updated"))
                return True

        # open-position edits (old -> new + confirm)
        if not positions:
            self.send(chat_id, "No open position to edit. Draft edits: "
                               "/edit stop 0.8, /edit target 1:2, ...")
            return True
        p = positions[0]
        long = p["direction"] == "LONG"
        entry = p["entry"]

        def confirm(what: str, old, new, apply):
            s["pending"] = {"kind": "EDIT_CONFIRM", "apply": apply}
            self.send(chat_id, f"EDIT {what}\nOld: {old}\nNew: {new}\n"
                               "Confirm? YES / no")

        try:
            if sub in ("stop", "sl"):
                v = float(toks[1])
                lvl = entry * (1 - v / 100) if long else entry * (1 + v / 100)
                if (long and lvl >= entry) or (not long and lvl <= entry):
                    raise core.CoreReject(
                        f"stop {v:g}% is on the wrong side of entry "
                        f"({entry:g}); refusing invalid stop")
                def apply():
                    db.update_position(p["id"], stop_current=lvl)
                    db.audit("telegram", "EDIT_STOP",
                             {"position_id": p["id"], "stop": lvl})
                    return f"Stop for {p['symbol']} set to {lvl:g}."
                confirm("STOP", nlg._usd(p.get("stop_current")),
                        f"{v:g}% from entry = {nlg._usd(lvl)}", apply)
                return True
            if sub in ("trail", "trailing"):
                v = float(toks[1])
                def apply():
                    db.update_position(p["id"], trailing_pct=v)
                    db.audit("telegram", "EDIT_TRAILING",
                             {"position_id": p["id"], "trailing_pct": v})
                    return (f"Trailing for {p['symbol']} set to {v:g}% "
                            "(favorable-only ratchet).")
                confirm("TRAILING", p.get("trailing_pct"), f"{v:g}%", apply)
                return True
            if sub == "breakeven":
                trig = float(toks[1])
                buf = float(toks[2]) if len(toks) > 2 else 0.0
                def apply():
                    detail = p.get("detail") or {}
                    detail["breakeven"] = {"trigger_pct": trig,
                                           "buffer_pct": buf}
                    detail.pop("breakeven_done", None)
                    db.update_position(p["id"], detail_json=db.json_dumps(detail))
                    db.audit("telegram", "EDIT_BREAKEVEN",
                             {"position_id": p["id"], "trigger": trig})
                    return (f"Break-even for {p['symbol']}: stop to cost at "
                            f"+{trig:g}% (buffer {buf:g}%).")
                confirm("BREAK-EVEN",
                        (p.get("detail") or {}).get("breakeven", "disabled"),
                        f"trigger +{trig:g}%, buffer {buf:g}%", apply)
                return True
            if sub in ("qty", "quantity"):
                m = re.fullmatch(r"([+-])(\d+(?:\.\d+)?)\s*%?", toks[1])
                if not m:
                    self.send(chat_id, "Format: /edit qty +20% or /edit qty -50%")
                    return True
                sign = 1 if m.group(1) == "+" else -1
                frac = float(m.group(2)) / 100.0
                delta = round(p["qty"] * frac, 6)
                if sign < 0 and delta > p["qty"]:
                    raise core.CoreReject("cannot reduce more than the "
                                          "remaining quantity")
                def apply():
                    if p["mode"] == "LIVE":
                        client = core._live_client()
                        side = "SELL" if p["direction"] == "LONG" else "BUY"
                        if sign > 0:
                            side = "BUY" if p["direction"] == "LONG" else "SELL"
                        norm = core.normalize_qty(p["symbol"], delta,
                                                  p["entry"])["qty"]
                        client.market_order(
                            p["symbol"].replace("-USDT", "USDT"), side,
                            p["direction"], norm,
                            f"oph-edit-{p['id']}-{int(time.time())}")
                        new_qty = round(p["qty"] + sign * norm, 6)
                    else:
                        new_qty = round(p["qty"] + sign * delta, 6)
                    db.update_position(p["id"], qty=new_qty)
                    db.audit("telegram", "EDIT_QTY",
                             {"position_id": p["id"], "delta": sign * delta,
                              "new_qty": new_qty})
                    return f"Quantity for {p['symbol']} is now {new_qty:g}."
                confirm("QUANTITY", f"{p['qty']:g}",
                        f"{p['qty'] + sign * delta:g} ({m.group(0)})", apply)
                return True
            if sub in ("leverage", "lev"):
                v = float(toks[1])
                def apply():
                    if p["mode"] == "LIVE":
                        core._live_client().set_leverage(
                            p["symbol"].replace("-USDT", "USDT"), int(v))
                    db.update_position(p["id"], leverage=v)
                    db.audit("telegram", "EDIT_LEVERAGE",
                             {"position_id": p["id"], "leverage": v})
                    return f"Leverage for {p['symbol']} set to {v:g}x."
                confirm("LEVERAGE", f"{p.get('leverage'):g}x", f"{v:g}x", apply)
                return True
        except (IndexError, ValueError) as e:
            self.send(chat_id, f"Couldn't parse edit: {e}. /edit shows options.")
            return True
        except core.CoreReject as e:
            self.send(chat_id, f"Rejected: {e}")
            return True
        self.send(chat_id, "Unknown edit. /edit shows the menu.")
        return True

    def _edit_menu(self, s: dict) -> str:
        pend = s.get("pending")
        if pend and pend.get("kind") == "AUTOMATION_CONFIRM":
            return ("Current pending setup:\n" + self._setup_view(s) +
                    "\n\nEdit with: /sl ..., /target ..., /partial ..., "
                    "/margin ..., /leverage ... (each shows old -> new, then "
                    "re-proposes).")
        d = s.get("trade")
        if d and (d.get("strategy") or d.get("symbol")):
            return ("Current draft:\n" + self._draft_view(s, "EDIT") +
                    "\n\nEdit with: /sl ..., /target ..., /partial ..., "
                    "/margin ..., /leverage ... .")
        positions = core.db.open_positions()
        if positions:
            p = positions[0]
            return (f"Current position:\n  {p['symbol']} {p['direction']} "
                    f"qty {p['qty']} @ {nlg._usd(p['entry'])}\n\n"
                    "Available:\n  1. Stop loss (/sl ...)\n  2. Targets "
                    "(/target, /partial)\n  3. Quantity (say: 'add 20% qty' / "
                    "'reduce 50%')\n  4. Trailing stop (/partial ... trail X)\n"
                    "  5. Break-even (/sl breakeven 0.8)\n"
                    "  6. Leverage (/leverage X)\n\n"
                    "Position edits apply to the live/shadow position and ask "
                    "confirmation for material changes.")
        autos = db.list_automations(status="ACTIVE")
        if autos:
            a = autos[0]
            return (f"Armed automation #{a['id']}: {a['symbol']} "
                    f"{a['timeframe']}m.\nTell me what to change (stop, "
                    "targets, margin, leverage, trailing, expiry).")
        return "Nothing to edit - no pending setup, draft, or open position."

    def _cmd_marketstate(self, sym: str) -> str:
        """Read-only summary of institutional market-state & microstructure."""
        from institutional.market_state import MarketStateEngine
        from institutional.structure_detectors import (
            detect_fvg,
            detect_liquidity_sweep,
            detect_equal_highs_lows,
            detect_displacement,
        )
        cd = analytics.get_candles(sym, lookback_min=180, base_interval_min=1, agg_interval_min=5)
        candles = cd.get("candles", [])
        if not candles:
            return f"Market state unavailable for {sym} (insufficient candle data)."

        closes = [c["close"] for c in candles]
        highs = [c["high"] for c in candles]
        lows = [c["low"] for c in candles]
        opens = [c["open"] for c in candles]
        volumes = [c.get("volume", 0.0) for c in candles]
        px = closes[-1]
        vreg = analytics.vwap_regime(sym, tf_min=5)
        vwap = float(vreg.get("vwap", px))
        st = analytics.get_supertrend(sym, tf_min=5)
        st_dir = "BULLISH" if st.get("state") == "GREEN" else ("BEARISH" if st.get("state") == "RED" else "NEUTRAL")

        now_ms = int(time.time() * 1000)
        detections = [
            detect_fvg(highs, lows, closes, now_ms, sym, "5m"),
            detect_liquidity_sweep(highs, lows, closes, now_ms, sym, "5m"),
            detect_equal_highs_lows(highs, lows, now_ms, sym, "5m"),
            detect_displacement(opens, highs, lows, closes, now_ms, sym, "5m"),
        ]

        ms = MarketStateEngine.compile(
            symbol=sym,
            timestamp=now_ms,
            timeframe="5m",
            closes=closes,
            highs=highs,
            lows=lows,
            volumes=volumes,
            current_price=px,
            vwap=vwap,
            supertrend_direction=st_dir,
            structure_detections=detections
        )

        det_lines = [f"• {d.detector_name}: {d.direction} (str: {d.strength:.2f})" for d in detections if d.detected]
        det_text = "\n".join(det_lines) if det_lines else "None detected (stable structure)"

        return (
            f"🔬 OPHELIA MARKET-STATE: {sym} [5m]\n"
            f"[RESEARCH / EXPERIMENTAL - NO EXECUTION AUTHORITY]\n\n"
            f"Price: {px:g} | VWAP: {vwap:g} ({ms.metrics.get('vwap_diff_pct', 0.0):+.2f}%)\n"
            f"Trend: {ms.trend_state} | Volatility: {ms.volatility_state} | Volume: {ms.volume_state}\n"
            f"VWAP State: {ms.vwap_state} | Session: {ms.session_state}\n"
            f"Order Flow: {ms.order_flow_state} | CVD State: {ms.cvd_state}\n"
            f"Displacement: {ms.displacement_state} | Liquidity: {ms.liquidity_state}\n\n"
            f"Structure Detections:\n{det_text}\n\n"
            f"Confidence: {ms.confidence:.2f} | Data Quality: {ms.data_quality}"
        )

    def _progress_report(self) -> str:
        bits = []
        oh = db.oldest_newest()
        if oh["newest_ts"]:
            age = (time.time() * 1000 - oh["newest_ts"]) / 60_000
            if age > 3:
                bits.append(f"Market data catching up (latest candle "
                            f"{age:.0f} min old)")
        if llm.last_error():
            bits.append(f"LLM recovering - {llm.last_error()}")
        return "\n".join(bits) if bits else "No background activity."

    def _watchlist_rows(self) -> list[dict]:
        rows = []
        for sym in db.watchlist_symbols():
            oh = db.oldest_newest(sym)
            px = None
            age = None
            if oh["newest_ts"]:
                age = round((time.time() * 1000 - oh["newest_ts"]) / 60_000, 1)
                r = db.query_candles(sym, oh["newest_ts"] - 60_000,
                                     oh["newest_ts"] + 1)
                if r:
                    px = r[-1]["close"]
            rows.append({"symbol": sym, "exchange": config.PRIMARY_EXCHANGE,
                         "last_price": px, "age_min": age, "rows": oh["rows"]})
        return rows

    def _watchlist_manage(self, chat_id: int, text: str) -> bool:
        """NL watchlist add/remove with exchange verification."""
        low = text.lower().strip()
        symbol: str | None = None
        m = re.search(r"\badd\s+([a-z0-9 ]+?)(?:\s+to(?:\s+my)?\s+watchlist|"
                      r"\s+watchlist)?\s*[.!]?$", low)
        if m and ("watchlist" in low or low.startswith("add ")):
            first_word = m.group(1).strip().split()[0]
            pair = first_word.upper().replace("-", "").replace("/", "") \
                .replace("_", "")
            pair = _SYMBOL_ALIASES.get(first_word, pair)
            if not pair.endswith("USDT"):
                pair += "USDT"
            if pair in ("USDTUSDT",) or not pair.isalnum():
                return False
            if not _verify_binance_pair(pair):
                self.send(chat_id, f"I can't find a tradable instrument for "
                                   f"'{first_word}' on the exchange data source. "
                                   "Double-check the symbol (e.g. AUXUSDT) and "
                                   "I'll verify again before adding anything.")
                return True
            symbol = f"{pair[:-4]}-USDT"
            if symbol in db.watchlist_symbols():
                self.send(chat_id, f"{symbol} is already on your watchlist.")
                return True
            db.watchlist_add(symbol)
            from . import ingest
            n = ingest.backfill_symbol(symbol)
            self.send(chat_id, f"Added {symbol}. Live 1-minute tracking started "
                               f"({n:,} candles backfilled, 24h rolling "
                               f"retention). Say 'remove {symbol[:-4].lower()}' "
                               "to stop tracking and delete its data.")
            return True
        m = re.search(r"\bremove\s+([a-z0-9 -]+?)(?:\s+from(?:\s+my)?\s+"
                      r"watchlist|\s+watchlist)?\s*[.!]?$", low)
        if m and ("watchlist" in low or low.startswith("remove ")):
            raw = m.group(1).strip()
            base = raw.upper().replace("-USDT", "").replace("USDT", "") \
                .replace("-", "").strip()
            alias = _SYMBOL_ALIASES.get(raw.split()[0], "").replace("USDT", "")
            symbol = None
            for sw in db.watchlist_symbols():
                if sw.replace("-USDT", "") in (base, alias):
                    symbol = sw
                    break
            if not symbol:
                self.send(chat_id, f"'{raw}' isn't on your watchlist. "
                                   "Say 'show my watchlist' to see it.")
                return True
            db.watchlist_remove(symbol)
            self.send(chat_id, f"Removed {symbol}. Live tracking stopped and "
                               "its retained market data was deleted "
                               "(research/backtest files untouched).")
            return True
        return False

    # ---------------- session memory ----------------
    def _remember(self, s: dict, intent: dict, grounded: dict):
        """Store params the user actually wrote (grounded) - never LLM inventions."""
        for k in CONTEXT_KEYS:
            if k in grounded:
                s["context"][k] = grounded[k]
            elif intent.get(k) is not None and k in s["context"]:
                s["context"][k] = intent[k]

    def _remember_turn(self, s: dict, user_text: str, reply: str):
        hist = s.setdefault("history", [])
        hist.append({"role": "user", "content": user_text[:400]})
        hist.append({"role": "assistant", "content": reply[:400]})
        del hist[:-8]

    def _pending_note(self, s: dict) -> str:
        pend = s.get("pending")
        if not pend or pend.get("kind") != "AUTOMATION_CONFIRM":
            return ""
        spec = pend.get("spec", {})
        return ("\n\n(By the way: the "
                f"{spec.get('symbol', '?')} {spec.get('timeframe_min', '?')}m proposal "
                "is still waiting - YES arms it, 'cancel' drops it.)")

    # ---------------- automation create/update (NL path) ----------------
    @staticmethod
    def _fmt_change(key: str, value) -> str:
        if key == "timeframe_min":
            return f"timeframe to {int(value)}m"
        if key == "margin_usage_pct":
            return f"margin to {value:g}%"
        if key == "leverage":
            return f"leverage to {float(value):g}x"
        if key == "direction_preference":
            return f"preference to {str(value).lower()}"
        return f"{key} to {value}"

    def _automation_flow(self, chat_id: int, s: dict, intent: dict,
                         user_text: str, grounded: dict) -> str:
        pend = s.get("pending")

        ctx = s.get("context", {})
        incoming: dict = {}
        for k in CONTEXT_KEYS:
            v = intent.get(k)
            if v is None:
                continue
            if k in grounded:
                incoming[k] = grounded[k]
            elif k in ctx:
                incoming[k] = v
            # else: value invented by the model -> dropped

        if pend and pend.get("kind") == "AUTOMATION_CONFIRM":
            spec = dict(pend["spec"])
            changed = {k: v for k, v in incoming.items()
                       if spec.get(k) != v
                       and not (isinstance(v, (int, float))
                                and isinstance(spec.get(k), (int, float))
                                and float(v) == float(spec[k]))}
            if not changed:
                return nlg.config_recap(spec)
            spec.update(changed)
            try:
                proposal = core.build_proposal(spec)
            except core.CoreReject as e:
                s["pending"] = None
                return ("I applied that, but the risk layer rejected the resulting "
                        f"setup: {e}\nThe old proposal was dropped - let's rebuild.")
            spec["mode"] = db.get_mode()
            s["pending"] = {"kind": "AUTOMATION_CONFIRM", "spec": spec}
            updates = ", ".join(self._fmt_change(k, v)
                                for k, v in changed.items())
            return (f"Done - updated {updates}. Revised proposal:\n\n"
                    + nlg.proposal_summary(proposal))

        merged = dict(s.get("context", {}))
        merged.update(incoming)
        missing = [p for p in ("symbol", "timeframe_min", "margin_usage_pct",
                               "leverage") if merged.get(p) is None]
        if missing:
            s["context"] = merged
            return nlg.missing_params_message(missing, merged)

        spec = {"strategy": merged.get("strategy") or "EMA_CROSSOVER",
                "symbol": merged["symbol"],
                "timeframe_min": int(merged["timeframe_min"]),
                "direction_preference": merged.get("direction_preference") or "ANY",
                "margin_usage_pct": float(merged["margin_usage_pct"]),
                "leverage": float(merged["leverage"]),
                "mode": db.get_mode()}
        try:
            proposal = core.build_proposal(spec)
        except core.CoreReject as e:
            return (f"The risk layer rejected this setup before anything was armed: "
                    f"{e}")
        s["pending"] = {"kind": "AUTOMATION_CONFIRM", "spec": spec}
        return nlg.proposal_summary(proposal)

    # ---------------- market query (NL path) ----------------
    def _market_flow(self, s: dict, intent: dict, raw: bool,
                     user_text: str = "") -> str:
        low = user_text.lower()
        wl = db.watchlist_symbols()
        ctx_sym = s.get("context", {}).get("symbol")
        sym = intent.get("symbol") or ctx_sym or (wl[0] if wl else "SOL-USDT")
        lookback = min(max(int(intent.get("lookback_min") or 30), 1),
                       config.MAX_LOOKBACK_HOURS * 60)
        agg = intent.get("aggregation_interval_min")
        agg = int(agg) if agg else None
        an = set(intent.get("analytics_requested") or [])
        sections: list[str] = []

        if re.search(r"\bema\s*(9|20)?\b", low) and "crossover_estimate" not in an:
            an.add("ema")
            if re.search(r"ema\s*state|ema\s*9|ema\s*20", low):
                an.discard("movement")
        if re.search(r"\bsupertrend\b", low):
            an.add("supertrend")
        if re.search(r"\bvwap\b", low):
            an.add("vwap")

        if lookback > config.MAX_LOOKBACK_HOURS * 60:
            return (f"I only keep {config.MAX_LOOKBACK_HOURS}h of live 1-minute "
                    f"data, so I can't analyze {lookback} minutes yet.")

        tf_default = agg or int(intent.get("timeframe_min") or 3)

        if "crossover_estimate" in an:
            snap = analytics.get_market_snapshot(sym, lookback_min=max(60, lookback),
                                                 agg_interval_min=agg or 5,
                                                 indicators=("EMA9", "EMA20"))
            if "error" not in snap:
                ind = snap.get("indicators", {})
                if ind.get("EMA9") is not None and ind.get("EMA20") is not None:
                    sections.append(
                        f"FACTS - {sym}: price {nlg._usd(snap.get('last_price'))}, "
                        f"EMA9 {ind['EMA9']:g}, EMA20 {ind['EMA20']:g} "
                        f"({str(ind.get('EMA_state', '')).lower()}).")
            tf = agg or int(intent.get("timeframe_min") or 5)
            sections.append(nlg.crossover_estimate_summary(
                analytics.ema_crossover_estimate(sym, tf), tf))
        elif "movement" in an and "ema" not in an:
            mv = analytics.movement_stats(sym, lookback, agg)
            sections.append(nlg.movement_summary(sym, mv, agg))
        elif "volume_flow" in an:
            sections.append(nlg.trade_flow_summary(
                sym, analytics.get_trade_flow(sym, lookback), lookback))
        elif "volume_profile" in an:
            sections.append(nlg.volume_profile_summary(
                analytics.get_volume_profile(sym, lookback)))
        elif "order_book" in an:
            sections.append(nlg.orderbook_summary(analytics.get_order_book(sym)))
        else:
            snap = analytics.get_market_snapshot(sym, lookback_min=max(60, lookback),
                                                 agg_interval_min=agg or 5,
                                                 indicators=("EMA9", "EMA20", "ATR"))
            sections.append(nlg.market_snapshot_summary(sym, snap,
                                                        max(60, lookback),
                                                        agg or 5))
            if "supertrend" in an:
                sections.append(nlg.supertrend_summary(
                    analytics.get_supertrend(sym, tf_default)))
            if "vwap" in an:
                sections.append(nlg.vwap_summary(analytics.get_vwap(sym, tf_default)))

        body = "\n\n".join(x for x in sections if x)
        if raw:
            payload = {"symbol": sym, "lookback_min": lookback,
                       "aggregation_interval_min": agg}
            body += "\n\n(raw)\n" + json.dumps(payload, default=str)[:1200]
        return body

    # ---------------- main handler ----------------
    def handle(self, chat_id: int, text: str):
        low = text.lower().strip()
        s = self.sessions.setdefault(chat_id, {"context": {}, "pending": None,
                                               "history": []})

        if self.try_confirmation(chat_id, low):
            return

        if self._command(chat_id, text):
            return

        # deterministic: asking about the pending configuration needs no LLM
        pend = s.get("pending")
        if pend and pend.get("kind") == "AUTOMATION_CONFIRM" and \
                re.search(r"config|setup|settings|current proposal", low):
            self.send(chat_id, nlg.config_recap(pend["spec"]))
            return

        # deterministic watchlist management (no LLM)
        if self._watchlist_manage(chat_id, text):
            return

        # deterministic fast-paths (no LLM latency needed)
        if low in ("ophelia health", "health", "health?", "status"):
            h = core.health()
            self.send(chat_id, nlg.maybe_raw(low, nlg.health_summary(h), h))
            return
        if low in ("vps health", "how's the vps?", "hows the vps", "is the vps okay"):
            h = core.health()
            self.send(chat_id, nlg.maybe_raw(low, nlg.health_summary(h), h))
            return
        if low in ("data health", "data engine health"):
            dh = core.health()["data_health"]
            self.send(chat_id, nlg.maybe_raw(low, (
                f"Data engine: {dh.get('rows', 0):,} one-minute rows retained "
                f"(24h rolling window).\nLatest candle is "
                f"{dh.get('data_age_min', '?')} min old; cleanup last ran "
                f"{dh.get('last_cleanup_min_ago', '?')} min ago."), dh))
            return
        if low in ("show my active automations", "active automations",
                   "show automations", "automations"):
            rows = db.list_automations()
            self.send(chat_id, nlg.automations_summary(rows))
            return
        if low in ("positions?", "positions", "open positions",
                   "show me my current positions"):
            self.send(chat_id, self._position_view())
            return
        if low in ("what's today's macro bias?", "macro bias", "news",
                   "today's bias", "todays bias", "how does the news look today?",
                   "how is the news today?", "how's the news?"):
            from . import news
            ctx = news.get_daily_macro_context()
            self.send(chat_id, nlg.maybe_raw(low, nlg.news_summary(ctx), ctx))
            return
        if low in ("help", "what can you do?"):
            self.send(chat_id, _HELP_TEXT)
            return

        # deterministic market fast-paths: common queries skip the LLM entirely
        fast = self._fast_market(chat_id, s, low)
        if fast is not None:
            self.send(chat_id, fast)
            return

        raw_mode = ("raw" in low) or ("json" in low)

        # LLM path (natural language only)
        intent, _model, err = llm.parse_intent(low, s.get("context") or {},
                                               s.get("history"))
        if intent is None:
            if err and err.startswith("llm_unavailable"):
                self.send(chat_id, nlg.LLM_DOWN_MESSAGE)
            else:
                self.send(chat_id,
                          f"I couldn't quite parse that ({err}). Could you rephrase?")
            return

        grounded = nlg.extract_params_from_text(low)
        self._remember(s, intent, grounded)
        itype = intent["intent_type"]

        if itype in ("AUTOMATION_CREATE", "CONDITION_CREATE"):
            reply = self._automation_flow(chat_id, s, intent, low, grounded)
        elif itype == "AUTOMATION_CONTROL":
            action = (intent.get("action") or "").upper()
            aid = intent.get("automation_id")
            if action == "CANCEL" and not aid and \
                    s.get("pending", {}) and \
                    s["pending"].get("kind") == "AUTOMATION_CONFIRM":
                spec = s["pending"]["spec"]
                s["pending"] = None
                reply = (f"Dropped the pending {spec.get('symbol', '?')} "
                         f"{spec.get('timeframe_min', '?')}m proposal. "
                        "Nothing was armed.")
            else:
                rows = db.list_automations()
                if action in ("LIST", ""):
                    reply = nlg.automations_summary(rows)
                else:
                    active = [r for r in rows if r["status"] == "ACTIVE"]
                    if not aid and len(active) == 1:
                        aid = active[0]["id"]
                    status_map = {"PAUSE": "PAUSED", "RESUME": "ACTIVE",
                                  "CANCEL": "CANCELLED"}
                    if action in status_map and aid:
                        ok = db.set_automation_status(int(aid), status_map[action])
                        if ok:
                            if action == "CANCEL":
                                s["pending"] = None
                            reply = nlg.automation_status_change(int(aid),
                                                                 status_map[action])
                        else:
                            reply = f"I couldn't find automation #{aid}."
                    elif action in ("PAUSE", "RESUME", "CANCEL"):
                        reply = ("Tell me which one - say 'show automations' for "
                                 "the list, or name the #id.")
                    else:
                        reply = nlg.automations_summary(rows)
        elif itype == "HEALTH_QUERY":
            h = core.health()
            reply = nlg.maybe_raw(low, nlg.health_summary(h), h)
        elif itype == "NEWS_QUERY":
            from . import news
            ctx = news.get_daily_macro_context()
            reply = nlg.maybe_raw(low, nlg.news_summary(ctx), ctx)
        elif itype == "MARKET_QUERY":
            reply = self._market_flow(s, intent, raw_mode, low)
        else:  # CHAT
            reply = intent.get("reply_hint") or nlg.FALLBACK_CHAT
            reply += self._pending_note(s)

        self.send(chat_id, reply)
        self._remember_turn(s, low, reply)

    # ---------------- deterministic market fast-paths ----------------
    def _fast_market(self, chat_id: int, s: dict, low: str) -> str | None:
        """Deterministic routing for the most common natural queries."""
        wl = db.watchlist_symbols()
        default_sym = (s.get("context", {}).get("symbol")
                       or (wl[0] if wl else "SOL-USDT"))

        def sym_from(text: str) -> str | None:
            for alias, pair in _SYMBOL_ALIASES.items():
                if re.search(rf"\b{alias}\b", text):
                    return pair.replace("USDT", "-USDT")
            return None

        sym = sym_from(low) or (default_sym if
                                re.search(r"\b(doing|price|market)\b", low)
                                else None)

        if re.search(r"what'?s \w+ doing|how'?s \w+|how does \w+ look|"
                     r"\w+\s*(price|rate)\b.*\??$", low) and sym and \
                not re.search(r"watchlist|setup|news|health|volume|profile|"
                              r"order book|flow|candle", low):
            snap = analytics.get_market_snapshot(sym, lookback_min=60,
                                                 agg_interval_min=3,
                                                 indicators=("EMA9", "EMA20", "ATR"))
            return nlg.market_snapshot_summary(sym, snap, 60, 3)

        m = re.search(r"last\s+(\d+)\s*(?:m\b|min)", low)
        if m and sym and "candle" not in low:
            lookback = min(int(m.group(1)), config.MAX_LOOKBACK_HOURS * 60)
            mv = analytics.movement_stats(sym, lookback, None)
            return nlg.movement_summary(sym, mv, None)

        m = re.search(r"(\d+)\s*m(?:in)?(?:ute)?s?\s+candles?", low)
        if m and sym:
            agg = int(m.group(1))
            lookback = 30
            m2 = re.search(r"last\s+(\d+)\s*(?:m\b|min)", low)
            if m2:
                lookback = min(int(m2.group(1)), config.MAX_LOOKBACK_HOURS * 60)
            mv = analytics.movement_stats(sym, lookback, agg)
            return nlg.movement_summary(sym, mv, agg)

        if re.search(r"\bvolume\b|\binflow\b|\boutflow\b|\bnet flow\b|"
                     r"buying pressure", low) and sym and "profile" not in low:
            f = analytics.get_trade_flow(sym, 30)
            return nlg.trade_flow_summary(sym, f, 30)

        if re.search(r"volume profile|\bprofile\b", low) and sym:
            return nlg.volume_profile_summary(analytics.get_volume_profile(sym, 60))

        if re.search(r"order book|\bbook\b|depth", low) and sym:
            return nlg.orderbook_summary(analytics.get_order_book(sym))

        if re.search(r"supertrend", low) and sym:
            m = re.search(r"(\d+)\s*m\b", low)
            tf = int(m.group(1)) if m else 3
            return nlg.supertrend_summary(analytics.get_supertrend(sym, tf))

        if re.search(r"\bvwap\b", low) and sym:
            m = re.search(r"(\d+)\s*m\b", low)
            tf = int(m.group(1)) if m else 3
            return nlg.vwap_summary(analytics.get_vwap(sym, tf))

        if re.search(r"(show|my)\s+watchlist|^watchlist$", low):
            return nlg.watchlist_report(self._watchlist_rows())

        if re.search(r"how does the market look|market overview|"
                     r"how'?s the market", low):
            sections = []
            for wsym in (wl or ["SOL-USDT"])[:6]:
                snap = analytics.get_market_snapshot(wsym, lookback_min=60,
                                                     agg_interval_min=3,
                                                     indicators=("EMA9", "EMA20"))
                sections.append(nlg.market_snapshot_summary(wsym, snap, 60, 3))
            return "\n\n".join(sections)

        return None

    # ---------------- condition watcher ----------------
    def watch_conditions(self, stop_event):
        while not stop_event.is_set():
            try:
                for a in db.list_automations(status="ACTIVE"):
                    fired = core.fire_condition_if_triggered(a)
                    if fired and fired.get("expired"):
                        for cid in (config.TELEGRAM_ALLOWED_USER_IDS or []):
                            self.send(cid, fired["message"])
                        continue
                    if fired:
                        for cid in (config.TELEGRAM_ALLOWED_USER_IDS or []):
                            self.send(cid, fired["message"])
                            s = self.sessions.setdefault(
                                cid, {"context": {}, "pending": None,
                                      "history": []})
                            s["pending"] = {"kind": "TRADE_CONFIRM",
                                            "trade_id":
                                            fired["proposal_trade_id"]}
                        break
                for act in core.evaluate_all_positions():
                    if act.get("action") in ("exit_all", "partial_exit",
                                             "breakeven"):
                        for cid in (config.TELEGRAM_ALLOWED_USER_IDS or []):
                            self.send(cid, (
                                f"POSITION UPDATE - {act.get('symbol', '')}: "
                                f"{act['action'].replace('_', ' ')}"
                                f"{(' (' + act['reason'] + ')') if act.get('reason') else ''}."
                                " Mode " + db.get_mode() + "."))
            except Exception as e:                                # noqa: BLE001
                print(f"[watcher] {e}", flush=True)
            stop_event.wait(15)


def run_bot(stop_event):
    if not config.TELEGRAM_BOT_TOKEN:
        print("[bot] TELEGRAM_BOT_TOKEN missing - Telegram disabled", flush=True)
        stop_event.wait(3600)
        return
    b = Bot()
    print("[bot] polling started", flush=True)
    while not stop_event.is_set():
        try:
            b.poll()
        except Exception as e:                                    # noqa: BLE001
            print(f"[bot] poll error {str(e)[:140]}", flush=True)
            time.sleep(5)
