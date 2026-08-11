from concurrent.futures import ThreadPoolExecutor

from exchange.bingx_client import BingXClient
from exchange.market_data import MarketData
from indicators.ema import EMAIndicator
from strategies.strategy_factory import StrategyFactory
from utils.logger import logger
from core.decision_engine import DecisionEngine


class Scanner:

    def __init__(self, client: BingXClient | None = None, institutional_data=None):

        self.client = client or BingXClient()

        self.market = MarketData(self.client)

        self.strategy = StrategyFactory.create()
        self.institutional_data = institutional_data
        self.decision_engine = DecisionEngine()
        self.failure_counts = {}
        self.last_failed_symbols = []

    def scan_symbol(self, symbol, timeframe="1m", ema_fast=None, ema_slow=None):

        try:

            df = self.market.get_klines(symbol=symbol, interval=timeframe)

            df = EMAIndicator.calculate(df)

            signal = self.strategy.get_signal(df, ema_fast=ema_fast, ema_slow=ema_slow)
            if isinstance(signal, dict):
                signal["symbol"] = symbol
                
                if signal.get("signal") in ("BUY", "SELL"):
                    snapshot = None
                    if self.institutional_data:
                        try:
                            snapshot = self.institutional_data.get_snapshot(symbol)
                        except Exception as e:
                            logger.warning(f"Institutional data failure for {symbol}: {e}")
                            
                    analysis = self.decision_engine.evaluate(symbol, df, signal, snapshot=snapshot)
                    if not analysis.approved:
                        return None

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

    def scan(self, watchlist, timeframe="1m", ema_fast=None, ema_slow=None):

        signals = []
        failed_symbols = []

        with ThreadPoolExecutor(max_workers=10) as executor:

            results = executor.map(
                lambda s: self.scan_symbol(s, timeframe=timeframe, ema_fast=ema_fast, ema_slow=ema_slow),
                watchlist
            )

            for symbol, signal in zip(watchlist, results):

                if signal is not None:

                    signals.append(signal)
                else:
                    failed_symbols.append(symbol)

        self.last_failed_symbols = failed_symbols

        return signals