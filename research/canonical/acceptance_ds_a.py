"""DS-A acceptance run CLI (Phase 2.9 §3/§18).

Usage:
    python -m research.canonical.acceptance_ds_a
"""
from __future__ import annotations

import json
import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from research.canonical.config import CanonicalConfig
from research.canonical.runner import prepare_dataset, run_pipeline
from research.canonical.data_contract import load_canonical_store

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RAW = os.path.join(ROOT, "research", "data", "raw", "tv_exports", "DS-A_BINGX_SOL_5M.csv")
CANON_DIR = os.path.join(ROOT, "research", "data", "canonical")
OUT_DIR = os.path.join(ROOT, "research", "canonical", "output", "ds_a_acceptance")


def main() -> int:
    cfg = CanonicalConfig()
    os.makedirs(CANON_DIR, exist_ok=True)
    canon_path = os.path.join(CANON_DIR, f"{cfg.dataset_version}_candles.csv")

    df, manifest = prepare_dataset(cfg, RAW, canon_path)
    with open(os.path.join(CANON_DIR, f"{cfg.dataset_version}_manifest.json"), "w",
              encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write("\n")

    candles = load_canonical_store(canon_path)
    res = run_pipeline(cfg, candles, OUT_DIR,
                       dataset_sha256=manifest["canonical_sha256"],
                       gates_stats={k: manifest[k] for k in
                                    ("missing_candle_count", "duplicate_timestamp_count",
                                     "invalid_ohlc_count", "zero_volume_bar_count",
                                     "volume_available")},
                       dataset_manifest=manifest)

    print("=== DS-A ACCEPTANCE ===")
    print("signals:", len(res["signals"]),
          "| LONG:", sum(1 for s in res['signals'] if s.direction == 1),
          "| SHORT:", sum(1 for s in res['signals'] if s.direction == -1))
    print("trades:", len(res["trades"]), "| skipped:", len(res["skipped"]),
          "| unfilled_eod:", res["unfilled_eod"])
    from collections import Counter
    print("skip reasons:", dict(Counter(s.reason for s in res["skipped"])))
    print("anchor:", res["anchor_check"])
    if res["invariant_errors"]:
        print("INVARIANT FAILURES:")
        for e in res["invariant_errors"]:
            print("  -", e)
    print("outputs:", json.dumps({k: v.replace(ROOT + os.sep, '')
                                  for k, v in res["paths"].items()}, indent=2))
    return 0 if str(res["anchor_check"]).startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
