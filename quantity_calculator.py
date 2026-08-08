from config import DEFAULT_SYMBOL, LEVERAGE, MARGIN_USDT
from exchange.bingx_client import BingXClient

client = BingXClient()

# ---------------------------------------
# Get Current Price
# ---------------------------------------

price = float(client.get_latest_price(DEFAULT_SYMBOL))

# ---------------------------------------
# Calculate Position
# ---------------------------------------

position_value = MARGIN_USDT * LEVERAGE

quantity = position_value / price

# Round to 3 decimal places
quantity = round(quantity, 3)

# ---------------------------------------
# Print
# ---------------------------------------

print("=" * 50)
print("POSITION SIZE CALCULATOR")
print("=" * 50)

print(f"Symbol          : {DEFAULT_SYMBOL}")
print(f"Current Price   : {price:.3f} USDT")
print(f"Margin          : {MARGIN_USDT} USDT")
print(f"Leverage        : {LEVERAGE}x")
print(f"Position Value  : {position_value:.2f} USDT")
print(f"Quantity        : {quantity} SOL")

print("=" * 50)