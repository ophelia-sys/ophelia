from config import DEFAULT_SYMBOL
from exchange.bingx_client import BingXClient
from exchange.order_manager import OrderManager

client = BingXClient()

orders = OrderManager(client)

print("=" * 60)
print("TRADE TEST")
print("=" * 60)

choice = input(
    "\n1 - Open LONG\n"
    "2 - Open SHORT\n"
    "3 - Close LONG\n"
    "4 - Close SHORT\n\n"
    "Choice: "
)

if choice == "1":

    print(orders.open_long(DEFAULT_SYMBOL))

elif choice == "2":

    print(orders.open_short(DEFAULT_SYMBOL))

elif choice == "3":

    print(orders.close_long(DEFAULT_SYMBOL))

elif choice == "4":

    print(orders.close_short(DEFAULT_SYMBOL))

else:

    print("Invalid Choice")