from config import DEFAULT_SYMBOL, LEVERAGE, MARGIN_USDT
from exchange.bingx_client import BingXClient
from exchange.order_manager import OrderManager


def main():

    client = BingXClient()

    order_manager = OrderManager(client)

    print("\n" + "=" * 60)
    print("      MANUAL USDT-M FUTURES TRADE")
    print("=" * 60)

    print(f"Symbol       : {DEFAULT_SYMBOL}")
    print(f"Margin       : {MARGIN_USDT} USDT")
    print(f"Leverage     : {LEVERAGE}x")

    # ============================================
    # CHECK BALANCE
    # ============================================

    balance = client.get_balance()

    if balance["code"] != 0:
        print(balance)
        return

    usdt = None

    for asset in balance["data"]:

        if asset["asset"] == "USDT":
            usdt = asset
            break

    if usdt is None:
        print("USDT wallet not found.")
        return

    available_balance = float(usdt["availableMargin"])

    print(f"Available Margin : {available_balance:.4f} USDT")

    if available_balance < MARGIN_USDT:

        print("\nInsufficient Margin")
        return

    # ============================================
    # SET LEVERAGE
    # ============================================

    leverage = client.set_leverage(
    symbol=DEFAULT_SYMBOL,
    leverage=LEVERAGE,
    side="LONG"
    )

    print("\nLeverage Response")

    print(leverage)

    # ============================================
    # CALCULATE QUANTITY
    # ============================================

    quantity = order_manager.calculate_quantity(
        DEFAULT_SYMBOL
    )

    print(f"\nCalculated Quantity : {quantity}")

    # ============================================
    # CONFIRM
    # ============================================

    confirm = input(
        "\nPlace BUY Market Order? (y/n): "
    ).strip().lower()

    if confirm != "y":

        print("Cancelled.")

        return

    # ============================================
    # PLACE ORDER
    # ============================================

    result = order_manager.buy(
        DEFAULT_SYMBOL
    )

    print("\n" + "=" * 60)
    print("ORDER RESPONSE")
    print("=" * 60)

    print(result)


if __name__ == "__main__":
    main()