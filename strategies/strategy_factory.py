from strategies.ema_strategy import EMAStrategy


class StrategyFactory:
    """
    Creates and returns the active trading strategy.
    """

    @staticmethod
    def create(strategy_name="EMA"):

        strategy_name = strategy_name.upper()

        if strategy_name == "EMA":
            return EMAStrategy()

        raise ValueError(
            f"Unknown strategy: {strategy_name}"
        )