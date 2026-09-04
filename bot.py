"""
Ophelia Application and Telegram Launcher Entry Point.

This script launches the authoritative TradingEngine instance.
Direct order submission loops outside TradingEngine have been removed
to guarantee production safety and adherence to AGENTS.md.
"""

import sys
import threading
import time
from core.trading_engine import TradingEngine
from utils.logger import logger
from institutional.cvd.paper_signal_engine import PaperSignalEngine

def paper_signal_loop(engine: TradingEngine):
    logger.info("Starting PaperSignalEngine observation thread...")
    telegram_adapter = getattr(engine, "telegram_adapter", None)
    paper_engine = PaperSignalEngine(engine.institutional_data, telegram_adapter=telegram_adapter)
    
    while True:
        try:
            now_ms = int(time.time() * 1000)
            symbols = list(engine.settings.symbols)
            for sym in symbols:
                paper_engine.evaluate(sym, now_ms)
        except Exception as e:
            logger.error(f"PaperSignalEngine loop error: {e}")
        time.sleep(1.0)

def main():
    logger.info("Starting Ophelia via bot.py entry point...")
    engine = TradingEngine()
    
    # Start Paper Signal observation path
    t = threading.Thread(target=paper_signal_loop, args=(engine,), daemon=True)
    t.start()
    
    engine.run()


if __name__ == "__main__":
    main()