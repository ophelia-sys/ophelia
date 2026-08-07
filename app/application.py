from brokers.paper_broker import PaperBroker
from core.candle_scheduler import CandleScheduler
from core.position_manager import PositionManager
from core.scanner import Scanner
from risk.risk_manager import RiskManager


class Application:

    def __init__(self):

        self.position_manager = PositionManager()

        self.risk_manager = RiskManager(
            self.position_manager
        )

        self.scanner = Scanner()

        self.scheduler = CandleScheduler(5)

        self.broker = PaperBroker(
            self.position_manager
        )