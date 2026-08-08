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
        self.failure_counts = {}
        self.last_failed_symbols = []

    def scan_symbol(self, symbol):

        try:

            df = self.market.get_klines(symbol=symbol)

            df = EMAIndicator.calculate(df)

            signal = self.strategy.get_signal(df)
            if isinstance(signal, dict):
                signal["symbol"] = symbol
            self.failure_counts[symbol] = 0

            return signal

        except Exception as e:
            count = self.failure_counts.get(symbol, 0) + 1
            self.failure_counts[symbol] = count

            logger.error(f"{symbol}: {e} (failure #{count})")
            if count >= 3:
                logger.error(
                    f"Scanner failure escalation for {symbol}: "
                    f"{count} consecutive failures"
                )

            return None

    def scan(self, watchlist):

        signals = []
        failed_symbols = []

        with ThreadPoolExecutor(max_workers=10) as executor:

            results = executor.map(
                self.scan_symbol,
                watchlist
            )

            for symbol, signal in zip(watchlist, results):

                if signal is not None:

                    signals.append(signal)
                else:
                    failed_symbols.append(symbol)

        self.last_failed_symbols = failed_symbols

        return signals