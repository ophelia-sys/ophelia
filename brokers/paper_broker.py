from brokers.broker import Broker
from config import LEVERAGE, MARGIN_USDT, MAX_OPEN_POSITIONS, USE_TRAILING_STOP
from core.trade import Trade
from risk.risk_manager import RiskManager
from utils.logger import logger


class PaperBroker(Broker):

    def __init__(
        self,
        position_manager,
        trade_journal
    ):

        self.position_manager = position_manager
        self.trade_journal = trade_journal
        self.stop_prices = {}
        self.locked_profits = {}
        self.position_states = {}

    def _close_and_record_trade(
        self,
        symbol,
        exit_price,
        exit_time,
        status,
    ):
        closed = self.position_manager.close_position(
            symbol,
            exit_price,
        )
        if closed is None:
            return

        self.stop_prices.pop(symbol, None)
        self.locked_profits.pop(symbol, None)
        self.position_states.pop(symbol, None)

        if closed.side == "LONG":
            pnl_percent = (
                (exit_price - closed.entry_price)
                / closed.entry_price
            ) * 100
        else:
            pnl_percent = (
                (closed.entry_price - exit_price)
                / closed.entry_price
            ) * 100

        pnl_amount = (
            (pnl_percent / 100)
            * closed.entry_price
            * closed.quantity
        )

        self.trade_journal.save_trade(
            Trade(
                symbol=closed.symbol,
                side=closed.side,
                entry_price=closed.entry_price,
                exit_price=exit_price,
                quantity=round(closed.quantity, 6),
                leverage=closed.leverage,
                entry_time=closed.entry_time,
                exit_time=exit_time,
                pnl_percent=round(pnl_percent, 4),
                pnl_amount=round(pnl_amount, 4),
                status=status,
            )
        )

    def _partial_close_and_record_trade(
        self,
        symbol,
        exit_price,
        exit_time,
        quantity,
        status,
    ):
        pos = self.position_manager.get_position(symbol)
        if pos is None:
            return

        close_qty = min(quantity, pos.quantity)
        if close_qty <= 0:
            return

        if pos.side == "LONG":
            pnl_percent = ((exit_price - pos.entry_price) / pos.entry_price) * 100.0
        else:
            pnl_percent = ((pos.entry_price - exit_price) / pos.entry_price) * 100.0

        pnl_amount = (pnl_percent / 100.0) * pos.entry_price * close_qty

        self.trade_journal.save_trade(
            Trade(
                symbol=symbol,
                side=pos.side,
                entry_price=pos.entry_price,
                exit_price=exit_price,
                quantity=round(close_qty, 6),
                leverage=pos.leverage,
                entry_time=pos.entry_time,
                exit_time=exit_time,
                pnl_percent=round(pnl_percent, 4),
                pnl_amount=round(pnl_amount, 4),
                status=status,
            )
        )

        pos.quantity -= close_qty
        state = self.position_states.get(symbol)
        if state:
            state["remaining_quantity"] = max(0.0, state.get("remaining_quantity", close_qty) - close_qty)

        if pos.quantity <= 1e-8:
            self.position_manager.close_position(symbol, exit_price)
            self.stop_prices.pop(symbol, None)
            self.locked_profits.pop(symbol, None)
            self.position_states.pop(symbol, None)

    def process_signal(self, signal, risk_manager=None, margin=None, leverage=None, risk_config=None):

        symbol = signal.get("symbol", "UNKNOWN")
        signal_type = signal.get("signal", "HOLD")
        price = float(signal.get("price", 0.0))
        entry_time = signal.get("timestamp", 0)
        margin_val = float(margin) if margin is not None else MARGIN_USDT
        leverage_val = int(leverage) if leverage is not None else LEVERAGE
        side = None
        if signal_type == "BUY":
            side = "LONG"
        elif signal_type == "SELL":
            side = "SHORT"

        logger.info(f"{symbol} -> {signal_type}")

        current = self.position_manager.get_position(symbol)
        if current is not None:
            self.position_manager.update_price(symbol, price)

            # Retrieve active risk configuration
            cfg = risk_config
            if cfg is None and hasattr(risk_manager, "get_risk_config"):
                cfg = risk_manager.get_risk_config(symbol)
            if cfg is None:
                cfg = {
                    "sl_mode": "PRICE_PERCENT",
                    "sl_value": 1.0,
                    "tp_mode": "PRICE_PERCENT",
                    "tp_value": 2.0,
                    "trailing_activation": 1.0,
                    "trailing_buffer": 0.8,
                    "exit_plan": [{"pct": 100.0, "type": "trailing"}],
                }

            # Initialize position state tracking if not existing
            if symbol not in self.position_states:
                sl_price = RiskManager.calculate_sl_price(
                    current.entry_price,
                    current.side,
                    cfg.get("sl_mode", "PRICE_PERCENT"),
                    cfg.get("sl_value", 1.0),
                    quantity=current.quantity,
                )
                tp_price = RiskManager.calculate_tp_price(
                    current.entry_price,
                    current.side,
                    cfg.get("tp_mode", "PRICE_PERCENT"),
                    cfg.get("tp_value", 2.0),
                    quantity=current.quantity,
                )
                legs = []
                for leg in cfg.get("exit_plan", [{"pct": 100.0, "type": "trailing"}]):
                    leg_qty = round(current.quantity * (leg["pct"] / 100.0), 6)
                    legs.append({
                        "pct": leg["pct"],
                        "type": leg["type"],
                        "target_pct": leg.get("target_pct"),
                        "qty": leg_qty,
                        "executed": False,
                    })

                self.position_states[symbol] = {
                    "original_quantity": current.quantity,
                    "remaining_quantity": current.quantity,
                    "favorable_price": price,
                    "sl_price": sl_price,
                    "tp_price": tp_price,
                    "trailing_stop": None,
                    "exit_legs": legs,
                    "risk_config": cfg,
                }
                self.stop_prices[symbol] = sl_price

            state = self.position_states[symbol]
            # Update favorable price (highest for LONG, lowest for SHORT)
            if current.side == "LONG":
                state["favorable_price"] = max(state.get("favorable_price", price), price)
            else:
                state["favorable_price"] = min(state.get("favorable_price", price), price)

            # 1. Check Stop Loss
            sl_price = state.get("sl_price")
            if sl_price is not None and (
                (current.side == "LONG" and price <= sl_price)
                or (current.side == "SHORT" and price >= sl_price)
            ):
                self._close_and_record_trade(
                    symbol=symbol,
                    exit_price=price,
                    exit_time=entry_time,
                    status="STOP_LOSS",
                )
                return

            # 2. Process Exit Legs (TP and Trailing)
            profit_pct = RiskManager.calculate_profit_percent(current.entry_price, price, current.side)
            for leg in state.get("exit_legs", []):
                if leg["executed"]:
                    continue

                if leg["type"] == "tp":
                    target_pct = leg.get("target_pct")
                    if target_pct is not None and profit_pct >= target_pct:
                        leg["executed"] = True
                        status_str = "PARTIAL_TP" if state["remaining_quantity"] > leg["qty"] else "TAKE_PROFIT"
                        self._partial_close_and_record_trade(
                            symbol=symbol,
                            exit_price=price,
                            exit_time=entry_time,
                            quantity=leg["qty"],
                            status=status_str,
                        )
                        if self.position_manager.get_position(symbol) is None:
                            return

                elif leg["type"] == "trailing":
                    act = cfg.get("trailing_activation", 1.0)
                    buf = cfg.get("trailing_buffer", 0.8)
                    trail_stop = RiskManager.calculate_trailing_stop(
                        entry_price=current.entry_price,
                        favorable_price=state["favorable_price"],
                        side=current.side,
                        trailing_activation=act,
                        trailing_buffer=buf,
                        current_stop=state.get("trailing_stop"),
                    )
                    if trail_stop is not None:
                        state["trailing_stop"] = trail_stop
                        self.stop_prices[symbol] = trail_stop
                        if (current.side == "LONG" and price <= trail_stop) or (current.side == "SHORT" and price >= trail_stop):
                            leg["executed"] = True
                            status_str = "PARTIAL_TRAILING" if state["remaining_quantity"] > leg["qty"] else "TRAILING_STOP"
                            self._partial_close_and_record_trade(
                                symbol=symbol,
                                exit_price=price,
                                exit_time=entry_time,
                                quantity=leg["qty"],
                                status=status_str,
                            )
                            if self.position_manager.get_position(symbol) is None:
                                return

        if signal_type == "HOLD":
            return

        if side is None:
            return

        if current is not None and current.side == side:
            return

        if current is None and self.position_manager.count() >= MAX_OPEN_POSITIONS:
            return

        if current is not None:
            self._close_and_record_trade(
                symbol=symbol,
                exit_price=price,
                exit_time=entry_time,
                status="CLOSED",
            )

        if price <= 0:
            return

        quantity = (margin_val * leverage_val) / price
        self.position_manager.open_position(
            symbol=symbol,
            side=side,
            price=price,
            quantity=quantity,
            leverage=leverage_val,
            entry_time=entry_time,
        )

        cfg = risk_config
        if cfg is None and hasattr(risk_manager, "get_risk_config"):
            cfg = risk_manager.get_risk_config(symbol)
        if cfg is None:
            cfg = {
                "sl_mode": "PRICE_PERCENT",
                "sl_value": 1.0,
                "tp_mode": "PRICE_PERCENT",
                "tp_value": 2.0,
                "trailing_activation": 1.0,
                "trailing_buffer": 0.8,
                "exit_plan": [{"pct": 100.0, "type": "trailing"}],
            }

        sl_price = RiskManager.calculate_sl_price(
            price,
            side,
            cfg.get("sl_mode", "PRICE_PERCENT"),
            cfg.get("sl_value", 1.0),
            quantity=quantity,
        )
        tp_price = RiskManager.calculate_tp_price(
            price,
            side,
            cfg.get("tp_mode", "PRICE_PERCENT"),
            cfg.get("tp_value", 2.0),
            quantity=quantity,
        )

        legs = []
        for leg in cfg.get("exit_plan", [{"pct": 100.0, "type": "trailing"}]):
            leg_qty = round(quantity * (leg["pct"] / 100.0), 6)
            legs.append({
                "pct": leg["pct"],
                "type": leg["type"],
                "target_pct": leg.get("target_pct"),
                "qty": leg_qty,
                "executed": False,
            })

        self.position_states[symbol] = {
            "original_quantity": quantity,
            "remaining_quantity": quantity,
            "favorable_price": price,
            "sl_price": sl_price,
            "tp_price": tp_price,
            "trailing_stop": None,
            "exit_legs": legs,
            "risk_config": cfg,
        }
        self.stop_prices[symbol] = sl_price

        self.trade_journal.save_trade(
            Trade(
                symbol=symbol,
                side=side,
                entry_price=price,
                exit_price=price,
                quantity=quantity,
                leverage=leverage_val,
                entry_time=entry_time,
                exit_time=entry_time,
                pnl_percent=0.0,
                pnl_amount=0.0,
                status="OPEN",
            )
        )

    def get_open_positions(self):

        return self.position_manager.get_all_positions()

    def get_protected_symbols(self, watchlist):
        symbols = set(watchlist)
        symbols.update(self.position_manager.get_all_positions().keys())
        symbols.update(self.stop_prices.keys())
        return list(symbols)

    def emergency_close_all(self):
        closed_symbols = list(self.position_manager.get_all_positions().keys())
        for symbol in closed_symbols:
            position = self.position_manager.get_position(symbol)
            if position is None:
                continue
            self._close_and_record_trade(
                symbol=symbol,
                exit_price=position.current_price,
                exit_time=position.entry_time,
                status="EMERGENCY_CLOSE",
            )
        return {"closed": closed_symbols}