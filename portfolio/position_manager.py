class PositionManager:

    def __init__(self, client):

        self.client = client

    # =====================================================
    # GET ALL POSITIONS
    # =====================================================

    def get_positions(self, symbol=None):

        response = self.client.get_positions(symbol)

        if response["code"] != 0:
            raise Exception(response)

        positions = []

        for position in response["data"]:

            if float(position["positionAmt"]) == 0:
                continue

            positions.append(position)

        return positions

    # =====================================================
    # GET ACTIVE POSITION
    # =====================================================

    def get_position(self, symbol):

        positions = self.get_positions(symbol)

        if len(positions) == 0:
            return None

        return positions[0]

    # =====================================================
    # HAS POSITION
    # =====================================================

    def has_position(self, symbol):

        return self.get_position(symbol) is not None

    # =====================================================
    # IS LONG
    # =====================================================

    def is_long(self, symbol):

        position = self.get_position(symbol)

        if position is None:
            return False

        return position["positionSide"] == "LONG"

    # =====================================================
    # IS SHORT
    # =====================================================

    def is_short(self, symbol):

        position = self.get_position(symbol)

        if position is None:
            return False

        return position["positionSide"] == "SHORT"

    # =====================================================
    # PRINT POSITION
    # =====================================================

    def print_position(self, symbol):

        position = self.get_position(symbol)

        print("\n" + "=" * 60)
        print("CURRENT POSITION")
        print("=" * 60)

        if position is None:
            print("No Open Position")
            return

        print(f"Symbol       : {position['symbol']}")
        print(f"Side         : {position['positionSide']}")
        print(f"Quantity     : {position['positionAmt']}")
        print(f"Entry Price  : {position['avgPrice']}")
        print(f"Mark Price   : {position.get('markPrice', 'N/A')}")
        print(f"PnL          : {position['unrealizedProfit']}")
        print(f"Leverage     : {position['leverage']}x")
        print(f"Liquidation  : {position['liquidationPrice']}")