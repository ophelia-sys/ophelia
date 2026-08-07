from datetime import datetime


class Logger:

    @staticmethod
    def _timestamp():

        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def line(char="-", length=60):

        print(char * length)

    @staticmethod
    def title(text):

        print()
        Logger.line("=")
        print(text.upper())
        Logger.line("=")

    @staticmethod
    def section(text):

        print()
        Logger.line("-")
        print(text)
        Logger.line("-")

    @staticmethod
    def info(message):

        print(
            f"[{Logger._timestamp()}] [INFO] {message}"
        )

    @staticmethod
    def success(message):

        print(
            f"[{Logger._timestamp()}] [SUCCESS] {message}"
        )

    @staticmethod
    def warning(message):

        print(
            f"[{Logger._timestamp()}] [WARNING] {message}"
        )

    @staticmethod
    def error(message):

        print(
            f"[{Logger._timestamp()}] [ERROR] {message}"
        )

    @staticmethod
    def trade(action, symbol, side):

        print(
            f"[{Logger._timestamp()}] "
            f"[TRADE] "
            f"{action} "
            f"{side} "
            f"{symbol}"
        )

    @staticmethod
    def position(
        symbol,
        side,
        entry,
        current,
        profit,
    ):

        Logger.section("POSITION")

        print(f"Symbol          : {symbol}")
        print(f"Side            : {side}")
        print(f"Entry Price     : {entry}")
        print(f"Current Price   : {current}")
        print(f"Move (%)        : {profit:.2f}")

    @staticmethod
    def trailing(
        current_profit,
        old_stop,
        new_stop,
    ):

        Logger.section("TRAILING STOP")

        print(f"Current Profit  : {current_profit:.2f}%")
        print(f"Previous Stop   : {old_stop:.2f}%")
        print(f"New Stop        : {new_stop:.2f}%")

    @staticmethod
    def signal(
        signal,
        fast,
        slow,
        candle,
    ):

        Logger.section("EMA SIGNAL")

        print(f"Signal          : {signal}")
        print(f"EMA Fast        : {fast:.4f}")
        print(f"EMA Slow        : {slow:.4f}")
        print(f"Candle          : {candle}")