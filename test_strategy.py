from config import DEFAULT_SYMBOL, TIMEFRAME
from exchange.bingx_client import BingXClient
from exchange.market_data import MarketData
from strategies.strategy_factory import StrategyFactory

client = BingXClient()

market = MarketData(client)

strategy = StrategyFactory.create()

candles = market.get_klines(
    DEFAULT_SYMBOL,
    TIMEFRAME,
    200
)

signal = strategy.get_signal(candles)

print("\n" + "=" * 60)
print("EMA STRATEGY")
print("=" * 60)
print("Signal:", signal)

strategy.print_status(candles)