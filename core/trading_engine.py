import time

import config
from brokers.bingx_broker import BingXBroker
from brokers.paper_broker import PaperBroker
from core.candle_scheduler import CandleScheduler
from core.position_manager import PositionManager
from core.scanner import Scanner
from exchange.bingx_client import BingXClient
from exchange.public_bingx_client import PublicBingXClient
from portfolio.position_manager import PositionManager as LivePositionManager
from paper.trade_journal import TradeJournal
from risk.risk_manager import RiskManager
from utils.logger import logger


class TradingEngine:

    def __init__(self):

        logger.info("=" * 70)
        logger.info("Initializing Ophelia Trading Platform")
        logger.info("=" * 70)

        self.live_trading = bool(getattr(config, "LIVE_TRADING", False))
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

            if should_enter_protection_only and not self.protection_only_mode:
                self.protection_only_mode = True
                self.protection_degraded = True
                logger.error(
                    "Entering PROTECTION_ONLY mode. "
                    "New entries are blocked."
                )

            has_fresh_scan = len(signals) > 0 and not self.scanner.last_failed_symbols
            has_fresh_prices = not stale_symbols and not protection_price_failures
            if (
                self.protection_only_mode
                and has_fresh_scan
                and has_fresh_prices
            ):
                self.protection_only_mode = False
                self.protection_degraded = False
                logger.info(
                    "Exiting PROTECTION_ONLY mode. "
                    "Normal trading resumed."
                )

            if not self.protection_only_mode:
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
                    "PROTECTION_ONLY mode active: "
                    "skipping new signal entries."
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