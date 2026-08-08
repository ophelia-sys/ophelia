"""
=====================================================
OPHELIA v1.0 CONFIGURATION
=====================================================
Central configuration for the Ophelia trading system.
"""

# =====================================================
# APPLICATION
# =====================================================

BOT_NAME = "Ophelia"
VERSION = "1.0"

LIVE_TRADING = False
SIMULATION = not LIVE_TRADING

# =====================================================
# MARKET
# =====================================================

SUPPORTED_SYMBOLS = (
    "BTC-USDT",
    "ETH-USDT",
    "SOL-USDT",
    "XRP-USDT",
)

# Default trading symbol
DEFAULT_SYMBOL = "SOL-USDT"

# Current active symbol
SYMBOL = DEFAULT_SYMBOL

# Backward compatibility
WATCHLIST = list(SUPPORTED_SYMBOLS)

# Candle timeframe
TIMEFRAME = "1m"

# Polling interval (seconds)
CHECK_INTERVAL = 5

# Only execute signals after candle closes
TRADE_ON_CLOSED_CANDLE = True

# =====================================================
# STRATEGY
# =====================================================

STRATEGY = "EMA"

EMA_FAST = 8
EMA_SLOW = 18

# =====================================================
# TREND FILTER
# =====================================================

USE_200_EMA_FILTER = False

EMA_FILTER_PERIOD = 200
EMA_FILTER_TIMEFRAME = "15m"

# =====================================================
# ACCOUNT
# =====================================================

# Margin per trade (USDT)
MARGIN_USDT = 10.0

# Default leverage
LEVERAGE = 20

# Maximum simultaneously open positions
MAX_OPEN_POSITIONS = 1

# Paper trading starting balance
PAPER_STARTING_BALANCE = 10_000.0

# =====================================================
# RISK MANAGEMENT
# =====================================================

# Initial stop loss (%)
INITIAL_STOP_PERCENT = 1.0

# =====================================================
# TRAILING STOP
# =====================================================

USE_TRAILING_STOP = True

# Start trailing after this profit (%)
TRAILING_TRIGGER = 2.0

# Keep stop this far behind price (%)
TRAILING_BUFFER = 0.8

# Update stop every X%
STOP_UPDATE_STEP = 0.2

# =====================================================
# EMA REVERSAL
# =====================================================

USE_EMA_REVERSAL = True
REVERSE_ON_SIGNAL = True

# =====================================================
# AUTOMATION
# =====================================================

MAX_COMPLETED_TRADES = 100

# =====================================================
# API
# =====================================================

REQUEST_TIMEOUT = 15
RECV_WINDOW = 5000

# =====================================================
# LOGGING
# =====================================================

PRINT_STATUS = True
PRINT_API_RESPONSES = False
PRINT_DEBUG = False

# =====================================================
# TELEGRAM
# =====================================================

import os
from dotenv import load_dotenv

load_dotenv()

ENABLE_TELEGRAM = os.getenv("ENABLE_TELEGRAM", "False").lower() in ("true", "1", "yes")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
_allowed_ids_raw = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "")
TELEGRAM_ALLOWED_USER_IDS = [
    int(uid.strip())
    for uid in _allowed_ids_raw.split(",")
    if uid.strip().isdigit()
]