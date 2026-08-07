import config
from brokers.paper_broker import PaperBroker
from core.candle_scheduler import CandleScheduler
from core.position_manager import PositionManager
from core.scanner import Scanner
from paper.trade_journal import TradeJournal
from risk.risk_manager import RiskManager
from utils.logger import logger


class TradingEngine:

    def __init__(self):

        logger.info("=" * 70)
        logger.info("Initializing Ophelia Trading Platform")
        logger.info("=" * 70)

        # Shared Managers
        self.position_manager = PositionManager()
        self.risk_manager = RiskManager(self.position_manager)

        # Scanner
        self.scanner = Scanner()

        self.watchlist = list(
            getattr(
                config,
                "WATCHLIST",
                config.SUPPORTED_SYMBOLS,
            )
        )

        self.trade_journal = TradeJournal()

        # Broker
        self.broker = PaperBroker(
            self.position_manager,
            self.trade_journal,
        )

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

            logger.info(f"Signals Received: {len(signals)}")

            for signal in signals:

                logger.info(
                    f"{signal.symbol} | {signal.signal}"
                )

                self.broker.process_signal(
                    signal,
                    self.risk_manager
                )

            logger.info(
                f"Open Positions: {self.position_manager.count()}"
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

                break

            except Exception as e:

                logger.error(f"Trading Engine Error: {e}")