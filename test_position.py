from config import DEFAULT_SYMBOL
from exchange.bingx_client import BingXClient
from portfolio.position_manager import PositionManager

client = BingXClient()

positions = PositionManager(client)

positions.print_position(DEFAULT_SYMBOL)

print()

print("Has Position :", positions.has_position(DEFAULT_SYMBOL))
print("Is Long      :", positions.is_long(DEFAULT_SYMBOL))
print("Is Short     :", positions.is_short(DEFAULT_SYMBOL))
