"""Authoritative Canonical Provenance Enumeration for Ophelia.

Layer: control_plane/provenance
Contract:
- Single canonical enumeration for all account, position, trade, and PnL figures.
- Strict segregation between live authenticated BingX figures and shadow/paper/simulation data.
- UI displays derive directly from this canonical enum.
"""
from enum import Enum


class DataProvenance(str, Enum):
    LIVE_BINGX = "LIVE_BINGX"       # Real authenticated BingX exchange account state
    SHADOW_PAPER = "SHADOW_PAPER"   # Internal shadow broker or paper simulated execution
    SIMULATION = "SIMULATION"       # Historical backtest or research simulation
    NO_DATA = "NO_DATA"             # Disconnected / no data available
