"""
Ophelia TimesFM 3.0 Forecasting Subsystem
=========================================
Strictly causal, shadow-only forecasting provider and governance service.

Authoritative Rules:
- Forecast-only: No trading authority, cannot place orders, alter stops, or override risk.
- Zero Lookahead: Truncates historical context strictly at forecast timestamp T.
- Provider Architecture: Abstract base class with TimesFM and Baseline implementations.
- Monotonic Quantiles: Enforces q10 <= q50 <= q90.
- Failure Isolation: Never brings down ophelia-api or ophelia-control.
"""

from __future__ import annotations

import os
import sys
import time
import uuid
import math
import json
import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from . import config, db

logger = logging.getLogger("ophelia.forecast_service")

# Pinned Constants
TIMESFM_PACKAGE_VERSION = "3.0.2"
TIMESFM_CHECKPOINT = "google/timesfm-3.0-pytorch"
TIMESFM_MODEL_VERSION = "3.0"
FEATURE_SCHEMA_VERSION = "TIMESFM_FEATURE_SCHEMA_V1"

# Universal Watchlist Instruments
UNIVERSAL_WATCHLIST = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "NCCOGOLD2USD-USDT"]

# Status Enums
STATUS_SUCCESS = "SUCCESS"
STATUS_STALE_INPUT = "STALE_INPUT"
STATUS_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
STATUS_MODEL_ERROR = "MODEL_ERROR"
STATUS_TIMEOUT = "TIMEOUT"
STATUS_NOT_AVAILABLE = "NOT_AVAILABLE"

# Model Lifecycle State
LIFECYCLE_UNINITIALIZED = "UNINITIALIZED"
LIFECYCLE_LOADING = "LOADING"
LIFECYCLE_READY = "READY"
LIFECYCLE_DEGRADED = "DEGRADED"
LIFECYCLE_ERROR = "ERROR"


@dataclass
class ForecastResult:
    forecast_id: str
    instrument: str
    timeframe: str
    forecast_timestamp: int
    data_timestamp: int
    model_name: str
    model_version: str
    checkpoint: str
    context_length: int
    horizon: int
    input_schema_version: str
    forecast_values: List[float]
    quantiles: Dict[str, List[float]]  # {"q10": [...], "q50": [...], "q90": [...]}
    forecast_generation_ms: float
    latency_ms: float
    status: str
    data_freshness: str
    error: Optional[str] = None
    mode: str = "SHADOW"
    user_id: Optional[int] = None
    created_at: int = field(default_factory=lambda: int(time.time() * 1000))
    # Derived / advisory metrics
    forecast_return_pct: float = 0.0
    quantile_spread_pct: float = 0.0
    direction: str = "NEUTRAL"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TimesFMFeatureBuilder:
    """Builds strictly causal context arrays with explicit past/future covariate separation."""

    @staticmethod
    def build_context(
        candles: List[Dict[str, Any]],
        forecast_ts: int,
        context_len: int = 128,
        min_context_len: int = 32
    ) -> Tuple[np.ndarray, Optional[np.ndarray], Optional[np.ndarray], int, str]:
        """
        Extracts causal price series and covariates up to forecast_ts.
        Guarantees: Zero data with timestamp > forecast_ts is admitted.
        Returns:
            (context_array, past_only_covariates, future_known_covariates, latest_data_ts, freshness)
        """
        # Filter strictly by causal cutoff: ts <= forecast_ts
        causal_candles = [c for c in candles if int(c.get("ts") or 0) <= forecast_ts]
        causal_candles.sort(key=lambda x: int(x.get("ts") or 0))

        if len(causal_candles) < min_context_len:
            return np.array([]), None, None, 0, STATUS_INSUFFICIENT_DATA

        # Truncate to desired context_len
        selected = causal_candles[-context_len:]
        latest_data_ts = int(selected[-1].get("ts") or 0)

        # Evaluate freshness: if latest candle is more than 3 intervals behind forecast_ts, flag STALE
        time_diff_ms = forecast_ts - latest_data_ts
        freshness = "FRESH" if time_diff_ms <= 300000 else "STALE"

        closes = np.array([float(c.get("close") or 0.0) for c in selected], dtype=np.float32)

        # PAST_ONLY Covariates: Volume, VWAP, Rolling Volatility
        vols = np.array([float(c.get("volume") or 0.0) for c in selected], dtype=np.float32)
        vwaps = np.array([float(c.get("vwap") or c.get("close") or 0.0) for c in selected], dtype=np.float32)
        past_only = np.column_stack([vols, vwaps])

        # FUTURE_KNOWN Covariates: Day-of-week, Hour-of-day (known calendar time)
        # For the past context:
        past_timestamps = [int(c.get("ts") or 0) for c in selected]
        dows = np.array([(ts // 86400000 + 4) % 7 for ts in past_timestamps], dtype=np.float32)
        hours = np.array([(ts // 3600000) % 24 for ts in past_timestamps], dtype=np.float32)
        future_known = np.column_stack([dows, hours])

        return closes, past_only, future_known, latest_data_ts, freshness


class ForecastProvider(ABC):
    """Abstract base class for all forecasting providers."""

    @abstractmethod
    def forecast(
        self,
        instrument: str,
        timeframe: str,
        context_series: np.ndarray,
        horizon: int,
        forecast_ts: int,
        data_ts: int,
        freshness: str,
        user_id: Optional[int] = None
    ) -> ForecastResult:
        pass


class StatisticalBaselineProvider(ForecastProvider):
    """Computes zero-lookahead statistical baselines: Naive persistence, EMA, and VWAP."""

    def __init__(self, mode: str = "NAIVE_PERSISTENCE"):
        self.mode = mode

    def forecast(
        self,
        instrument: str,
        timeframe: str,
        context_series: np.ndarray,
        horizon: int = 10,
        forecast_ts: int = 0,
        data_ts: int = 0,
        freshness: str = "FRESH",
        user_id: Optional[int] = None
    ) -> ForecastResult:
        t0 = time.perf_counter()
        fid = str(uuid.uuid4())
        now_ms = int(time.time() * 1000)
        forecast_ts = forecast_ts or now_ms

        if len(context_series) == 0:
            return ForecastResult(
                forecast_id=fid,
                instrument=instrument,
                timeframe=timeframe,
                forecast_timestamp=forecast_ts,
                data_timestamp=data_ts,
                model_name=f"baseline_{self.mode.lower()}",
                model_version="1.0",
                checkpoint="statistical_baseline",
                context_length=0,
                horizon=horizon,
                input_schema_version=FEATURE_SCHEMA_VERSION,
                forecast_values=[],
                quantiles={},
                forecast_generation_ms=0.0,
                latency_ms=0.0,
                status=STATUS_INSUFFICIENT_DATA,
                data_freshness=freshness,
                error="Empty context series"
            )

        last_p = float(context_series[-1])

        # Naive persistence: P_{t+h} = P_t
        if self.mode == "NAIVE_PERSISTENCE":
            path = [last_p] * horizon
            vol = float(np.std(context_series[-20:]) if len(context_series) >= 20 else last_p * 0.005)
        elif self.mode == "EMA":
            alpha = 2.0 / (len(context_series) + 1.0)
            ema = float(context_series[0])
            for p in context_series[1:]:
                ema = alpha * float(p) + (1 - alpha) * ema
            path = [round(ema, 4)] * horizon
            vol = float(np.std(context_series[-20:]) if len(context_series) >= 20 else last_p * 0.005)
        else:
            path = [last_p] * horizon
            vol = float(last_p * 0.005)

        # Baseline quantile bands around path
        q10 = [round(p - 1.28 * vol, 4) for p in path]
        q50 = [round(p, 4) for p in path]
        q90 = [round(p + 1.28 * vol, 4) for p in path]

        gen_ms = (time.perf_counter() - t0) * 1000
        return ForecastResult(
            forecast_id=fid,
            instrument=instrument,
            timeframe=timeframe,
            forecast_timestamp=forecast_ts,
            data_timestamp=data_ts,
            model_name=f"baseline_{self.mode.lower()}",
            model_version="1.0",
            checkpoint="statistical_baseline",
            context_length=len(context_series),
            horizon=horizon,
            input_schema_version=FEATURE_SCHEMA_VERSION,
            forecast_values=path,
            quantiles={"q10": q10, "q50": q50, "q90": q90},
            forecast_generation_ms=round(gen_ms, 2),
            latency_ms=round(gen_ms, 2),
            status=STATUS_SUCCESS,
            data_freshness=freshness,
            forecast_return_pct=0.0,
            quantile_spread_pct=round(((q90[-1] - q10[-1]) / last_p) * 100, 2) if last_p > 0 else 0.0,
            direction="NEUTRAL",
            mode="SHADOW",
            user_id=user_id
        )


class TimesFMProvider(ForecastProvider):
    """
    Production-grade wrapper for official TimesFM 3.0 PyTorch implementation.
    Pinned to: google/timesfm-3.0-pytorch
    """

    def __init__(self, checkpoint: str = TIMESFM_CHECKPOINT, device: Optional[str] = "cpu"):
        self.checkpoint = checkpoint
        self.device = device or "cpu"
        self.model = None
        self.lifecycle_state = LIFECYCLE_UNINITIALIZED
        self.last_error: Optional[str] = None
        self.init_lock = threading.Lock()

    def load_model(self) -> bool:
        """Loads TimesFM 3.0 checkpoint into singleton instance and runs warmup inference."""
        with self.init_lock:
            if self.lifecycle_state == LIFECYCLE_READY and self.model is not None:
                return True

            self.lifecycle_state = LIFECYCLE_LOADING
            t0 = time.perf_counter()
            try:
                import timesfm
                # Use official TimesFM3Forecaster from pretrained checkpoint
                logger.info(f"Loading TimesFM 3.0 from checkpoint '{self.checkpoint}' on device '{self.device}'...")
                self.model = timesfm.TimesFM3Forecaster.from_pretrained(
                    pretrained_model_name_or_path=self.checkpoint,
                    device=self.device
                )

                # Warmup inference with synthetic 64-step sequence
                warmup_ctx = np.linspace(100.0, 105.0, 64, dtype=np.float32)
                _ = self.model.predict(context=warmup_ctx, horizon=10, return_quantiles=True)
                
                load_sec = time.perf_counter() - t0
                logger.info(f"TimesFM 3.0 loaded and warmed up successfully in {load_sec:.2f}s")
                self.lifecycle_state = LIFECYCLE_READY
                self.last_error = None
                return True

            except ImportError as ie:
                self.last_error = f"timesfm package not installed: {ie}"
                self.lifecycle_state = LIFECYCLE_DEGRADED
                logger.warning(self.last_error)
                return False
            except Exception as e:
                self.last_error = f"Failed to load TimesFM model: {e}"
                self.lifecycle_state = LIFECYCLE_ERROR
                logger.error(self.last_error)
                return False

    def forecast(
        self,
        instrument: str,
        timeframe: str,
        context_series: np.ndarray,
        horizon: int = 10,
        forecast_ts: int = 0,
        data_ts: int = 0,
        freshness: str = "FRESH",
        user_id: Optional[int] = None
    ) -> ForecastResult:
        t0 = time.perf_counter()
        fid = str(uuid.uuid4())
        now_ms = int(time.time() * 1000)
        forecast_ts = forecast_ts or now_ms

        if len(context_series) < 32:
            return ForecastResult(
                forecast_id=fid,
                instrument=instrument,
                timeframe=timeframe,
                forecast_timestamp=forecast_ts,
                data_timestamp=data_ts,
                model_name="timesfm",
                model_version=TIMESFM_MODEL_VERSION,
                checkpoint=self.checkpoint,
                context_length=len(context_series),
                horizon=horizon,
                input_schema_version=FEATURE_SCHEMA_VERSION,
                forecast_values=[],
                quantiles={},
                forecast_generation_ms=0.0,
                latency_ms=0.0,
                status=STATUS_INSUFFICIENT_DATA,
                data_freshness=freshness,
                error=f"Context series length {len(context_series)} is less than minimum 32",
                mode="SHADOW",
                user_id=user_id
            )

        # Ensure model is ready
        if self.model is None:
            loaded = self.load_model()
            if not loaded or self.model is None:
                # Graceful fallback: return MODEL_ERROR or NOT_AVAILABLE without crashing
                gen_ms = (time.perf_counter() - t0) * 1000
                return ForecastResult(
                    forecast_id=fid,
                    instrument=instrument,
                    timeframe=timeframe,
                    forecast_timestamp=forecast_ts,
                    data_timestamp=data_ts,
                    model_name="timesfm",
                    model_version=TIMESFM_MODEL_VERSION,
                    checkpoint=self.checkpoint,
                    context_length=len(context_series),
                    horizon=horizon,
                    input_schema_version=FEATURE_SCHEMA_VERSION,
                    forecast_values=[],
                    quantiles={},
                    forecast_generation_ms=round(gen_ms, 2),
                    latency_ms=round(gen_ms, 2),
                    status=STATUS_MODEL_ERROR if self.lifecycle_state == LIFECYCLE_ERROR else STATUS_NOT_AVAILABLE,
                    data_freshness=freshness,
                    error=self.last_error or "Model not loaded",
                    mode="SHADOW",
                    user_id=user_id
                )

        # Run actual TimesFM inference
        try:
            output = self.model.predict(
                context=context_series.astype(np.float32),
                horizon=horizon,
                return_quantiles=True,
                sort_quantiles=True
            )
            # output is ForecastOutput(ts_id, forecast, quantiles)
            forecast_raw = output.forecast
            if isinstance(forecast_raw, np.ndarray):
                # Shape can be (horizon,) or (1, horizon)
                forecast_vals = [round(float(x), 4) for x in forecast_raw.flatten()[:horizon]]
            else:
                forecast_vals = [round(float(x), 4) for x in list(forecast_raw)[:horizon]]

            quantiles_dict: Dict[str, List[float]] = {}
            if output.quantiles is not None and isinstance(output.quantiles, np.ndarray):
                # Typically quantiles has 9 channels for 0.1 to 0.9
                q_arr = output.quantiles
                if q_arr.ndim == 3:  # (1, horizon, num_quantiles)
                    q_arr = q_arr[0]
                num_q = q_arr.shape[-1] if q_arr.ndim >= 2 else 0
                if num_q >= 3:
                    # Pick q10 (index 0), q50 (median index), q90 (last index)
                    q10_raw = q_arr[:, 0]
                    q50_raw = q_arr[:, num_q // 2]
                    q90_raw = q_arr[:, -1]
                    quantiles_dict["q10"] = [round(float(x), 4) for x in q10_raw[:horizon]]
                    quantiles_dict["q50"] = [round(float(x), 4) for x in q50_raw[:horizon]]
                    quantiles_dict["q90"] = [round(float(x), 4) for x in q90_raw[:horizon]]

            # Fallback if quantiles not populated
            if "q50" not in quantiles_dict:
                last_p = float(context_series[-1])
                spread = abs(forecast_vals[-1] - last_p) if forecast_vals else last_p * 0.01
                quantiles_dict["q10"] = [round(v - spread, 4) for v in forecast_vals]
                quantiles_dict["q50"] = forecast_vals
                quantiles_dict["q90"] = [round(v + spread, 4) for v in forecast_vals]

            # Invariant: verify monotonic quantiles q10 <= q50 <= q90
            for i in range(len(forecast_vals)):
                q10 = quantiles_dict["q10"][i]
                q50 = quantiles_dict["q50"][i]
                q90 = quantiles_dict["q90"][i]
                if not (q10 <= q50 <= q90):
                    # Sort canonically if minor crossing occurred
                    s = sorted([q10, q50, q90])
                    quantiles_dict["q10"][i] = s[0]
                    quantiles_dict["q50"][i] = s[1]
                    quantiles_dict["q90"][i] = s[2]

            last_p = float(context_series[-1])
            target_p = forecast_vals[-1] if forecast_vals else last_p
            ret_pct = round(((target_p - last_p) / last_p) * 100, 2) if last_p > 0 else 0.0
            q_spread = round(((quantiles_dict["q90"][-1] - quantiles_dict["q10"][-1]) / last_p) * 100, 2) if last_p > 0 else 0.0
            direction = "BULLISH" if ret_pct > 0.1 else ("BEARISH" if ret_pct < -0.1 else "NEUTRAL")

            gen_ms = (time.perf_counter() - t0) * 1000
            return ForecastResult(
                forecast_id=fid,
                instrument=instrument,
                timeframe=timeframe,
                forecast_timestamp=forecast_ts,
                data_timestamp=data_ts,
                model_name="timesfm",
                model_version=TIMESFM_MODEL_VERSION,
                checkpoint=self.checkpoint,
                context_length=len(context_series),
                horizon=horizon,
                input_schema_version=FEATURE_SCHEMA_VERSION,
                forecast_values=forecast_vals,
                quantiles=quantiles_dict,
                forecast_generation_ms=round(gen_ms, 2),
                latency_ms=round(gen_ms, 2),
                status=STATUS_SUCCESS,
                data_freshness=freshness,
                forecast_return_pct=ret_pct,
                quantile_spread_pct=q_spread,
                direction=direction,
                mode="SHADOW",
                user_id=user_id
            )

        except Exception as e:
            gen_ms = (time.perf_counter() - t0) * 1000
            logger.error(f"Inference error in TimesFMProvider: {e}")
            return ForecastResult(
                forecast_id=fid,
                instrument=instrument,
                timeframe=timeframe,
                forecast_timestamp=forecast_ts,
                data_timestamp=data_ts,
                model_name="timesfm",
                model_version=TIMESFM_MODEL_VERSION,
                checkpoint=self.checkpoint,
                context_length=len(context_series),
                horizon=horizon,
                input_schema_version=FEATURE_SCHEMA_VERSION,
                forecast_values=[],
                quantiles={},
                forecast_generation_ms=round(gen_ms, 2),
                latency_ms=round(gen_ms, 2),
                status=STATUS_MODEL_ERROR,
                data_freshness=freshness,
                error=str(e),
                mode="SHADOW",
                user_id=user_id
            )


class ForecastService:
    """
    Central orchestration and governance singleton for Ophelia forecasting.
    Enforces concurrency limits, cache ttl, and failure isolation.
    """

    _instance: Optional[ForecastService] = None
    _service_lock = threading.Lock()

    def __init__(self):
        self.timesfm_provider = TimesFMProvider()
        self.baseline_provider = StatisticalBaselineProvider(mode="NAIVE_PERSISTENCE")
        self.cache: Dict[Tuple[str, str], Dict[str, Any]] = {}  # (symbol, tf) -> {result, valid_until, next_refresh}
        self.cache_lock = threading.Lock()
        self.inference_lock = threading.Lock()
        self.total_forecasts_count = 0
        self.last_inference_ms = 0.0
        self.last_inference_ts = 0
        self.last_error: Optional[str] = None
        self.queue_depth = 0

    @classmethod
    def get_instance(cls) -> ForecastService:
        with cls._service_lock:
            if cls._instance is None:
                cls._instance = ForecastService()
            return cls._instance

    def get_status(self_or_cls=None) -> Dict[str, Any]:
        svc = self_or_cls if isinstance(self_or_cls, ForecastService) else ForecastService.get_instance()
        return {
            "model_loaded": svc.timesfm_provider.lifecycle_state == LIFECYCLE_READY,
            "lifecycle_state": svc.timesfm_provider.lifecycle_state,
            "version": TIMESFM_MODEL_VERSION,
            "package_version": TIMESFM_PACKAGE_VERSION,
            "checkpoint": TIMESFM_CHECKPOINT,
            "device": svc.timesfm_provider.device,
            "forecast_count": svc.total_forecasts_count,
            "last_inference_ms": svc.last_inference_ms,
            "last_inference_ts": svc.last_inference_ts,
            "last_error": svc.last_error or svc.timesfm_provider.last_error,
            "queue_depth": svc.queue_depth,
            "mode": "SHADOW_ONLY",
            "trading_authority": False
        }

    def generate_forecast(
        self,
        instrument: str,
        timeframe: str = "15m",
        horizon: int = 10,
        user_id: Optional[int] = None,
        force_refresh: bool = False
    ) -> ForecastResult:
        """
        Retrieves cached forecast if valid; otherwise executes governed inference.
        """
        cache_key = (instrument, timeframe)
        now_ms = int(time.time() * 1000)

        # Check Cache
        with self.cache_lock:
            if not force_refresh and cache_key in self.cache:
                entry = self.cache[cache_key]
                if entry.get("valid_until", 0) > now_ms:
                    return entry["result"]

        # Concurrency & Governance: Max Concurrent = 1
        with self.inference_lock:
            # Double check cache inside lock
            if not force_refresh and cache_key in self.cache:
                entry = self.cache[cache_key]
                if entry.get("valid_until", 0) > now_ms:
                    return entry["result"]

            self.queue_depth = 1
            t_start = time.perf_counter()
            try:
                # 1. Fetch historical candles from DB
                candles = db.get_candles(instrument, limit=256)
                if not candles:
                    # Try universal symbol normalization if symbol has alternate naming
                    alt_sym = instrument.replace("-", "")
                    candles = db.get_candles(alt_sym, limit=256)

                # 2. Build strictly causal context
                context_arr, past_covs, fut_covs, data_ts, freshness = TimesFMFeatureBuilder.build_context(
                    candles=candles,
                    forecast_ts=now_ms,
                    context_len=128,
                    min_context_len=32
                )

                # 3. If context is insufficient, fall back to baseline or insufficient data
                if len(context_arr) < 32:
                    result = self.baseline_provider.forecast(
                        instrument=instrument,
                        timeframe=timeframe,
                        context_series=context_arr,
                        horizon=horizon,
                        forecast_ts=now_ms,
                        data_ts=data_ts,
                        freshness=freshness,
                        user_id=user_id
                    )
                    result.status = STATUS_INSUFFICIENT_DATA
                    result.error = f"Insufficient market data for {instrument} (found {len(context_arr)} bars, need >= 32)"
                else:
                    # 4. Execute TimesFM inference
                    result = self.timesfm_provider.forecast(
                        instrument=instrument,
                        timeframe=timeframe,
                        context_series=context_arr,
                        horizon=horizon,
                        forecast_ts=now_ms,
                        data_ts=data_ts,
                        freshness=freshness,
                        user_id=user_id
                    )

                # 5. Persist to SQLite model_forecasts
                try:
                    db.save_model_forecast(result.to_dict())
                except Exception as dbe:
                    logger.error(f"Failed to persist forecast to database: {dbe}")

                # 6. Update cache based on timeframe validity
                ttl_ms = self._get_timeframe_ttl_ms(timeframe)
                with self.cache_lock:
                    self.cache[cache_key] = {
                        "result": result,
                        "generated_at": now_ms,
                        "valid_until": now_ms + ttl_ms,
                        "next_refresh_at": now_ms + ttl_ms
                    }

                self.total_forecasts_count += 1
                self.last_inference_ms = round((time.perf_counter() - t_start) * 1000, 2)
                self.last_inference_ts = now_ms
                self.last_error = None
                return result

            except Exception as e:
                self.last_error = str(e)
                logger.error(f"Error in ForecastService: {e}")
                # Fallback to Baseline Provider
                fallback = self.baseline_provider.forecast(
                    instrument=instrument,
                    timeframe=timeframe,
                    context_series=np.array([100.0] * 32, dtype=np.float32),
                    horizon=horizon,
                    forecast_ts=now_ms,
                    data_ts=now_ms,
                    freshness="DEGRADED",
                    user_id=user_id
                )
                fallback.status = STATUS_MODEL_ERROR
                fallback.error = str(e)
                return fallback
            finally:
                self.queue_depth = 0

    def _get_timeframe_ttl_ms(self, tf: str) -> int:
        if tf == "1m":
            return 50000  # 50s
        elif tf == "5m":
            return 240000  # 4m
        elif tf == "1h":
            return 3000000  # 50m
        return 600000  # 10m for 15m default


class ForecastScheduler:
    """Background worker scheduling periodic forecast generation on candle boundaries."""

    def __init__(self, service: Optional[ForecastService] = None, interval_seconds: int = 60):
        self.service = service or ForecastService.get_instance()
        self.interval = interval_seconds
        self.running = False
        self.thread: Optional[threading.Thread] = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True, name="ForecastScheduler")
        self.thread.start()
        logger.info("ForecastScheduler background thread started.")

    def stop(self):
        self.running = False

    def _run_loop(self):
        while self.running:
            try:
                for inst in UNIVERSAL_WATCHLIST:
                    if not self.running:
                        break
                    try:
                        self.service.generate_forecast(instrument=inst, timeframe="15m", horizon=10)
                    except Exception as fe:
                        logger.error(f"Scheduler forecast failed for {inst}: {fe}")
                    time.sleep(1.0)
            except Exception as e:
                logger.error(f"Unhandled error in ForecastScheduler loop: {e}")
            time.sleep(self.interval)
