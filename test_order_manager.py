from config import DEFAULT_SYMBOL
from exchange.bingx_client import BingXClient
from exchange.order_manager import OrderManager

client = BingXClient()

orders = OrderManager(client)

print("=" * 60)
print("ORDER MANAGER TEST")
print("=" * 60)

print("\n1. Quantity Calculation")
print("----------------------")
print(orders.calculate_quantity(DEFAULT_SYMBOL))

print("\n2. Current Price")
print("----------------")
print(orders.get_current_price(DEFAULT_SYMBOL))

print("\n3. Symbol Info")
print("--------------")
print(orders.get_symbol_info(DEFAULT_SYMBOL))