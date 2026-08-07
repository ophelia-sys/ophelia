from config import DEFAULT_SYMBOL
from exchange.bingx_client import BingXClient
from exchange.order_manager import OrderManager


def main():

    client = BingXClient()

    order_manager = OrderManager(client)

    print("\n" + "=" * 60)
    print("        MANUAL POSITION CLOSE")
    print("=" * 60)

    positions = client.get_positions(DEFAULT_SYMBOL)

    if positions["code"] != 0:
        print(positions)
        return

    open_position = None

    for position in positions["data"]:

        qty = abs(float(position["positionAmt"]))

        if qty > 0:

            open_position = position
            break

    if open_position is None:

        print("\nNo open position found.")
        return

    print(f"Symbol        : {open_position['symbol']}")
    print(f"Side          : {open_position['positionSide']}")
    print(f"Quantity      : {open_position['positionAmt']}")
    print(f"Entry Price   : {open_position['avgPrice']}")
    print(f"Leverage      : {open_position['leverage']}x")
    print(f"PnL           : {open_position['unrealizedProfit']}")

    confirm = input("\nClose this position? (y/n): ").strip().lower()

    if confirm != "y":

        print("Cancelled.")
        return

    response = order_manager.close(
        DEFAULT_SYMBOL,
        open_position["positionSide"]
    )

    print("\n" + "=" * 60)
    print("CLOSE RESPONSE")
    print("=" * 60)

    print(response)


if __name__ == "__main__":
    main()