from config import DEFAULT_SYMBOL
from exchange.bingx_client import BingXClient

client = BingXClient()

print("=" * 60)
print("TEST MARKET ORDER")
print("=" * 60)

# Optional: set leverage first
print(client.set_leverage(DEFAULT_SYMBOL, 20))

print("\nSending Market Buy...")

response = client.place_market_order(
    symbol=DEFAULT_SYMBOL,
    side="BUY",
    position_side="LONG",
    quantity=2.712
)

print("\nResponse:")
print(response)