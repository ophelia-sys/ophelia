import time

from config import (
    CHECK_INTERVAL,
    DEFAULT_SYMBOL,
    LIVE_TRADING,
    TIMEFRAME,
)
from exchange.bingx_client import BingXClient
from exchange.market_data import MarketData
from exchange.order_manager import OrderManager
from portfolio.position_manager import PositionManager
from strategies.strategy_factory import StrategyFactory


def main():

    client = BingXClient()
    market = MarketData(client)
    position_manager = PositionManager(client)
    order_manager = OrderManager(client)
    strategy = StrategyFactory.create()

    last_processed_candle = None

    print("=" * 60)
    print("EMA BOT STARTED")
    print(f"MODE : {'LIVE' if LIVE_TRADING else 'SIMULATION'}")
    print("=" * 60)

    while True:

        try:

            candles = market.get_klines(
                symbol=DEFAULT_SYMBOL,
                interval=TIMEFRAME,
                limit=200
            )

            closed_candle = candles["timestamp"].iloc[-2]

            if last_processed_candle is not None and closed_candle == last_processed_candle:
                time.sleep(CHECK_INTERVAL)
                continue

            last_processed_candle = closed_candle

            signal_data = strategy.get_signal(candles)
            signal = signal_data["signal"]

            strategy.print_status(candles)

            print(f"Candle : {closed_candle}")
            print(f"Signal : {signal_data}")

            position = position_manager.get_position(DEFAULT_SYMBOL)

            if signal == "HOLD":
                print("No action.")

            elif position is None:

                if signal == "BUY":
                    print("OPEN LONG")
                    if LIVE_TRADING:
                        print(order_manager.open_long(DEFAULT_SYMBOL))
                    else:
                        print("SIMULATION: OPEN LONG")

                elif signal == "SELL":
                    print("OPEN SHORT")
                    if LIVE_TRADING:
                        print(order_manager.open_short(DEFAULT_SYMBOL))
                    else:
                        print("SIMULATION: OPEN SHORT")

            else:

                side = position.side.value

                if side == "LONG" and signal == "SELL":

                    print("REVERSE LONG -> SHORT")

                    if LIVE_TRADING:
                        print(order_manager.close_long(DEFAULT_SYMBOL))
                        time.sleep(1)
                        print(order_manager.open_short(DEFAULT_SYMBOL))
                    else:
                        print("SIMULATION: CLOSE LONG")
                        print("SIMULATION: OPEN SHORT")

                elif side == "SHORT" and signal == "BUY":

                    print("REVERSE SHORT -> LONG")

                    if LIVE_TRADING:
                        print(order_manager.close_short(DEFAULT_SYMBOL))
                        time.sleep(1)
                        print(order_manager.open_long(DEFAULT_SYMBOL))
                    else:
                        print("SIMULATION: CLOSE SHORT")
                        print("SIMULATION: OPEN LONG")

                else:
                    print(f"HOLD {side}")

            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("\nBot stopped.")
            break

        except Exception as e:
            print("\nERROR:", e)
            time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()