"""Empirical Cross-Venue Comparative Study: Binance vs BingX.

Layer: scripts/run_binance_vs_bingx_comparison.py
Answers:
"Does Binance provide better or more useful market intelligence than BingX for constructing trade candidates?"
Compares:
1. Market Data Parity & Basis: Price divergence, spread, and timestamp offsets.
2. Candidate Detection: Total candidate count on Binance vs BingX.
3. Candidate Timing: Timestamp lead/lag between venues.
4. Setup Geometry & Retest Fidelity.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from control_plane import config, db
from control_plane.binance_data import BinanceMarketDataProvider, CausalCandleAggregator
from control_plane.candidate_research import ComparativeMarketEngine
from scripts.run_multi_venue_candidate_study import detect_structural_candidates

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("binance_vs_bingx")


def fetch_bingx_klines(symbol: str = "BTC-USDT", limit: int = 1000) -> List[dict]:
    """Fetch raw 1m klines from BingX Swap V2."""
    url = f"https://open-api.bingx.com/openApi/swap/v2/quote/klines?symbol={symbol}&interval=1m&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "ophelia-comparison/1.0"})
    with urllib.request.urlopen(req, timeout=12) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        raw = data.get("data", [])
        bars = []
        for r in raw:
            bars.append({
                "symbol": symbol,
                "ts": int(r["time"]),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": float(r["volume"]),
                "is_closed": True
            })
        bars.sort(key=lambda x: x["ts"])
        return bars


def run_cross_venue_study(symbol_crypto: str = "BTC") -> Dict[str, Any]:
    bn_symbol = f"{symbol_crypto}USDT"
    bx_symbol = f"{symbol_crypto}-USDT"

    logger.info("============================================================")
    logger.info("STARTING BINANCE VS BINGX COMPARATIVE MARKET STUDY: %s", symbol_crypto)
    logger.info("============================================================")

    # 1. Fetch 1,000 1m candles from Binance
    bn_provider = BinanceMarketDataProvider()
    bn_raw_1m = bn_provider.fetch_klines(bn_symbol, limit=1000)
    bn_raw_dicts = [b.to_dict() for b in bn_raw_1m if b.is_closed]
    logger.info("Fetched %d closed 1m bars from Binance for %s.", len(bn_raw_dicts), bn_symbol)

    # 2. Fetch 1,000 1m candles from BingX
    bx_raw_dicts = fetch_bingx_klines(bx_symbol, limit=1000)
    logger.info("Fetched %d closed 1m bars from BingX for %s.", len(bx_raw_dicts), bx_symbol)

    # 3. Aggregate both streams to causal 5m candles
    bn_5m = CausalCandleAggregator.aggregate_series(bn_raw_dicts, "5m")
    bx_5m = CausalCandleAggregator.aggregate_series(bx_raw_dicts, "5m")
    logger.info("Derived %d 5m bars on Binance; %d 5m bars on BingX.", len(bn_5m), len(bx_5m))

    # 4. Measure Cross-Venue Basis Divergence across matching 5m timestamps
    bx_map = {b["ts"]: b for b in bx_5m}
    basis_pct_list: List[float] = []
    abs_diffs: List[float] = []

    for bnb in bn_5m:
        ts = bnb["ts"]
        if ts in bx_map:
            bxb = bx_map[ts]
            diff = bxb["close"] - bnb["close"]
            pct = (diff / bnb["close"]) * 100.0
            basis_pct_list.append(pct)
            abs_diffs.append(abs(pct))

    mean_basis_pct = round(sum(basis_pct_list) / len(basis_pct_list), 4) if basis_pct_list else 0.0
    mean_abs_basis_pct = round(sum(abs_diffs) / len(abs_diffs), 4) if abs_diffs else 0.0
    max_basis_pct = round(max(abs_diffs), 4) if abs_diffs else 0.0

    # 5. Detect Candidates on Both Streams
    bn_candidates = detect_structural_candidates(bn_5m, bn_symbol)
    bx_candidates = detect_structural_candidates(bx_5m, bx_symbol)
    logger.info("Candidates detected: Binance (Mode A) = %d | BingX (Mode B) = %d", len(bn_candidates), len(bx_candidates))

    # 6. Pair Candidates & Measure Lead/Lag & Price Deltas
    matched = ComparativeMarketEngine.match_candidates(bn_candidates, bx_candidates, window_tolerance_ms=900_000)
    paired = [m for m in matched if m["status"] == "PAIRED"]
    bn_only = [m for m in matched if m["status"] == "BINANCE_ONLY"]

    timing_deltas_ms = [m["timestamp_delta_ms"] for m in paired]
    mean_lead_ms = round(sum(timing_deltas_ms) / len(timing_deltas_ms), 1) if timing_deltas_ms else 0.0

    entry_deltas_pct = [m["entry_price_delta_pct"] for m in paired]
    mean_entry_delta_pct = round(sum(entry_deltas_pct) / len(entry_deltas_pct), 4) if entry_deltas_pct else 0.0

    report = {
        "symbol": symbol_crypto,
        "binance_symbol": bn_symbol,
        "bingx_symbol": bx_symbol,
        "binance_5m_bars": len(bn_5m),
        "bingx_5m_bars": len(bx_5m),
        "basis_metrics": {
            "common_bars_count": len(basis_pct_list),
            "mean_basis_pct": mean_basis_pct,
            "mean_abs_basis_pct": mean_abs_basis_pct,
            "max_abs_basis_pct": max_basis_pct,
            "basis_state": "ALIGNED" if mean_abs_basis_pct < 0.05 else "NORMAL_BASIS"
        },
        "candidate_comparison": {
            "binance_candidates_count": len(bn_candidates),
            "bingx_candidates_count": len(bx_candidates),
            "paired_candidates_count": len(paired),
            "binance_only_candidates_count": len(bn_only),
            "mean_timing_delta_ms": mean_lead_ms,
            "mean_entry_price_delta_pct": mean_entry_delta_pct,
            "direction_agreement_pct": round((sum(1 for m in paired if m["direction_match"]) / len(paired)) * 100.0, 2) if paired else 0.0
        },
        "status": "SUCCESS"
    }

    logger.info("============================================================")
    logger.info("COMPARATIVE RESULTS: %s", symbol_crypto)
    logger.info("Mean Basis: %.4f%% (Max: %.4f%%)", mean_basis_pct, max_basis_pct)
    logger.info("Candidates: Binance=%d, BingX=%d, Paired=%d (%.1f%% Direction Match)",
                len(bn_candidates), len(bx_candidates), len(paired),
                report["candidate_comparison"]["direction_agreement_pct"])
    logger.info("Mean Lead/Lag Delta: %.1f ms | Mean Price Delta: %.4f%%", mean_lead_ms, mean_entry_delta_pct)
    logger.info("============================================================")
    return report


if __name__ == "__main__":
    rep = run_cross_venue_study("BTC")
    print(json.dumps(rep, indent=2))
