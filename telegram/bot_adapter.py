import threading
import time
from typing import Any

import requests
import config
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
            # If no user IDs configured, reject all by default for safety
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
            # Silent reject or generic rejection without exposing system details
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
        else:
            self.send_message(
                chat_id,
                "❓ Unknown command. Type /status for system overview."
            )

    # =====================================================
    # COMMAND HANDLERS
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
            f"• *Scanner Failures*: `{status_info['scanner_failures']}`\n"
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
