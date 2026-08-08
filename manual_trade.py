from config import DEFAULT_SYMBOL, LEVERAGE, MARGIN_USDT
from core.enums import OrderSide, OrderType, PositionSide
from exchange.bingx_client import BingXClient
from models.order_request import OrderRequest


def main():

    client = BingXClient()

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
    available_balance = float(balance.available_margin)

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

    contract = client.get_contract(DEFAULT_SYMBOL)
    if contract is None:
        print("Contract not found.")
        return

    price = float(client.get_latest_price(DEFAULT_SYMBOL))
    quantity = (MARGIN_USDT * LEVERAGE) / price
    quantity = max(quantity, contract.min_quantity)
    quantity = round(quantity, contract.quantity_precision)

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

    request = OrderRequest(
        symbol=DEFAULT_SYMBOL,
        side=OrderSide.BUY,
        position_side=PositionSide.LONG,
        order_type=OrderType.MARKET,
        quantity=quantity,
    )
    result = client.place_order(request)

    print("\n" + "=" * 60)
    print("ORDER RESPONSE")
    print("=" * 60)

    print(result)


if __name__ == "__main__":
    main()