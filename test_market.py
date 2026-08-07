from config import DEFAULT_SYMBOL
from exchange.bingx_client import BingXClient
from exchange.market_data import MarketData

client = BingXClient()

market = MarketData(client)

print()

print("Current Price")
print(market.get_current_price(DEFAULT_SYMBOL))

print()

print("Quantity Precision")
print(market.get_quantity_precision(DEFAULT_SYMBOL))

print()

print("Price Precision")
print(market.get_price_precision(DEFAULT_SYMBOL))

print()

print("Minimum Quantity")
print(market.get_min_quantity(DEFAULT_SYMBOL))

print()

print("Minimum USDT")
print(market.get_min_notional(DEFAULT_SYMBOL))