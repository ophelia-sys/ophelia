import time

from brokers.broker import Broker
from config import MAX_OPEN_POSITIONS, USE_TRAILING_STOP
from core.errors import BingXNetworkError
from core.trade import Trade
from exchange.order_manager import OrderManager
from utils.logger import logger


class BingXBroker(Broker):

    def __init__(
        self,
        client,
        position_manager,
        trade_journal,
    ):
        self.client = client
        self.position_manager = position_manager
        self.trade_journal = trade_journal
        self.order_manager = OrderManager(client)
        self.stop_prices = {}
        self.locked_profits = {}
        self.last_signal_guard = {}
        self.pending_intents = {}
        self._bootstrap_existing_positions()

    def _bootstrap_existing_positions(self):
        positions = self.position_manager.get_positions()
        for position in positions:
            self.stop_prices[position.symbol] = None
            self.locked_profits[position.symbol] = 0.0

    def get_protected_symbols(self, watchlist):
        symbols = set(watchlist)
        for position in self.position_manager.get_positions():
            symbols.add(position.symbol)
        symbols.update(self.stop_prices.keys())
        return list(symbols)

    def _refresh_position(self, symbol):
        return self.position_manager.get_position(symbol)

    def _ensure_initial_stop(self, symbol, position, risk_manager):
        if (
            risk_manager is None
            or position is None
        ):
            return
        if (
            symbol in self.stop_prices
            and self.stop_prices[symbol] is not None
        ):
            return
        self.stop_prices[symbol] = risk_manager.calculate_initial_stop(
            position.entry_price,
            position.side.value,
        )
        self.locked_profits[symbol] = 0.0

    def _update_trailing_stop(self, symbol, position, price, risk_manager):
        if (
            position is None
            or risk_manager is None
            or not USE_TRAILING_STOP
        ):
            return
        stop_price = self.stop_prices.get(symbol)
        if stop_price is None:
            return
        trail = risk_manager.next_stop(
            entry_price=position.entry_price,
            current_price=price,
            side=position.side.value,
            current_locked_profit=self.locked_profits.get(symbol, 0.0),
        )
        candidate_stop = trail.get("stop_price")
        if not trail.get("move_stop") or candidate_stop is None:
            return
        if (
            (position.side.value == "LONG" and candidate_stop > stop_price)
            or (position.side.value == "SHORT" and candidate_stop < stop_price)
        ):
            self.stop_prices[symbol] = candidate_stop
            self.locked_profits[symbol] = trail.get(
                "candidate_locked_profit",
                self.locked_profits.get(symbol, 0.0),
            )

    def _close_if_stop_hit(self, symbol, position, price, pending_side):
        stop_price = self.stop_prices.get(symbol)
        if position is None or stop_price is None:
            return False
        if pending_side is not None and pending_side != position.side.value:
            return False
        if position.side.value == "LONG" and price <= stop_price:
            self._close_position(symbol, "LONG", "STOP_LOSS")
            return True
        if position.side.value == "SHORT" and price >= stop_price:
            self._close_position(symbol, "SHORT", "STOP_LOSS")
            return True
        return False

    def _safe_order_call(
        self,
        symbol: str,
        action,
        expected_side_after: str | None,
        client_order_id: str,
    ):
        try:
            return action()
        except BingXNetworkError:
            # Ambiguous order state: reconcile against exchange before
            # allowing any subsequent order attempt.
            exchange_order = None
            try:
                exchange_order = self.client.get_order(
                    symbol=symbol,
                    client_order_id=client_order_id,
                )
            except Exception:
                exchange_order = None

            if (
                exchange_order is not None
                and exchange_order.position_side.value == expected_side_after
            ):
                return exchange_order

            reconciled = self._refresh_position(symbol)
            if expected_side_after is None:
                if reconciled is None:
                    return None
            elif (
                reconciled is not None
                and reconciled.side.value == expected_side_after
            ):
                return None

            self.pending_intents[symbol] = {
                "client_order_id": client_order_id,
                "side": expected_side_after,
                "updated_at": self._event_timestamp(),
            }
            raise

    @staticmethod
    def _event_timestamp():
        return int(time.time() * 1000)

    @staticmethod
    def _intent_id(symbol: str, side: str, timestamp: int):
        normalized = symbol.replace("-", "").lower()
        return f"ophelia-{normalized}-{side.lower()}-{timestamp}"

    def _reconcile_pending_intent(self, symbol: str):
        pending = self.pending_intents.get(symbol)
        if pending is None:
            return None

        side = pending["side"]
        client_order_id = pending["client_order_id"]
        order_confirmed = False
        try:
            order = self.client.get_order(
                symbol=symbol,
                client_order_id=client_order_id,
            )
            order_confirmed = (
                order is not None
                and order.position_side.value == side
            )
        except Exception:
            order_confirmed = False

        position = self._refresh_position(symbol)
        position_matches = (
            position is not None
            and side is not None
            and position.side.value == side
        )

        if order_confirmed or position_matches:
            if side is None:
                if position is None:
                    self.pending_intents.pop(symbol, None)
                    return "confirmed"
                return "pending"
            if position_matches:
                self.pending_intents.pop(symbol, None)
                return "confirmed"
            return "pending"

        return "pending"

    def _open_position(
        self,
        symbol,
        target_side,
        event_timestamp,
        risk_manager=None,
        margin=None,
        leverage=None,
    ):
        client_order_id = self._intent_id(
            symbol=symbol,
            side=target_side,
            timestamp=event_timestamp,
        )
        if target_side == "LONG":
            response = self._safe_order_call(
                symbol,
                lambda: self.order_manager.open_long(
                    symbol,
                    client_order_id=client_order_id,
                    margin=margin,
                    leverage=leverage,
                ),
                "LONG",
                client_order_id,
            )
        else:
            response = self._safe_order_call(
                symbol,
                lambda: self.order_manager.open_short(
                    symbol,
                    client_order_id=client_order_id,
                    margin=margin,
                    leverage=leverage,
                ),
                "SHORT",
                client_order_id,
            )
        if (
            response is not None
            and hasattr(response, "position_side")
            and response.position_side.value != target_side
        ):
            raise RuntimeError(
                f"Order response side mismatch for {symbol}"
            )
        position = self._refresh_position(symbol)
        if position is None:
            # Exchange may accept order before position snapshot updates.
            self.pending_intents[symbol] = {
                "client_order_id": client_order_id,
                "side": target_side,
                "updated_at": self._event_timestamp(),
            }
            logger.warning(
                f"Open reconciliation pending for {symbol} -> {target_side}"
            )
            return response
        if position.side.value != target_side:
            raise RuntimeError(
                f"Open reconciliation failed for {symbol} -> {target_side}"
            )
        self.pending_intents.pop(symbol, None)
        self.stop_prices.pop(symbol, None)
        self.locked_profits.pop(symbol, None)
        if risk_manager is not None:
            self.stop_prices[symbol] = risk_manager.calculate_initial_stop(
                position.entry_price,
                position.side.value,
            )
            self.locked_profits[symbol] = 0.0
        self.trade_journal.save_trade(
            Trade(
                symbol=position.symbol,
                side=position.side.value,
                entry_price=position.entry_price,
                exit_price=position.entry_price,
                quantity=position.quantity,
                leverage=position.leverage,
                entry_time=event_timestamp,
                exit_time=event_timestamp,
                pnl_percent=0.0,
                pnl_amount=0.0,
                status="OPEN",
            )
        )
        return response

    def _close_position(self, symbol, current_side, status="CLOSED"):
        existing = self._refresh_position(symbol)
        if existing is None:
            return
        if current_side == "LONG":
            self._safe_order_call(
                symbol,
                lambda: self.order_manager.close_long(symbol),
                None,
                self._intent_id(
                    symbol=symbol,
                    side="close-long",
                    timestamp=self._event_timestamp(),
                ),
            )
        else:
            self._safe_order_call(
                symbol,
                lambda: self.order_manager.close_short(symbol),
                None,
                self._intent_id(
                    symbol=symbol,
                    side="close-short",
                    timestamp=self._event_timestamp(),
                ),
            )
        position = self._refresh_position(symbol)
        if position is not None:
            raise RuntimeError(
                f"Close reconciliation failed for {symbol}"
            )
        if current_side == "LONG":
            pnl_percent = (
                (self._last_price - existing.entry_price)
                / existing.entry_price
            ) * 100
        else:
            pnl_percent = (
                (existing.entry_price - self._last_price)
                / existing.entry_price
            ) * 100
        pnl_amount = (
            (pnl_percent / 100)
            * existing.entry_price
            * existing.quantity
        )
        self.trade_journal.save_trade(
            Trade(
                symbol=existing.symbol,
                side=existing.side.value,
                entry_price=existing.entry_price,
                exit_price=self._last_price,
                quantity=existing.quantity,
                leverage=existing.leverage,
                entry_time=self._event_timestamp(),
                exit_time=self._event_timestamp(),
                pnl_percent=round(pnl_percent, 4),
                pnl_amount=round(pnl_amount, 4),
                status=status,
            )
        )
        self.stop_prices.pop(symbol, None)
        self.locked_profits.pop(symbol, None)

    def _partial_close_position(
        self,
        symbol,
        current_side,
        close_quantity,
        status="PARTIAL_EXIT",
    ):
        timestamp = int(time.time())
        client_order_id = self._intent_id(
            symbol=symbol,
            side=f"PARTIAL_{current_side}",
            timestamp=timestamp,
        )
        if current_side == "LONG":
            response = self._safe_order_call(
                symbol,
                lambda: self.order_manager.close_long(
                    symbol,
                    quantity=close_quantity,
                    client_order_id=client_order_id,
                ),
                "LONG",
                client_order_id,
            )
        else:
            response = self._safe_order_call(
                symbol,
                lambda: self.order_manager.close_short(
                    symbol,
                    quantity=close_quantity,
                    client_order_id=client_order_id,
                ),
                "SHORT",
                client_order_id,
            )

        pos = self.position_manager.get_position(symbol)
        if pos:
            entry_price = pos.entry_price
            exit_price = getattr(pos, "mark_price", entry_price)
            if current_side == "LONG":
                pnl_percent = ((exit_price - entry_price) / entry_price) * 100.0
            else:
                pnl_percent = ((entry_price - exit_price) / entry_price) * 100.0
            pnl_amount = (pnl_percent / 100.0) * entry_price * close_quantity
            self.trade_journal.save_trade(
                Trade(
                    symbol=symbol,
                    side=current_side,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    quantity=round(close_quantity, 6),
                    leverage=pos.leverage,
                    entry_time=timestamp,
                    exit_time=timestamp,
                    pnl_percent=round(pnl_percent, 4),
                    pnl_amount=round(pnl_amount, 4),
                    status=status,
                )
            )

    def process_signal(self, signal, risk_manager=None, margin=None, leverage=None, risk_config=None):
        symbol = signal.get("symbol", "UNKNOWN")
        signal_type = signal.get("signal", "HOLD")
        price = float(signal.get("price", 0.0))
        timestamp = int(signal.get("timestamp", 0))
        self._last_price = price
        side = None
        if signal_type == "BUY":
            side = "LONG"
        elif signal_type == "SELL":
            side = "SHORT"

        logger.info(f"{symbol} -> {signal_type}")

        if price <= 0:
            raise ValueError(f"Invalid price for {symbol}: {price}")

        pending_state = self._reconcile_pending_intent(symbol)
        if pending_state == "pending":
            logger.warning(
                f"Pending order reconciliation for {symbol}; "
                "new submission blocked."
            )
            return

        current = self._refresh_position(symbol)

        # Apply advanced risk management if position exists
        if current is not None:
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

            cur_side = current.side.value if hasattr(current.side, "value") else str(current.side)
            if symbol not in self.stop_prices:
                sl_price = RiskManager.calculate_sl_price(
                    current.entry_price,
                    cur_side,
                    cfg.get("sl_mode", "PRICE_PERCENT"),
                    cfg.get("sl_value", 1.0),
                    quantity=current.quantity,
                )
                self.stop_prices[symbol] = sl_price

        self._ensure_initial_stop(symbol, current, risk_manager)
        self._update_trailing_stop(symbol, current, price, risk_manager)
        if self._close_if_stop_hit(symbol, current, price, side):
            return

        if signal_type == "HOLD":
            return

        if side is None:
            return
        target_side = side

        guard = self.last_signal_guard.get(symbol)
        if guard == (signal_type, timestamp):
            return
        self.last_signal_guard[symbol] = (signal_type, timestamp)

        current = self._refresh_position(symbol)
        if current is not None and current.side.value == target_side:
            return

        if current is not None:
            self._close_position(symbol, current.side.value)
        else:
            open_count = len(self.position_manager.get_positions())
            if open_count >= MAX_OPEN_POSITIONS:
                return

        self._open_position(
            symbol,
            target_side,
            timestamp,
            risk_manager,
            margin=margin,
            leverage=leverage,
        )

    def get_open_positions(self):
        return self.position_manager.get_positions()

    def emergency_close_all(self):
        logger.warning("Emergency close-all requested for live positions.")
        return self.client.close_all_positions()