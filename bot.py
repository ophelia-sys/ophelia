"""
Ophelia Application and Telegram Launcher Entry Point.

This script launches the authoritative TradingEngine instance.
Direct order submission loops outside TradingEngine have been removed
to guarantee production safety and adherence to AGENTS.md.
"""

import sys
from core.trading_engine import TradingEngine
from utils.logger import logger


def main():
    logger.info("Starting Ophelia via bot.py entry point...")
    engine = TradingEngine()
    engine.run()


if __name__ == "__main__":
    main()