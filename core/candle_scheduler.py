import time
from datetime import datetime, timedelta


class CandleScheduler:

    def __init__(self, timeframe_minutes=5):

        self.timeframe = timeframe_minutes

    def wait_for_next_candle(self):

        now = datetime.now()

        minutes = now.minute

        remainder = minutes % self.timeframe

        next_candle = now.replace(second=0, microsecond=0)

        if remainder == 0 and now.second == 0:

            return

        minutes_to_add = self.timeframe - remainder

        next_candle = next_candle + timedelta(minutes=minutes_to_add)

        seconds = (next_candle - now).total_seconds()

        print()

        print("=" * 60)

        print(f"Current Time : {now.strftime('%H:%M:%S')}")

        print(f"Next Candle  : {next_candle.strftime('%H:%M:%S')}")

        print(f"Sleeping     : {round(seconds)} seconds")

        print("=" * 60)

        time.sleep(seconds)