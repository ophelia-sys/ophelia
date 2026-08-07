from config import DEFAULT_SYMBOL, TIMEFRAME
from exchange.bingx_client import BingXClient
from exchange.market_data import MarketData

client = BingXClient()
market = MarketData(client)

df = market.get_klines(
    DEFAULT_SYMBOL,
    TIMEFRAME,
    20
)

print(df.tail())