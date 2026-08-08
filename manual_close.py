from config import DEFAULT_SYMBOL
from exchange.bingx_client import BingXClient


def main():

    client = BingXClient()

    print("\n" + "=" * 60)
    print("        MANUAL POSITION CLOSE")
    print("=" * 60)

    positions = client.get_positions(DEFAULT_SYMBOL)

    open_position = None

    for position in positions:
        if position.quantity > 0:
            open_position = position
            break

    if open_position is None:

        print("\nNo open position found.")
        return

    print(f"Symbol        : {open_position.symbol}")
    print(f"Side          : {open_position.side.value}")
    print(f"Quantity      : {open_position.quantity}")
    print(f"Entry Price   : {open_position.entry_price}")
    print(f"Leverage      : {open_position.leverage}x")
    print(f"PnL           : {open_position.unrealized_pnl}")

    confirm = input("\nClose this position? (y/n): ").strip().lower()

    if confirm != "y":

        print("Cancelled.")
        return

    if open_position.position_id is None:
        print("Position ID unavailable.")
        return

    response = client.close_position(open_position.position_id)

    print("\n" + "=" * 60)
    print("CLOSE RESPONSE")
    print("=" * 60)

    print(response)


if __name__ == "__main__":
    main()