class BotState:

    def __init__(self):

        self.last_signal = None
        self.last_candle = None

    # =====================================================
    # SHOULD EXECUTE
    # =====================================================

    def should_execute(
        self,
        signal,
        candle
    ):

        if signal == "HOLD":
            return False

        if (
            signal == self.last_signal
            and candle == self.last_candle
        ):
            return False

        return True

    # =====================================================
    # SAVE EXECUTED SIGNAL
    # =====================================================

    def mark_executed(
        self,
        signal,
        candle
    ):

        self.last_signal = signal
        self.last_candle = candle