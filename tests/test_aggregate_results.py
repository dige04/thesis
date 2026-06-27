"""Tests for sequence-level aggregation (src/analysis/aggregate_results.py).

Focus of these tests (plan 5.2):
- CL-F1 is no longer a silent placeholder. When per-run anchor-probe data is
  present, the real §14.2 anchor-probe CL-F1 is computed and tagged with
  cl_f1_source == "anchor_probe". When absent, the resolved-rate proxy is used
  and tagged cl_f1_source == "resolved_rate_proxy".
"""

import json
from pathlib import Path

from src.analysis.aggregate_results import aggregate_sequence_results


def _base_task(seq_index: int, resolved: int, seed: int = 1) -> dict:
    return {
        "run_id": f"run_seed{seed}",
        "policy": "type_aware_decay",
        "seed": seed,
        "repo": "django/django",
        "task_id": f"django__django-{seq_index:03d}",
        "sequence_index": seq_index,
        "resolved": resolved,
        "total_tokens": 1000,
        "estimated_cost_usd": 0.01,
        "tool_calls": 5,
        "wall_time_seconds": 100.0,
    }


def _write_run(run_dir: Path, tasks: list[dict], anchor_probe: dict | None = None):
    run_dir.mkdir(parents=True)
    with open(run_dir / "task_results.jsonl", "w", encoding="utf-8") as f:
        for t in tasks:
            f.write(json.dumps(t) + "\n")
    if anchor_probe is not None:
        with open(run_dir / "anchor_probe.json", "w", encoding="utf-8") as f:
            json.dump(anchor_probe, f)


def test_cl_f1_falls_back_to_proxy_and_records_marker(tmp_path):
    """No anchor-probe data -> CL-F1 falls back to resolved_rate, marked proxy."""
    runs_dir = tmp_path / "runs"
    # 3 seeds, one (policy, sequence). Each seed resolves 2/4 -> resolved_rate 0.5.
    for seed in (1, 2, 3):
        tasks = [_base_task(i, 1 if i < 2 else 0, seed=seed) for i in range(4)]
        _write_run(runs_dir / f"run_seed{seed}", tasks)

    result = aggregate_sequence_results(runs_dir)

    seq = result["type_aware_decay"]["django/django"]
    assert seq["cl_f1_source"] == "resolved_rate_proxy"
    # Proxy CL-F1 equals resolved_rate (0.5) since that is the documented fallback.
    assert abs(seq["mean_cl_f1"] - 0.5) < 1e-9
    assert abs(seq["mean_resolved_rate"] - 0.5) < 1e-9


def test_cl_f1_uses_anchor_probe_when_available(tmp_path):
    """Anchor-probe data present -> real §14.2 CL-F1 computed, marked anchor_probe."""
    runs_dir = tmp_path / "runs"

    # Single seed for clarity. T=4. Online diagonal: resolve all 4 -> Plasticity 1.0.
    # Anchors {0,1}. Probes {1,3}. Anchor 0 forgotten at final (1->0),
    # anchor 1 retained. forgetting = [1.0, 0.0] -> Stability = 0.5.
    # CL_F1 = 2*1.0*0.5/(1.5) = 0.6667.
    tasks = [_base_task(i, 1, seed=1) for i in range(4)]
    anchor_probe = {
        "policy": "type_aware_decay",
        "repo": "django/django",
        "seed": 1,
        "n_tasks": 4,
        "anchor_indices": [0, 1],
        "probe_points": [1, 3],
        "online_resolved": [1, 1, 1, 1],
        "probed_accuracy": [
            {"i": 0, "p": 1, "acc": 1.0},
            {"i": 0, "p": 3, "acc": 0.0},
            {"i": 1, "p": 1, "acc": 1.0},
            {"i": 1, "p": 3, "acc": 0.0},
        ],
    }
    _write_run(runs_dir / "run_seed1", tasks, anchor_probe=anchor_probe)

    result = aggregate_sequence_results(runs_dir)

    seq = result["type_aware_decay"]["django/django"]
    assert seq["cl_f1_source"] == "anchor_probe"
    # Anchor 1 also forgotten (1->0): forgetting=[1.0,1.0] -> Stability 0.0 -> CL_F1 0.0
    assert abs(seq["mean_cl_f1"] - 0.0) < 1e-9


def test_anchor_probe_known_partial_forgetting(tmp_path):
    """A run where exactly one of two anchors forgets -> Stability 0.5, CL_F1 0.6667."""
    runs_dir = tmp_path / "runs"
    tasks = [_base_task(i, 1, seed=1) for i in range(4)]
    anchor_probe = {
        "policy": "type_aware_decay",
        "repo": "django/django",
        "seed": 1,
        "n_tasks": 4,
        "anchor_indices": [0, 1],
        "probe_points": [1, 3],
        "online_resolved": [1, 1, 1, 1],
        "probed_accuracy": [
            {"i": 0, "p": 1, "acc": 1.0},
            {"i": 0, "p": 3, "acc": 0.0},  # anchor 0 forgotten
            {"i": 1, "p": 1, "acc": 1.0},
            {"i": 1, "p": 3, "acc": 1.0},  # anchor 1 retained
        ],
    }
    _write_run(runs_dir / "run_seed1", tasks, anchor_probe=anchor_probe)

    result = aggregate_sequence_results(runs_dir)
    seq = result["type_aware_decay"]["django/django"]
    assert seq["cl_f1_source"] == "anchor_probe"
    # P=1.0, S=0.5 -> CL_F1 = 2*1*0.5/1.5 = 0.6667
    assert abs(seq["mean_cl_f1"] - (2 * 1.0 * 0.5 / 1.5)) < 1e-9
