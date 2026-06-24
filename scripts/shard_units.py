"""Enumerate the units a shard/worker must run from a manifest (Codex 2026-06-24).

Single source of truth for "which units, in which tool_mode" — the bash runner
(`run_matrix_shard.sh`) is a thin shell over this, so the per-unit tool_mode
threading is unit-testable in Python.

Sharding modes (auto-detected):
  - worker-field: if ANY manifest row has a ``worker`` field, select rows where
    ``int(row["worker"]) == shard``. Used by the A/B manifest to co-locate the
    legacy & fixed cells of a pair on one worker.
  - modulo: otherwise select rows where ``(global_index % num) == shard`` (the
    144 matrix default).

Every emitted unit carries ``tool_mode`` (``""`` if the row omits it -> the
runner falls back to the ``AGENT_TOOL_MODE`` env / "fixed").
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def enumerate_units(manifest_path: str | Path, shard: int, num: int) -> list[dict]:
    """Return the list of unit dicts assigned to ``shard``.

    Each unit: ``{index, run_id, policy, seed, sequence_name, tool_mode}``.
    """
    data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    runs = data["runs"]
    by_worker = any("worker" in r for r in runs)

    units: list[dict] = []
    for i, r in enumerate(runs):
        if by_worker:
            if int(r.get("worker", -1)) != shard:
                continue
        else:
            if i % num != shard:
                continue
        units.append(
            {
                "index": i,
                "run_id": r["run_id"],
                "policy": r["policy"],
                "seed": r["seed"],
                "sequence_name": r["sequence_name"],
                "tool_mode": r.get("tool_mode", ""),
            }
        )
    return units


def main() -> None:
    manifest_path, shard, num = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    for u in enumerate_units(manifest_path, shard, num):
        # index|run_id|policy|seed|sequence_name|tool_mode
        print(f'{u["index"]}|{u["run_id"]}|{u["policy"]}|{u["seed"]}|{u["sequence_name"]}|{u["tool_mode"]}')


if __name__ == "__main__":
    main()
