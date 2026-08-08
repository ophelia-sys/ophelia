import config
from brokers.bingx_broker import BingXBroker
from brokers.paper_broker import PaperBroker
from core.candle_scheduler import CandleScheduler
from core.position_manager import PositionManager
from core.scanner import Scanner
from exchange.bingx_client import BingXClient
from exchange.public_bingx_client import PublicBingXClient
from paper.trade_journal import TradeJournal
from portfolio.position_manager import PositionManager as LivePositionManager
from risk.risk_manager import RiskManager


class Application:

    def __init__(self):

        self.live_trading = bool(getattr(config, "LIVE_TRADING", False))

        self.scheduler = CandleScheduler(5)
        self.trade_journal = TradeJournal()

        if self.live_trading:
            self.client = BingXClient()
            market_client = self.client
            self.position_manager = LivePositionManager(self.client)
            self.broker = BingXBroker(
                self.client,
                self.position_manager,
                self.trade_journal,
            )
        else:
            market_client = PublicBingXClient()
            self.position_manager = PositionManager()
            self.broker = PaperBroker(
                self.position_manager,
                self.trade_journal,
            )

        self.scanner = Scanner(market_client)

        self.risk_manager = RiskManager(
            self.position_manager
        )