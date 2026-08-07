from config import (
    CHECK_INTERVAL,
    EMA_FAST,
    EMA_FILTER_PERIOD,
    EMA_SLOW,
    INITIAL_STOP_PERCENT,
    LEVERAGE,
    MARGIN_USDT,
    MAX_COMPLETED_TRADES,
    SUPPORTED_SYMBOLS,
    SYMBOL,
    TIMEFRAME,
    TRAILING_BUFFER,
    TRAILING_TRIGGER,
)


class ConfigValidator:

    VALID_TIMEFRAMES = (
        "1m",
        "3m",
        "5m",
        "15m",
        "30m",
        "1h",
        "2h",
        "4h",
        "6h",
        "8h",
        "12h",
        "1d",
    )

    @staticmethod
    def validate():

        print("=" * 60)
        print("VALIDATING CONFIGURATION")
        print("=" * 60)

        # -------------------------------------------------
        # SYMBOL
        # -------------------------------------------------

        if SYMBOL not in SUPPORTED_SYMBOLS:
            raise ValueError(
                f"Unsupported symbol: {SYMBOL}"
            )

        # -------------------------------------------------
        # TIMEFRAME
        # -------------------------------------------------

        if TIMEFRAME not in ConfigValidator.VALID_TIMEFRAMES:
            raise ValueError(
                f"Unsupported timeframe: {TIMEFRAME}"
            )

        # -------------------------------------------------
        # EMA
        # -------------------------------------------------

        if EMA_FAST <= 0:
            raise ValueError(
                "EMA_FAST must be greater than zero."
            )

        if EMA_SLOW <= 0:
            raise ValueError(
                "EMA_SLOW must be greater than zero."
            )

        if EMA_FAST >= EMA_SLOW:
            raise ValueError(
                "EMA_FAST must be smaller than EMA_SLOW."
            )

        if EMA_FILTER_PERIOD <= EMA_SLOW:
            raise ValueError(
                "EMA_FILTER_PERIOD should be greater than EMA_SLOW."
            )

        # -------------------------------------------------
        # ACCOUNT
        # -------------------------------------------------

        if MARGIN_USDT <= 0:
            raise ValueError(
                "MARGIN_USDT must be greater than zero."
            )

        if LEVERAGE <= 0:
            raise ValueError(
                "LEVERAGE must be greater than zero."
            )

        if LEVERAGE > 125:
            raise ValueError(
                "LEVERAGE exceeds BingX limit."
            )

        # -------------------------------------------------
        # STOP LOSS
        # -------------------------------------------------

        if INITIAL_STOP_PERCENT <= 0:
            raise ValueError(
                "INITIAL_STOP_PERCENT must be positive."
            )

        # -------------------------------------------------
        # TRAILING
        # -------------------------------------------------

        if TRAILING_TRIGGER <= 0:
            raise ValueError(
                "TRAILING_TRIGGER must be positive."
            )

        if TRAILING_BUFFER <= 0:
            raise ValueError(
                "TRAILING_BUFFER must be positive."
            )

        if TRAILING_BUFFER >= TRAILING_TRIGGER:
            raise ValueError(
                "TRAILING_BUFFER must be smaller than TRAILING_TRIGGER."
            )

        # -------------------------------------------------
        # BOT
        # -------------------------------------------------

        if CHECK_INTERVAL <= 0:
            raise ValueError(
                "CHECK_INTERVAL must be positive."
            )

        if MAX_COMPLETED_TRADES <= 0:
            raise ValueError(
                "MAX_COMPLETED_TRADES must be positive."
            )

        print("Configuration OK")
        print("=" * 60)