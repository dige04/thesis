"""
Aggregate task-level results into sequence-level means for statistical analysis.

This module implements Task 14.1: Sequence-level aggregation.

Per THESIS_FINAL_v5.md §15.2:
- Primary statistical unit: sequence-level means (N=8 paired observations)
- Aggregate across 3 seeds for each (policy, sequence) combination
- Compute mean CL-F1, resolved rate, costs, and other metrics
"""

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from src.benchmark.cl_metrics import compute_anchor_probe_cl_metrics

# Markers recorded on every aggregated sequence so CL-F1 is NEVER a silent
# placeholder (plan 5.2). Either the real §14.2 anchor-probe CL-F1 was computed,
# or the resolved-rate proxy was used as an explicit, traceable fallback.
CL_F1_SOURCE_ANCHOR_PROBE = "anchor_probe"
CL_F1_SOURCE_PROXY = "resolved_rate_proxy"


def load_anchor_probe_data(
    runs_dir: Path,
) -> dict[tuple[str, str, int], dict[str, Any]]:
    """Load per-run anchor-probe re-evaluation data, keyed by (policy, repo, seed).

    Per THESIS_FINAL_v5.md §14.2, the PRIMARY CL-Stability/CL-F1 estimator is the
    anchor-probe schedule (k=5 anchors re-evaluated at 4 probe points against the
    memory snapshot after each probe task). That re-evaluation requires the real
    eval harness + runner re-eval, which is a SEPARATE PHASE — it is NOT
    implemented here. This loader only reads its output if/when it has been
    produced, so the aggregation can use the real CL-F1 the moment that data
    lands, and otherwise fall back to the resolved-rate proxy with an explicit
    marker.

    Expected per-run file: ``runs/{run_id}/anchor_probe.json`` with shape::

        {
          "policy": str, "repo": str, "seed": int, "n_tasks": int,
          "anchor_indices": [int, ...],          # the anchor set A (§14.2)
          "probe_points": [int, ...],            # 0-indexed probe columns p
          "online_resolved": [0|1, ...],         # a_{i,i} for all T tasks
          "probed_accuracy": [{"i": int, "p": int, "acc": float}, ...]
        }

    Runs lacking this file are simply absent from the returned mapping.

    Args:
        runs_dir: Path to runs/ directory containing all run folders.

    Returns:
        Mapping {(policy, repo, seed): anchor_probe_dict}.
    """
    anchor_probe: dict[tuple[str, str, int], dict[str, Any]] = {}

    for run_dir in runs_dir.iterdir():
        if not run_dir.is_dir():
            continue

        probe_path = run_dir / "anchor_probe.json"
        if not probe_path.exists():
            continue

        with open(probe_path, encoding="utf-8") as f:
            data = json.load(f)

        key = (data["policy"], data["repo"], int(data["seed"]))
        anchor_probe[key] = data

    return anchor_probe


def _anchor_probe_cl_f1(probe_data: dict[str, Any]) -> float:
    """Compute the real §14.2 anchor-probe CL-F1 from a per-run probe payload."""
    probed_accuracy = {
        (int(cell["i"]), int(cell["p"])): float(cell["acc"])
        for cell in probe_data["probed_accuracy"]
    }
    metrics = compute_anchor_probe_cl_metrics(
        online_resolved=probe_data["online_resolved"],
        anchor_indices=[int(i) for i in probe_data["anchor_indices"]],
        probe_points=[int(p) for p in probe_data["probe_points"]],
        probed_accuracy=probed_accuracy,
        n_tasks=int(probe_data["n_tasks"]),
    )
    return metrics.cl_f1


def aggregate_task_results(
    runs_dir: Path,
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """
    Load all task results from runs directory.

    Args:
        runs_dir: Path to runs/ directory containing all run folders

    Returns:
        Nested dict: {policy: {sequence: [task_results]}}
        where task_results is a list of dicts from task_results.jsonl
    """
    results: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for run_dir in runs_dir.iterdir():
        if not run_dir.is_dir():
            continue

        task_results_path = run_dir / "task_results.jsonl"
        if not task_results_path.exists():
            continue

        # Load all task results for this run
        with open(task_results_path) as f:
            for line in f:
                if not line.strip():
                    continue
                task_result = json.loads(line)

                policy = task_result["policy"]
                repo = task_result["repo"]

                results[policy][repo].append(task_result)

    return dict(results)


def aggregate_sequence_results(
    runs_dir: Path,
    output_path: Path | None = None,
) -> dict[str, dict[str, dict[str, Any]]]:
    """
    Aggregate task-level results into sequence-level means.

    Per THESIS_FINAL_v5.md §15.2:
    - Compute mean across 3 seeds for each (policy, sequence) pair
    - Primary metrics: CL-F1, resolved rate, costs
    - N=8 paired observations per condition pair

    Args:
        runs_dir: Path to runs/ directory
        output_path: Optional path to save aggregated results JSON

    Returns:
        Nested dict: {policy: {sequence: {metric: value}}}
        where metrics include:
        - mean_cl_f1: Mean CL-F1 across 3 seeds
        - std_cl_f1: Standard deviation across 3 seeds
        - mean_resolved_rate: Mean task success rate
        - mean_total_cost: Mean total API cost (USD)
        - mean_total_tokens: Mean total token count
        - mean_tool_calls: Mean tool calls per task
        - mean_wall_time: Mean wall time per task (seconds)
        - n_seeds: Number of seeds aggregated
        - n_tasks: Number of tasks in sequence
    """
    # Load all task results
    task_results = aggregate_task_results(runs_dir)

    # Load anchor-probe re-evaluation data, if the (separate-phase) eval harness
    # has produced it. Keyed by (policy, repo, seed). Empty until that phase runs.
    anchor_probe_data = load_anchor_probe_data(runs_dir)

    # Aggregate by (policy, sequence, seed)
    seed_aggregates: dict[str, dict[str, dict[int, dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(dict))
    )

    for policy, sequences in task_results.items():
        for sequence, tasks in sequences.items():
            # Group by seed
            by_seed: dict[int, list[dict[str, Any]]] = defaultdict(list)
            for task in tasks:
                seed = task["seed"]
                by_seed[seed].append(task)

            # Compute per-seed aggregates
            for seed, seed_tasks in by_seed.items():
                n_tasks = len(seed_tasks)
                resolved_count = sum(t["resolved"] for t in seed_tasks)
                resolved_rate = resolved_count / n_tasks if n_tasks > 0 else 0.0

                total_cost = sum(t.get("estimated_cost_usd", 0.0) for t in seed_tasks)
                total_tokens = sum(t.get("total_tokens", 0) for t in seed_tasks)
                total_tool_calls = sum(t.get("tool_calls", 0) for t in seed_tasks)
                total_wall_time = sum(
                    t.get("wall_time_seconds", 0.0) for t in seed_tasks
                )

                mean_tool_calls = total_tool_calls / n_tasks if n_tasks > 0 else 0.0
                mean_wall_time = total_wall_time / n_tasks if n_tasks > 0 else 0.0

                # CL-F1: use the real §14.2 anchor-probe estimator when its
                # re-evaluation data is available for this (policy, sequence,
                # seed). The anchor-probe data COLLECTION is a separate phase
                # (needs the real eval harness + runner re-eval); this code only
                # consumes it. Until that data exists, fall back to resolved_rate
                # as an EXPLICIT proxy and record cl_f1_source so it is never a
                # silent placeholder.
                probe_data = anchor_probe_data.get((policy, sequence, seed))
                if probe_data is not None:
                    cl_f1 = _anchor_probe_cl_f1(probe_data)
                    cl_f1_source = CL_F1_SOURCE_ANCHOR_PROBE
                else:
                    cl_f1 = resolved_rate  # proxy fallback (NOT a silent placeholder)
                    cl_f1_source = CL_F1_SOURCE_PROXY

                seed_aggregates[policy][sequence][seed] = {
                    "cl_f1": cl_f1,
                    "cl_f1_source": cl_f1_source,
                    "resolved_rate": resolved_rate,
                    "total_cost": total_cost,
                    "total_tokens": total_tokens,
                    "mean_tool_calls": mean_tool_calls,
                    "mean_wall_time": mean_wall_time,
                    "n_tasks": n_tasks,
                }

    # Aggregate across seeds (mean ± std)
    sequence_aggregates: dict[str, dict[str, dict[str, Any]]] = defaultdict(
        lambda: defaultdict(dict)
    )

    for policy, sequences in seed_aggregates.items():
        for sequence, seeds in sequences.items():
            seed_values = list(seeds.values())
            n_seeds = len(seed_values)

            if n_seeds == 0:
                continue

            # Extract arrays for each metric
            cl_f1_values = [s["cl_f1"] for s in seed_values]
            # A sequence's CL-F1 is "anchor_probe" only if EVERY seed used the
            # real §14.2 estimator; otherwise the proxy marker dominates so the
            # provenance is never overstated.
            cl_f1_source = (
                CL_F1_SOURCE_ANCHOR_PROBE
                if all(
                    s["cl_f1_source"] == CL_F1_SOURCE_ANCHOR_PROBE
                    for s in seed_values
                )
                else CL_F1_SOURCE_PROXY
            )
            resolved_rate_values = [s["resolved_rate"] for s in seed_values]
            total_cost_values = [s["total_cost"] for s in seed_values]
            total_tokens_values = [s["total_tokens"] for s in seed_values]
            mean_tool_calls_values = [s["mean_tool_calls"] for s in seed_values]
            mean_wall_time_values = [s["mean_wall_time"] for s in seed_values]
            n_tasks = seed_values[0]["n_tasks"]  # Same for all seeds

            sequence_aggregates[policy][sequence] = {
                "mean_cl_f1": float(np.mean(cl_f1_values)),
                "cl_f1_source": cl_f1_source,
                "std_cl_f1": float(np.std(cl_f1_values, ddof=1))
                if n_seeds > 1
                else 0.0,
                "mean_resolved_rate": float(np.mean(resolved_rate_values)),
                "std_resolved_rate": float(np.std(resolved_rate_values, ddof=1))
                if n_seeds > 1
                else 0.0,
                "mean_total_cost": float(np.mean(total_cost_values)),
                "std_total_cost": float(np.std(total_cost_values, ddof=1))
                if n_seeds > 1
                else 0.0,
                "mean_total_tokens": float(np.mean(total_tokens_values)),
                "std_total_tokens": float(np.std(total_tokens_values, ddof=1))
                if n_seeds > 1
                else 0.0,
                "mean_tool_calls": float(np.mean(mean_tool_calls_values)),
                "std_tool_calls": float(np.std(mean_tool_calls_values, ddof=1))
                if n_seeds > 1
                else 0.0,
                "mean_wall_time": float(np.mean(mean_wall_time_values)),
                "std_wall_time": float(np.std(mean_wall_time_values, ddof=1))
                if n_seeds > 1
                else 0.0,
                "n_seeds": n_seeds,
                "n_tasks": n_tasks,
                "seed_cl_f1_values": cl_f1_values,  # For downstream analysis
            }

    result = dict(sequence_aggregates)

    # Save if output path provided
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2)

    return result
