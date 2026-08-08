import threading
import time
from typing import Any

import requests
import config
from core.settings import TradingSettings
from utils.logger import logger


class TelegramAdapter:
    """
    Production-safe Telegram interface adapter for Ophelia.

    This adapter acts strictly as an interface layer.
    It NEVER instantiates trading clients, brokers, or strategies directly.
    All operations are delegated through thread-safe methods on TradingEngine.
    """

    def __init__(self, engine: Any):
        self.engine = engine
        self.token = getattr(config, "TELEGRAM_TOKEN", "")
        self.allowed_user_ids = set(
            getattr(config, "TELEGRAM_ALLOWED_USER_IDS", [])
        )
        self.chat_id = getattr(config, "TELEGRAM_CHAT_ID", "")
        self.base_url = f"https://api.telegram.org/bot{self.token}"

        self._running = False
        self._thread = None
        self._last_update_id = 0
        self._pending_confirmations = {}
        self._lock = threading.Lock()

        # Register event notification listener if engine supports it
        if hasattr(self.engine, "add_listener"):
            self.engine.add_listener(self.handle_engine_event)

    def is_authorized(self, user_id: int | None) -> bool:
        if user_id is None:
            return False
        if not self.allowed_user_ids:
            return False
        return int(user_id) in self.allowed_user_ids

    def send_message(self, chat_id: int | str, text: str) -> bool:
        if not self.token or not chat_id:
            return False
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }
        try:
            resp = requests.post(url, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Telegram send_message failed: {e}")
            return False

    def notify(self, text: str) -> None:
        try:
            if self.chat_id:
                self.send_message(self.chat_id, text)
            # Also notify allowed users
            for uid in self.allowed_user_ids:
                if str(uid) != str(self.chat_id):
                    self.send_message(uid, text)
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}")

    def handle_engine_event(self, event_type: str, details: dict) -> None:
        if event_type == "POSITION_OPENED":
            msg = (
                f"🟢 *POSITION OPENED*\n"
                f"Symbol: `{details.get('symbol')}`\n"
                f"Side: `{details.get('side')}`\n"
                f"Entry Price: `{details.get('price')}`"
            )
            self.notify(msg)
        elif event_type == "POSITION_CLOSED":
            msg = (
                f"🔴 *POSITION CLOSED*\n"
                f"Symbol: `{details.get('symbol')}`\n"
                f"Status: `{details.get('status')}`\n"
                f"Exit Price: `{details.get('price')}`\n"
                f"PnL: `{details.get('pnl_percent')}%`"
            )
            self.notify(msg)
        elif event_type == "PROTECTION_ONLY":
            msg = (
                f"⚠️ *PROTECTION ONLY MODE ACTIVATED*\n"
                f"Reason: {details.get('reason', 'Safety condition triggered')}"
            )
            self.notify(msg)

    def start(self) -> None:
        if not self.token:
            logger.warning("Telegram token missing. TelegramAdapter disabled.")
            return
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._poll_loop,
            name="TelegramAdapterThread",
            daemon=True,
        )
        self._thread.start()
        logger.info("TelegramAdapter started in background thread.")

    def stop(self) -> None:
        self._running = False

    def _poll_loop(self) -> None:
        while self._running:
            try:
                updates = self._get_updates()
                for update in updates:
                    self._process_update(update)
            except Exception as e:
                logger.error(f"Telegram polling error: {e}")
                time.sleep(5)
            time.sleep(1)

    def _get_updates(self) -> list:
        url = f"{self.base_url}/getUpdates"
        params = {
            "offset": self._last_update_id + 1,
            "timeout": 5,
        }
        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    return data.get("result", [])
        except Exception:
            pass
        return []

    def _process_update(self, update: dict) -> None:
        update_id = update.get("update_id", 0)
        if update_id > self._last_update_id:
            self._last_update_id = update_id

        message = update.get("message") or update.get("edited_message")
        if not message:
            return

        user = message.get("from", {})
        user_id = user.get("id")
        chat_id = message.get("chat", {}).get("id")
        text = (message.get("text") or "").strip()

        if not self.is_authorized(user_id):
            logger.warning(
                f"Unauthorized Telegram access attempt from user_id={user_id}"
            )
            self.send_message(
                chat_id,
                "🚫 *Access Denied*: Unauthorized User ID."
            )
            return

        if text.startswith("/"):
            self._dispatch_command(chat_id, user_id, text)

    def _dispatch_command(self, chat_id: int, user_id: int, text: str) -> None:
        parts = text.split()
        cmd = parts[0].lower().split("@")[0]
        args = parts[1:]

        if cmd == "/status":
            self._cmd_status(chat_id)
        elif cmd == "/health":
            self._cmd_health(chat_id)
        elif cmd == "/mode":
            self._cmd_mode(chat_id)
        elif cmd == "/balance":
            self._cmd_balance(chat_id)
        elif cmd == "/positions":
            self._cmd_positions(chat_id)
        elif cmd == "/pnl":
            self._cmd_pnl(chat_id)
        elif cmd == "/orders":
            self._cmd_orders(chat_id)
        elif cmd == "/trades":
            self._cmd_trades(chat_id)
        elif cmd == "/start":
            self._cmd_start(chat_id)
        elif cmd == "/stop":
            self._cmd_stop(chat_id)
        elif cmd == "/pause":
            self._cmd_pause(chat_id)
        elif cmd == "/resume":
            self._cmd_resume(chat_id)
        elif cmd == "/close":
            self._cmd_close(chat_id, user_id, args)
        elif cmd == "/confirm_close":
            self._cmd_confirm_close(chat_id, user_id, args)
        elif cmd == "/emergency":
            self._cmd_emergency(chat_id, user_id)
        elif cmd == "/confirm_emergency":
            self._cmd_confirm_emergency(chat_id, user_id)
        elif cmd == "/settings":
            self._cmd_settings(chat_id)
        elif cmd == "/symbols":
            self._cmd_symbols(chat_id)
        elif cmd == "/set_ema":
            self._cmd_set_ema(chat_id, user_id, args)
        elif cmd == "/set_timeframe":
            self._cmd_set_timeframe(chat_id, user_id, args)
        elif cmd == "/set_margin":
            self._cmd_set_margin(chat_id, user_id, args)
        elif cmd == "/set_leverage":
            self._cmd_set_leverage(chat_id, user_id, args)
        elif cmd == "/add_symbol":
            self._cmd_add_symbol(chat_id, user_id, args)
        elif cmd == "/remove_symbol":
            self._cmd_remove_symbol(chat_id, user_id, args)
        elif cmd == "/set_trade_limit":
            self._cmd_set_trade_limit(chat_id, user_id, args)
        elif cmd == "/risk_settings":
            self._cmd_risk_settings(chat_id, args)
        elif cmd == "/set_sl":
            self._cmd_set_sl(chat_id, user_id, args)
        elif cmd == "/set_tp":
            self._cmd_set_tp(chat_id, user_id, args)
        elif cmd == "/set_trailing":
            self._cmd_set_trailing(chat_id, user_id, args)
        elif cmd == "/set_trailing_activation":
            self._cmd_set_trailing_activation(chat_id, user_id, args)
        elif cmd == "/set_exit_plan":
            self._cmd_set_exit_plan(chat_id, user_id, args)
        elif cmd == "/confirm_settings":
            self._cmd_confirm_settings(chat_id, user_id)
        else:
            self.send_message(
                chat_id,
                "❓ Unknown command. Type /status or /settings for system overview."
            )

    # =====================================================
    # STATUS & READ-ONLY COMMAND HANDLERS
    # =====================================================

    def _cmd_mode(self, chat_id: int) -> None:
        mode = "LIVE" if self.engine.live_trading else "PAPER"
        self.send_message(chat_id, f"📌 *Execution Mode*: `{mode}`")

    def _cmd_status(self, chat_id: int) -> None:
        status_info = self.engine.get_status_summary()
        msg = (
            f"📊 *OPHELIA STATUS REPORT*\n"
            f"• *Mode*: `{status_info['mode']}`\n"
            f"• *Engine State*: `{status_info['engine_state']}`\n"
            f"• *Protection Only*: `{status_info['protection_only']}`\n"
            f"• *Open Positions*: `{status_info['open_positions_count']}`\n"
            f"• *Protected Symbols*: `{', '.join(status_info['protected_symbols']) or 'None'}`\n"
            f"• *Active Symbols*: `{', '.join(status_info['watchlist'])}`\n"
            f"• *EMA Fast/Slow*: `{status_info['ema_fast']} / {status_info['ema_slow']}`\n"
            f"• *Timeframe*: `{status_info['timeframe']}`\n"
            f"• *Margin*: `{status_info['margin_usdt']} USDT` | *Leverage*: `{status_info['leverage']}x`\n"
            f"• *Trade Limit*: `{status_info['trade_limit']}` (Used: `{status_info['trades_used']}`, Rem: `{status_info['trades_remaining']}`)\n"
            f"• *Stop-Loss*: `{status_info['sl_mode']}` (`{status_info['sl_value']}`)\n"
            f"• *Take-Profit*: `{status_info['tp_mode']}` (`{status_info['tp_value']}`)\n"
            f"• *Trailing*: Activation `{status_info['trailing_activation']}%` | Buffer `{status_info['trailing_buffer']}%`\n"
            f"• *Pending Intents*: `{status_info['pending_intents_count']}`"
        )
        self.send_message(chat_id, msg)

    def _cmd_health(self, chat_id: int) -> None:
        health = self.engine.get_health_summary()
        msg = (
            f"🏥 *SYSTEM HEALTH*\n"
            f"• *Status*: `{health['status']}`\n"
            f"• *Engine State*: `{health['engine_state']}`\n"
            f"• *Scanner Health*: `{health['scanner_health']}`\n"
            f"• *Price Freshness*: `{health['price_freshness']}`"
        )
        self.send_message(chat_id, msg)

    def _cmd_balance(self, chat_id: int) -> None:
        balance_info = self.engine.get_balance_summary()
        self.send_message(chat_id, f"💰 *ACCOUNT BALANCE*\n{balance_info}")

    def _cmd_positions(self, chat_id: int) -> None:
        positions = self.engine.get_positions_summary()
        if not positions:
            self.send_message(chat_id, "ℹ️ *No open positions.*")
            return

        lines = ["📈 *CURRENT POSITIONS*"]
        for pos in positions:
            lines.append(
                f"• *{pos['symbol']}* ({pos['side']})\n"
                f"  Qty: `{pos['quantity']}` | Leverage: `{pos['leverage']}x`\n"
                f"  Entry: `${pos['entry_price']}` | Current: `${pos['current_price']}`\n"
                f"  Unrealized PnL: `${pos['unrealized_pnl']}`\n"
                f"  Stop Price: `${pos['stop_price'] or 'None'}`"
            )
        self.send_message(chat_id, "\n\n".join(lines))

    def _cmd_pnl(self, chat_id: int) -> None:
        pnl_info = self.engine.get_pnl_summary()
        self.send_message(chat_id, f"💵 *PNL SUMMARY*\n{pnl_info}")

    def _cmd_orders(self, chat_id: int) -> None:
        orders_info = self.engine.get_orders_summary()
        self.send_message(chat_id, f"📋 *ACTIVE ORDERS / INTENTS*\n{orders_info}")

    def _cmd_trades(self, chat_id: int) -> None:
        trades = self.engine.get_recent_trades(limit=5)
        if not trades:
            self.send_message(chat_id, "ℹ️ *No recent trades logged.*")
            return
        lines = ["📜 *RECENT TRADES*"]
        for t in trades:
            lines.append(
                f"• *{t['symbol']}* | {t['side']} | Status: `{t['status']}`\n"
                f"  Entry: `${t['entry_price']}` | Exit: `${t['exit_price']}`\n"
                f"  PnL: `{t['pnl_percent']}%` (${t['pnl_amount']})"
            )
        self.send_message(chat_id, "\n\n".join(lines))

    # =====================================================
    # ENGINE STATE CONTROL COMMAND HANDLERS
    # =====================================================

    def _cmd_start(self, chat_id: int) -> None:
        success, msg = self.engine.start_trading()
        prefix = "✅" if success else "⚠️"
        self.send_message(chat_id, f"{prefix} {msg}")

    def _cmd_stop(self, chat_id: int) -> None:
        success, msg = self.engine.stop_trading()
        self.send_message(chat_id, f"🛑 {msg}")

    def _cmd_pause(self, chat_id: int) -> None:
        success, msg = self.engine.pause_trading()
        self.send_message(chat_id, f"⏸️ {msg}")

    def _cmd_resume(self, chat_id: int) -> None:
        success, msg = self.engine.resume_trading()
        prefix = "▶️" if success else "⚠️"
        self.send_message(chat_id, f"{prefix} {msg}")

    # =====================================================
    # POSITION COMMAND HANDLERS
    # =====================================================

    def _cmd_close(self, chat_id: int, user_id: int, args: list) -> None:
        if not args:
            self.send_message(chat_id, "⚠️ Usage: `/close <symbol>` (e.g. `/close SOL-USDT`)")
            return
        symbol = args[0].upper()
        position = self.engine.get_position(symbol)
        if position is None:
            self.send_message(chat_id, f"❌ No active position found for `{symbol}`.")
            return

        with self._lock:
            key = (user_id, "close", symbol)
            self._pending_confirmations[key] = {
                "expires_at": time.time() + 60,
                "symbol": symbol,
                "side": position["side"],
                "quantity": position["quantity"],
            }

        msg = (
            f"⚠️ *CLOSE POSITION CONFIRMATION REQUIRED*\n"
            f"Symbol: `{symbol}`\n"
            f"Side: `{position['side']}`\n"
            f"Quantity: `{position['quantity']}`\n\n"
            f"Reply with `/confirm_close {symbol}` within 60 seconds to proceed."
        )
        self.send_message(chat_id, msg)

    def _cmd_confirm_close(self, chat_id: int, user_id: int, args: list) -> None:
        if not args:
            self.send_message(chat_id, "⚠️ Usage: `/confirm_close <symbol>`")
            return
        symbol = args[0].upper()
        key = (user_id, "close", symbol)

        with self._lock:
            intent = self._pending_confirmations.pop(key, None)

        if not intent:
            self.send_message(chat_id, "❌ Confirmation expired or missing.")
            return

        if time.time() > intent["expires_at"]:
            self.send_message(chat_id, "❌ Confirmation has expired.")
            return

        success, msg = self.engine.close_position_safe(symbol)
        prefix = "✅" if success else "❌"
        self.send_message(chat_id, f"{prefix} {msg}")

    def _cmd_emergency(self, chat_id: int, user_id: int) -> None:
        with self._lock:
            key = (user_id, "emergency", "ALL")
            self._pending_confirmations[key] = {
                "expires_at": time.time() + 30,
            }

        msg = (
            f"🚨 *EMERGENCY CLOSE CONFIRMATION REQUIRED*\n"
            f"This will close ALL open positions immediately!\n\n"
            f"Reply with `/confirm_emergency` within 30 seconds to proceed."
        )
        self.send_message(chat_id, msg)

    def _cmd_confirm_emergency(self, chat_id: int, user_id: int) -> None:
        key = (user_id, "emergency", "ALL")
        with self._lock:
            intent = self._pending_confirmations.pop(key, None)

        if not intent:
            self.send_message(chat_id, "❌ Emergency confirmation expired or missing.")
            return

        if time.time() > intent["expires_at"]:
            self.send_message(chat_id, "❌ Emergency confirmation expired.")
            return

        success, msg = self.engine.emergency_close_safe()
        prefix = "🚨" if success else "❌"
        self.send_message(chat_id, f"{prefix} {msg}")

    # =====================================================
    # STRATEGY & RISK SETTINGS COMMAND HANDLERS
    # =====================================================

    def _cmd_settings(self, chat_id: int) -> None:
        s = self.engine.get_settings_summary()
        msg = (
            f"⚙️ *OPHELIA STRATEGY SETTINGS*\n\n"
            f"• *EMA Fast / Slow*: `{s['ema_fast']} / {s['ema_slow']}`\n"
            f"• *Timeframe*: `{s['timeframe']}`\n"
            f"• *Margin*: `{s['margin_usdt']} USDT` | *Leverage*: `{s['leverage']}x`\n"
            f"• *Symbols*: `{', '.join(s['symbols'])}`\n"
            f"• *Trade Limit*: `{s['trade_limit']}` (Used: `{s['trades_used']}`, Rem: `{s['trades_remaining']}`)\n"
            f"• *SL Mode*: `{s['sl_mode']}` (`{s['sl_value']}`)\n"
            f"• *TP Mode*: `{s['tp_mode']}` (`{s['tp_value']}`)\n"
            f"• *Trailing*: Activation `{s['trailing_activation']}%` | Buffer `{s['trailing_buffer']}%`\n"
            f"• *Engine State*: `{s['engine_state']}`\n\n"
            f"Use `/risk_settings` for detailed per-symbol risk management."
        )
        self.send_message(chat_id, msg)

    def _cmd_risk_settings(self, chat_id: int, args: list) -> None:
        symbol = args[0].upper().strip() if args else None
        r = self.engine.get_risk_settings_summary(symbol)

        exit_legs_str = ", ".join(
            f"{leg['pct']}% @ {'trailing' if leg['type']=='trailing' else str(leg.get('target_pct'))+'%'}"
            for leg in r["exit_plan"]
        )

        msg = (
            f"🛡️ *RISK MANAGEMENT CONFIGURATION ({r['symbol']})*\n\n"
            f"• *Stop-Loss (SL)*: Mode `{r['sl_mode']}` | Value `{r['sl_value']}`\n"
            f"• *Take-Profit (TP)*: Mode `{r['tp_mode']}` | Value `{r['tp_value']}`\n"
            f"• *Trailing Stop*: Activation `{r['trailing_activation']}%` | Buffer `{r['trailing_buffer']}%`\n"
            f"• *Exit Plan Legs*: `{exit_legs_str}`\n\n"
            f"*Available Commands:*\n"
            f"`/set_sl <percent|fixed> <val> [symbol]`\n"
            f"`/set_tp <percent|fixed> <val> [symbol]`\n"
            f"`/set_trailing <buffer_pct> [symbol]`\n"
            f"`/set_trailing_activation <activation_pct> [symbol]`\n"
            f"`/set_exit_plan <global|symbol> <leg1> <leg2> ...`"
        )
        self.send_message(chat_id, msg)

    def _cmd_symbols(self, chat_id: int) -> None:
        s = self.engine.get_settings_summary()
        supported = getattr(config, "SUPPORTED_SYMBOLS", ("BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT"))
        msg = (
            f"🔤 *CONFIGURED WATCHLIST*\n"
            f"• *Active Symbols*: `{', '.join(s['symbols'])}` \n\n"
            f"• *Supported Contracts*: `{', '.join(supported)}`\n\n"
            f"Use `/add_symbol <sym>` or `/remove_symbol <sym>` to modify."
        )
        self.send_message(chat_id, msg)

    def _request_settings_confirm(
        self,
        chat_id: int,
        user_id: int,
        method_name: str,
        args: tuple,
        desc: str,
        old_val: str,
        new_val: str,
    ) -> None:
        with self._lock:
            key = (user_id, "settings")
            self._pending_confirmations[key] = {
                "expires_at": time.time() + 60,
                "method_name": method_name,
                "args": args,
                "desc": desc,
            }
        msg = (
            f"⚙️ *SETTINGS CHANGE CONFIRMATION REQUIRED*\n\n"
            f"Setting: *{desc}*\n"
            f"Current: `{old_val}`\n"
            f"Requested: `{new_val}`\n\n"
            f"Reply with `/confirm_settings` within 60 seconds to apply."
        )
        self.send_message(chat_id, msg)

    def _cmd_set_ema(self, chat_id: int, user_id: int, args: list) -> None:
        if len(args) < 2:
            self.send_message(chat_id, "⚠️ Usage: `/set_ema <fast> <slow>` (e.g. `/set_ema 9 21`)")
            return
        try:
            fast = int(args[0])
            slow = int(args[1])
        except ValueError:
            self.send_message(chat_id, "❌ Error: EMA periods must be integers.")
            return

        valid, err = TradingSettings.validate_ema(fast, slow)
        if not valid:
            self.send_message(chat_id, f"❌ Validation Error: {err}")
            return

        s = self.engine.get_settings_summary()
        self._request_settings_confirm(
            chat_id=chat_id,
            user_id=user_id,
            method_name="update_ema_settings",
            args=(fast, slow),
            desc="EMA Fast / Slow",
            old_val=f"{s['ema_fast']} / {s['ema_slow']}",
            new_val=f"{fast} / {slow}",
        )

    def _cmd_set_timeframe(self, chat_id: int, user_id: int, args: list) -> None:
        if not args:
            self.send_message(chat_id, "⚠️ Usage: `/set_timeframe <tf>` (e.g. `/set_timeframe 5m`)")
            return
        tf = args[0].lower().strip()
        valid, err = TradingSettings.validate_timeframe(tf)
        if not valid:
            self.send_message(chat_id, f"❌ Validation Error: {err}")
            return

        s = self.engine.get_settings_summary()
        self._request_settings_confirm(
            chat_id=chat_id,
            user_id=user_id,
            method_name="update_timeframe",
            args=(tf,),
            desc="Strategy Timeframe",
            old_val=s["timeframe"],
            new_val=tf,
        )

    def _cmd_set_margin(self, chat_id: int, user_id: int, args: list) -> None:
        if not args:
            self.send_message(chat_id, "⚠️ Usage: `/set_margin <usdt>` (e.g. `/set_margin 15.0`)")
            return
        try:
            margin = float(args[0])
        except ValueError:
            self.send_message(chat_id, "❌ Error: Margin must be a numeric value.")
            return

        valid, err = TradingSettings.validate_margin(margin)
        if not valid:
            self.send_message(chat_id, f"❌ Validation Error: {err}")
            return

        s = self.engine.get_settings_summary()
        self._request_settings_confirm(
            chat_id=chat_id,
            user_id=user_id,
            method_name="update_margin",
            args=(margin,),
            desc="Trade Margin (USDT)",
            old_val=f"{s['margin_usdt']} USDT",
            new_val=f"{margin} USDT",
        )

    def _cmd_set_leverage(self, chat_id: int, user_id: int, args: list) -> None:
        if not args:
            self.send_message(chat_id, "⚠️ Usage: `/set_leverage <val>` (e.g. `/set_leverage 10`)")
            return
        try:
            leverage = int(args[0])
        except ValueError:
            self.send_message(chat_id, "❌ Error: Leverage must be an integer.")
            return

        valid, err = TradingSettings.validate_leverage(leverage)
        if not valid:
            self.send_message(chat_id, f"❌ Validation Error: {err}")
            return

        s = self.engine.get_settings_summary()
        self._request_settings_confirm(
            chat_id=chat_id,
            user_id=user_id,
            method_name="update_leverage",
            args=(leverage,),
            desc="Trade Leverage",
            old_val=f"{s['leverage']}x",
            new_val=f"{leverage}x",
        )

    def _cmd_add_symbol(self, chat_id: int, user_id: int, args: list) -> None:
        if not args:
            self.send_message(chat_id, "⚠️ Usage: `/add_symbol <sym>` (e.g. `/add_symbol BTC-USDT`)")
            return
        sym = args[0].upper().strip()
        valid, err = TradingSettings.validate_symbol(sym)
        if not valid:
            self.send_message(chat_id, f"❌ Validation Error: {err}")
            return

        s = self.engine.get_settings_summary()
        if sym in s["symbols"]:
            self.send_message(chat_id, f"ℹ️ Symbol `{sym}` is already in the watchlist.")
            return

        self._request_settings_confirm(
            chat_id=chat_id,
            user_id=user_id,
            method_name="add_symbol",
            args=(sym,),
            desc="Add Symbol to Watchlist",
            old_val=", ".join(s["symbols"]),
            new_val=f"{', '.join(s['symbols'])}, {sym}",
        )

    def _cmd_remove_symbol(self, chat_id: int, user_id: int, args: list) -> None:
        if not args:
            self.send_message(chat_id, "⚠️ Usage: `/remove_symbol <sym>` (e.g. `/remove_symbol XRP-USDT`)")
            return
        sym = args[0].upper().strip()
        s = self.engine.get_settings_summary()
        if sym not in s["symbols"]:
            self.send_message(chat_id, f"❌ Error: Symbol `{sym}` is not in the watchlist.")
            return

        remaining = [x for x in s["symbols"] if x != sym]
        self._request_settings_confirm(
            chat_id=chat_id,
            user_id=user_id,
            method_name="remove_symbol",
            args=(sym,),
            desc="Remove Symbol from Watchlist",
            old_val=", ".join(s["symbols"]),
            new_val=", ".join(remaining) or "None",
        )

    def _cmd_set_trade_limit(self, chat_id: int, user_id: int, args: list) -> None:
        if not args:
            self.send_message(
                chat_id,
                "⚠️ Usage: `/set_trade_limit <number>` or `/set_trade_limit unlimited`"
            )
            return
        raw_val = args[0].lower().strip()
        limit_val = None if raw_val in ("unlimited", "none", "0") else raw_val

        valid, err = TradingSettings.validate_trade_limit(limit_val)
        if not valid:
            self.send_message(chat_id, f"❌ Validation Error: {err}")
            return

        s = self.engine.get_settings_summary()
        new_val_str = "unlimited" if limit_val is None else str(limit_val)
        self._request_settings_confirm(
            chat_id=chat_id,
            user_id=user_id,
            method_name="set_trade_limit",
            args=(limit_val,),
            desc="Session Automated Trade Limit",
            old_val=str(s["trade_limit"]),
            new_val=new_val_str,
        )

    def _cmd_set_sl(self, chat_id: int, user_id: int, args: list) -> None:
        if len(args) < 2:
            self.send_message(chat_id, "⚠️ Usage: `/set_sl <percent|fixed> <val> [symbol]`")
            return
        mode = args[0]
        try:
            val = float(args[1])
        except ValueError:
            self.send_message(chat_id, "❌ Error: SL value must be numeric.")
            return
        symbol = args[2].upper().strip() if len(args) >= 3 else None

        valid, err = TradingSettings.validate_sl(mode, val)
        if not valid:
            self.send_message(chat_id, f"❌ Validation Error: {err}")
            return

        r = self.engine.get_risk_settings_summary(symbol)
        self._request_settings_confirm(
            chat_id=chat_id,
            user_id=user_id,
            method_name="update_sl_setting",
            args=(mode, val, symbol),
            desc=f"Stop-Loss ({symbol or 'Global'})",
            old_val=f"{r['sl_mode']} ({r['sl_value']})",
            new_val=f"{mode.upper()} ({val})",
        )

    def _cmd_set_tp(self, chat_id: int, user_id: int, args: list) -> None:
        if len(args) < 2:
            self.send_message(chat_id, "⚠️ Usage: `/set_tp <percent|fixed> <val> [symbol]`")
            return
        mode = args[0]
        try:
            val = float(args[1])
        except ValueError:
            self.send_message(chat_id, "❌ Error: TP value must be numeric.")
            return
        symbol = args[2].upper().strip() if len(args) >= 3 else None

        valid, err = TradingSettings.validate_tp(mode, val)
        if not valid:
            self.send_message(chat_id, f"❌ Validation Error: {err}")
            return

        r = self.engine.get_risk_settings_summary(symbol)
        self._request_settings_confirm(
            chat_id=chat_id,
            user_id=user_id,
            method_name="update_tp_setting",
            args=(mode, val, symbol),
            desc=f"Take-Profit ({symbol or 'Global'})",
            old_val=f"{r['tp_mode']} ({r['tp_value']})",
            new_val=f"{mode.upper()} ({val})",
        )

    def _cmd_set_trailing(self, chat_id: int, user_id: int, args: list) -> None:
        if not args:
            self.send_message(chat_id, "⚠️ Usage: `/set_trailing <buffer_pct> [symbol]`")
            return
        try:
            buf = float(args[0])
        except ValueError:
            self.send_message(chat_id, "❌ Error: Trailing buffer must be numeric.")
            return
        symbol = args[1].upper().strip() if len(args) >= 2 else None

        r = self.engine.get_risk_settings_summary(symbol)
        valid, err = TradingSettings.validate_trailing(buf, r["trailing_activation"])
        if not valid:
            self.send_message(chat_id, f"❌ Validation Error: {err}")
            return

        self._request_settings_confirm(
            chat_id=chat_id,
            user_id=user_id,
            method_name="update_trailing_setting",
            args=(buf, symbol),
            desc=f"Trailing Buffer ({symbol or 'Global'})",
            old_val=f"{r['trailing_buffer']}%",
            new_val=f"{buf}%",
        )

    def _cmd_set_trailing_activation(self, chat_id: int, user_id: int, args: list) -> None:
        if not args:
            self.send_message(chat_id, "⚠️ Usage: `/set_trailing_activation <activation_pct> [symbol]`")
            return
        try:
            act = float(args[0])
        except ValueError:
            self.send_message(chat_id, "❌ Error: Trailing activation must be numeric.")
            return
        symbol = args[1].upper().strip() if len(args) >= 2 else None

        r = self.engine.get_risk_settings_summary(symbol)
        valid, err = TradingSettings.validate_trailing(r["trailing_buffer"], act)
        if not valid:
            self.send_message(chat_id, f"❌ Validation Error: {err}")
            return

        self._request_settings_confirm(
            chat_id=chat_id,
            user_id=user_id,
            method_name="update_trailing_activation_setting",
            args=(act, symbol),
            desc=f"Trailing Activation ({symbol or 'Global'})",
            old_val=f"{r['trailing_activation']}%",
            new_val=f"{act}%",
        )

    def _cmd_set_exit_plan(self, chat_id: int, user_id: int, args: list) -> None:
        if len(args) < 2:
            self.send_message(
                chat_id,
                "⚠️ Usage: `/set_exit_plan <global|symbol> <leg1> <leg2> ...` (e.g. `/set_exit_plan XRP-USDT 25@1.0 25@2.0 50@trailing`)"
            )
            return

        target = args[0].upper().strip()
        symbol = None if target == "GLOBAL" else target
        tokens = args[1:]

        valid, err, legs = TradingSettings.parse_exit_plan(tokens)
        if not valid:
            self.send_message(chat_id, f"❌ Validation Error: {err}")
            return

        r = self.engine.get_risk_settings_summary(symbol)
        old_str = ", ".join(f"{leg['pct']}%" for leg in r["exit_plan"])
        new_str = ", ".join(tokens)

        self._request_settings_confirm(
            chat_id=chat_id,
            user_id=user_id,
            method_name="update_exit_plan_setting",
            args=(tokens, symbol),
            desc=f"Exit Plan Legs ({symbol or 'Global'})",
            old_val=old_str,
            new_val=new_str,
        )

    def _cmd_confirm_settings(self, chat_id: int, user_id: int) -> None:
        key = (user_id, "settings")
        with self._lock:
            intent = self._pending_confirmations.pop(key, None)

        if not intent:
            self.send_message(chat_id, "❌ Settings confirmation expired or missing.")
            return

        if time.time() > intent["expires_at"]:
            self.send_message(chat_id, "❌ Settings confirmation has expired.")
            return

        method_name = intent["method_name"]
        args = intent["args"]

        method = getattr(self.engine, method_name, None)
        if not method:
            self.send_message(chat_id, "❌ Error: Engine method not found.")
            return

        success, msg = method(*args)
        prefix = "✅" if success else "❌"
        self.send_message(chat_id, f"{prefix} {msg}")
