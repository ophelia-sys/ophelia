class PositionManager:

    def __init__(self, client):

        self.client = client

    # =====================================================
    # GET ALL POSITIONS
    # =====================================================

    def get_positions(self, symbol=None):

        positions = self.client.get_positions(symbol)

        return [
            position
            for position in positions
            if position.quantity > 0
        ]

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

        return position.is_long

    # =====================================================
    # IS SHORT
    # =====================================================

    def is_short(self, symbol):

        position = self.get_position(symbol)

        if position is None:
            return False

        return position.is_short

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

        print(f"Symbol       : {position.symbol}")
        print(f"Side         : {position.side.value}")
        print(f"Quantity     : {position.quantity}")
        print(f"Entry Price  : {position.entry_price}")
        print(f"Mark Price   : {position.mark_price}")
        print(f"PnL          : {position.unrealized_pnl}")
        print(f"Leverage     : {position.leverage}x")
        print(f"Liquidation  : {position.liquidation_price}")