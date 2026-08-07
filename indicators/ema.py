

class EMA:

    @staticmethod
    def calculate(df, period, source="close"):
        """
        Calculate Exponential Moving Average.
        """

        return df[source].ewm(
            span=period,
            adjust=False
        ).mean()

    @staticmethod
    def crossover(fast_ema, slow_ema):
        """
        Returns True if fast EMA crosses above slow EMA.
        """

        if len(fast_ema) < 2:
            return False

        return (
            fast_ema.iloc[-2] <= slow_ema.iloc[-2]
            and
            fast_ema.iloc[-1] > slow_ema.iloc[-1]
        )

    @staticmethod
    def crossunder(fast_ema, slow_ema):
        """
        Returns True if fast EMA crosses below slow EMA.
        """

        if len(fast_ema) < 2:
            return False

        return (
            fast_ema.iloc[-2] >= slow_ema.iloc[-2]
            and
            fast_ema.iloc[-1] < slow_ema.iloc[-1]
        )