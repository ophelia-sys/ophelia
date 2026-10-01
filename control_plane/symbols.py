"""Authoritative centralized symbol normalization and contract resolution for Ophelia.

Layer: control_plane/symbols
Contract:
- Single authoritative resolver shared across market data, scanner, strategies,
  automations, risk, leverage, order submission, reconciliation, and position history.
- Strictly preserves hyphenated BingX Perpetual Swap V2 symbols (e.g. SOL-USDT, BTC-USDT, ETH-USDT, XRP-USDT).
- Stripping hyphens (e.g. SOLUSDT) is prohibited as Swap V2 requires ending with -USDT or -USDC.
- Dynamically resolves current BingX Gold contract symbol from active BingX contract metadata.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional

from control_plane import config

logger = logging.getLogger("ophelia.symbols")

# Valid BingX perpetual swap format: ^[A-Z0-9]+-(USDT|USDC)$
BINGX_SWAP_REGEX = re.compile(r"^[A-Z0-9]+-(USDT|USDC)$")

# Canonical internal watchlist symbols
CANONICAL_WATCHLIST = [
    "BTC-USDT",
    "ETH-USDT",
    "SOL-USDT",
    "XRP-USDT",
    "GOLD (XAU)",
]

# Cached dynamically resolved Gold contract
_GOLD_CONTRACT_CACHE: Dict[str, Any] = {
    "symbol": "GOLD-USDT",
    "resolved_at_ms": 0,
    "ttl_ms": 300_000,  # 5 minutes
}


def to_bingx_symbol(symbol: str) -> str:
    """Normalize any symbol reference to the canonical BingX Perpetual Futures V2 format.
    
    Examples:
    - 'SOL-USDT' -> 'SOL-USDT'
    - 'sol-usdt' -> 'SOL-USDT'
    - 'SOLUSDT'  -> 'SOL-USDT' (restores missing hyphen)
    - 'GOLD (XAU)' -> dynamic BingX gold contract (e.g. 'GOLD-USDT')
    - 'XAU' -> dynamic BingX gold contract
    """
    if not symbol or not isinstance(symbol, str):
        raise ValueError(f"Invalid symbol: {symbol!r}")

    s = symbol.strip().upper()

    # Handle Gold references dynamically
    if s in ("GOLD (XAU)", "GOLD", "XAU", "XAUUSD", "GOLD-USDT"):
        return resolve_gold_symbol()

    # If already correctly formatted with hyphen
    if BINGX_SWAP_REGEX.match(s):
        return s

    # If hyphen missing but ends with USDT or USDC (e.g. SOLUSDT -> SOL-USDT)
    if s.endswith("USDT") and "-" not in s:
        base = s[:-4]
        return f"{base}-USDT"
    if s.endswith("USDC") and "-" not in s:
        base = s[:-4]
        return f"{base}-USDC"

    # Default fallback: append -USDT if no suffix
    if "-" not in s:
        return f"{s}-USDT"

    return s


def to_canonical_display(symbol: str) -> str:
    """Convert exchange symbol to user-facing canonical display name."""
    if not symbol:
        return ""
    s = symbol.strip().upper()
    if s in ("GOLD-USDT", "XAU-USDT", "XAUUSD", "GOLD"):
        return "GOLD (XAU)"
    return to_bingx_symbol(s)


def resolve_gold_symbol() -> str:
    """Dynamically resolve the currently active BingX Gold contract symbol.
    
    Queries BingX contracts metadata when cache expires, falling back safely
    to config.GOLD_FALLBACK_SYMBOL ('GOLD-USDT').
    """
    now_ms = int(time.time() * 1000)
    cached = _GOLD_CONTRACT_CACHE
    if cached["symbol"] and (now_ms - cached["resolved_at_ms"] < cached["ttl_ms"]):
        return cached["symbol"]

    # Fallback to configured default
    gold_sym = getattr(config, "GOLD_FALLBACK_SYMBOL", "GOLD-USDT")

    try:
        from control_plane import bingx_client
        c = bingx_client.public_client()
        # Query contracts without signing (public endpoint)
        data = c._request("GET", bingx_client.CONTRACTS, signed=False)
        rows = data if isinstance(data, list) else []
        for row in rows:
            sym = str(row.get("symbol", "")).upper()
            # Match gold or XAU contracts ending with -USDT or -USDC
            if ("GOLD" in sym or "XAU" in sym) and ("-USDT" in sym or "-USDC" in sym):
                gold_sym = sym
                break
    except Exception as e:
        logger.warning("Dynamic Gold contract resolution failed, using fallback: %s", e)

    _GOLD_CONTRACT_CACHE["symbol"] = gold_sym
    _GOLD_CONTRACT_CACHE["resolved_at_ms"] = now_ms
    return gold_sym


def validate_symbol_for_trade(symbol: str) -> str:
    """Validate that a symbol is valid for trade execution.
    
    Returns normalized BingX symbol or raises ValueError.
    """
    norm = to_bingx_symbol(symbol)
    if not BINGX_SWAP_REGEX.match(norm):
        raise ValueError(f"Symbol '{symbol}' normalized to '{norm}' does not end with -USDT or -USDC")
    return norm
