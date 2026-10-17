"""Runner: end-to-end canonical pipeline (data -> strategy -> engine -> outputs)."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

if __package__ in (None, ""):
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from research.canonical import config as C
from research.canonical import __version__ as ENGINE_VERSION, SPEC_VERSION as SPEC_V
from research.canonical.config import CanonicalConfig
from research.canonical.data_contract import (
    DataIntegrityError, load_canonical_store, load_raw_tv_export,
    ingest_raw_to_canonical, write_canonical_store, drop_partial_final_candle,
    _sha256_file,
)
from research.canonical.strategies.vwap_supertrend import (
    VwapSupertrendVendorStrategy, VwapSupertrendEngineStrategy)
from research.canonical import execution as EX
from research.canonical import accounting as ACC
from research.canonical import metrics as MET
from research.canonical import audit as AUD


def _content_run_id(dataset_sha: str, config_sha: str) -> str:
    return hashlib.sha256(f"{dataset_sha}|{config_sha}".encode()).hexdigest()[:12]


def prepare_dataset(cfg: CanonicalConfig, raw_path: str, canon_path: str,
                    now_utc_ms: Optional[int] = None):
    """Ingest raw -> gates -> canonical store (idempotent). Returns (df, manifest_dict)."""
    df_raw, stats = ingest_raw_to_canonical(raw_path, canon_path, cfg.timeframe_minutes)
    if now_utc_ms is None:
        now_utc_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    df, dropped = drop_partial_final_candle(df_raw, now_utc_ms, cfg.timeframe_minutes)
    write_canonical_store(df, canon_path)
    tf_ms = cfg.timeframe_minutes * 60_000
    manifest = {
        "dataset_id": cfg.dataset_id,
        "version": cfg.dataset_version,
        "source_description": "TradingView export of BINGX:SOLUSDT.P",
        "venue": "BINGX (via TradingView)",
        "symbol": cfg.symbol,
        "timeframe": f"{cfg.timeframe_minutes}m",
        "timezone": "UTC",
        "first_candle_open_time": int(df["candle_open_time"].iloc[0]),
        "last_candle_open_time": int(df["candle_open_time"].iloc[-1]),
        "candle_count": int(len(df)),
        **{k: v for k, v in stats.items()},
        "raw_export_filename": raw_path,
        "raw_export_sha256": _sha256_file(raw_path),
        "canonical_filename": canon_path,
        "canonical_sha256": _sha256_file(canon_path),
        "ingestion_script_path": "research/canonical/data_contract.py",
        "partial_final_candle_dropped": bool(dropped is not None),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "_tf_ms": tf_ms,
    }
    return df, manifest


def run_pipeline(cfg: CanonicalConfig, candles: pd.DataFrame, out_dir: str,
                 dataset_sha256: str = "", gates_stats: Optional[dict] = None,
                 dataset_manifest: Optional[dict] = None):
    """Full canonical run. Returns dict of artifact paths + summary."""
    os.makedirs(out_dir, exist_ok=True)
    gates_stats = gates_stats or {}

    # ---- strategy layer ----------------------------------------------------
    if cfg.indicator_source == "VENDOR_PROVIDED":
        strategy = VwapSupertrendVendorStrategy(cfg.st_factor, cfg.st_length,
                                                cfg.stop_buffer_bps)
    else:
        strategy = VwapSupertrendEngineStrategy(cfg.st_factor, cfg.st_length,
                                                cfg.stop_buffer_bps,
                                                warmup_bars=cfg.warmup_bars)
    signals = strategy.generate(candles, cfg.dataset_id, cfg.dataset_version,
                                cfg.timeframe_minutes)
    for s in signals:
        s.symbol = cfg.symbol   # enforce config symbol

    # regimes attached to intents before simulation (causal at signal close)
    regime_by_bar = AUD.compute_regimes(candles, cfg)
    otime = candles["candle_open_time"].to_numpy().astype(np.int64)
    bar_of = {int(t): i for i, t in enumerate(otime)}
    regime_labels: Dict[str, str] = {}
    for s in signals:
        r = regime_by_bar.get(bar_of.get(int(s.signal_candle_open_time_ms), -1))
        s.metadata["regime_at_signal"] = r
        regime_labels[s.signal_id] = r or "NULL"

    # ---- execution layer ---------------------------------------------------
    trades, skipped, unfilled_eod = EX.simulate(candles, signals, cfg)

    # ---- accounting --------------------------------------------------------
    rows = ACC.trade_ledger_rows(trades, cfg)
    rows = MET.attach_diagnostics(trades, rows)

    # ---- invariants / anchor ----------------------------------------------
    anchor_expected = None
    if cfg.dataset_id == "DS-A" and cfg.strategy_id == "VWAP_SUPERTREND_ACTIVE_LINE_CROSS":
        anchor_expected = (121, 58, 63)
    inv_errors = AUD.check_invariants(trades, skipped, unfilled_eod, signals,
                                      candles, cfg, anchor_expected)
    n_sig, nL = len(signals), sum(1 for s in signals if s.direction == 1)
    anchor_check = ("PASS" if not any(e.startswith("I7") for e in inv_errors)
                    else next(e for e in inv_errors if e.startswith("I7")))

    # ---- metrics -----------------------------------------------------------
    metrics = MET.aggregate(rows, cfg, regime_labels=regime_labels)
    risk_bps = np.array([t.risk_frac * 1e4 for t in trades])
    metrics["breakeven_table"] = ACC.breakeven_table(risk_bps) if len(trades) else []

    # ---- outputs -----------------------------------------------------------
    ds_sha = dataset_sha256 or _sha256_file(
        os.path.join("research", "data", "canonical", f"{cfg.dataset_version}_candles.csv"))
    run_id = _content_run_id(ds_sha, cfg.sha256())
    sig_rows = []
    taken_ids = {t.intent.signal_id for t in trades}
    skip_map = {s.signal_id: s.reason for s in skipped}
    for s in signals:
        row = {
            "signal_id": s.signal_id, "symbol": s.symbol,
            "timeframe": f"{s.timeframe_minutes}m",
            "data_source": f"{cfg.dataset_id}.{cfg.dataset_version}",
            "signal_candle_open_time_ms": s.signal_candle_open_time_ms,
            "signal_candle_close_time_ms": s.signal_time_ms,
            "signal_time_ms": s.signal_time_ms,
            "entry_time_ms": s.entry_reference_open_time_ms,
            "direction": "LONG" if s.direction == 1 else "SHORT",
            "signal_price": s.metadata.get("signal_price"),
            "theoretical_entry_price": None,     # resolved on trade; Model A = next open
            "VWAP_at_signal": s.metadata.get("vwap_at_signal"),
            "supertrend_line_at_signal": s.metadata.get("supertrend_line_at_signal"),
            "st_direction_at_signal": s.direction,
            "atr_at_signal": None,               # vendor path lacks ATR series (S1/S2)
            "stop_price": s.stop_price,
            "risk_price": None,                  # frozen at trade creation (engine)
            "risk_pct": None,
            "regime_at_signal": regime_labels.get(s.signal_id),
            "status": ("TRADED" if s.signal_id in taken_ids
                       else skip_map.get(s.signal_id, "UNKNOWN")),
            "indicator_source": s.indicator_source,
        }
        tr = next((t for t in trades if t.intent.signal_id == s.signal_id), None)
        if tr is not None:
            row["theoretical_entry_price"] = tr.entry_price_theoretical
            row["risk_price"] = tr.risk_price
            row["risk_pct"] = tr.risk_frac
        sig_rows.append(row)
    sig_df = pd.DataFrame(sig_rows)
    trade_df = pd.DataFrame(rows)

    paths = {
        "signals": os.path.join(out_dir, "OPHELIA_CANONICAL_SIGNAL_LEDGER.csv"),
        "trades": os.path.join(out_dir, "OPHELIA_CANONICAL_TRADE_LEDGER.csv"),
        "metrics": os.path.join(out_dir, "OPHELIA_CANONICAL_METRICS.json"),
        "audit": os.path.join(out_dir, "OPHELIA_CANONICAL_AUDIT.md"),
    }
    sig_df.to_csv(paths["signals"], index=False, lineterminator="\n")
    trade_df.to_csv(paths["trades"], index=False, lineterminator="\n")
    with open(paths["metrics"], "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, sort_keys=True, default=float)
        f.write("\n")

    # ---- audit + manifest --------------------------------------------------
    notes = [
        f"indicator_source={cfg.indicator_source}: vendor TV series used for DS-A "
        "because export lacks pre-window history (SPEC-GAP S1).",
        "DS-A has no volume column (SPEC-GAP S2): engine VWAP path inactive; vendor VWAP consumed as data.",
        "Regime window is DEGRADED for DS-A (<90d history): HIGH_VOL/CHOP split uses "
        "expanding post-warmup median (documented limitation L3).",
        "Ambiguity policy STOP_FIRST biases results downward (conservative, spec A1).",
        "Secondary exit policies are PATH-INDEPENDENT estimates; only "
        f"{cfg.primary_exit_policy} drives the state machine.",
        "Bootstrap/ESS computed on primary-policy net bps series.",
    ]
    audit_md = AUD.build_audit_md(
        cfg,
        manifest={"run_id": run_id, "engine_version": ENGINE_VERSION,
                  "spec_version": SPEC_V,
                  "dataset_sha256": dataset_sha256,
                  "config_sha256": cfg.sha256()},
        gates_stats=gates_stats, signals=signals, trades=trades,
        skipped=skipped, unfilled_eod=unfilled_eod,
        invariant_errors=inv_errors, anchor_check=anchor_check, notes=notes)
    with open(paths["audit"], "w", encoding="utf-8") as f:
        f.write(audit_md)

    run_manifest = {
        "run_id": run_id,
        "engine_version": ENGINE_VERSION,
        "spec_version": SPEC_V,
        "git_commit": _git_commit(),
        "git_dirty_flag": _git_dirty(),
        "dataset_id": cfg.dataset_id,
        "dataset_version": cfg.dataset_version,
        "dataset_sha256": dataset_sha256,
        "config_sha256": cfg.sha256(),
        "bootstrap_seed": cfg.bootstrap_seed,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_manifest": dataset_manifest or {},
        "output_file_hashes": {
            os.path.basename(p): _sha256_file(p) for p in paths.values()
        },
        "counts": {
            "signals": len(signals),
            "trades": len(trades),
            "skipped": len(skipped),
            "unfilled_eod": unfilled_eod,
        },
        "anchor_check": anchor_check,
    }
    mpath = os.path.join(out_dir, "run_manifest.json")
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(run_manifest, f, indent=2, sort_keys=True)
        f.write("\n")
    paths["manifest"] = mpath

    return {"paths": paths, "run_id": run_id, "signals": signals, "trades": trades,
            "skipped": skipped, "unfilled_eod": unfilled_eod,
            "invariant_errors": inv_errors, "anchor_check": anchor_check,
            "regime_labels": regime_labels, "rows": rows,
            "metrics": metrics, "sig_df": sig_df, "trade_df": trade_df}


def _git_commit() -> str:
    import subprocess
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=os.path.join(os.path.dirname(__file__)),
            stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "UNKNOWN"


def _git_dirty() -> bool:
    import subprocess
    try:
        out = subprocess.check_output(["git", "status", "--porcelain"],
                                      cwd=os.path.dirname(__file__),
                                      stderr=subprocess.DEVNULL).decode()
        return bool(out.strip())
    except Exception:
        return True
