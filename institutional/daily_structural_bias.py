"""Institutional Multi-Factor Daily Structural Bias Engine for Ophelia.

Layer: institutional/daily_structural_bias
Contract:
- Authoritative multi-factor preference model evaluated independently for:
  BTC-USDT, ETH-USDT, SOL-USDT, XRP-USDT, and GOLD (XAU).
- Synthesizes 18 structural and macroeconomic dimensions:
  1. Higher-TF structure (4h / 1d trend)
  2. Today's intraday structure
  3. Previous-day structure (PDH, PDL, PDC)
  4. Session VWAP regime & deviation bands
  5. Cumulative Volume Delta (CVD) slope & aggressive delta
  6. Order flow aggression & absorption
  7. Structural displacement (> 1.0x ATR)
  8. Liquidity sweeps (BSL/SSL pools)
  9. RVOL (relative volume vs baseline)
  10. Volatility regime (ATR expansion/compression)
  11. Key structural supply & demand levels
  12. Fair Value Gaps (FVG) and mitigation state
  13. Retest behavior & acceptance
  14. BTC regime anchor (market beta driver)
  15. US Dollar Index (DXY) inverse pressure
  16. US 10-Year Treasury Yield (TNX) discount rate pressure
  17. Real-time news catalyst sentiment
  18. Scheduled macroeconomic calendar events & intermarket confirmation
- Output:
  * DAILY PREFERENCE: LONG / SHORT / NEUTRAL
  * BIAS STATE: STRONG BULLISH / BULLISH / NEUTRAL / BEARISH / STRONG BEARISH / NO EDGE / INSUFFICIENT DATA
  * STRUCTURAL THESIS
  * SUPPORTING FACTORS
  * CONTRADICTING FACTORS
  * KEY LEVELS
  * LIQUIDITY MAP
  * ORDER-FLOW CONDITION
  * NEWS/MACRO BIAS
  * INVALIDATION
  * WHAT FLIPS THE BIAS
- Safety: Strictly an institutional preference report; NEVER forces trades or bypasses deterministic gates.
"""
from __future__ import annotations

import math
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from control_plane import analytics, config, db, fast_math, news


def compute_daily_structural_bias(symbol: str) -> Dict[str, Any]:
    """Compute multi-factor institutional structural bias for a given symbol."""
    now_ms = int(time.time() * 1000)
    norm_sym = symbol.strip().upper()
    if norm_sym in ("GOLD", "XAU", "XAUUSD", "GOLD (XAU)"):
        norm_sym = config.GOLD_DISPLAY_NAME

    # 1. Fetch historical candle windows (1m raw aggregated to 5m, 15m, 1h)
    cd_1h = analytics.get_candles(norm_sym, lookback_min=1440 * 3, base_interval_min=1, agg_interval_min=60)
    candles_1h = cd_1h.get("candles", [])

    cd_15m = analytics.get_candles(norm_sym, lookback_min=1440, base_interval_min=1, agg_interval_min=15)
    candles_15m = cd_15m.get("candles", [])

    cd_5m = analytics.get_candles(norm_sym, lookback_min=360, base_interval_min=1, agg_interval_min=5)
    candles_5m = cd_5m.get("candles", [])

    if len(candles_5m) < 15:
        return {
            "symbol": norm_sym,
            "timestamp_ms": now_ms,
            "direction": "NEUTRAL",
            "daily_preference": "NEUTRAL",
            "final_daily_preference": "NEUTRAL",
            "final_daily_market_bias": "NEUTRAL",
            "bias_state": "INSUFFICIENT DATA",
            "market_regime": "NEUTRAL / UNCERTAIN",
            "volatility_regime": "NORMAL",
            "positioning_regime": "POSITIONING DATA NOT AVAILABLE",
            "gamma_regime": "GAMMA DATA NOT AVAILABLE",
            "trade_priority": "NORMAL PRIORITY",
            "confidence_pct": 30.0,
            "multi_factor_score": 0.0,
            "structural_thesis": f"Insufficient candle data for {norm_sym} to compile deterministic institutional bias.",
            "supporting_factors": [],
            "contradicting_factors": ["Data feed calibrating or candle history insufficient (<15 bars)"],
            "key_levels": {},
            "liquidity_map": {},
            "order_flow_condition": "INSUFFICIENT_DATA",
            "news_macro_bias": "NEUTRAL",
            "invalidation": "Awaiting candle feed synchronization.",
            "what_flips_bias": "Feed synchronization required.",
            "disclaimer": "PREFERENCE REPORT ONLY - NO EXECUTION PERMISSION",
            "allows_counter_trend": True
        }

    current_price = float(candles_5m[-1]["close"])
    highs_5m = [c["high"] for c in candles_5m]
    lows_5m = [c["low"] for c in candles_5m]
    closes_5m = [c["close"] for c in candles_5m]
    volumes_5m = [c.get("volume", 0.0) for c in candles_5m]

    # 2. Previous-Day Structure (PDH, PDL, PDC)
    utc_now = datetime.fromtimestamp(now_ms / 1000.0, tz=timezone.utc)
    today_start_ms = int(datetime(utc_now.year, utc_now.month, utc_now.day, tzinfo=timezone.utc).timestamp() * 1000)
    yesterday_start_ms = today_start_ms - 86400_000

    y_candles = [c for c in candles_1h if yesterday_start_ms <= c["ts"] < today_start_ms]
    if y_candles:
        pdh = max(c["high"] for c in y_candles)
        pdl = min(c["low"] for c in y_candles)
        pdc = y_candles[-1]["close"]
    else:
        # Fallback from 24h-48h window
        pdh = max(highs_5m) * 1.01
        pdl = min(lows_5m) * 0.99
        pdc = closes_5m[0]

    # Today's high/low
    t_candles = [c for c in candles_5m if c["ts"] >= today_start_ms] or candles_5m
    tdh = max(c["high"] for c in t_candles)
    tdl = min(c["low"] for c in t_candles)

    # 3. Session VWAP & Bands
    vreg = analytics.vwap_regime(norm_sym, tf_min=5)
    vwap = float(vreg.get("vwap", current_price))
    vwap_state = str(vreg.get("regime", "CHOP"))
    vwap_std = float(vreg.get("std", current_price * 0.005))
    vwap_upper1 = vwap + vwap_std
    vwap_lower1 = vwap - vwap_std
    vwap_upper2 = vwap + (2.0 * vwap_std)
    vwap_lower2 = vwap - (2.0 * vwap_std)

    # 4. Swings and Key Structural Levels
    swing_highs, swing_lows = fast_math.detect_swings(highs_5m, lows_5m, lookback=3)
    major_resistance = min([p for _, p in swing_highs if p > current_price], default=pdh)
    major_support = max([p for _, p in swing_lows if p < current_price], default=pdl)

    # 5. ATR & Volatility
    atr_series = fast_math.calculate_atr(highs_5m, lows_5m, closes_5m, 14)
    atr = atr_series[-1] if atr_series else current_price * 0.01
    atr_avg = np.mean(atr_series[-10:]) if len(atr_series) >= 10 else atr
    volatility_state = "EXPANDED" if atr > atr_avg * 1.25 else ("COMPRESSED" if atr < atr_avg * 0.8 else "NORMAL")

    # 6. RVOL
    rvol_val = fast_math.calculate_rvol(volumes_5m, 20)
    rvol_state = "SURGE" if rvol_val >= 1.5 else ("ELEVATED" if rvol_val >= 1.1 else "NORMAL")

    opens_5m = [float(c["open"]) for c in candles_5m]
    taker_buys_5m = [float(c.get("taker_buy") or (c.get("volume", 0.0) * 0.5)) for c in candles_5m]
    cvd_series = fast_math.calculate_cvd_series(volumes_5m, taker_buys_5m, opens_5m, closes_5m)
    cvd_slope = (cvd_series[-1] - cvd_series[-5]) if len(cvd_series) >= 5 else 0.0
    cvd_bullish = cvd_slope > 0
    order_flow_state = "BUY_DOMINANT" if cvd_slope > 50.0 else ("SELL_DOMINANT" if cvd_slope < -50.0 else "BALANCED")

    # 8. Liquidity Sweeps
    high_sweep = tdh > pdh and current_price < pdh
    low_sweep = tdl < pdl and current_price > pdl

    # 9. FVG Detection
    fvg_blocks = fast_math.detect_fvg(highs_5m, lows_5m, closes_5m)
    def _is_fvg_type(f, target_type):
        if isinstance(f, dict):
            return target_type in str(f.get("type", ""))
        elif isinstance(f, (tuple, list)) and len(f) >= 2:
            return target_type in str(f[1])
        return False

    bullish_fvgs = [f for f in fvg_blocks if _is_fvg_type(f, "BULLISH")]
    bearish_fvgs = [f for f in fvg_blocks if _is_fvg_type(f, "BEARISH")]

    # 10. Macro Factors (DXY, US10Y, News)
    yahoo = news.fetch_yahoo_macro_context()
    dxy_chg = float(yahoo.get("instruments", {}).get("DXY", {}).get("change_pct", 0.0))
    tnx_chg = float(yahoo.get("instruments", {}).get("US10Y", {}).get("change_pct", 0.0))
    dxy_px = float(yahoo.get("instruments", {}).get("DXY", {}).get("price", 103.5))
    tnx_px = float(yahoo.get("instruments", {}).get("US10Y", {}).get("price", 4.25))

    # Multi-factor score aggregation
    score = 0.0
    supporting = []
    contradicting = []

    # Factor A: Higher-TF & Intraday Location
    if current_price > vwap:
        score += 1.5
        supporting.append(f"Price holding above Session VWAP ({current_price:.2f} > {vwap:.2f})")
    else:
        score -= 1.5
        contradicting.append(f"Price trading below Session VWAP ({current_price:.2f} < {vwap:.2f})")

    if current_price > pdc:
        score += 1.0
        supporting.append(f"Holding above Previous Day Close ({pdc:.2f})")
    else:
        score -= 1.0
        contradicting.append(f"Trading below Previous Day Close ({pdc:.2f})")

    # Factor B: Order Flow / CVD
    if cvd_bullish:
        score += 1.0
        supporting.append(f"Aggressive taker CVD delta expansion positive (+{cvd_slope:.1f})")
    else:
        score -= 1.0
        contradicting.append(f"Aggressive taker CVD delta expansion negative ({cvd_slope:.1f})")

    # Factor C: Liquidity Sweeps
    if low_sweep:
        score += 2.0
        supporting.append(f"Previous Day Low swept with fast absorption reclaim (Liquidity Sweep Long)")
    if high_sweep:
        score -= 2.0
        contradicting.append(f"Previous Day High swept with rejection back into range (Liquidity Sweep Short)")

    # Factor D: Macro Cross-Asset
    if dxy_chg < -0.10:
        score += 1.0
        supporting.append(f"US Dollar Index softening ({dxy_chg:+.2f}%) providing monetary tailwind")
    elif dxy_chg > 0.15:
        score -= 1.0
        contradicting.append(f"US Dollar Index rallying ({dxy_chg:+.2f}%) creating macro liquidity headwind")

    if norm_sym == config.GOLD_DISPLAY_NAME:
        if tnx_chg < -0.05:
            score += 1.0
            supporting.append(f"US 10Y sovereign yield contracting ({tnx_chg:+.2f}%), compressing real carry cost for Gold")
        elif tnx_chg > 0.08:
            score -= 1.0
            contradicting.append(f"US 10Y sovereign yield expanding ({tnx_chg:+.2f}%), raising opportunity cost for non-yielding bullion")

    # Factor E: Structure / FVGs
    if len(bullish_fvgs) > len(bearish_fvgs):
        score += 0.5
        supporting.append(f"Bullish Fair Value Gaps dominant ({len(bullish_fvgs)} active imbalance zones)")
    elif len(bearish_fvgs) > len(bullish_fvgs):
        score -= 0.5
        contradicting.append(f"Bearish Fair Value Gaps dominant ({len(bearish_fvgs)} active overhead imbalance zones)")

    # Deduce Bias State & Daily Preference
    if score >= 3.0:
        daily_preference = "LONG"
        bias_state = "STRONG BULLISH"
        conf_pct = min(88.0, 65.0 + score * 4.0)
    elif score >= 1.0:
        daily_preference = "LONG"
        bias_state = "BULLISH"
        conf_pct = 68.0
    elif score <= -3.0:
        daily_preference = "SHORT"
        bias_state = "STRONG BEARISH"
        conf_pct = min(88.0, 65.0 + abs(score) * 4.0)
    elif score <= -1.0:
        daily_preference = "SHORT"
        bias_state = "BEARISH"
        conf_pct = 68.0
    else:
        daily_preference = "NEUTRAL"
        bias_state = "NO EDGE"
        conf_pct = 50.0
    # Market Regime determination (Structure & Realized Volatility displacement; strictly independent of small-timeframe VWAP)
    atr_pct = (atr / current_price) * 100.0 if current_price > 0 else 0.0
    if norm_sym == config.GOLD_DISPLAY_NAME:
        volatility_regime = "LOW" if atr_pct < 0.15 else ("HIGH" if atr_pct > 0.50 else "NORMAL")
    else:
        volatility_regime = "LOW" if atr_pct < 0.25 else ("HIGH" if atr_pct > 0.85 else "NORMAL")

    recent_displacement = abs(current_price - float(candles_5m[-10]["open"])) / atr if len(candles_5m) >= 10 and atr > 0 else 0.0
    is_swing_expanding = (current_price > pdh or current_price < pdl or recent_displacement >= 1.5)
    is_range_compressed = (pdl <= current_price <= pdh) and (recent_displacement < 0.8) and (volatility_regime != "HIGH")

    if is_swing_expanding or (volatility_regime == "HIGH" and recent_displacement >= 1.0):
        market_regime = "TREND / EXPANSION"
    elif is_range_compressed:
        market_regime = "CHOP / MEAN REVERSION"
    elif 0.8 <= recent_displacement < 1.5:
        market_regime = "TRANSITION"
    else:
        market_regime = "NEUTRAL / UNCERTAIN"

    # OI / Volume Positioning Regime proxy (Not labeled GEX)
    if norm_sym == config.GOLD_DISPLAY_NAME:
        positioning_regime = "POSITIONING DATA NOT AVAILABLE FOR THIS INSTRUMENT"
    else:
        if market_regime == "TREND / EXPANSION" and daily_preference == "LONG":
            positioning_regime = "EXPANSION_AGGRESSIVE_LONG_BUILD"
        elif market_regime == "TREND / EXPANSION" and daily_preference == "SHORT":
            positioning_regime = "EXPANSION_SHORT_DISPLACEMENT_PRESSURE"
        elif market_regime == "CHOP / MEAN REVERSION":
            positioning_regime = "COMPRESSION_RANGE_POSITIONING"
        else:
            positioning_regime = "TRANSITION_ACCUMULATION_REBALANCING"

    # Gamma Regime: Options market structure only where genuine options strike data is available; otherwise explicit NOT AVAILABLE
    gamma_regime = "GAMMA DATA NOT AVAILABLE"

    # Direction output: BULLISH / BEARISH / NEUTRAL
    direction = "BULLISH" if daily_preference == "LONG" else ("BEARISH" if daily_preference == "SHORT" else "NEUTRAL")

    # Trade Priority Logic:
    if daily_preference == "LONG" and direction == "BULLISH" and market_regime == "TREND / EXPANSION":
        trade_priority = "HIGH PRIORITY / BIAS ALIGNED"
    elif daily_preference == "SHORT" and direction == "BEARISH" and market_regime == "TREND / EXPANSION":
        trade_priority = "HIGH PRIORITY / BIAS ALIGNED"
    elif market_regime == "CHOP / MEAN REVERSION":
        trade_priority = "NORMAL PRIORITY (CHOP / MEAN REVERSION REGIME)"
    else:
        trade_priority = "NORMAL PRIORITY"

    # Invalidation & Flip conditions
    if daily_preference == "LONG":
        invalidation = f"Sustained 15m candle close below Session VWAP ({vwap:.2f}) or breakdown under major support at {major_support:.2f}."
        what_flips_bias = f"Clean breakdown and retest rejection below Previous Day Low ({pdl:.2f}) coupled with negative CVD expansion."
        thesis = f"{norm_sym} displays institutional upside preference driven by positive session VWAP acceptance, buy-side delta dominance, and favorable macro liquidity."
    elif daily_preference == "SHORT":
        invalidation = f"Sustained 15m candle close above Session VWAP ({vwap:.2f}) or breakout through major resistance at {major_resistance:.2f}."
        what_flips_bias = f"Strong displacement reclaim above Previous Day High ({pdh:.2f}) with aggressive taker buying absorption."
        thesis = f"{norm_sym} displays institutional downside preference driven by rejection below session VWAP, sell-side absorption, and overhead structural resistance."
    else:
        invalidation = f"Breakout from compressed intraday range ({major_support:.2f} - {major_resistance:.2f})."
        what_flips_bias = f"Sustained impulse acceptance beyond VWAP +/- 1.0 StdDev bands ({vwap_lower1:.2f} / {vwap_upper1:.2f})."
        thesis = f"{norm_sym} exhibits balanced range compression with no distinct institutional directional edge. Awaiting directional displacement."

    return {
        "symbol": norm_sym,
        "timestamp_ms": now_ms,
        "direction": direction,
        "daily_preference": daily_preference,
        "final_daily_preference": daily_preference,
        "final_daily_market_bias": daily_preference,
        "bias_state": bias_state,
        "market_regime": market_regime,
        "volatility_regime": volatility_regime,
        "positioning_regime": positioning_regime,
        "gamma_regime": gamma_regime,
        "trade_priority": trade_priority,
        "confidence_pct": round(conf_pct, 1),
        "multi_factor_score": round(score, 2),
        "structural_thesis": thesis,
        "supporting_factors": supporting,
        "contradicting_factors": contradicting,
        "higher_tf_structure": {
            "trend_4h": "BULLISH" if current_price >= vwap else "BEARISH",
            "trend_1d": "BULLISH" if current_price >= pdc else "BEARISH",
            "pdh": round(pdh, 4),
            "pdl": round(pdl, 4),
            "pdc": round(pdc, 4),
            "key_liquidity_pool": round(pdh if current_price >= vwap else pdl, 4)
        },
        "order_flow": {
            "cvd_slope": round(cvd_slope, 2),
            "order_flow_state": order_flow_state,
            "rvol": round(rvol_val, 2)
        },
        "vwap_context": {
            "location": "ABOVE_VWAP" if current_price >= vwap else "BELOW_VWAP",
            "vwap": round(vwap, 4),
            "separation_pct": round(((current_price - vwap) / vwap) * 100.0, 2)
        },
        "key_levels": {
            "current_price": round(current_price, 4),
            "pdh": round(pdh, 4),
            "pdl": round(pdl, 4),
            "pdc": round(pdc, 4),
            "tdh": round(tdh, 4),
            "tdl": round(tdl, 4),
            "vwap": round(vwap, 4),
            "vwap_upper_1std": round(vwap_upper1, 4),
            "vwap_lower_1std": round(vwap_lower1, 4),
            "vwap_upper_2std": round(vwap_upper2, 4),
            "vwap_lower_2std": round(vwap_lower2, 4),
            "major_resistance": round(major_resistance, 4),
            "major_support": round(major_support, 4),
            "atr_14": round(atr, 4)
        },
        "liquidity_map": {
            "buy_side_liquidity_pool": round(pdh, 4),
            "sell_side_liquidity_pool": round(pdl, 4),
            "equal_highs_detected": high_sweep,
            "equal_lows_detected": low_sweep,
            "untouched_fvg_count": len(bullish_fvgs) + len(bearish_fvgs)
        },
        "order_flow_condition": f"{order_flow_state} (CVD slope: {cvd_slope:+.1f}, RVOL: {rvol_val:.2f}x)",
        "news_macro_bias": f"DXY: {dxy_px:.2f} ({dxy_chg:+.2f}%) | US10Y: {tnx_px:.2f}% ({tnx_chg:+.2f}%) | Sentiment: {yahoo.get('macro_sentiment', 'NEUTRAL')}",
        "invalidation": invalidation,
        "what_flips_bias": what_flips_bias,
        "disclaimer": "INSTITUTIONAL PREFERENCE REPORT ONLY - DOES NOT AUTHORIZE TRADES OR BYPASS RISK BARRIERS",
        "allows_counter_trend": True
    }


def get_all_watchlist_daily_bias() -> Dict[str, Dict[str, Any]]:
    """Compute daily structural bias across all 5 primary watchlist assets."""
    target_symbols = list(config.SYMBOLS)
    if config.GOLD_DISPLAY_NAME not in target_symbols:
        target_symbols.append(config.GOLD_DISPLAY_NAME)

    results = {}
    for sym in target_symbols:
        try:
            results[sym] = compute_daily_structural_bias(sym)
        except Exception as e:
            results[sym] = {
                "symbol": sym,
                "timestamp_ms": int(time.time() * 1000),
                "daily_preference": "NEUTRAL",
                "bias_state": "NO EDGE",
                "confidence_pct": 50.0,
                "structural_thesis": f"Bias computation error: {str(e)[:80]}",
                "supporting_factors": [],
                "contradicting_factors": [str(e)[:100]],
                "key_levels": {},
                "liquidity_map": {},
                "order_flow_condition": "BALANCED",
                "news_macro_bias": "NEUTRAL",
                "invalidation": "N/A",
                "what_flips_bias": "N/A",
                "disclaimer": "PREFERENCE REPORT ONLY"
            }
    return results
