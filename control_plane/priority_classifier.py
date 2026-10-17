"""Ophelia Priority Classifier with Decoupled Gamma.

Rules:
1. Do NOT equate Gamma sign with market regime or direction:
   - Gamma sign is market-maker hedging regime context (volatility dampener vs accelerator),
     NOT directional trend.
   - BTC and ETH have genuine gamma; SOL, XRP, GOLD must state 'GAMMA DATA NOT AVAILABLE'.
2. Keep strictly separate:
   - genuine GEX / Gamma state
   - market regime (TREND / EXPANSION vs CHOP / MEAN REVERSION vs TRANSITION vs UNCERTAIN)
   - market direction / HTF bias (LONG vs SHORT vs NEUTRAL)
   - R:R (canonical reward / risk, never artificial max(1.0, rr))
   - trade setup quality
3. SL / TP Geometry is authoritative and NEVER overridden:
   - LONG: SL < Entry < TP1 < TP2 < TP3
   - SHORT: SL > Entry > TP1 > TP2 > TP3
   - If invalid: REJECT candidate. Never reorder or invent synthetic targets.
4. Gamma and regime may influence priority rank and preference for tighter/wider structural targets,
   but must NEVER invent artificial fixed bounds (no arbitrary 'SL <= 1%').
"""
from __future__ import annotations

from typing import Any, Dict, Optional


def validate_target_geometry(entry: float, sl: float, tp1: float, tp2: Optional[float] = None, tp3: Optional[float] = None, direction: str = "LONG") -> Tuple[bool, str]:
    if entry <= 0 or sl <= 0 or tp1 <= 0:
        return False, "Non-positive price in trade candidate"
    
    if direction == "LONG":
        if not (sl < entry < tp1):
            return False, f"Invalid LONG geometry: SL ({sl}) must be < Entry ({entry}) < TP1 ({tp1})"
        if tp2 is not None and not (tp1 < tp2):
            return False, f"Invalid LONG geometry: TP1 ({tp1}) must be < TP2 ({tp2})"
        if tp3 is not None and tp2 is not None and not (tp2 < tp3):
            return False, f"Invalid LONG geometry: TP2 ({tp2}) must be < TP3 ({tp3})"
        if tp3 is not None and tp2 is None:
            return False, "Invalid LONG geometry: TP3 populated without TP2"
    elif direction == "SHORT":
        if not (sl > entry > tp1):
            return False, f"Invalid SHORT geometry: SL ({sl}) must be > Entry ({entry}) > TP1 ({tp1})"
        if tp2 is not None and not (tp1 > tp2):
            return False, f"Invalid SHORT geometry: TP1 ({tp1}) must be > TP2 ({tp2})"
        if tp3 is not None and tp2 is not None and not (tp2 > tp3):
            return False, f"Invalid SHORT geometry: TP2 ({tp2}) must be > TP3 ({tp3})"
        if tp3 is not None and tp2 is None:
            return False, "Invalid SHORT geometry: TP3 populated without TP2"
    else:
        return False, f"Unknown direction: {direction}"

    return True, "VALID"


def compute_canonical_rr(entry: float, sl: float, tp1: float, direction: str = "LONG") -> float:
    if direction == "LONG":
        risk = entry - sl
        reward = tp1 - entry
    else:
        risk = sl - entry
        reward = entry - tp1
    if risk <= 0:
        return 0.0
    return round(reward / risk, 2)


def classify_trade_priority(candidate: Dict[str, Any], market_context: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluates candidate trade priority with cleanly decoupled Gamma, Regime, and Direction."""
    entry = float(candidate.get("entry_price") or candidate.get("entry") or candidate.get("breakout_price") or 0.0)
    sl = float(candidate.get("sl") or candidate.get("stop_loss") or candidate.get("suggested_sl") or 0.0)
    tp1 = float(candidate.get("tp1") or candidate.get("target_price") or candidate.get("suggested_tp1") or 0.0)
    tp2 = float(candidate["tp2"]) if candidate.get("tp2") is not None else (float(candidate["suggested_tp2"]) if candidate.get("suggested_tp2") is not None else None)
    tp3 = float(candidate["tp3"]) if candidate.get("tp3") is not None else (float(candidate["suggested_tp3"]) if candidate.get("suggested_tp3") is not None else None)
    direction = str(candidate.get("direction", "LONG")).upper()
    symbol = str(candidate.get("symbol", "")).upper()

    # 1. Authoritative Geometry Validation
    geom_ok, geom_reason = validate_target_geometry(entry, sl, tp1, tp2, tp3, direction)
    if not geom_ok:
        return {
            "priority": "DISQUALIFIED",
            "eligible": False,
            "status": "REJECTED_GEOMETRY",
            "reason": geom_reason,
            "risk_reward": 0.0,
            "gamma_state": "N/A",
            "market_regime": "N/A",
            "htf_alignment": False,
        }

    # 2. Canonical Risk/Reward (descriptive & informational, decoupled from eligibility by default)
    rr = compute_canonical_rr(entry, sl, tp1, direction)
    strict_rr = bool(candidate.get("strict_rr_gate", False) or market_context.get("strict_rr_gate", False))
    if strict_rr and rr < 1.0:
        return {
            "priority": "DISQUALIFIED",
            "eligible": False,
            "status": "REJECTED_RISK_REWARD",
            "reason": f"Canonical R:R ({rr:.2f}) < 1.0 minimum threshold",
            "risk_reward": rr,
            "gamma_state": "N/A",
            "market_regime": "N/A",
            "htf_alignment": False,
            "priority_reasons": [f"Canonical R:R ({rr:.2f}) is below 1.0:1 break-even threshold"],
            "actionability_score": 0.0,
        }

    # 3. Decoupled Context Extraction
    raw_gamma = str(market_context.get("gamma_regime", "")).upper()
    if any(k in symbol for k in ("SOL", "XRP", "GOLD", "XAU")):
        gamma_state = "GAMMA DATA NOT AVAILABLE"
    elif "POSITIVE" in raw_gamma:
        gamma_state = "POSITIVE_GAMMA"
    elif "NEGATIVE" in raw_gamma:
        gamma_state = "NEGATIVE_GAMMA"
    else:
        gamma_state = "GAMMA DATA NOT AVAILABLE"

    market_regime = str(market_context.get("market_regime", "UNCERTAIN")).upper()
    htf_bias = str(market_context.get("htf_bias") or market_context.get("daily_preference") or "NEUTRAL").upper()
    allows_counter_trend = bool(market_context.get("allows_counter_trend", False))

    # 4. Alignment & Countertrend Analysis
    is_aligned = (direction == htf_bias) or (htf_bias == "NEUTRAL")
    is_countertrend = not is_aligned and htf_bias in ("LONG", "SHORT")

    if is_countertrend and not allows_counter_trend and "TREND" in market_regime:
        return {
            "priority": "DISQUALIFIED",
            "eligible": False,
            "status": "REJECTED_COUNTERTREND",
            "reason": f"Countertrend {direction} prohibited in strong {market_regime} against {htf_bias} bias",
            "risk_reward": rr,
            "gamma_state": gamma_state,
            "market_regime": market_regime,
            "htf_alignment": False,
            "priority_reasons": [f"Countertrend {direction} prohibited in strong {market_regime} against {htf_bias} bias"],
            "actionability_score": 0.0,
        }

    # 5. Explainable Priority & Actionability Ranking (Phase 4 Refinement)
    # Primary ranking: Setup maturity / actionability stage
    raw_state = candidate.get("current_state") or candidate.get("retest_state")
    current_state = str(raw_state).upper() if raw_state else "ENTRY_READY"
    
    state_base_scores = {
        "ENTRY_READY": 1000,
        "ENTRY_CANDIDATE": 1000,
        "CONFIRMING_REJECTION": 800,
        "REJECTION_CONFIRMED": 800,
        "RETEST_TOUCHED": 600,
        "RETEST_ZONE_TOUCHED": 600,
        "WAITING_FOR_RETEST": 400,
        "IDENTIFIED": 200,
        "TRIGGERED": 100,
        "EXPIRED": 50,
        "INVALIDATED": 0,
    }
    actionability_score = float(state_base_scores.get(current_state, 500))
    priority_reasons: list[str] = []

    # Reason 1: Maturity Stage
    if current_state in ("ENTRY_READY", "ENTRY_CANDIDATE"):
        priority_reasons.append("Setup fully matured: all entry & structural conditions satisfied")
    elif current_state in ("CONFIRMING_REJECTION", "REJECTION_CONFIRMED"):
        priority_reasons.append("Retest confirmed: candle rejection formed at zone")
    elif current_state in ("RETEST_TOUCHED", "RETEST_ZONE_TOUCHED"):
        priority_reasons.append("Retest zone touched: awaiting rejection wick confirmation")
    elif current_state in ("WAITING_FOR_RETEST", "IDENTIFIED"):
        priority_reasons.append(f"Breakout established: actively monitoring approach to retest zone")

    # Reason 2: Proximity / Volatility-Aware Distance
    dist_atr = candidate.get("distance_atr")
    dist_pct = candidate.get("distance_pct")
    if dist_atr is not None:
        try:
            d_atr = float(dist_atr)
            if d_atr <= 0.25:
                actionability_score += 150
                priority_reasons.append(f"Zone proximity: extremely close ({d_atr:.2f} ATR / {dist_pct or 0.0:.2f}%)")
            elif d_atr <= 0.50:
                actionability_score += 100
                priority_reasons.append(f"Zone proximity: approaching ({d_atr:.2f} ATR / {dist_pct or 0.0:.2f}%)")
            elif d_atr <= 1.00:
                actionability_score += 50
                priority_reasons.append(f"Zone proximity: within 1.0 ATR ({d_atr:.2f} ATR)")
        except (ValueError, TypeError):
            pass

    # Reason 3: Supporting Strategy Conditions
    conditions = candidate.get("conditions") or []
    if isinstance(conditions, list):
        for c in conditions:
            c_name = c.get("name")
            c_status = c.get("status")
            if c_status == "MET":
                actionability_score += 25
                priority_reasons.append(f"{c_name}: verified MET")
            elif c_status == "PENDING":
                priority_reasons.append(f"{c_name}: pending confirmation")

    # Reason 4: HTF Alignment & Regime Context
    if is_aligned:
        actionability_score += 50
        priority_reasons.append(f"Higher-Timeframe Alignment: {direction} aligns with {htf_bias} daily bias")
    elif is_countertrend:
        actionability_score -= 30
        priority_reasons.append(f"Countertrend: {direction} opposes {htf_bias} daily bias")

    if "TREND" in market_regime:
        if is_aligned:
            actionability_score += 30
            priority_reasons.append(f"Regime synergy: {market_regime} supports directional expansion")
        if gamma_state == "NEGATIVE_GAMMA":
            actionability_score += 20
            priority_reasons.append("Negative gamma regime: volatility accelerator favors trend expansion")
    elif "CHOP" in market_regime:
        if gamma_state == "POSITIVE_GAMMA":
            actionability_score += 20
            priority_reasons.append("Positive gamma regime: dampens volatility, favoring mean reversion retest")

    # Reason 5: Descriptive R:R Context
    priority_reasons.append(f"Canonical R:R: {rr:.2f}:1 (SL: {sl:.2f}, Entry: {entry:.2f}, TP1: {tp1:.2f})")
    if rr >= 2.5:
        actionability_score += 30
    elif rr >= 1.8:
        actionability_score += 15

    # Reason 6: Data Freshness
    freshness = candidate.get("data_freshness") or {}
    if isinstance(freshness, dict):
        q = freshness.get("quality", "GOOD")
        age = freshness.get("data_age_seconds", 0.0)
        if q == "GOOD":
            actionability_score += 15
            priority_reasons.append(f"Data freshness: live (< {age:.0f}s old)")
        elif q == "STALE":
            actionability_score -= 100
            priority_reasons.append(f"Data warning: market data is stale ({age:.0f}s old)")

    # 6. Assign Tier from Actionability Score & State
    if current_state in ("INVALIDATED", "EXPIRED"):
        priority = "DISQUALIFIED"
        eligible = False
        status = current_state
    elif is_countertrend:
        # Countertrend trade with explicit permission receives at most MEDIUM priority
        priority = "MEDIUM" if actionability_score >= 400 else "LOW"
        eligible = True
        status = "APPROVED"
    elif actionability_score >= 650 or current_state in ("ENTRY_READY", "CONFIRMING_REJECTION"):
        priority = "HIGH"
        eligible = True
        status = "APPROVED"
    elif actionability_score >= 400 or current_state in ("RETEST_TOUCHED", "WAITING_FOR_RETEST"):
        priority = "MEDIUM"
        eligible = True
        status = "APPROVED"
    else:
        priority = "LOW"
        eligible = True
        status = "APPROVED"

    return {
        "priority": priority,
        "eligible": eligible,
        "status": status,
        "reason": f"Classified {priority} (Actionability {actionability_score:.0f}, Stage {current_state}, R:R {rr:.2f})",
        "risk_reward": rr,
        "gamma_state": gamma_state,
        "market_regime": market_regime,
        "htf_alignment": is_aligned,
        "is_countertrend": is_countertrend,
        "actionability_score": round(actionability_score, 1),
        "priority_reasons": priority_reasons,
    }

