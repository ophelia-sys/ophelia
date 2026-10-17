"""Canonical engine configuration (Phase 2.9 spec §20: no hidden defaults)."""
from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass, field
from typing import Tuple


@dataclass(frozen=True)
class CanonicalConfig:
    """Immutable engine configuration. Every field is explicit; unknown keys are fatal."""

    dataset_id: str = "DS-A"
    dataset_version: str = "DS-A.v1"
    symbol: str = "SOLUSDT"
    timeframe_minutes: int = 5

    # Strategy (acceptance anchor D2)
    strategy_id: str = "VWAP_SUPERTREND_ACTIVE_LINE_CROSS"
    strategy_version: str = "1.0.0"
    st_length: int = 10
    st_factor: float = 4.0
    indicator_source: str = "VENDOR_PROVIDED"   # VENDOR_PROVIDED | ENGINE_COMPUTED (spec-gap S1)

    # Execution (locked decisions)
    entry_model: str = "NEXT_OPEN"              # NEXT_OPEN (Model A) | TRIGGER (Model B)
    stop_buffer_bps: float = 1.0                # Active line ± 1 bp (D12)
    ambiguity_policy: str = "STOP_FIRST"        # A1/D1
    position_mode: str = "SINGLE_POSITION"      # SINGLE_POSITION | MULTI_POSITION (ext EX2)

    # Exit policies (§7/§9 of spec; primary drives the state machine)
    r_targets: Tuple[float, ...] = (1.0, 1.5, 2.0, 3.0)
    abs_targets_bps: Tuple[float, ...] = (50.0, 75.0, 100.0)
    primary_exit_policy: str = "FIXED_R_150"

    # Costs (§10)
    fee_rate_per_side_bps: float = 5.0
    slippage_scenarios_bps: Tuple[float, ...] = (0.0, 1.0, 2.0)

    # Statistics (§16)
    bootstrap_B: int = 5000
    bootstrap_seed: int = 290719
    bootstrap_blocks_days: Tuple[int, ...] = (1, 7)
    ess_autocorr_lag: int = 1

    # Regimes (§17, predeclared, causal)
    regime_ret24h_up: float = 0.01
    regime_ret24h_down: float = -0.01
    regime_vol_lookback_bars: int = 288          # rolling window for atr_pct median proxy
    regime_atr_length: int = 14

    # Reproducibility
    warmup_bars: int = 300                       # D4 (ENGINE_COMPUTED path only; see S1)

    def policy_names(self) -> Tuple[str, ...]:
        names = tuple(f"FIXED_R_{int(round(k*100)):03d}" for k in self.r_targets)
        names += tuple(f"ABS_{int(p):03d}BP" for p in self.abs_targets_bps)
        return names

    def to_json(self) -> str:
        return json.dumps(dataclasses.asdict(self), indent=2, sort_keys=True)

    def sha256(self) -> str:
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()

    @staticmethod
    def from_unknown_keys(d: dict) -> "CanonicalConfig":
        allowed = {f.name for f in dataclasses.fields(CanonicalConfig)}
        unknown = set(d) - allowed
        if unknown:
            raise ValueError(f"Unknown config keys (fatal per spec §20): {sorted(unknown)}")
        return CanonicalConfig(**d)


DEFAULT_CONFIG = CanonicalConfig()
