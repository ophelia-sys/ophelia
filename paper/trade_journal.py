import csv
import os

from utils.logger import logger


class TradeJournal:

    FILE_NAME = "data/trades.csv"

    def __init__(self):

        os.makedirs("data", exist_ok=True)

        if not os.path.exists(self.FILE_NAME):

            with open(self.FILE_NAME, "w", newline="") as file:

                writer = csv.writer(file)

                writer.writerow([
                    "Symbol",
                    "Side",
                    "Entry Price",
                    "Exit Price",
                    "Quantity",
                    "Leverage",
                    "Entry Time",
                    "Exit Time",
                    "PnL %",
                    "PnL Amount",
                    "Status"
                ])

    def save_trade(self, trade):

        with open(self.FILE_NAME, "a", newline="") as file:

            writer = csv.writer(file)

            writer.writerow([

                trade.symbol,

                trade.side,

                trade.entry_price,

                trade.exit_price,

                trade.quantity,

                trade.leverage,

                trade.entry_time,

                trade.exit_time,

                trade.pnl_percent,

                trade.pnl_amount,

                trade.status

            ])

        logger.info(
            f"Trade saved -> {trade.symbol}"
        )