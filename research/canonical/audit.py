"""Regimes (spec §17, predeclared, causal) + invariant checks (spec §21) + audit builder."""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd


# ------------------------------------------------------------------ regimes (§17)

def compute_regimes(candles: pd.DataFrame, cfg) -> Dict[int, str]:
    """Causal regime bucket per bar index. NULL before 288-bar history."""
    close = candles["close"].to_numpy(float)
    n = len(close)
    out: Dict[int, str] = {}
    from .indicators import atr_pct
    ap = atr_pct(candles, cfg.regime_atr_length)
    # rolling median of atr_pct over lookback (causal: window ending at i)
    med = pd.Series(ap).rolling(cfg.regime_vol_lookback_bars, min_periods=cfg.regime_vol_lookback_bars).median().to_numpy()
    for i in range(n):
        if i < cfg.regime_vol_lookback_bars or not np.isfinite(med[i]) or not np.isfinite(ap[i]):
            continue
        ret24 = close[i] / close[i - 288] - 1.0 if i >= 288 else None
        if ret24 is None:
            continue
        if ret24 >= cfg.regime_ret24h_up:
            out[i] = "TREND_UP"
        elif ret24 <= cfg.regime_ret24h_down:
            out[i] = "TREND_DOWN"
        elif ap[i] >= med[i]:
            out[i] = "HIGH_VOL"
        else:
            out[i] = "CHOP"
    return out


# ------------------------------------------------------------------ invariants (§21)

def check_invariants(trades, skipped, unfilled_eod, signals, candles, cfg,
                     anchor_expected=None) -> List[str]:
    errors: List[str] = []
    otime = candles["candle_open_time"].to_numpy().astype(np.int64)
    idx_of = {int(t): i for i, t in enumerate(otime)}
    sig_ids = [s.signal_id for s in signals]
    if len(set(sig_ids)) != len(sig_ids):
        errors.append("I3 duplicate signal_id")

    taken_ids = set()
    open_bars = []
    for t in trades:
        sid = t.intent.signal_id
        if sid in taken_ids:
            errors.append(f"I4 duplicate trade for {sid}")
        taken_ids.add(sid)
        e_ref = int(t.intent.entry_reference_open_time_ms)
        if idx_of.get(e_ref) != t.entry_idx:
            errors.append(f"I1 entry offset wrong for {sid}")
        d = t.intent.direction
        ep = t.entry_price_theoretical
        if d == 1 and not (t.stop_price < ep):
            errors.append(f"I2 stop side LONG {sid}")
        if d == -1 and not (t.stop_price > ep):
            errors.append(f"I2 stop side SHORT {sid}")
        rp = t.risk_frac
        if not (0 < rp <= 0.05):
            errors.append(f"I3 risk_pct {rp} out of bounds {sid}")
        prim = t.outcomes[t.primary_policy]
        # I5 terminal monotonicity: primary exit >= entry
        if prim.exit_idx < t.entry_idx:
            errors.append(f"I5 exit before entry {sid}")
        open_bars.append((t.entry_idx, prim.exit_idx))
    # single-position overlap check on primary paths
    open_bars.sort()
    for (s1, e1), (s2, _) in zip(open_bars, open_bars[1:]):
        if s2 <= e1:
            errors.append(f"I5 overlapping positions: bars {s1}-{e1} and {s2}")
    # I6 fill sanity: touch fills equal level; gap fills equal bar open — verified in T06-T09
    # I7 acceptance anchor
    n_sig = len(signals)
    n_long = sum(1 for s in signals if s.direction == 1)
    n_short = sum(1 for s in signals if s.direction == -1)
    if anchor_expected is not None:
        exp_total, exp_long, exp_short = anchor_expected
        if not (n_sig == exp_total and n_long == exp_long and n_short == exp_short):
            errors.append(
                f"I7 ANCHOR MISMATCH: got {n_sig}/{n_long}/{n_short} "
                f"expected {exp_total}/{exp_long}/{exp_short}")
    # I8/I9 handled by runner (gates passed pre-run); I10 structural by construction;
    # I11 regime labels validated at attach time; I12 counts reported in audit body.
    return errors


def build_audit_md(cfg, manifest, gates_stats, signals, trades, skipped,
                   unfilled_eod, invariant_errors, anchor_check, notes) -> str:
    n_sig = len(signals)
    n_long = sum(1 for s in signals if s.direction == 1)
    n_short = n_sig - n_long
    lines = [
        "# OPHELIA CANONICAL AUDIT",
        "",
        f"- run_id: `{manifest['run_id']}`",
        f"- engine_version: {manifest['engine_version']} | spec_version: {manifest['spec_version']}",
        f"- dataset: {cfg.dataset_id} {cfg.dataset_version} sha256={manifest['dataset_sha256'][:16]}…",
        f"- strategy: {cfg.strategy_id} v{cfg.strategy_version} | indicator_source: {cfg.indicator_source}",
        f"- config sha256: {manifest['config_sha256'][:16]}…",
        "",
        "## Integrity gates",
        f"- G1–G9 executed pre-run; missing candles: {gates_stats.get('missing_candle_count')}; "
        f"duplicates: {gates_stats.get('duplicate_timestamp_count')}; "
        f"invalid OHLC: {gates_stats.get('invalid_ohlc_count', 'n/a')}; "
        f"zero-volume bars: {gates_stats.get('zero_volume_bar_count')} (volume_available="
        f"{gates_stats.get('volume_available')})",
        "",
        "## Counts",
        f"- signals: {n_sig} (LONG {n_long} / SHORT {n_short})",
        f"- trades taken: {len(trades)}",
        f"- ignored POSITION_OPEN: {sum(1 for s in skipped if s.reason=='POSITION_OPEN')}",
        f"- ignored SIGNAL_PENDING: {sum(1 for s in skipped if s.reason=='SIGNAL_PENDING')}",
        f"- TRIGGER_EXPIRED: {sum(1 for s in skipped if s.reason=='TRIGGER_EXPIRED')}",
        f"- UNFILLED_EOD: {unfilled_eod}",
        f"- censored (open at dataset end): {sum(1 for t in trades if t.censored)}",
        "",
        "## Acceptance anchor (D2)",
        f"- {anchor_check}",
        "",
        "## Invariants",
        "- ALL PASS" if not invariant_errors else ("- FAILURES:" + "".join(
            f"\n  - {e}" for e in invariant_errors)),
        "",
        "## Standing notes",
    ]
    lines += [f"- {n}" for n in notes]
    lines += [
        "",
        "## Funding",
        "- funding_status = NOT_MODELED on every row (spec D17). Funding drag is NOT",
        "  assumed to be zero; it is unaccounted until an external overlay exists.",
        "",
        "## Ambiguity policy",
        f"- {cfg.ambiguity_policy}: same-candle stop+target resolves as LOSS (A1).",
        "- Within-bar order assumed OPEN → {{HIGH, LOW}} → CLOSE (D14).",
    ]
    return "\n".join(lines) + "\n"
