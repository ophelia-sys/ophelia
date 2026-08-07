class PnLCalculator:

    @staticmethod
    def calculate(position):

        if position.side == "LONG":

            pnl_amount = (
                position.current_price
                - position.entry_price
            ) * position.quantity

        else:

            pnl_amount = (
                position.entry_price
                - position.current_price
            ) * position.quantity

        pnl_percent = (
            pnl_amount
            / (position.entry_price * position.quantity)
        ) * 100

        return pnl_percent, pnl_amount