from concurrent.futures import ThreadPoolExecutor

from exchange.bingx_client import BingXClient
from exchange.market_data import MarketData
from indicators.ema import EMAIndicator
from strategies.strategy_factory import StrategyFactory
from utils.logger import logger


class Scanner:

    def __init__(self, client: BingXClient | None = None):

        self.client = client or BingXClient()

        self.market = MarketData(self.client)

        self.strategy = StrategyFactory.create()

    def scan_symbol(self, symbol):

        try:

            df = self.market.get_klines(symbol=symbol)

            df = EMAIndicator.calculate(df)

            signal = self.strategy.generate_signal(
                df,
                symbol
            )

            return signal

        except Exception as e:

            logger.error(f"{symbol}: {e}")

            return None

    def scan(self, watchlist):

        signals = []

        with ThreadPoolExecutor(max_workers=10) as executor:

            results = executor.map(
                self.scan_symbol,
                watchlist
            )

            for signal in results:

                if signal is not None:

                    signals.append(signal)

        return signals