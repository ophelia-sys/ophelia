"""Strategy layer: generic, engine-agnostic signal interface (spec prompt §6, §22-26).

The EXECUTION/ACCOUNTING engine knows nothing about VWAP, Supertrend, EMA, or RSI.
A strategy only produces SignalIntent objects.

Extensions prepared for the future 5-EMA strategy (NOT implemented here):
  EX1 (Model B): entry_model="TRIGGER" with a TriggerEvent (intrabar breakout fill).
  EX2          : position_mode="MULTI_POSITION" allows overlapping trades.
  EX3 (Multi-TF): signals may be generated on any timeframe; execution always runs on
                  the base candle stream. The intent carries `signal_timeframe` and
                  `entry_reference_bar_open_time` resolved by the strategy.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd


@dataclass(frozen=True)
class TriggerEvent:
    """Model B intrabar trigger (spec prompt §24). Filled by execution.py.

    LONG breakout:  triggered iff high_j >= trigger_price
                    fill = open_j if open_j >= trigger_price else trigger_price
    SHORT breakout: triggered iff low_j  <= trigger_price
                    fill = open_j if open_j <= trigger_price else trigger_price
    valid_from/valid_to are candle_open_times (ms); outside the window the trigger expires.
    """
    trigger_price: float
    direction: int                      # +1 break-above (LONG), -1 break-below (SHORT)
    valid_from_open_time_ms: int
    valid_to_open_time_ms_exclusive: int


@dataclass(frozen=True)
class TargetSpec:
    """Strategy-declared target geometry. Policies themselves live in exit_policies.py;
    a strategy may either accept the standard policy set or declare custom absolute/R
    targets via `custom` (name -> price fraction of entry)."""
    use_standard_policies: bool = True
    custom: tuple = field(default=())   # e.g. (("ABS_120BP", 0.0120),)


@dataclass
class SignalIntent:
    """One canonical signal produced by any strategy."""
    signal_id: str
    strategy_id: str
    strategy_version: str
    dataset_id: str
    dataset_version: str
    symbol: str
    timeframe_minutes: int              # execution timeframe
    signal_timeframe_minutes: int       # may differ (EX3), informational
    signal_candle_open_time_ms: int
    signal_time_ms: int                 # == close time of signal candle
    entry_reference_open_time_ms: int   # bar whose OPEN fills the entry (Model A)
    direction: int                      # +1 LONG, -1 SHORT
    theoretical_entry_price: Optional[float]   # None => engine uses next open (Model A)
    stop_price: float
    target_spec: TargetSpec = field(default_factory=TargetSpec)
    entry_model: str = "NEXT_OPEN"      # NEXT_OPEN | TRIGGER
    trigger: Optional[TriggerEvent] = None
    indicator_source: str = "ENGINE_COMPUTED"
    metadata: dict = field(default_factory=dict)


class BaseStrategy(ABC):
    """Contract for all strategies. generate() receives the canonical candle frame."""

    strategy_id: str = "BASE"
    strategy_version: str = "0.0.0"

    @abstractmethod
    def generate(self, candles: pd.DataFrame, dataset_id: str,
                 dataset_version: str, timeframe_minutes: int) -> List[SignalIntent]:
        """Return deterministic list of SignalIntent sorted by signal_time."""
        raise NotImplementedError
