"""Ophelia Phase 2.9 Canonical Engine package.

Implements OPHELIA_PHASE29_CANONICAL_ENGINE_SPEC.md (v1.0).
Strategy-agnostic execution/accounting; strategies plug in via
canonical.strategies.base.BaseStrategy.
"""

__version__ = "2.9.0"

SPEC_VERSION = "1.0"
BOOTSTRAP_SEED = 290719          # D16/D23 of spec
WARMUP_BARS = 300                # spec D4
REFERENCE_NOTIONAL_USD = 100.0   # spec §12
REFERENCE_MARGIN_USD = 10.0
REFERENCE_LEVERAGE = 10.0
FEE_RATE_PER_SIDE_BPS_DEFAULT = 5.0   # measured BingX taker
SLIPPAGE_SCENARIOS_BPS = (0, 1, 2)
