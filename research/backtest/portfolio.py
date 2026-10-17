from typing import List, Dict, Any

class PortfolioSimulation:
    """
    Simulates positional accounting for backtests.
    Tracks realized and unrealized PnL and deducts fees.
    """
    def __init__(self, initial_capital: float = 10000.0):
        self.capital = initial_capital
        self.realized_pnl = 0.0
        self.current_position = 0.0
        self.average_entry_price = 0.0
        self.total_fees = 0.0
        self.total_slippage = 0.0
        
        self.trade_history: List[Dict[str, Any]] = []

    def execute_trade(self, timestamp: int, side: str, price: float, quantity: float, cost_config):
        """
        Executes a simulated trade, updates inventory and PnL.
        """
        # Calculate costs for this leg
        notional = price * quantity
        fee_rate = cost_config.entry_fee if self.current_position == 0 else cost_config.exit_fee
        slip_rate = cost_config.entry_slippage if self.current_position == 0 else cost_config.exit_slippage
        
        fee_amount = notional * fee_rate
        slip_amount = notional * slip_rate
        
        self.total_fees += fee_amount
        self.total_slippage += slip_amount
        
        # Deduct costs immediately from capital
        self.capital -= (fee_amount + slip_amount)
        
        if side == "BUY":
            if self.current_position < 0:
                # Closing a short
                closing_qty = min(quantity, abs(self.current_position))
                pnl = (self.average_entry_price - price) * closing_qty
                self.realized_pnl += pnl
                self.capital += pnl
                
                self.current_position += closing_qty
                remaining_qty = quantity - closing_qty
                
                if remaining_qty > 0:
                    # Flipped to long
                    self.current_position = remaining_qty
                    self.average_entry_price = price
            else:
                # Adding to long
                new_notional = (abs(self.current_position) * self.average_entry_price) + (quantity * price)
                self.current_position += quantity
                self.average_entry_price = new_notional / abs(self.current_position)
                
        elif side == "SELL":
            if self.current_position > 0:
                # Closing a long
                closing_qty = min(quantity, self.current_position)
                pnl = (price - self.average_entry_price) * closing_qty
                self.realized_pnl += pnl
                self.capital += pnl
                
                self.current_position -= closing_qty
                remaining_qty = quantity - closing_qty
                
                if remaining_qty > 0:
                    # Flipped to short
                    self.current_position = -remaining_qty
                    self.average_entry_price = price
            else:
                # Adding to short
                new_notional = (abs(self.current_position) * self.average_entry_price) + (quantity * price)
                self.current_position -= quantity
                self.average_entry_price = new_notional / abs(self.current_position)

        self.trade_history.append({
            "timestamp": timestamp,
            "side": side,
            "price": price,
            "quantity": quantity,
            "fees": fee_amount,
            "slippage": slip_amount
        })

    def get_unrealized_pnl(self, current_price: float) -> float:
        if self.current_position == 0:
            return 0.0
        if self.current_position > 0:
            return (current_price - self.average_entry_price) * self.current_position
        else:
            return (self.average_entry_price - current_price) * abs(self.current_position)
