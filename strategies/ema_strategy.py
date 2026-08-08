from config import EMA_FAST, EMA_SLOW, TRADE_ON_CLOSED_CANDLE
from indicators.ema import EMA
from strategies.strategy import Strategy


class EMAStrategy(Strategy):

    def __init__(self):
        self.name = "EMA Crossover"

    def get_signal(self, candles, ema_fast=None, ema_slow=None):

        fast_period = int(ema_fast) if ema_fast is not None else EMA_FAST
        slow_period = int(ema_slow) if ema_slow is not None else EMA_SLOW

        df = candles.copy()

        df["ema_fast"] = EMA.calculate(df, fast_period)
        df["ema_slow"] = EMA.calculate(df, slow_period)

        if TRADE_ON_CLOSED_CANDLE:
            previous = df.iloc[-3]
            current = df.iloc[-2]
        else:
            previous = df.iloc[-2]
            current = df.iloc[-1]

        signal = Strategy.HOLD
        cross = None

        if previous["ema_fast"] <= previous["ema_slow"] and current["ema_fast"] > current["ema_slow"]:
            signal = Strategy.BUY
            cross = "BULLISH"

        elif previous["ema_fast"] >= previous["ema_slow"] and current["ema_fast"] < current["ema_slow"]:
            signal = Strategy.SELL
            cross = "BEARISH"

        return {
            "signal": signal,
            "cross": cross,
            "timestamp": current["timestamp"],
            "price": float(current["close"]),
            "ema_fast": float(current["ema_fast"]),
            "ema_slow": float(current["ema_slow"]),
        }


    def print_status(self, candles):

        result = self.get_signal(candles)

        print("\n" + "=" * 60)
        print("EMA STATUS")
        print("=" * 60)
        print(f"EMA {EMA_FAST}: {result['ema_fast']:.4f}")
        print(f"EMA {EMA_SLOW}: {result['ema_slow']:.4f}")
        print(f"Signal : {result['signal']}")