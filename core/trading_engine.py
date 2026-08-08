import threading
import time
from typing import Any, Callable

import config
from brokers.bingx_broker import BingXBroker
from brokers.paper_broker import PaperBroker
from core.candle_scheduler import CandleScheduler
from core.enums import EngineState
from core.position_manager import PositionManager
from core.scanner import Scanner
from exchange.bingx_client import BingXClient
from exchange.public_bingx_client import PublicBingXClient
from paper.trade_journal import TradeJournal
from portfolio.position_manager import PositionManager as LivePositionManager
from risk.risk_manager import RiskManager
from utils.logger import logger


class TradingEngine:

    def __init__(self):

        logger.info("=" * 70)
        logger.info("Initializing Ophelia Trading Platform")
        logger.info("=" * 70)

        self._lock = threading.RLock()
        self._listeners: list[Callable[[str, dict], None]] = []

        self.live_trading = bool(getattr(config, "LIVE_TRADING", False))
        self.engine_state = EngineState.NORMAL
        self.protection_only_mode = False
        self.protection_degraded = False
        self.price_failure_counts = {}
        self.last_fresh_price_ts = {}
        self.max_price_staleness_seconds = int(
            getattr(
                config,
                "MAX_PRICE_STALENESS_SECONDS",
                max(30, config.CHECK_INTERVAL * 6),
            )
        )

        if self.live_trading:
            self.client = BingXClient()
            market_client = self.client
        else:
            market_client = PublicBingXClient()

        # Scanner
        self.scanner = Scanner(market_client)
        self.watchlist = list(
            getattr(
                config,
                "WATCHLIST",
                config.SUPPORTED_SYMBOLS,
            )
        )

        self.trade_journal = TradeJournal()

        if self.live_trading:
            self.position_manager = LivePositionManager(self.client)
            self.broker = BingXBroker(
                self.client,
                self.position_manager,
                self.trade_journal,
            )
            logger.warning("Execution mode: LIVE")
        else:
            self.position_manager = PositionManager()
            self.broker = PaperBroker(
                self.position_manager,
                self.trade_journal,
            )
            logger.info("Execution mode: PAPER")

        self.risk_manager = RiskManager(self.position_manager)

        # Candle Scheduler
        self.scheduler = CandleScheduler(5)

        logger.info("Initialization Complete")
        logger.info(f"Watching {len(self.watchlist)} Coins")
        logger.info("Trading Engine Ready")

        # Start Telegram Adapter if enabled
        if getattr(config, "ENABLE_TELEGRAM", False) and getattr(config, "TELEGRAM_TOKEN", ""):
            try:
                from telegram.bot_adapter import TelegramAdapter
                self.telegram_adapter = TelegramAdapter(self)
                self.telegram_adapter.start()
            except Exception as e:
                logger.error(f"Failed to initialize TelegramAdapter: {e}")

    # =====================================================
    # EVENT LISTENER REGISTRATION & NOTIFICATIONS
    # =====================================================

    def add_listener(self, callback: Callable[[str, dict], None]) -> None:
        with self._lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def notify_listeners(self, event_type: str, details: dict) -> None:
        with self._lock:
            listeners = list(self._listeners)
        for listener in listeners:
            try:
                listener(event_type, details)
            except Exception as e:
                logger.error(f"Error in event listener callback: {e}")

    # =====================================================
    # MARKET PROCESSING LOOP
    # =====================================================

    def process_market(self):

        logger.info("=" * 70)
        logger.info("Scanning Market...")

        try:

            signals = self.scanner.scan(self.watchlist)
            if self.scanner.last_failed_symbols:
                failed = ", ".join(self.scanner.last_failed_symbols)
                logger.error(f"Scanner failed symbols this cycle: {failed}")

            logger.info(f"Signals Received: {len(signals)}")

            now = int(time.time())
            stale_symbols = []
            protection_price_failures = []
            protection_symbols = self.broker.get_protected_symbols(self.watchlist)
            for symbol in protection_symbols:
                try:
                    price = self.scanner.market.get_current_price(symbol)
                    self.last_fresh_price_ts[symbol] = now
                    self.price_failure_counts[symbol] = 0
                    self.broker.process_signal(
                        {
                            "symbol": symbol,
                            "signal": "HOLD",
                            "price": price,
                            "timestamp": now,
                        },
                        self.risk_manager,
                    )
                except Exception as e:
                    logger.error(
                        f"Protection update failed for {symbol}: {e}"
                    )
                    protection_price_failures.append(symbol)
                    self.price_failure_counts[symbol] = (
                        self.price_failure_counts.get(symbol, 0) + 1
                    )
                    try:
                        position = self.position_manager.get_position(symbol)
                        if position is None:
                            continue
                        if self.live_trading:
                            fallback_price = float(position.mark_price)
                        else:
                            fallback_price = float(position.current_price)
                        self.broker.process_signal(
                            {
                                "symbol": symbol,
                                "signal": "HOLD",
                                "price": fallback_price,
                                "timestamp": now,
                            },
                            self.risk_manager,
                        )
                    except Exception as fallback_error:
                        logger.error(
                            f"Fallback protection failed for {symbol}: "
                            f"{fallback_error}"
                        )

                last_fresh = self.last_fresh_price_ts.get(symbol)
                if last_fresh is None or (now - last_fresh) > self.max_price_staleness_seconds:
                    stale_symbols.append(symbol)

            repeated_scanner_failures = [
                symbol
                for symbol, count in self.scanner.failure_counts.items()
                if count >= 3
            ]
            should_enter_protection_only = (
                bool(repeated_scanner_failures)
                or bool(stale_symbols)
                or bool(protection_price_failures)
            )

            with self._lock:
                if should_enter_protection_only and not self.protection_only_mode:
                    self.protection_only_mode = True
                    self.protection_degraded = True
                    self.engine_state = EngineState.PROTECTION_ONLY
                    logger.error(
                        "Entering PROTECTION_ONLY mode. "
                        "New entries are blocked."
                    )
                    self.notify_listeners(
                        "PROTECTION_ONLY",
                        {"reason": "Scanner/price staleness threshold exceeded"}
                    )

                has_fresh_scan = len(signals) > 0 and not self.scanner.last_failed_symbols
                has_fresh_prices = not stale_symbols and not protection_price_failures
                if (
                    self.protection_only_mode
                    and has_fresh_scan
                    and has_fresh_prices
                    and self.engine_state == EngineState.PROTECTION_ONLY
                ):
                    self.protection_only_mode = False
                    self.protection_degraded = False
                    self.engine_state = EngineState.NORMAL
                    logger.info(
                        "Exiting PROTECTION_ONLY mode. "
                        "Normal trading resumed."
                    )

                can_enter_new_trades = (
                    not self.protection_only_mode
                    and self.engine_state == EngineState.NORMAL
                )

            if can_enter_new_trades:
                for signal in signals:

                    symbol = signal.get("symbol", "UNKNOWN")
                    signal_type = signal.get("signal", "HOLD")

                    logger.info(
                        f"{symbol} | {signal_type}"
                    )

                    self.broker.process_signal(
                        signal,
                        self.risk_manager
                    )
            else:
                logger.warning(
                    f"New signal entries blocked. "
                    f"Engine State: {self.engine_state.value}, "
                    f"Protection Only: {self.protection_only_mode}"
                )

            logger.info(
                f"Open Positions: {len(self.broker.get_open_positions())}"
            )

            logger.info("Market Scan Complete")

        except Exception as e:

            logger.error(f"Market Processing Error: {e}")

    def run(self):

        logger.info("Trading Engine Started")

        while True:

            try:

                # Wait until the next candle closes
                self.scheduler.wait_for_next_candle()

                # Process one complete market cycle
                self.process_market()

            except KeyboardInterrupt:

                logger.warning("Trading Engine Stopped By User")
                if self.live_trading:
                    logger.warning(
                        "Emergency close path: "
                        "call broker.emergency_close_all() if needed."
                    )

                break

            except Exception as e:

                logger.error(f"Trading Engine Error: {e}")

    # =====================================================
    # SAFE ENGINE CONTROL APIS FOR TELEGRAM ADAPTER
    # =====================================================

    def pause_trading(self) -> tuple[bool, str]:
        with self._lock:
            if self.protection_only_mode or self.engine_state == EngineState.PROTECTION_ONLY:
                return False, "Cannot set PAUSED: system is in PROTECTION_ONLY safety state."
            self.engine_state = EngineState.PAUSED
            logger.info("Engine state changed to PAUSED via Telegram.")
            return True, "Trading engine PAUSED. New entries blocked; protection remains active."

    def stop_trading(self) -> tuple[bool, str]:
        with self._lock:
            if self.protection_only_mode or self.engine_state == EngineState.PROTECTION_ONLY:
                return False, "Cannot set STOPPED: system is in PROTECTION_ONLY safety state."
            self.engine_state = EngineState.STOPPED
            logger.info("Engine state changed to STOPPED via Telegram.")
            return True, "Trading engine STOPPED. New entries blocked; protection remains active."

    def start_trading(self) -> tuple[bool, str]:
        with self._lock:
            if self.protection_degraded or self.protection_only_mode:
                return False, "Cannot START: system is in PROTECTION_ONLY safety state due to active errors."
            self.engine_state = EngineState.NORMAL
            logger.info("Engine state changed to NORMAL via Telegram / start.")
            return True, "Trading engine set to NORMAL. New entries enabled."

    def resume_trading(self) -> tuple[bool, str]:
        return self.start_trading()

    # =====================================================
    # SAFE POSITION ACTIONS FOR TELEGRAM ADAPTER
    # =====================================================

    def get_position(self, symbol: str) -> dict | None:
        with self._lock:
            pos = self.position_manager.get_position(symbol)
            if pos is None:
                return None

            if self.live_trading:
                return {
                    "symbol": pos.symbol,
                    "side": pos.side.value if hasattr(pos.side, "value") else str(pos.side),
                    "quantity": pos.quantity,
                    "entry_price": pos.entry_price,
                    "current_price": getattr(pos, "mark_price", pos.entry_price),
                    "unrealized_pnl": getattr(pos, "unrealized_pnl", 0.0),
                    "leverage": pos.leverage,
                    "stop_price": self.broker.stop_prices.get(symbol),
                }
            else:
                return {
                    "symbol": pos.symbol,
                    "side": pos.side,
                    "quantity": pos.quantity,
                    "entry_price": pos.entry_price,
                    "current_price": pos.current_price,
                    "unrealized_pnl": round(
                        (pos.current_price - pos.entry_price) * pos.quantity
                        if pos.side == "LONG"
                        else (pos.entry_price - pos.current_price) * pos.quantity,
                        4
                    ),
                    "leverage": pos.leverage,
                    "stop_price": self.broker.stop_prices.get(symbol),
                }

    def close_position_safe(self, symbol: str) -> tuple[bool, str]:
        with self._lock:
            pos = self.position_manager.get_position(symbol)
            if pos is None:
                return False, f"Reconciliation failed: Position for {symbol} not found on exchange/portfolio."

            current_side = pos.side.value if hasattr(pos.side, "value") else str(pos.side)

            try:
                if self.live_trading:
                    self.broker._close_position(symbol, current_side, status="MANUAL_CLOSE")
                else:
                    self.broker._close_and_record_trade(
                        symbol=symbol,
                        exit_price=pos.current_price,
                        exit_time=int(time.time()),
                        status="MANUAL_CLOSE",
                    )
                logger.info(f"Position {symbol} closed safely via Telegram request.")
                self.notify_listeners(
                    "POSITION_CLOSED",
                    {
                        "symbol": symbol,
                        "status": "MANUAL_CLOSE",
                        "price": getattr(pos, "current_price", getattr(pos, "mark_price", 0.0)),
                        "pnl_percent": 0.0,
                    }
                )
                return True, f"Successfully closed position for {symbol}."
            except Exception as e:
                logger.error(f"Error closing position {symbol}: {e}")
                return False, f"Position close error for {symbol}: {e}"

    def emergency_close_safe(self) -> tuple[bool, str]:
        with self._lock:
            try:
                res = self.broker.emergency_close_all()
                logger.warning("Emergency close executed via Telegram request.")
                return True, f"Emergency close-all triggered: {res}"
            except Exception as e:
                logger.error(f"Emergency close failed: {e}")
                return False, f"Emergency close failed: {e}"

    # =====================================================
    # STATUS & REPORTING APIS FOR TELEGRAM ADAPTER
    # =====================================================

    def get_status_summary(self) -> dict:
        with self._lock:
            open_positions = self.broker.get_open_positions()
            count = len(open_positions) if isinstance(open_positions, list) else len(open_positions.keys())
            protected_symbols = self.broker.get_protected_symbols(self.watchlist)
            return {
                "mode": "LIVE" if self.live_trading else "PAPER",
                "engine_state": self.engine_state.value,
                "protection_only": self.protection_only_mode,
                "open_positions_count": count,
                "protected_symbols": protected_symbols,
                "watchlist": self.watchlist,
                "scanner_failures": dict(self.scanner.failure_counts),
                "pending_intents_count": len(getattr(self.broker, "pending_intents", {})),
            }

    def get_health_summary(self) -> dict:
        with self._lock:
            has_scanner_issues = any(c > 0 for c in self.scanner.failure_counts.values())
            has_price_issues = any(c > 0 for c in self.price_failure_counts.values())
            is_ok = not (self.protection_only_mode or has_scanner_issues or has_price_issues)
            return {
                "status": "HEALTHY" if is_ok else "DEGRADED",
                "engine_state": self.engine_state.value,
                "scanner_health": "OK" if not has_scanner_issues else "WARNING",
                "price_freshness": "OK" if not has_price_issues else "WARNING",
            }

    def get_balance_summary(self) -> str:
        if self.live_trading:
            try:
                balance = self.client.get_balance()
                return (
                    f"• Account Balance: `${balance.balance:.2f}` USDT\n"
                    f"• Available Margin: `${balance.available_margin:.2f}` USDT\n"
                    f"• Unrealized PnL: `${balance.unrealized_pnl:.2f}` USDT"
                )
            except Exception as e:
                return f"Error fetching BingX balance: {e}"
        else:
            return (
                f"• Paper Mode Balance: `${config.PAPER_STARTING_BALANCE:.2f}` USDT\n"
                f"• Initial Margin per trade: `${config.MARGIN_USDT:.2f}` USDT ({config.LEVERAGE}x)"
            )

    def get_positions_summary(self) -> list[dict]:
        with self._lock:
            symbols = list(self.watchlist)
            protected = self.broker.get_protected_symbols(symbols)
            result = []
            for s in protected:
                pos_info = self.get_position(s)
                if pos_info:
                    result.append(pos_info)
            return result

    def get_pnl_summary(self) -> str:
        positions = self.get_positions_summary()
        total_unrealized = sum(p.get("unrealized_pnl", 0.0) for p in positions)
        return (
            f"• Active Open Positions: `{len(positions)}`\n"
            f"• Current Total Unrealized PnL: `${total_unrealized:.4f}` USDT"
        )

    def get_orders_summary(self) -> str:
        with self._lock:
            intents = getattr(self.broker, "pending_intents", {})
            if not intents:
                return "No pending order intents requiring reconciliation."
            lines = ["Pending Intents:"]
            for sym, data in intents.items():
                lines.append(f"• {sym}: order_id `{data.get('client_order_id')}` side `{data.get('side')}`")
            return "\n".join(lines)

    def get_recent_trades(self, limit: int = 5) -> list[dict]:
        try:
            filename = getattr(self.trade_journal, "FILE_NAME", "data/trades.csv")
            import csv
            import os
            if not os.path.exists(filename):
                return []
            trades = []
            with open(filename, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    trades.append({
                        "symbol": row.get("Symbol"),
                        "side": row.get("Side"),
                        "entry_price": row.get("Entry Price"),
                        "exit_price": row.get("Exit Price"),
                        "status": row.get("Status"),
                        "pnl_percent": row.get("PnL %"),
                        "pnl_amount": row.get("PnL Amount"),
                    })
            return trades[-limit:]
        except Exception as e:
            logger.error(f"Error loading trade journal: {e}")
            return []