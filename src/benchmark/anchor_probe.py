"""Anchor-probe producer (THESIS_FINAL_v5.md §14.2) — review blocker E2.

Generates the per-run ``anchor_probe.json`` that the aggregation
(:func:`src.analysis.aggregate_results.load_anchor_probe_data` →
:func:`src.benchmark.cl_metrics.compute_anchor_probe_cl_metrics`) consumes to
compute the PRIMARY CL-Stability / CL-F1 (Invariant §0.1 #29), replacing the
resolved-rate proxy.

Design (standalone, post-hoc):

* The **schedule** — k=5 anchor positions and 4 probe points — is pure and
  deterministic (the §14.2 formulas), pinned by tests.
* The **re-evaluation** — restore the memory state after task ``p`` (reconstructed
  from the run's ``memory/memory.db`` filtered to the snapshot's active set) and
  re-run the agent on each anchor task, scored by the SWE-bench evaluator — is
  *injected* (``restore_memory_fn`` / ``solve_and_eval_fn``). That keeps the
  orchestration unit-testable with mocks and lets the live agent/evaluator be
  wired on the run host (Docker + Kimi), where this producer runs after the main
  forward pass rather than inline (no coupling to ``sequence_runner``).

Output schema (matches ``load_anchor_probe_data``)::

    {
      "policy": str, "repo": str, "seed": int, "n_tasks": int,
      "anchor_indices": [int, ...],      # the anchor set A (1-indexed, §14.2)
      "probe_points": [int, ...],        # probe columns p; max(p) == T
      "online_resolved": [0|1, ...],     # a_{i,i} for all T tasks, sequence order
      "probed_accuracy": [{"i": int, "p": int, "acc": float}, ...]
    }
"""

import json
import math
from collections.abc import Callable
from pathlib import Path
from typing import Any


def anchor_indices(n_tasks: int) -> list[int]:
    """Deterministic anchor set A (§14.2): k=5 anchors at positions
    ``{⌈T/10⌉, ⌈3T/10⌉, ⌈5T/10⌉, ⌈7T/10⌉, ⌈9T/10⌉}`` (1-indexed).

    De-duplicated and clamped to ``[1, T]`` so very short sequences still yield a
    valid (possibly < 5) anchor set.
    """
    if n_tasks < 1:
        return []
    raw = [math.ceil(f * n_tasks / 10) for f in (1, 3, 5, 7, 9)]
    return sorted({min(max(a, 1), n_tasks) for a in raw})


def probe_points(n_tasks: int) -> list[int]:
    """Probe columns (§14.2): ``{⌈T/4⌉, ⌈T/2⌉, ⌈3T/4⌉, T}`` (1-indexed).

    The largest probe is always ``T`` (the end-of-sequence column used for
    ``a_{i,T}``). De-duplicated and clamped to ``[1, T]``.
    """
    if n_tasks < 1:
        return []
    raw = [
        math.ceil(n_tasks / 4),
        math.ceil(n_tasks / 2),
        math.ceil(3 * n_tasks / 4),
        n_tasks,
    ]
    return sorted({min(max(p, 1), n_tasks) for p in raw})


def online_resolved_from_task_results(run_dir: Path) -> list[int]:
    """Read the online diagonal ``a_{i,i}`` (resolved 0/1 per task) in sequence order.

    Source: the run's ``task_results.jsonl`` (always collected). The list is
    ordered by ``sequence_index`` so position ``i`` corresponds to task ``i``.
    """
    path = Path(run_dir) / "task_results.jsonl"
    rows: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    rows.sort(key=lambda r: r.get("sequence_index", 0))
    return [int(bool(r.get("resolved", 0))) for r in rows]


def build_anchor_probe_record(
    *,
    policy: str,
    repo: str,
    seed: int,
    online_resolved: list[int],
    anchor_task_ids: dict[int, str],
    restore_memory_fn: Callable[[int], Any],
    solve_and_eval_fn: Callable[[str, Any], float],
) -> dict[str, Any]:
    """Build the §14.2 anchor-probe payload by re-evaluating anchors at probe points.

    For each probe ``p`` (largest = T): restore the memory state after task ``p``,
    then for every anchor ``i ≤ p`` re-run + score the anchor task. Anchors with
    ``i > p`` did not yet exist at probe ``p`` and are skipped (no leakage).

    Args:
        policy, repo, seed: Run identity (keys for the aggregation loader).
        online_resolved: ``a_{i,i}`` for all T tasks (length T), sequence order.
        anchor_task_ids: anchor position ``i`` (1-indexed) → that task's id.
        restore_memory_fn: ``p -> memory_state`` — the snapshot after task ``p``
            reconstructed from ``memory/memory.db`` (injected; mockable).
        solve_and_eval_fn: ``(anchor_task_id, memory_state) -> acc`` in ``{0, 1}``
            (injected; the real impl runs the agent + SWE-bench evaluator).

    Returns:
        The anchor-probe record dict (schema above).
    """
    n_tasks = len(online_resolved)
    anchors = anchor_indices(n_tasks)
    probes = probe_points(n_tasks)

    probed_accuracy: list[dict[str, Any]] = []
    for p in probes:
        memory_state = restore_memory_fn(p)
        for i in anchors:
            if i <= p:
                acc = float(solve_and_eval_fn(anchor_task_ids[i], memory_state))
                probed_accuracy.append({"i": int(i), "p": int(p), "acc": acc})

    return {
        "policy": policy,
        "repo": repo,
        "seed": int(seed),
        "n_tasks": int(n_tasks),
        "anchor_indices": anchors,
        "probe_points": probes,
        "online_resolved": [int(x) for x in online_resolved],
        "probed_accuracy": probed_accuracy,
    }


def write_anchor_probe(run_dir: Path, record: dict[str, Any]) -> Path:
    """Write ``anchor_probe.json`` into ``run_dir``; returns the written path."""
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    out = run_dir / "anchor_probe.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
    return out
