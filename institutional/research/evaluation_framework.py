"""
Feature and Microstructure Research Evaluation Framework for Ophelia.
Layer: institutional/research
Contract: Isolated analytical harness. Evaluates signal efficacy without execution authority.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
import numpy as np


@dataclass(frozen=True)
class ExcursionMetrics:
    """Excursion profile for a forward-simulated research event."""
    event_index: int
    entry_price: float
    direction: str  # "LONG" or "SHORT"
    forward_horizon_bars: int
    max_favorable_excursion_pct: float  # MFE %
    max_adverse_excursion_pct: float    # MAE %
    final_return_pct: float             # Return at end of horizon
    is_favorable_win: bool              # Reached target threshold before stop threshold


@dataclass
class ResearchEvaluationSummary:
    """Statistical summary across research events."""
    feature_name: str
    symbol: str
    timeframe: str
    sample_size: int
    win_rate_pct: float
    avg_mfe_pct: float
    avg_mae_pct: float
    mfe_to_mae_ratio: float
    avg_return_pct: float
    false_positive_rate_pct: float
    session_distribution: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FeatureEvaluator:
    """
    Evaluates market-state features and structure detectors against forward candle paths.
    Does NOT connect to order execution or portfolio managers.
    """

    @classmethod
    def evaluate_events(
        cls,
        feature_name: str,
        symbol: str,
        timeframe: str,
        closes: List[float],
        highs: List[float],
        lows: List[float],
        event_indices: List[int],
        event_directions: List[str],
        horizon_bars: int = 15,
        target_pct: float = 0.5,
        stop_pct: float = 0.3
    ) -> ResearchEvaluationSummary:
        """
        Evaluate a sequence of feature trigger events forward across price series.
        """
        if not event_indices:
            return ResearchEvaluationSummary(
                feature_name=feature_name,
                symbol=symbol,
                timeframe=timeframe,
                sample_size=0,
                win_rate_pct=0.0,
                avg_mfe_pct=0.0,
                avg_mae_pct=0.0,
                mfe_to_mae_ratio=0.0,
                avg_return_pct=0.0,
                false_positive_rate_pct=0.0
            )

        excursions: List[ExcursionMetrics] = []
        n_candles = len(closes)

        for idx, direction in zip(event_indices, event_directions):
            if idx + 1 >= n_candles:
                continue
            
            entry_price = closes[idx]
            forward_limit = min(n_candles, idx + 1 + horizon_bars)
            f_highs = highs[idx + 1 : forward_limit]
            f_lows = lows[idx + 1 : forward_limit]
            f_closes = closes[idx + 1 : forward_limit]

            if not f_highs:
                continue

            if direction == "LONG":
                max_high = max(f_highs)
                min_low = min(f_lows)
                mfe_pct = ((max_high - entry_price) / entry_price) * 100.0
                mae_pct = ((entry_price - min_low) / entry_price) * 100.0
                final_ret = ((f_closes[-1] - entry_price) / entry_price) * 100.0
                win = mfe_pct >= target_pct and mae_pct <= stop_pct
            else:  # SHORT
                max_high = max(f_highs)
                min_low = min(f_lows)
                mfe_pct = ((entry_price - min_low) / entry_price) * 100.0
                mae_pct = ((max_high - entry_price) / entry_price) * 100.0
                final_ret = ((entry_price - f_closes[-1]) / entry_price) * 100.0
                win = mfe_pct >= target_pct and mae_pct <= stop_pct

            excursions.append(
                ExcursionMetrics(
                    event_index=idx,
                    entry_price=entry_price,
                    direction=direction,
                    forward_horizon_bars=len(f_highs),
                    max_favorable_excursion_pct=round(mfe_pct, 4),
                    max_adverse_excursion_pct=round(mae_pct, 4),
                    final_return_pct=round(final_ret, 4),
                    is_favorable_win=win
                )
            )

        n = len(excursions)
        if n == 0:
            return ResearchEvaluationSummary(
                feature_name=feature_name,
                symbol=symbol,
                timeframe=timeframe,
                sample_size=0,
                win_rate_pct=0.0,
                avg_mfe_pct=0.0,
                avg_mae_pct=0.0,
                mfe_to_mae_ratio=0.0,
                avg_return_pct=0.0,
                false_positive_rate_pct=0.0
            )

        wins = sum(1 for e in excursions if e.is_favorable_win)
        win_rate = (wins / n) * 100.0
        avg_mfe = sum(e.max_favorable_excursion_pct for e in excursions) / n
        avg_mae = sum(e.max_adverse_excursion_pct for e in excursions) / n
        avg_ret = sum(e.final_return_pct for e in excursions) / n
        mfe_mae_ratio = avg_mfe / max(avg_mae, 1e-4)
        false_positives = sum(1 for e in excursions if e.final_return_pct < 0)
        fp_rate = (false_positives / n) * 100.0

        return ResearchEvaluationSummary(
            feature_name=feature_name,
            symbol=symbol,
            timeframe=timeframe,
            sample_size=n,
            win_rate_pct=round(win_rate, 2),
            avg_mfe_pct=round(avg_mfe, 3),
            avg_mae_pct=round(avg_mae, 3),
            mfe_to_mae_ratio=round(mfe_mae_ratio, 2),
            avg_return_pct=round(avg_ret, 3),
            false_positive_rate_pct=round(fp_rate, 2)
        )
