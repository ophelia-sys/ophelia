"""Governance registries (spec §18-§19): append-only CSV logs."""
from __future__ import annotations

import csv
import os
from typing import List

REGISTRY_DIR_DEFAULT = os.path.join("research", "registry")

HYPOTHESIS_FIELDS = ["hypothesis_id", "date_utc", "phase", "feature_or_rule",
                     "threshold_values", "dataset_id", "split_used",
                     "primary_metric", "result_value", "decision", "reason",
                     "git_commit"]
PARTITION_FIELDS = ["timestamp_utc", "experiment_id", "partition_accessed",
                    "ledger_hash_at_access", "purpose"]


def _ensure(path: str, fields: List[str]) -> None:
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(fields)


def ensure_registries(registry_dir: str = REGISTRY_DIR_DEFAULT) -> dict:
    hyp = os.path.join(registry_dir, "hypothesis_registry.csv")
    part = os.path.join(registry_dir, "partition_access_log.csv")
    _ensure(hyp, HYPOTHESIS_FIELDS)
    _ensure(part, PARTITION_FIELDS)
    return {"hypothesis_registry": hyp, "partition_access_log": part}


def log_partition_access(experiment_id: str, partition: str, ledger_hash: str,
                         purpose: str, registry_dir: str = REGISTRY_DIR_DEFAULT,
                         timestamp_utc: str = "") -> None:
    paths = ensure_registries(registry_dir)
    with open(paths["partition_access_log"], "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([timestamp_utc, experiment_id, partition,
                                ledger_hash, purpose])
