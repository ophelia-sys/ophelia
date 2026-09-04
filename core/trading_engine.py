import threading
import time
import json
import os
import tempfile
from typing import Any, Callable

import config
from brokers.bingx_broker import BingXBroker
from brokers.paper_broker import PaperBroker
from brokers.shadow_broker import ShadowBroker
from core.candle_scheduler import CandleScheduler
from core.enums import EngineState
from core.position_manager import PositionManager
from core.scanner import Scanner
from core.settings import TradingSettings
from exchange.bingx_client import BingXClient
from exchange.public_bingx_client import PublicBingXClient
from paper.trade_journal import TradeJournal
from portfolio.position_manager import PositionManager as LivePositionManager
from risk.risk_manager import RiskManager
from utils.logger import logger
from institutional.data.engine import InstitutionalDataEngine
from institutional.cvd.probability_engine import Phase7ProbabilityEngine


class ShadowStateManager:
    def __init__(self):
        self.state_file = os.path.join(os.path.dirname(__file__), "../data/shadow_state.json")
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        self.state = {
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
        self._load()

    def _load(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    data = json.load(f)
                self.state.update(data)
            except Exception as e:
                logger.error(f"Failed to load shadow state: {e}")

    def save(self):
        try:
            self.state["last_update"] = int(time.time())
            tmp_path = self.state_file + ".tmp"
            with open(tmp_path, "w") as f:
                json.dump(self.state, f)
            os.replace(tmp_path, self.state_file)
        except Exception as e:
            logger.error(f"Failed to save shadow state: {e}")

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

        self.settings = TradingSettings.load()

        if self.live_trading:
            self.client = BingXClient()
            market_client = self.client
        else:
            market_client = PublicBingXClient()

        self.institutional_data = InstitutionalDataEngine(market_client)
        self.probability_engine = Phase7ProbabilityEngine(self.institutional_data)

        # Scanner (Legacy Kronos/EMA - Quarantined)
        self.scanner = Scanner(market_client, institutional_data=self.institutional_data)
        self.watchlist = list(self.settings.symbols)

        # Load Phase 7 Decision Thresholds for Shadow Mode
        self.phase7_thresholds = {}
        try:
            import json
            import os
            threshold_path = os.path.join(os.path.dirname(__file__), "../PHASE7_DECISION_THRESHOLDS.json")
            if os.path.exists(threshold_path):
                with open(threshold_path, "r") as f:
                    self.phase7_thresholds = json.load(f)
                logger.info("Loaded Phase 7 Decision Thresholds for Shadow Mode.")
            else:
                logger.warning("PHASE7_DECISION_THRESHOLDS.json not found. Shadow Mode will lack threshold evaluation.")
        except Exception as e:
            logger.error(f"Failed to load Phase 7 thresholds: {e}")

        self.shadow_state_manager = ShadowStateManager()
        self.trade_journal = TradeJournal()

        if getattr(config, "OPHELIA_MODE", "RESEARCH") == "SHADOW":
            self.position_manager = PositionManager()
            self.broker = ShadowBroker(
                self.position_manager,
                self.trade_journal,
            )
            logger.warning("Execution mode: SHADOW (Broker completely isolated)")
        elif self.live_trading:
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
        logger.info(f"Watching {len(self.settings.symbols)} Coins")
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
            active_symbols = list(self.settings.symbols)

            # -------------------------------------------------------------
            # PHASE 7 PROBABILITY ENGINE (OBSERVATION ONLY)
            # -------------------------------------------------------------
            now = int(time.time())
            now_ms = now * 1000
            
            for symbol in active_symbols:
                prob_result = self.probability_engine.get_probability(symbol, now_ms)
                if prob_result is not None:
                    if prob_result.get("status") == "warming":
                        logger.info(f"[PHASE 7] {symbol} Buffer Warming: {prob_result['blocks']}/{prob_result['required']} blocks (Failed Closed)")
                    else:
                        prob_long = prob_result.get('probability_long', 0.0)
                        prob_short = prob_result.get('probability_short', 0.0)
                        logger.info(f"[PHASE 7] {symbol} Probability: LONG={prob_long:.4f} SHORT={prob_short:.4f}")
                        
                        # -------------------------------------------------------------
                        # SHADOW MODE EVALUATION
                        # -------------------------------------------------------------
                        threshold_data = self.phase7_thresholds.get(symbol) or self.phase7_thresholds.get(symbol.replace("-", ""))
                        if threshold_data is not None:
                            thresh_long = threshold_data.get("threshold")
                            thresh_short = threshold_data.get("short_threshold")
                            thresh_version = threshold_data.get("version", "1.0.0")
                            
                            if thresh_long is not None and thresh_short is not None:
                                long_margin = prob_long - thresh_long
                                short_margin = prob_short - thresh_short
                                
                                decision = "HOLD"
                                reason = "P < THRESH"
                                
                                telemetry = prob_result.get("telemetry", {})
                                conf_long = []
                                conf_short = []
                                
                                if telemetry.get("delta_deterioration_bullish", 0) == 1.0: conf_long.append("DTR")
                                if telemetry.get("delta_flip_bullish", 0) == 1.0: conf_long.append("FLP")
                                if telemetry.get("divergence_bullish", 0) == 1.0: conf_long.append("DIV")
                                
                                if telemetry.get("delta_deterioration_bearish", 0) == 1.0: conf_short.append("DTR")
                                if telemetry.get("delta_flip_bearish", 0) == 1.0: conf_short.append("FLP")
                                if telemetry.get("divergence_bearish", 0) == 1.0: conf_short.append("DIV")
                                
                                l_flags = f" [{','.join(conf_long)}]" if conf_long else ""
                                s_flags = f" [{','.join(conf_short)}]" if conf_short else ""
                                
                                if long_margin >= 0 and short_margin >= 0:
                                    if long_margin >= short_margin:
                                        decision = "LONG_CANDIDATE"
                                        reason = f"CONFLICT RESOLVED: LONG_MARGIN ({long_margin:.4f}) >= SHORT_MARGIN ({short_margin:.4f}){l_flags}"
                                    else:
                                        decision = "SHORT_CANDIDATE"
                                        reason = f"CONFLICT RESOLVED: SHORT_MARGIN ({short_margin:.4f}) > LONG_MARGIN ({long_margin:.4f}){s_flags}"
                                elif long_margin >= 0:
                                    decision = "LONG_CANDIDATE"
                                    reason = f"LONG P >= THRESH ({prob_long:.4f} >= {thresh_long:.4f}){l_flags}"
                                elif short_margin >= 0:
                                    decision = "SHORT_CANDIDATE"
                                    reason = f"SHORT P >= THRESH ({prob_short:.4f} >= {thresh_short:.4f}){s_flags}"
                                
                                snapshot = self.institutional_data.get_snapshot(symbol, "5m")
                                hypothetical_entry = snapshot.ohlcv[-1].close if snapshot and snapshot.ohlcv else 0.0
                                
                                import json
                                shadow_log = {
                                    "timestamp": now_ms,
                                    "symbol": symbol,
                                    "probability_long": float(prob_long),
                                    "probability_short": float(prob_short),
                                    "frozen_threshold_long": float(thresh_long),
                                    "frozen_threshold_short": float(thresh_short),
                                    "threshold_version": thresh_version,
                                    "model_version": "frozen_v1",
                                    "feature_version": "frozen_v1",
                                    "decision": decision,
                                    "reason": reason,
                                    "data_freshness": "FRESH",  # Assumes valid if probability exists
                                    "feature_validity": "VALID",
                                    "hypothetical_entry_price": float(hypothetical_entry),
                                    "hypothetical_risk_status": "N/A",
                                    "engine_version": "phase7_1.2_adv_orderflow",
                                    "telemetry": telemetry
                                }
                                logger.info(f"[SHADOW_JSON] {json.dumps(shadow_log)}")
                                
                                # Update durable shadow state
                                with self._lock:
                                    s_state = self.shadow_state_manager.state
                                    
                                    if s_state["phase"] == "WARMING":
                                        s_state["phase"] = "SHADOW_RUNNING"
                                        s_state["shadow_started_at"] = now_ms / 1000.0
                                        logger.info(f"Shadow State transitioned to SHADOW_RUNNING at {now_ms}")
                                        
                                    s_state["observations"] += 1
                                    if decision == "LONG_CANDIDATE":
                                        s_state["long_candidates"] += 1
                                    elif decision == "SHORT_CANDIDATE":
                                        s_state["short_candidates"] += 1
                                    elif decision == "HOLD":
                                        s_state["holds"] += 1
                                        
                                    if "CONFLICT RESOLVED" in reason:
                                        s_state["conflicts"] += 1
                                        
                                    if telemetry.get("delta_deterioration_bullish", 0) == 1.0 or telemetry.get("delta_deterioration_bearish", 0) == 1.0:
                                        s_state["telemetry_counts"]["dtr"] += 1
                                    if telemetry.get("delta_flip_bullish", 0) == 1.0 or telemetry.get("delta_flip_bearish", 0) == 1.0:
                                        s_state["telemetry_counts"]["flp"] += 1
                                    if telemetry.get("divergence_bullish", 0) == 1.0 or telemetry.get("divergence_bearish", 0) == 1.0:
                                        s_state["telemetry_counts"]["div"] += 1
                                    if telemetry.get("absorption_bullish_proxy", 0) == 1.0 or telemetry.get("absorption_bearish_proxy", 0) == 1.0:
                                        s_state["telemetry_counts"]["abs"] += 1
                                        
                                    self.shadow_state_manager.save()
                else:
                    logger.info(f"[PHASE 7] {symbol} Probability: NONE (Failed Closed)")
                    
            # -------------------------------------------------------------
            # LEGACY KRONOS/EMA SCANNER (QUARANTINED)
            # -------------------------------------------------------------
            _legacy_signals = self.scanner.scan(
                active_symbols,
                timeframe=self.settings.timeframe,
                ema_fast=self.settings.ema_fast,
                ema_slow=self.settings.ema_slow,
            )
            # Force empty signals to completely quarantine Kronos/EMA from placing orders.
            signals = []
            
            if self.scanner.last_failed_symbols:
                failed = ", ".join(self.scanner.last_failed_symbols)
                logger.error(f"Scanner failed symbols this cycle: {failed}")

            logger.info(f"Legacy Signals Ignored (Quarantined): {len(_legacy_signals)}")

            now = int(time.time())
            stale_symbols = []
            protection_price_failures = []
            protection_symbols = self.broker.get_protected_symbols(active_symbols)
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
                        margin=self.settings.margin_usdt,
                        leverage=self.settings.leverage,
                        risk_config=self.settings.get_risk_config(symbol),
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
                            margin=self.settings.margin_usdt,
                            leverage=self.settings.leverage,
                            risk_config=self.settings.get_risk_config(symbol),
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

                    if signal_type in ("BUY", "SELL"):
                        if (
                            self.settings.trade_limit is not None
                            and self.settings.new_trades_count >= self.settings.trade_limit
                        ):
                            logger.warning(
                                f"Trade limit reached ({self.settings.new_trades_count}/{self.settings.trade_limit}). "
                                f"Skipping new entry for {symbol}."
                            )
                            continue

                    pos_before = self.position_manager.get_position(symbol)

                    self.broker.process_signal(
                        signal,
                        self.risk_manager,
                        margin=self.settings.margin_usdt,
                        leverage=self.settings.leverage,
                        risk_config=self.settings.get_risk_config(symbol),
                    )

                    pos_after = self.position_manager.get_position(symbol)

                    # Increment trade limit count if a new position was opened
                    if pos_before is None and pos_after is not None:
                        with self._lock:
                            self.settings.new_trades_count += 1
                            self.settings.save()
                        logger.info(
                            f"New trade opened for {symbol}. Session trade count: "
                            f"{self.settings.new_trades_count}"
                            f"{'/' + str(self.settings.trade_limit) if self.settings.trade_limit else ''}"
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
        
        try:
            self.institutional_data.start(watchlist=list(self.settings.symbols))
        except Exception as e:
            logger.error(f"Failed to start InstitutionalDataEngine: {e}")

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
                
                try:
                    self.institutional_data.stop()
                except Exception as e:
                    logger.error(f"Failed to stop InstitutionalDataEngine: {e}")

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
    # SAFE RUNTIME SETTINGS APIS FOR TELEGRAM ADAPTER
    # =====================================================

    def get_settings_summary(self) -> dict:
        with self._lock:
            limit_str = (
                str(self.settings.trade_limit)
                if self.settings.trade_limit is not None
                else "unlimited"
            )
            rem_str = (
                str(max(0, self.settings.trade_limit - self.settings.new_trades_count))
                if self.settings.trade_limit is not None
                else "unlimited"
            )
            return {
                "ema_fast": self.settings.ema_fast,
                "ema_slow": self.settings.ema_slow,
                "timeframe": self.settings.timeframe,
                "margin_usdt": self.settings.margin_usdt,
                "leverage": self.settings.leverage,
                "symbols": list(self.settings.symbols),
                "trade_limit": limit_str,
                "new_trades_count": self.settings.new_trades_count,
                "trades_remaining": rem_str,
                "engine_state": self.engine_state.value,
                "sl_mode": self.settings.sl_mode,
                "sl_value": self.settings.sl_value,
                "tp_mode": self.settings.tp_mode,
                "tp_value": self.settings.tp_value,
                "trailing_activation": self.settings.trailing_activation,
                "trailing_buffer": self.settings.trailing_buffer,
                "exit_plan": list(self.settings.exit_plan),
                "symbol_risk": dict(self.settings.symbol_risk),
            }

    def update_ema_settings(self, fast: int, slow: int) -> tuple[bool, str]:
        with self._lock:
            valid, err = TradingSettings.validate_ema(fast, slow)
            if not valid:
                return False, err
            old_val = f"{self.settings.ema_fast}/{self.settings.ema_slow}"
            self.settings.ema_fast = int(fast)
            self.settings.ema_slow = int(slow)
            self.settings.save()
            logger.info(f"EMA settings updated: {old_val} -> {fast}/{slow}")
            return True, f"EMA settings updated from {old_val} to {fast}/{slow}."

    def update_timeframe(self, tf: str) -> tuple[bool, str]:
        with self._lock:
            valid, err = TradingSettings.validate_timeframe(tf)
            if not valid:
                return False, err
            old_val = self.settings.timeframe
            self.settings.timeframe = str(tf).lower()
            self.settings.save()
            logger.info(f"Timeframe updated: {old_val} -> {self.settings.timeframe}")
            return True, f"Timeframe updated from {old_val} to {self.settings.timeframe}."

    def update_margin(self, margin: float) -> tuple[bool, str]:
        with self._lock:
            valid, err = TradingSettings.validate_margin(margin)
            if not valid:
                return False, err
            old_val = self.settings.margin_usdt
            self.settings.margin_usdt = float(margin)
            self.settings.save()
            logger.info(f"Margin updated: {old_val} -> {self.settings.margin_usdt} USDT")
            return True, f"Margin updated from {old_val} USDT to {self.settings.margin_usdt} USDT."

    def update_leverage(self, leverage: int) -> tuple[bool, str]:
        with self._lock:
            valid, err = TradingSettings.validate_leverage(leverage)
            if not valid:
                return False, err
            old_val = self.settings.leverage
            self.settings.leverage = int(leverage)
            self.settings.save()
            logger.info(f"Leverage updated: {old_val}x -> {self.settings.leverage}x")
            return True, f"Leverage updated from {old_val}x to {self.settings.leverage}x."

    def add_symbol(self, symbol: str) -> tuple[bool, str]:
        with self._lock:
            sym = str(symbol).upper().strip()
            valid, err = TradingSettings.validate_symbol(sym)
            if not valid:
                return False, err
            if sym in self.settings.symbols:
                return False, f"Symbol '{sym}' is already in the watchlist."
            self.settings.symbols.append(sym)
            self.settings.save()
            logger.info(f"Symbol '{sym}' added to watchlist.")
            return True, f"Symbol '{sym}' added to watchlist."

    def remove_symbol(self, symbol: str) -> tuple[bool, str]:
        with self._lock:
            sym = str(symbol).upper().strip()
            if sym not in self.settings.symbols:
                return False, f"Symbol '{sym}' is not in the watchlist."
            self.settings.symbols.remove(sym)
            self.settings.save()
            msg = f"Symbol '{sym}' removed from watchlist."
            if self.position_manager.get_position(sym) is not None:
                msg += " (Note: Open position exists; protection remains active)."
            logger.info(msg)
            return True, msg

    def set_trade_limit(self, limit_val: Any) -> tuple[bool, str]:
        with self._lock:
            valid, err = TradingSettings.validate_trade_limit(limit_val)
            if not valid:
                return False, err
            old_val = (
                str(self.settings.trade_limit)
                if self.settings.trade_limit is not None
                else "unlimited"
            )
            if limit_val is None or str(limit_val).lower() in ("unlimited", "none", "0"):
                self.settings.trade_limit = None
                new_str = "unlimited"
            else:
                self.settings.trade_limit = int(limit_val)
                new_str = str(self.settings.trade_limit)
            self.settings.save()
            logger.info(f"Trade limit updated: {old_val} -> {new_str}")
            return True, f"Trade limit updated from {old_val} to {new_str}."

    # =====================================================
    # SAFE RUNTIME RISK SETTINGS APIS FOR TELEGRAM ADAPTER
    # =====================================================

    def get_risk_settings_summary(self, symbol: str | None = None) -> dict:
        with self._lock:
            global_cfg = self.settings.get_risk_config(None)
            target_cfg = self.settings.get_risk_config(symbol)
            return {
                "symbol": symbol.upper() if symbol else "GLOBAL",
                "sl_mode": target_cfg["sl_mode"],
                "sl_value": target_cfg["sl_value"],
                "tp_mode": target_cfg["tp_mode"],
                "tp_value": target_cfg["tp_value"],
                "trailing_activation": target_cfg["trailing_activation"],
                "trailing_buffer": target_cfg["trailing_buffer"],
                "exit_plan": target_cfg["exit_plan"],
                "global_defaults": global_cfg,
                "symbol_overrides": dict(self.settings.symbol_risk),
            }

    def update_sl_setting(self, mode: str, value: float, symbol: str | None = None) -> tuple[bool, str]:
        with self._lock:
            valid, err = TradingSettings.validate_sl(mode, value)
            if not valid:
                return False, err
            mode_norm = "PRICE_PERCENT" if str(mode).upper() in ("PERCENT", "PRICE_PERCENT", "%") else "FIXED_LOSS"
            val = float(value)
            if symbol:
                sym = str(symbol).upper().strip()
                if sym not in self.settings.symbol_risk:
                    self.settings.symbol_risk[sym] = {}
                self.settings.symbol_risk[sym]["sl_mode"] = mode_norm
                self.settings.symbol_risk[sym]["sl_value"] = val
                target_str = f"Symbol '{sym}'"
            else:
                self.settings.sl_mode = mode_norm
                self.settings.sl_value = val
                target_str = "Global"
            self.settings.save()
            msg = f"{target_str} Stop-Loss updated to {mode_norm} ({val}{'%' if mode_norm=='PRICE_PERCENT' else ' USDT'})."
            logger.info(msg)
            return True, msg

    def update_tp_setting(self, mode: str, value: float, symbol: str | None = None) -> tuple[bool, str]:
        with self._lock:
            valid, err = TradingSettings.validate_tp(mode, value)
            if not valid:
                return False, err
            mode_norm = "PRICE_PERCENT" if str(mode).upper() in ("PERCENT", "PRICE_PERCENT", "%") else "FIXED_PROFIT"
            val = float(value)
            if symbol:
                sym = str(symbol).upper().strip()
                if sym not in self.settings.symbol_risk:
                    self.settings.symbol_risk[sym] = {}
                self.settings.symbol_risk[sym]["tp_mode"] = mode_norm
                self.settings.symbol_risk[sym]["tp_value"] = val
                target_str = f"Symbol '{sym}'"
            else:
                self.settings.tp_mode = mode_norm
                self.settings.tp_value = val
                target_str = "Global"
            self.settings.save()
            msg = f"{target_str} Take-Profit updated to {mode_norm} ({val}{'%' if mode_norm=='PRICE_PERCENT' else ' USDT'})."
            logger.info(msg)
            return True, msg

    def update_trailing_setting(self, buffer_pct: float, symbol: str | None = None) -> tuple[bool, str]:
        with self._lock:
            act = self.settings.get_risk_config(symbol)["trailing_activation"]
            valid, err = TradingSettings.validate_trailing(buffer_pct, act)
            if not valid:
                return False, err
            val = float(buffer_pct)
            if symbol:
                sym = str(symbol).upper().strip()
                if sym not in self.settings.symbol_risk:
                    self.settings.symbol_risk[sym] = {}
                self.settings.symbol_risk[sym]["trailing_buffer"] = val
                target_str = f"Symbol '{sym}'"
            else:
                self.settings.trailing_buffer = val
                target_str = "Global"
            self.settings.save()
            msg = f"{target_str} Trailing Buffer updated to {val}%."
            logger.info(msg)
            return True, msg

    def update_trailing_activation_setting(self, activation_pct: float, symbol: str | None = None) -> tuple[bool, str]:
        with self._lock:
            buf = self.settings.get_risk_config(symbol)["trailing_buffer"]
            valid, err = TradingSettings.validate_trailing(buf, activation_pct)
            if not valid:
                return False, err
            val = float(activation_pct)
            if symbol:
                sym = str(symbol).upper().strip()
                if sym not in self.settings.symbol_risk:
                    self.settings.symbol_risk[sym] = {}
                self.settings.symbol_risk[sym]["trailing_activation"] = val
                target_str = f"Symbol '{sym}'"
            else:
                self.settings.trailing_activation = val
                target_str = "Global"
            self.settings.save()
            msg = f"{target_str} Trailing Activation updated to {val}%."
            logger.info(msg)
            return True, msg

    def update_exit_plan_setting(self, tokens: list[str], symbol: str | None = None) -> tuple[bool, str]:
        with self._lock:
            valid, err, legs = TradingSettings.parse_exit_plan(tokens)
            if not valid:
                return False, err
            if symbol:
                sym = str(symbol).upper().strip()
                if sym not in self.settings.symbol_risk:
                    self.settings.symbol_risk[sym] = {}
                self.settings.symbol_risk[sym]["exit_plan"] = legs
                target_str = f"Symbol '{sym}'"
            else:
                self.settings.exit_plan = legs
                target_str = "Global"
            self.settings.save()
            msg = f"{target_str} Exit Plan updated with {len(legs)} legs."
            logger.info(msg)
            return True, msg

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
            protected_symbols = self.broker.get_protected_symbols(self.settings.symbols)
            limit_str = (
                str(self.settings.trade_limit)
                if self.settings.trade_limit is not None
                else "unlimited"
            )
            rem_str = (
                str(max(0, self.settings.trade_limit - self.settings.new_trades_count))
                if self.settings.trade_limit is not None
                else "unlimited"
            )
            return {
                "mode": "LIVE" if self.live_trading else "PAPER",
                "engine_state": self.engine_state.value,
                "protection_only": self.protection_only_mode,
                "open_positions_count": count,
                "protected_symbols": protected_symbols,
                "watchlist": list(self.settings.symbols),
                "scanner_failures": dict(self.scanner.failure_counts),
                "pending_intents_count": len(getattr(self.broker, "pending_intents", {})),
                "ema_fast": self.settings.ema_fast,
                "ema_slow": self.settings.ema_slow,
                "timeframe": self.settings.timeframe,
                "margin_usdt": self.settings.margin_usdt,
                "leverage": self.settings.leverage,
                "trade_limit": limit_str,
                "trades_used": self.settings.new_trades_count,
                "trades_remaining": rem_str,
                "sl_mode": self.settings.sl_mode,
                "sl_value": self.settings.sl_value,
                "tp_mode": self.settings.tp_mode,
                "tp_value": self.settings.tp_value,
                "trailing_activation": self.settings.trailing_activation,
                "trailing_buffer": self.settings.trailing_buffer,
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
                f"• Configured Margin per trade: `${self.settings.margin_usdt:.2f}` USDT ({self.settings.leverage}x)"
            )

    def get_positions_summary(self) -> list[dict]:
        with self._lock:
            symbols = list(self.settings.symbols)
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
                        "quantity": row.get("Quantity"),
                        "status": row.get("Status"),
                        "pnl_percent": row.get("PnL %"),
                        "pnl_amount": row.get("PnL Amount"),
                    })
            return trades[-limit:]
        except Exception as e:
            logger.error(f"Error loading trade journal: {e}")
            return []