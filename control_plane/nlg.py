"""Deterministic natural-language rendering of control-plane results.

Every number shown to the user comes from a tool/engine output in this module.
The LLM never fabricates figures: it interprets, this module formats.
"""
from __future__ import annotations

from typing import Any

from . import analytics, config


def _usd(price: float | None) -> str:
    """Format a price with magnitude-appropriate decimals (min 2 for >= $1)."""
    if price is None:
        return "n/a"
    p = abs(float(price))
    if p >= 1000:
        return f"${float(price):,.2f}"
    if p >= 1:
        s = f"{float(price):,.4f}"
        int_part, _dot, frac = s.partition(".")
        frac = frac.rstrip("0")
        if len(frac) < 2:
            frac = frac.ljust(2, "0")
        return f"${int_part}.{frac}"
    s = f"${float(price):,.6f}".rstrip("0").rstrip(".")
    if s.endswith("$") or s.endswith("."):
        s = f"${float(price):,.6f}"
    return s


def _pct(x: float | None, digits: int = 2) -> str:
    if x is None:
        return "n/a"
    sign = "+" if x > 0 else ""
    return f"{sign}{float(x):.{digits}f}%"


def _move_pct(x: float | None) -> str:
    """Precision-aware percent for small per-candle moves (never shows a bare 0%)."""
    if x is None:
        return "n/a"
    v = abs(float(x))
    if v < 0.0005:
        return "<0.001%"
    digits = 3 if v >= 0.05 else (4 if v >= 0.005 else 5)
    s = f"{float(x):.{digits}f}".rstrip("0").rstrip(".")
    return f"{s}%"


_PARAM_LABELS = {
    "strategy": "the strategy",
    "symbol": "which symbol",
    "timeframe_min": "the timeframe (for example 1m or 5m)",
    "margin_usage_pct": "margin percent (for example 50%)",
    "leverage": "leverage (for example 20x)",
}


def missing_params_message(missing: list[str], ctx: dict) -> str:
    """Ask naturally for the parameters still required before arming."""
    known = []
    label_map = [("Strategy", "strategy"), ("Symbol", "symbol"),
                 ("Timeframe", "timeframe_min"), ("Preference", "direction_preference"),
                 ("Margin", "margin_usage_pct"), ("Leverage", "leverage")]
    for label, key in label_map:
        v = ctx.get(key)
        if v is None:
            continue
        if key == "timeframe_min":
            v = f"{v}m"
        elif key == "direction_preference":
            v = str(v).lower()
        elif key in ("margin_usage_pct",):
            v = f"{v}%"
        elif key == "leverage":
            v = f"{float(v):g}x"
        known.append(f"{label}: {v}")
    lines = []
    if known:
        lines.append("Got it. Noted so far:\n" + "\n".join(f"- {k}" for k in known))
    asks = [_PARAM_LABELS.get(m, m) for m in missing]
    if len(asks) == 1:
        lines.append(f"Before I can prepare this, I still need {asks[0]}.")
    else:
        joined = ", ".join(asks[:-1]) + f" and {asks[-1]}"
        lines.append(f"Before I can prepare this, I still need {joined}.")
    return "\n".join(lines)


def _volume_wording(pct_diff: float) -> str:
    if pct_diff > 25:
        return "well above"
    if pct_diff > 5:
        return "slightly above"
    if pct_diff >= -5:
        return "roughly in line with"
    if pct_diff >= -25:
        return "slightly below"
    return "well below"


def volume_comparison(symbol: str, lookback_min: int) -> dict:
    """Compare traded volume of the last window against the preceding equal window."""
    cd = analytics.get_candles(symbol, lookback_min * 2 + 2, 1, 1)
    if "error" in cd or cd["count"] < 6:
        return {"error": "insufficient data for volume comparison"}
    rows = cd["candles"]
    cutoff = rows[-1]["ts"] - lookback_min * 60_000
    recent = sum(r["volume"] or 0 for r in rows if r["ts"] >= cutoff)
    prev_rows = [r for r in rows if r["ts"] < cutoff]
    prev = sum(r["volume"] or 0 for r in prev_rows[-lookback_min:])
    if prev <= 0:
        return {"error": "no baseline volume in previous window"}
    diff_pct = (recent - prev) / prev * 100
    return {"recent_volume": round(recent, 2), "previous_volume": round(prev, 2),
            "diff_pct": round(diff_pct, 1),
            "wording": _volume_wording(diff_pct)}


def _spread_label(spread_pct: float) -> str:
    a = abs(spread_pct)
    if a < 0.05:
        return "still very small"
    if a < 0.15:
        return "small but visible"
    return "fairly wide"


def market_snapshot_summary(symbol: str, snap: dict, lookback_min: int,
                            agg_min: int) -> str:
    """Render get_market_snapshot output as a short natural briefing."""
    if "error" in snap:
        return (f"I don't have usable recent data for {symbol} "
                f"({snap['error']}). The ingest service may still be warming up.")
    px = snap.get("last_price")
    ind = snap.get("indicators", {})
    e9 = ind.get("EMA9")
    e20 = ind.get("EMA20")
    state = str(ind.get("EMA_state", "n/a")).lower()
    lines = [f"{symbol} is at {_usd(px)}.", ""]
    if e9 is not None and e20 is not None:
        spread_pct = (e9 - e20) / px * 100 if px else None
        lines.append(f"EMA9: {e9:g} | EMA20: {e20:g}")
        if spread_pct is not None:
            lines.append(f"EMA state: {state} (separation {_pct(spread_pct)}, "
                         f"{_spread_label(spread_pct)})")
    mv = analytics.movement_stats(symbol, lookback_min, agg_min)
    if "error" not in mv:
        tf_label = f"{agg_min}m" if agg_min > 1 else "1m"
        lines.append(
            f"Average {tf_label} movement over the last {lookback_min} min: "
            f"{_move_pct(mv['avg_abs_move_pct'])} | net {_pct(mv['net_move_pct'])}")
    vc = volume_comparison(symbol, lookback_min)
    if "error" not in vc:
        lines.append(f"Volume over that window is {vc['wording']} the "
                     f"preceding {lookback_min} min ({_pct(vc['diff_pct'], 0)}).")
    if state == "bullish":
        read = ("Short-term structure currently reads bullish, though confirmation "
                "still requires an actual crossover event.")
    elif state == "bearish":
        read = ("Short-term structure currently reads bearish; a bullish turn would "
                "need a confirmed crossover first.")
    else:
        read = "Indicator state is currently unclear."
    lines.append(read)
    return "\n".join(lines)


def movement_summary(symbol: str, m: dict, agg_min: int | None) -> str:
    if "error" in m:
        return f"Movement data unavailable for {symbol}: {m['error']}"
    tf_label = f"{agg_min}m" if (agg_min or 1) > 1 else "1-minute"
    return (
        f"{symbol} over the last {m['window_min']} minutes "
        f"(per-{tf_label} candles):\n"
        f"- average move: {_move_pct(m['avg_abs_move_pct'])}\n"
        f"- largest single candle move: {_move_pct(m['max_abs_move_pct'])}\n"
        f"- net move: {_pct(m['net_move_pct'])} ({m['direction'].lower()})\n"
        f"- total range: {m['range_pct']:.3f}%")


def trade_flow_summary(symbol: str, f: dict, lookback_min: int) -> str:
    if f.get("total") is None or "error" in f:
        return (f"Buy/sell flow for {symbol} is unavailable right now "
                f"({f.get('error', 'no taker data')}).")
    lean = ("buyers are more aggressive" if f["net_flow"] > 0 else
            "sellers are more aggressive" if f["net_flow"] < 0
            else "pressure is balanced")
    return (
        f"{symbol} flow over the last {lookback_min} min (taker-based estimate):\n"
        f"- total volume: {f['total']:,.2f}\n"
        f"- aggressive buy (inflow): {f['inflow']:,.2f}\n"
        f"- aggressive sell (outflow): {f['outflow']:,.2f}\n"
        f"- net flow: {f['net_flow']:,.2f} ({_pct(f['net_flow_pct'])}) -> {lean}.\n"
        "Note: inflow/outflow are taker-buy approximations, not exact exchange flows.")


def volume_profile_summary(vp: dict) -> str:
    if "error" in vp:
        return f"Volume profile unavailable: {vp['error']}"
    return (
        f"Volume profile over the last {vp['window_min']} min:\n"
        f"- point of control: {_usd(vp['POC'])}\n"
        f"- value area: {_usd(vp['VAL'])} to {_usd(vp['VAH'])} (~70% of volume)\n"
        "Price inside the value area usually means balance; outside suggests trend.")


def orderbook_summary(ob: dict) -> str:
    if "error" in ob:
        return f"Order book unavailable: {ob['error']}"
    lean = ("bids are heavier" if ob["imbalance_pct"] > 0 else
            "asks are heavier" if ob["imbalance_pct"] < 0 else "balanced")
    return (
        f"BingX perpetual order book (top {ob['levels_returned']} levels):\n"
        f"- best bid {_usd(ob['best_bid'])} | best ask {_usd(ob['best_ask'])}\n"
        f"- spread: {ob['spread']:g} ({ob['spread_bps']} bps)\n"
        f"- top-of-book imbalance: {ob['imbalance_pct']}% -> {lean}")


def crossover_estimate_summary(ce: dict, tf_min: int) -> str:
    if ce.get("estimate_bars"):
        return (
            f"EMA state right now: {ce['state']} (spread {ce['spread_now']:g}).\n"
            f"At the recent convergence rate, a crossover toward "
            f"{ce['would_cross_to']} looks possible within roughly "
            f"{ce['estimate_bars']:g} x {tf_min}-minute candles.\n"
            "That is a linear extrapolation - an ESTIMATE, not a prediction. "
            "One strong candle can change it immediately.")
    note = ce.get("note", "insufficient data")
    return (f"No reliable crossover timing estimate right now: {note}. "
            f"Current EMA state is {ce.get('state', 'unclear')}. Estimates need a "
            "clear recent convergence slope.")


def proposal_summary(proposal: dict) -> str:
    """Stage-A proposal message (spec section 5)."""
    r = proposal.get("risk", {})
    pref = str(proposal.get("direction_preference", "ANY")).lower()
    pref_note = ""
    if pref in ("bullish", "bearish"):
        pref_note = (f"\nDirection preference: {pref} - this is a preference only; "
                     "a valid setup in the opposite direction can still be taken.")
    return (
        "Here's what I'm proposing:\n\n"
        f"{proposal['symbol']} | EMA 9/20 crossover | {proposal['timeframe_min']}m\n"
        f"Margin: {r.get('allocated_margin', '?')} USDT "
        f"| Leverage: {float(proposal.get('leverage', r.get('leverage', '?'))):g}x "
        f"| Reference notional: {r.get('notional', '?')} USDT\n"
        f"Reference entry: {_usd(proposal.get('entry_ref_price'))} "
        f"| Current EMA state: {proposal.get('ema_state', 'n/a').lower()}\n"
        f"Mode: SHADOW - nothing touches the live exchange.{pref_note}\n\n"
        "Entries will only happen after a confirmed crossover.\n"
        "Do you want me to arm this? (YES / NO)")


def config_recap(spec: dict) -> str:
    """Natural recap of the pending configuration (no re-proposal)."""
    pref = str(spec.get("direction_preference") or "any").lower()
    return (
        "Current pending configuration:\n"
        f"- strategy: EMA 9/20 crossover\n"
        f"- symbol: {spec.get('symbol', '?')}\n"
        f"- timeframe: {spec.get('timeframe_min', '?')}m\n"
        f"- direction preference: {pref} (preference only, not a restriction)\n"
        f"- margin: {spec.get('margin_usage_pct', '?')}% at "
        f"{float(spec.get('leverage') or 0):g}x leverage\n"
        "- mode: SHADOW\n\n"
        "Say YES to arm it, or tell me what to change.")


def armed_confirmation(out: dict) -> str:
    p = out.get("proposal", {})
    return (
        f"Armed. Automation #{out['automation_id']} is now watching "
        f"{p.get('symbol', '')} on the {p.get('timeframe_min', '?')}m chart for a "
        "confirmed EMA 9/20 crossover.\n"
        "When it triggers, I'll prepare the shadow trade and ask you before anything "
        "is recorded. Mode stays SHADOW.")


def triggered_trade_summary(ev: dict) -> str:
    return (
        f"Crossover confirmed: {'BULLISH' if ev['direction'] == 'LONG' else 'BEARISH'} "
        f"EMA 9/20 on {ev['symbol']}.\n\n"
        f"Prepared shadow trade #{ev['proposal_trade_id']}:\n"
        f"- direction: {ev['direction']}\n"
        f"- entry reference: {_usd(ev['entry'])}\n"
        f"- stop: {_usd(ev['stop'])} | target: {_usd(ev['target'])}\n"
        f"- qty: {ev['qty']}\n\n"
        "Record this shadow trade? (YES / NO, or 'skip it')")


def automations_summary(rows: list[dict]) -> str:
    if not rows:
        return "You have no automations right now."
    lines = ["Your automations:"]
    for r in rows:
        pref = (r.get("direction_pref") or "any").lower()
        lines.append(
            f"- #{r['id']} {r['status']}: {r['strategy'].replace('_', ' ').title()} "
            f"on {r['symbol']} {r['timeframe']}m, prefer {pref}, "
            f"{r['margin_usage_pct']:g}% margin at {float(r['leverage']):g}x "
            f"({str(r.get('mode', 'SHADOW')).lower()} mode)")
    return "\n".join(lines)


def automation_status_change(aid: int, status: str) -> str:
    verb = {"PAUSED": "paused", "ACTIVE": "resumed",
            "CANCELLED": "cancelled", "TRIGGERED_AWAITING_CONFIRM": "triggered"}.get(
        status, status.lower())
    return f"Automation #{aid} is now {verb}."


def news_summary(ctx: dict) -> str:
    bias = ctx.get("daily_bias", "UNKNOWN")
    conf = ctx.get("confidence", 0)
    reasons = ctx.get("reason_codes", [])
    strength = ctx.get("bias_strength")
    lines = [f"Today's market bias: {bias} (confidence {conf:g})."]
    if strength is not None:
        lines.append(f"Bias strength score: {strength:+g}.")
    if reasons:
        lines.append("Basis: " + "; ".join(str(x) for x in reasons) + ".")
    lines.append("Remember: this bias is a preference only. A sufficiently strong "
                 "technical setup against it remains valid.")
    lines.append("(Macro, dollar, rates and calendar inputs are unavailable from "
                 "free sources, so they're scored UNKNOWN rather than guessed.)")
    return "\n".join(lines)


def health_summary(h: dict) -> str:
    dh = h.get("data_health", {})
    age = dh.get("data_age_min")
    age_txt = f"{age:g} min old" if age is not None else "no data yet"
    cleanup = dh.get("last_cleanup_min_ago")
    cleanup_txt = (f"{cleanup:g} min ago" if cleanup is not None
                   else "not run yet")
    sess = h.get("sessions", {})
    blackout = sess.get("blackout_new_entries")
    ss = h.get("sessions", {}).get("sessions_active_utc", [])
    return (
        "Ophelia is healthy.\n\n"
        f"CPU: {h.get('cpu_pct', '?')}% | RAM used: {h.get('ram_used_pct', '?')}% "
        f"({h.get('ram_available_gb', '?')} GB free) | Disk: {h.get('disk_used_pct', '?')}%\n"
        f"Data feed: rolling 1m store has {dh.get('rows', 0):,} rows; latest candle "
        f"is {age_txt}.\n"
        f"Retention/cleanup: last ran {cleanup_txt} "
        f"({'healthy' if dh.get('cleanup_ok') else 'check logs'}).\n"
        f"Trading engine: SHADOW mode. Blackout active: {'yes' if blackout else 'no'}.\n"
        f"Active sessions: {', '.join(ss) if ss else 'none'}.\n"
        "LLM: qwen3 4B loaded via Ollama.")


def supertrend_summary(st: dict) -> str:
    if "error" in st:
        return f"Supertrend unavailable: {st['error']}"
    side = "above" if st["price"] > st["line"] else "below"
    return (f"Supertrend (10, 4) on {st['timeframe_min']}m: "
            f"{st['state']}/{('BULLISH' if st['direction'] == 1 else 'BEARISH')} | "
            f"active line {_usd(st['line'])} | price {_usd(st['price'])} "
            f"({side} the line)")


def vwap_summary(v: dict) -> str:
    if "error" in v:
        return f"VWAP unavailable: {v['error']}"
    return (f"Session VWAP on {v['timeframe_min']}m: {_usd(v['vwap'])} | "
            f"price is {_pct(v['distance_pct'])} "
            f"{'above' if v['above'] else 'below'} VWAP "
            f"(UTC session, resets 00:00 UTC)")


LLM_DOWN_MESSAGE = ("My language service (local LLM) is temporarily unavailable, so I "
                    "can't parse free-form messages right now. Ophelia core and the "
                    "market-data services are still running normally. Try again in a "
                    "moment - fixed phrases like 'health' still work.")
FALLBACK_CHAT = ("Understood. I couldn't map that to a specific action - try asking "
                 "about a symbol, your automations, or say 'health'.")


_SYMBOL_ALIASES = {
    "btc": "BTC-USDT", "bitcoin": "BTC-USDT",
    "eth": "ETH-USDT", "ethereum": "ETH-USDT",
    "sol": "SOL-USDT", "solana": "SOL-USDT",
    "xrp": "XRP-USDT", "bnb": "BNB-USDT", "ada": "ADA-USDT",
    "doge": "DOGE-USDT", "link": "LINK-USDT", "avax": "AVAX-USDT",
}


def extract_params_from_text(text: str) -> dict:
    """Deterministically extract trading parameters explicitly present in text.

    This is a safety net against LLM fabrication: only values literally written
    by the user (or unambiguous aliases) are accepted into proposals.
    """
    import re
    t = text.lower()
    out: dict = {}
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:m\b|min\b|minutes?\b)", t)
    if m:
        v = int(float(m.group(1)))
        if v in (1, 2, 3, 5, 10, 15, 30, 60):
            out["timeframe_min"] = v
    m = re.search(r"(\d+(?:\.\d+)?)\s*x\b", t)
    if m:
        out["leverage"] = float(m.group(1))
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", t)
    if m:
        out["margin_usage_pct"] = float(m.group(1))
    if re.search(r"\bbullish\b|\blongs?\s+preferred\b", t):
        out["direction_preference"] = "BULLISH"
    elif re.search(r"\bbearish\b|\bshorts?\s+preferred\b", t):
        out["direction_preference"] = "BEARISH"
    for alias, sym in _SYMBOL_ALIASES.items():
        if re.search(rf"\b{alias}\b", t):
            out["symbol"] = sym
            break
    else:
        for s in config.SYMBOLS:
            base = s.replace("-USDT", "").lower()
            if base and re.search(rf"\b{base}\b", t):
                out["symbol"] = s
                break
    if re.search(r"\bema\b|crossover", t):
        out["strategy"] = "EMA_CROSSOVER"
    elif re.search(r"\bvwap\b.*supertrend|supertrend", t):
        out["strategy"] = "VWAP_SUPERTREND"
    return out


def maybe_raw(text: str, natural: str, payload: Any) -> str:
    """Append compact JSON only when the user explicitly asked for raw output."""
    low = text.lower()
    if "raw" in low or "json" in low:
        import json as _j
        return natural + "\n\n(raw)\n" + _j.dumps(payload, default=str)[:1500]
    return natural

# ---------------------------------------------------------------- commands

def bingx_account_view(v: dict) -> str:
    """Ophelia-tracked accounting view. Deliberately EXCLUDES exchange-wide
    realized PnL (it mixes manual/external activity into Ophelia performance)."""
    if "error" in v:
        return f"BingX account unavailable: {v['error']}"
    a = v["account"]
    pnl = v["pnl"]
    lines = [
        "BINGX ACCOUNT",
        f"- wallet balance: {a['balance']:,.2f} {a['asset']}",
        f"- equity: {a['equity']:,.2f}",
        f"- available margin: {a['available_margin']:,.2f}",
        f"- used margin: {a['used_margin']:,.2f}",
        f"- unrealized PnL (exchange): {a['unrealized_pnl']:+,.4f}",
        f"- open exposure: {v['open_exposure']:,.2f} USDT "
        f"({len(v['positions'])} position(s))",
        "",
        "OPHELIA DAILY PNL (Ophelia-tracked only)",
        f"- realized: {pnl['realized']:+,.4f} USDT",
        f"- unrealized (Ophelia open positions): {pnl['unrealized']:+,.4f}",
        f"- total: {pnl['total']:+,.4f}",
        f"(accounting day {pnl['day_utc']} UTC; resets {pnl['resets']})",
    ]
    if pnl.get("realized_items"):
        for it in pnl["realized_items"][:6]:
            lines.append(f"  • {it['kind']} #{it['id']} "
                         f"{it.get('symbol', '')}: {it['pnl']:+.4f}")
    if v.get("positions"):
        lines.append("Exchange positions:")
        for p in v["positions"]:
            liq = (f", liq {_usd(p['liquidation_price'])}"
                   if p.get("liquidation_price") else "")
            lines.append(
                f"- {p['symbol']} {p['side']} {p['qty']:g} @ {_usd(p['entry'])} "
                f"| mark {_usd(p['mark'])} | {p['leverage']:g}x | "
                f"uPnL {p['unrealized_pnl']:+,.4f}{liq}")
    return "\n".join(lines)


def position_report(positions: list[dict], shadow_trades: list[dict],
                    last_prices: dict) -> str:
    if not positions and not shadow_trades:
        return "No active position."
    lines = []
    for p in positions:
        px = last_prices.get(p["symbol"], p["entry"])
        long = p["direction"] == "LONG"
        upnl = (px - p["entry"]) * p["qty"] * (1 if long else -1)
        pnl_pct = (px / p["entry"] - 1) * 100 * (1 if long else -1)
        lines.append(
            f"{p['symbol']} {p['direction']} ({p.get('mode', '?')} mode)\n"
            f"- entry {_usd(p['entry'])} | now {_usd(px)} | qty {p['qty']}\n"
            f"- leverage {float(p.get('leverage') or 1):g}x | margin "
            f"{p.get('margin_usdt') or '?'} USDT\n"
            f"- current stop: {_usd(p.get('stop_current')) or 'none'}\n"
            f"- stop conditions: {', '.join(s.get('type', '?') for s in (p.get('stops') or [])) or 'default'}\n"
            f"- unrealized PnL: {upnl:+.4f} USDT ({_pct(pnl_pct)})")
    for t in shadow_trades:
        lines.append(
            f"Shadow trade #{t['id']}: {t['direction']} {t.get('qty', '?')} @ "
            f"{_usd(t['entry'])} | stop {_usd(t['stop'])} | target "
            f"{_usd(t['target'])}")
    return "\n\n".join(lines)


def setup_report(spec: dict, status: str, mode: str) -> str:
    stops = spec.get("stops") or []
    targets = spec.get("targets") or []
    lines = [
        f"SETUP - {spec.get('symbol', '?')} {spec.get('timeframe_min', '?')}m "
        f"{spec.get('direction_preference') or 'ANY'}",
        f"Strategy: {str(spec.get('strategy') or 'EMA_CROSSOVER').replace('_', '/')}"
        " crossover",
        "Entry: confirmed crossover",
        f"Margin: {spec.get('margin_usage_pct', '?')}% | Leverage: "
        f"{float(spec.get('leverage') or 0):g}x",
        "Initial stop rules: " + (
            "; ".join(f"{s.get('value')}% {s.get('type')}" for s in stops)
            or "default ATR-based"),
        "First triggered stop: EXIT",
        "Targets: " + ("; ".join(
            f"{t.get('pct_qty')}% at +{t.get('move_pct')}%"
            for t in targets) or "single 2R target (default)"),
        "Trailing: " + (f"remaining qty, {spec.get('trailing_pct')}% buffer"
                        if spec.get("trailing_pct") else "none"),
        f"Mode: {mode}",
        f"Status: {status}",
    ]
    if spec.get("expiry_hours"):
        lines.append(f"Expiry: {spec.get('expiry_hours')}h")
    return "\n".join(lines)


def watchlist_report(rows: list[dict]) -> str:
    if not rows:
        return "Watchlist is empty. Say e.g. 'add SOL' to start tracking."
    lines = ["Watchlist:"]
    for r in rows:
        age = r.get("age_min")
        age_txt = f"{age:g} min old" if age is not None else "no data yet"
        px = _usd(r.get("last_price"))
        lines.append(f"- {r['symbol']} ({r.get('exchange', 'BINANCE')}): "
                     f"latest {px}, 1m candle {age_txt}, rows {r.get('rows', 0):,}")
    return "\n".join(lines)


def account_report(a: dict) -> str:
    if "error" in a:
        return f"BingX account unavailable: {a['error']}"
    lines = [
        "BingX perpetual account (read-only view):",
        f"- balance: {a['balance']:,.2f} {a['asset']}",
        f"- available margin: {a['available_margin']:,.2f}",
        f"- used margin: {a['used_margin']:,.2f}",
        f"- equity: {a['equity']:,.2f}",
        f"- unrealized PnL: {a['unrealized_pnl']:+,.4f}",
        f"- realized PnL (exchange, total): {a['realized_pnl_total']:+,.4f}",
        f"- today's realized (Ophelia-tracked): "
        f"{a['today_realized_ophelia']:+,.4f}",
        f"(today's session resets {a['today_resets_utc']})",
    ]
    if a.get("open_exchange_positions"):
        lines.append("Exchange positions:")
        for p in a["open_exchange_positions"]:
            liq = (f", liq {_usd(p['liquidation_price'])}"
                   if p.get("liquidation_price") else "")
            lines.append(
                f"- {p['symbol']} {p['side']} qty {p['qty']:g} @ "
                f"{_usd(p['entry'])} | mark {_usd(p['mark'])} | "
                f"{p['leverage']:g}x | uPnL {p['unrealized_pnl']:+,.4f}{liq}")
    else:
        lines.append("No open exchange positions.")
    return "\n".join(lines)


def status_report(s: dict) -> str:
    llm = s.get("llm", {})
    llm_txt = f"ok ({llm.get('primary')})" if llm.get("available") else "DOWN"
    if llm.get("last_error"):
        llm_txt += f" - last error: {llm['last_error']}"
    return (
        f"Mode: {s.get('mode')} | LLM: {llm_txt}\n"
        f"Data: {s.get('rows', 0):,} rows, newest "
        f"{s.get('data_age_min', '?')} min old\n"
        f"News bias: {s.get('news_bias')} | Blackout: "
        f"{'ACTIVE' if s.get('blackout') else 'no'}\n"
        f"Active automations: {s.get('active_automations', 0)} | "
        f"Open positions: {s.get('open_positions', 0)}\n"
        f"Sessions: {', '.join(s.get('sessions') or []) or 'none'}")


def hi_report(s: dict) -> str:
    attn = []
    if not s.get("llm", {}).get("available"):
        attn.append("LLM down")
    if (s.get("data_age_min") or 0) > 5:
        attn.append("market data stale")
    if s.get("blackout"):
        attn.append("new-entry blackout active")
    return (
        f"Ophelia here - {s.get('mode')} mode. "
        f"{s.get('active_automations', 0)} armed automation(s), "
        f"{s.get('open_positions', 0)} open position(s). "
        f"News bias {s.get('news_bias')}. "
        + ("Needs attention: " + ", ".join(attn) + "."
           if attn else "Everything nominal."))


def live_mode_message(current: str) -> str:
    return (
        f"Current trading mode: {current}.\n"
        "LIVE mode places REAL BingX orders with your configured risk; "
        "SHADOW mode simulates everything safely.\n"
        "- To enable live trading: /live on (double confirmation required)\n"
        "- To stop live trading: /live off")


def closeall_warning(mode: str, n: int) -> str:
    if mode == "LIVE":
        return (
            f"WARNING: This will close ALL {n} tracked position(s) AND send a "
            "close-all request to BingX at market price, regardless of "
            "configured strategy rules.\nType /yes to continue, /no to abort.")
    return (f"WARNING: This will close all {n} SHADOW position(s)/trades at "
            "current reference price.\nType /yes to continue, /no to abort.")
