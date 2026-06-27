"""Build the tracked A/B re-validation manifest + worker map (Codex 2026-06-24).

The post-hotfix 36-cell A/B (experiment_sha cceb325) needs an explicit, tracked
manifest so the runner consumes a fixed unit list (never accidentally the 144
manifest) and provenance is auditable.

- 36 cells come from :func:`scripts.ab_schedule.ab_schedule` (canonical).
- Each row carries ``tool_mode`` (legacy|fixed) so the runner sets
  ``AGENT_TOOL_MODE`` per unit (NOT globally).
- Each row carries a ``worker`` assignment that CO-LOCATES the legacy & fixed
  cells of the same (sequence, policy, seed) pair on the same worker, so a pair
  is never split across machines.
- ``task_count``/``task_ids`` are sourced from ``runs_144.json`` for the same two
  sequences, guaranteeing consistency with the 144 manifest.

Usage::

    python -m scripts.build_ab_manifest        # writes the two artifacts
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scripts.ab_schedule import ab_schedule

# Frozen provenance for this A/B (must match results/manifest/freeze.json).
EXPERIMENT_SHA = "cceb3253d7b7cfeae16123af30197a8271e1d84a"
CONFIG_HASH = "2e7f341cc35d31c2"
DEFAULT_N_WORKERS = 9
DEFAULT_RUNS_144 = "results/manifest/runs_144.json"


def _seq_task_index(runs_144_path: str | Path) -> dict[str, dict]:
    """Map sequence_name -> {task_count, task_ids} from the 144 manifest."""
    data = json.loads(Path(runs_144_path).read_text(encoding="utf-8"))
    idx: dict[str, dict] = {}
    for r in data["runs"]:
        s = r["sequence_name"]
        if s not in idx:
            ids = r.get("task_ids", [])
            idx[s] = {"task_count": r.get("task_count", len(ids)), "task_ids": ids}
    return idx


def build_ab_manifest(
    schedule_seed: int = 20260622,
    n_workers: int = DEFAULT_N_WORKERS,
    runs_144_path: str | Path = DEFAULT_RUNS_144,
) -> dict:
    """Return the A/B manifest dict (36 cells, tool_mode + co-located worker)."""
    cells = ab_schedule(schedule_seed)
    seq_idx = _seq_task_index(runs_144_path)

    # Pair assignment: legacy+fixed of the same (seq, policy, seed) share a worker.
    pair_keys = sorted({(c["sequence_name"], c["policy"], c["seed"]) for c in cells})
    pair_worker = {pk: i % n_workers for i, pk in enumerate(pair_keys)}

    runs: list[dict] = []
    for c in cells:
        pk = (c["sequence_name"], c["policy"], c["seed"])
        ti = seq_idx.get(c["sequence_name"], {"task_count": 0, "task_ids": []})
        runs.append(
            {
                "run_id": c["run_id"],
                "policy": c["policy"],
                "sequence_name": c["sequence_name"],
                "seed": c["seed"],
                "tool_mode": c["tool_mode"],
                "pair_key": f'{c["sequence_name"]}|{c["policy"]}|seed{c["seed"]}',
                "worker": pair_worker[pk],
                "task_count": ti["task_count"],
                "task_ids": ti["task_ids"],
            }
        )

    payload = json.dumps(
        [(r["run_id"], r["tool_mode"], r["worker"]) for r in sorted(runs, key=lambda r: r["run_id"])],
        sort_keys=True,
    )
    mhash = hashlib.sha256(payload.encode()).hexdigest()[:16]

    return {
        "generated_for": "A/B re-validation (post-hotfix) at experiment_sha cceb325",
        "experiment_sha": EXPERIMENT_SHA,
        "config_hash": CONFIG_HASH,
        "manifest_hash": mhash,
        "schedule_seed": schedule_seed,
        "n_workers": n_workers,
        "policies": sorted({c["policy"] for c in cells}),
        "seeds": sorted({c["seed"] for c in cells}),
        "sequences": sorted({c["sequence_name"] for c in cells}),
        "tool_modes": ["legacy", "fixed"],
        "n_runs": len(runs),
        "amended_gate": "docs/amended-gate-2026-06-24.md",
        "note": (
            "36-cell A/B; each (sequence,policy,seed) has BOTH legacy+fixed, "
            "co-located on one worker. Runner sets AGENT_TOOL_MODE per row. "
            "Gate: scripts/ab_gate_amended.py. RUNS_ROOT=runs_ab_cceb325."
        ),
        "runs": runs,
    }


def build_worker_map(manifest: dict) -> dict:
    """Return {worker -> [run_ids]} for human/Codex audit."""
    workers: dict[str, list[str]] = {}
    for r in manifest["runs"]:
        workers.setdefault(str(r["worker"]), []).append(r["run_id"])
    return {
        "n_workers": manifest["n_workers"],
        "experiment_sha": manifest["experiment_sha"],
        "manifest_hash": manifest["manifest_hash"],
        "workers": {k: sorted(v) for k, v in sorted(workers.items(), key=lambda kv: int(kv[0]))},
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Build the tracked A/B manifest + worker map.")
    p.add_argument("--out", default="results/manifest/runs_ab_cceb325.json")
    p.add_argument("--worker-map", default="results/manifest/worker_map_ab_cceb325.json")
    p.add_argument("--n-workers", type=int, default=DEFAULT_N_WORKERS)
    a = p.parse_args()

    manifest = build_ab_manifest(n_workers=a.n_workers)
    wmap = build_worker_map(manifest)
    Path(a.out).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    Path(a.worker_map).write_text(json.dumps(wmap, indent=2), encoding="utf-8")
    print(f"wrote {a.out}: {manifest['n_runs']} runs, manifest_hash {manifest['manifest_hash']}")
    print(f"wrote {a.worker_map}: {len(wmap['workers'])} workers")


if __name__ == "__main__":
    main()
