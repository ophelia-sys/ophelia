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
            
        if strategy_name == "ANTI_CHOP":
            from strategies.anti_chop_ema_strategy import AntiChopEMAStrategy
            return AntiChopEMAStrategy()

        raise ValueError(
            f"Unknown strategy: {strategy_name}"
        )