"""Data contract: canonical candle store, integrity gates G1-G9, dataset manifest.

Spec: OPHELIA_PHASE29_CANONICAL_ENGINE_SPEC.md §2.
Fail-closed: any gate violation raises DataIntegrityError.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, asdict
from typing import Optional

import numpy as np
import pandas as pd

CANONICAL_COLUMNS = [
    "candle_open_time", "candle_close_time",
    "open", "high", "low", "close", "volume",
]
# Vendor indicator columns may be appended (SPEC-GAP S1/S2): vwap_vendor,
# up_trend_vendor, down_trend_vendor. They are DATA, never engine indicators.


class DataIntegrityError(RuntimeError):
    """Raised when an integrity gate fails. Engine must refuse to start."""


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- raw ingestion

def load_raw_tv_export(path: str) -> pd.DataFrame:
    """Load a TradingView export (time,open,high,low,close[,volume],VWAP,Up Trend,Down Trend).

    time is epoch SECONDS at candle OPEN. Empty indicator cells become NaN.
    """
    df = pd.read_csv(path)
    required = {"time", "open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise DataIntegrityError(f"Raw export missing columns: {sorted(missing)}")
    out = pd.DataFrame()
    out["candle_open_time"] = df["time"].astype("int64") * 1000  # s -> ms (G7: UTC epoch)
    out["open"] = df["open"].astype(float)
    out["high"] = df["high"].astype(float)
    out["low"] = df["low"].astype(float)
    out["close"] = df["close"].astype(float)
    if "volume" in df.columns:
        out["volume"] = df["volume"].astype(float)
    else:
        out["volume"] = np.nan                       # SPEC-GAP S2: volume unavailable
    for src, dst in (("VWAP", "vwap_vendor"),
                     ("Up Trend", "up_trend_vendor"),
                     ("Down Trend", "down_trend_vendor")):
        if src in df.columns:
            out[dst] = pd.to_numeric(df[src], errors="coerce")
    return out


def ingest_raw_to_canonical(raw_path: str, canon_path: str,
                            timeframe_minutes: int = 5) -> dict:
    """Run integrity gates on RAW input, write canonical CSV store, build manifest."""
    tf_ms = timeframe_minutes * 60_000
    df = load_raw_tv_export(raw_path)
    df["candle_close_time"] = df["candle_open_time"].astype("int64") + tf_ms

    # ---- gates on raw frame -------------------------------------------------
    times = df["candle_open_time"].to_numpy()
    if np.any(np.diff(times) <= 0):                                   # G1
        dup_or_nonmono = np.where(np.diff(times) <= 0)[0]
        raise DataIntegrityError(f"G1 duplicate/non-monotonic timestamps at rows {dup_or_nonmono[:5]}")
    gaps = np.diff(times)
    gap_rows = np.where(gaps != tf_ms)[0]
    long_gaps = [(int(times[i]), int(times[i + 1])) for i in gap_rows
                 if gaps[i] > 60 * 60_000]                            # G2 fatal if >60min
    if long_gaps:
        raise DataIntegrityError(f"G2 data gap(s) > 60min not in exceptions file: {long_gaps[:3]}")
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    bad = (~np.isfinite(o)) | (~np.isfinite(h)) | (~np.isfinite(l)) | (~np.isfinite(c))
    if bad.any():                                                     # G4 prices
        raise DataIntegrityError(f"G4 non-finite OHLC at rows {np.where(bad)[0][:5]}")
    invalid = ((h < l) | (h < o - 1e-12) | (h < c - 1e-12)
               | (l > o + 1e-12) | (l > c + 1e-12))
    if invalid.any():                                                 # G3
        raise DataIntegrityError(f"G3 invalid OHLC relationships at rows {np.where(invalid)[0][:5]}")
    vol = df["volume"].to_numpy()
    volume_available = bool(np.isfinite(vol).any())
    if volume_available and (vol < 0).any():                          # G5
        raise DataIntegrityError("G5 negative volume present")
    zero_volume_count = int(np.isfinite(vol).sum() and (vol[np.isfinite(vol)] == 0).sum())
    # partial final candle check happens against ingest-time clock (caller supplies 'now_ms')
    return df, {
        "missing_candle_count": int(len(gap_rows)),
        "duplicate_timestamp_count": 0,
        "invalid_ohlc_count": int(invalid.sum()),
        "zero_volume_bar_count": zero_volume_count,
        "volume_available": volume_available,
    }


def write_canonical_store(df: pd.DataFrame, path: str) -> None:
    """Deterministic CSV store (fixed float formatting => byte-stable across runs).

    NOTE (implementation note IN-1): spec §2.3 named Parquet; CSV chosen for guaranteed
    byte-determinism of the hash chain (T20). Schema columns are identical.
    """
    cols = [c for c in df.columns if c in CANONICAL_COLUMNS or c.endswith("_vendor")]
    out = df[cols].copy()
    fmt = {k: "%.10f" for k in ("open", "high", "low", "close", "volume",
                                "vwap_vendor", "up_trend_vendor", "down_trend_vendor")}
    out.to_csv(path, index=False, float_format=None, lineterminator="\n",
               na_rep="", decimal=".")
    # apply fixed precision via re-write to keep determinism explicit:
    out.to_csv(path, index=False, float_format="%.10f", lineterminator="\n", na_rep="")


def load_canonical_store(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = set(CANONICAL_COLUMNS) - set(df.columns)
    if missing:
        raise DataIntegrityError(f"Canonical store missing columns: {sorted(missing)}")
    df["candle_open_time"] = df["candle_open_time"].astype("int64")
    df["candle_close_time"] = df["candle_close_time"].astype("int64")
    # re-run OHLC gates on load (fail closed even if store was hand-edited)
    _gates_on_frame(df)
    return df


def _gates_on_frame(df: pd.DataFrame) -> dict:
    times = df["candle_open_time"].to_numpy()
    if np.any(np.diff(times) <= 0):
        raise DataIntegrityError("G1 duplicate/non-monotonic timestamps")
    tf = int(times[1] - times[0]) if len(times) > 1 else 300_000
    gap_rows = np.where(np.diff(times) != tf)[0]
    for i in gap_rows:
        if times[i + 1] - times[i] > 60 * 60_000:
            raise DataIntegrityError(f"G2 gap > 60min at {times[i]}")
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    if not (np.isfinite(o).all() and np.isfinite(h).all()
            and np.isfinite(l).all() and np.isfinite(c).all()):
        raise DataIntegrityError("G4 non-finite OHLC")
    bad = (h < l) | (h < o - 1e-9) | (h < c - 1e-9) | (l > o + 1e-9) | (l > c + 1e-9)
    if bad.any():
        raise DataIntegrityError(f"G3 invalid OHLC at rows {np.where(bad)[0][:5]}")
    vol = df.get("volume")
    stats = {"missing_candle_count": int(len(gap_rows)),
             "duplicate_timestamp_count": 0,
             "zero_volume_bar_count": int((vol == 0).sum()) if vol is not None else 0}
    return stats


def drop_partial_final_candle(df: pd.DataFrame, now_utc_ms: int,
                              timeframe_minutes: int = 5):
    """G6: drop last candle whose close_time would exceed 'now'."""
    tf_ms = timeframe_minutes * 60_000
    if len(df) and int(df["candle_open_time"].iloc[-1]) + tf_ms > now_utc_ms:
        dropped = df.iloc[[-1]].copy()
        return df.iloc[:-1].reset_index(drop=True), dropped
    return df.reset_index(drop=True), None
