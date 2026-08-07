from config import PAPER_STARTING_BALANCE
from utils.logger import logger


class PortfolioManager:

    def __init__(self):

        self.starting_balance = PAPER_STARTING_BALANCE
        self.balance = PAPER_STARTING_BALANCE

        self.realized_pnl = 0.0
        self.unrealized_pnl = 0.0

        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0

    def record_trade(self, pnl_amount):

        self.realized_pnl += pnl_amount
        self.balance += pnl_amount
        self.total_trades += 1

        if pnl_amount > 0:
            self.winning_trades += 1
        elif pnl_amount < 0:
            self.losing_trades += 1

        logger.info(
            f"Portfolio Updated | Balance: {self.balance:.2f} USDT"
        )

    def update_unrealized(self, pnl):

        self.unrealized_pnl = pnl

    def get_equity(self):

        return self.balance + self.unrealized_pnl

    def get_win_rate(self):

        if self.total_trades == 0:
            return 0.0

        return round(
            (self.winning_trades / self.total_trades) * 100,
            2
        )

    def summary(self):

        return {
            "Starting Balance": round(self.starting_balance, 2),
            "Balance": round(self.balance, 2),
            "Equity": round(self.get_equity(), 2),
            "Realized PnL": round(self.realized_pnl, 2),
            "Unrealized PnL": round(self.unrealized_pnl, 2),
            "Trades": self.total_trades,
            "Wins": self.winning_trades,
            "Losses": self.losing_trades,
            "Win Rate": self.get_win_rate()
        }