"""A/B gate calculator for instrument-health validation (Task 5e).

Reads the 36 A/B run directories under ``runs_root`` and computes the §5
instrument-health metrics.

Gate states
-----------
BLOCKED  Structural only: <36 completed, any RUN_FAILED.json present, any run
         missing, or every (sequence, policy, seed, task_id) is NOT present in
         both legacy AND fixed.  Metrics are NOT computed when blocked.

STOP     Health check failed: edit path/index failures > 0, overall edit failure
         ratio > 0.15, total_edit_file == 0 (undefined ratio — agent made no
         edits), OR token inflation (fixed median > 1.5× legacy median on either
         prompt_tokens or total_tokens).

GO       All health metrics pass.

Note on range-correctness
-------------------------
Range correctness (read_file start_line/end_line) is verified independently by
the deterministic Task-1 unit tests:

    .venv/bin/pytest tests/test_agents_tools.py -k read_file

``ab_gate`` does NOT re-derive range correctness from LLM run data (LLM output
is non-deterministic); it notes this dependency in the returned dict.

Usage
-----
    python -m scripts.ab_gate --runs-root /path/to/runs --results-dir /path/to/results
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

from scripts.ab_schedule import ab_schedule
from src.benchmark.completion import is_run_complete

# ---------------------------------------------------------------------------
# Edit-failure detection strings
# ---------------------------------------------------------------------------

# These patterns are grounded in src/agents/langgraph_agent.py::_execute_tool
# which wraps tools.py edit_file exceptions as:
#   f"ERROR: tool 'edit_file' failed: {e}"
#
# The git-apply error message includes "does not match index" in stderr from git.
# The path guard errors (fixed mode) include "Security: diff path" or absolute
# "/testbed" paths appearing in FileNotFoundError messages.
#
# We treat an edit_file observation as a FAILURE if it starts with "ERROR:"
# and is NOT just "Edited <path>" success.
# Path/index failures are a SUBSET: observations containing "/testbed" in an error
# context, OR "does not match index" from git apply stderr.

_EDIT_SUCCESS_PREFIX = "Edited "
_ERROR_PREFIX = "ERROR:"
_PATH_INDEX_MARKERS = [
    "/testbed",
    "does not match index",
]


def _is_edit_failure(obs: str) -> bool:
    """Return True if the observation represents an edit_file failure."""
    obs_str = str(obs)
    return obs_str.startswith(_ERROR_PREFIX)


def _is_path_index_failure(obs: str) -> bool:
    """Return True if the observation represents a path/index failure.

    These are a subset of edit failures: absolute /testbed paths in error context,
    or git apply 'does not match index' errors.
    """
    obs_str = str(obs)
    if not obs_str.startswith(_ERROR_PREFIX):
        return False
    return any(marker in obs_str for marker in _PATH_INDEX_MARKERS)


# ---------------------------------------------------------------------------
# Run-data loading helpers
# ---------------------------------------------------------------------------


def _load_task_results(run_dir: Path) -> list[dict]:
    """Load all rows from task_results.jsonl; return [] on any error."""
    trfile = run_dir / "task_results.jsonl"
    if not trfile.exists():
        return []
    rows: list[dict] = []
    for line in trfile.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return rows


def _load_trajectories(run_dir: Path) -> list[dict]:
    """Load all trajectory files in run_dir/trajectories/; return [] on errors."""
    traj_dir = run_dir / "trajectories"
    if not traj_dir.is_dir():
        return []
    trajs: list[dict] = []
    for fp in sorted(traj_dir.glob("*.json")):
        try:
            trajs.append(json.loads(fp.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass
    return trajs


def _collect_edit_observations(traj: dict) -> list[str]:
    """Extract all edit_file observation_summary strings from a trajectory."""
    obs_list: list[str] = []
    for step in traj.get("steps", []):
        if step.get("action") == "edit_file":
            obs = step.get("observation_summary", "")
            obs_list.append(str(obs))
    return obs_list


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def ab_gate(runs_root: Path | str, results_dir: Path | str) -> dict[str, Any]:
    """Compute A/B instrument-health gate.

    Args:
        runs_root: Directory containing the 36 run subdirectories.
        results_dir: Directory where gate output JSON may be written (reserved
                     for future artefact storage; not written by this call).

    Returns:
        Dict with keys:
            gate          "GO" | "STOP" | "BLOCKED"
            metrics       dict of computed health metrics (empty if BLOCKED)
            reported_deltas  dict of fixed-vs-legacy deltas (informational only)
            reasons       list of human-readable failure strings
            range_correctness_note  str — dependency on unit tests
    """
    runs_root = Path(runs_root)
    results_dir = Path(results_dir)

    schedule = ab_schedule(seed=20260622)
    expected_run_ids: list[str] = [c["run_id"] for c in schedule]

    range_note = (
        "Range correctness (read_file start_line/end_line) is verified by "
        "tests/test_agents_tools.py -k read_file — not re-derived from LLM runs."
    )

    # -----------------------------------------------------------------------
    # Phase 1: structural checks (BLOCKED conditions)
    # -----------------------------------------------------------------------
    reasons: list[str] = []

    missing_runs: list[str] = []
    failed_runs: list[str] = []
    incomplete_runs: list[str] = []

    for run_id in expected_run_ids:
        run_dir = runs_root / run_id
        if not run_dir.exists():
            missing_runs.append(run_id)
        elif (run_dir / "RUN_FAILED.json").exists():
            failed_runs.append(run_id)
        elif not is_run_complete(run_dir):
            incomplete_runs.append(run_id)

    if missing_runs:
        reasons.append(f"Missing {len(missing_runs)} run dir(s): {missing_runs[:5]}")
    if failed_runs:
        reasons.append(f"RUN_FAILED.json in {len(failed_runs)} run(s): {failed_runs[:5]}")
    if incomplete_runs:
        reasons.append(
            f"{len(incomplete_runs)} run(s) lack RUN_COMPLETED.json: {incomplete_runs[:5]}"
        )

    if reasons:
        return {
            "gate": "BLOCKED",
            "reason": reasons[0],
            "reasons": reasons,
            "metrics": {},
            "reported_deltas": {},
            "range_correctness_note": range_note,
        }

    # -----------------------------------------------------------------------
    # Phase 2: pairing check — every (sequence, policy, seed, task_id) must
    # appear in BOTH legacy AND fixed.
    # -----------------------------------------------------------------------
    # Group run_ids by (policy, sequence_name, seed)
    cell_by_key: dict[tuple, dict[str, str]] = {}  # key → {mode: run_id}
    for cell in schedule:
        key = (cell["policy"], cell["sequence_name"], cell["seed"])
        if key not in cell_by_key:
            cell_by_key[key] = {}
        cell_by_key[key][cell["tool_mode"]] = cell["run_id"]

    pairing_issues: list[str] = []
    for key, mode_map in cell_by_key.items():
        legacy_id = mode_map.get("legacy")
        fixed_id = mode_map.get("fixed")
        if not legacy_id or not fixed_id:
            pairing_issues.append(f"Key {key} missing a mode: {mode_map}")
            continue

        legacy_tasks = {
            row["task_id"]
            for row in _load_task_results(runs_root / legacy_id)
            if "task_id" in row
        }
        fixed_tasks = {
            row["task_id"]
            for row in _load_task_results(runs_root / fixed_id)
            if "task_id" in row
        }

        only_legacy = legacy_tasks - fixed_tasks
        only_fixed = fixed_tasks - legacy_tasks
        if only_legacy or only_fixed:
            pairing_issues.append(
                f"Unmatched task_ids for {key}: "
                f"legacy-only={sorted(only_legacy)[:3]}, "
                f"fixed-only={sorted(only_fixed)[:3]}"
            )

    if pairing_issues:
        return {
            "gate": "BLOCKED",
            "reason": pairing_issues[0],
            "reasons": pairing_issues,
            "metrics": {},
            "reported_deltas": {},
            "range_correctness_note": range_note,
        }

    # -----------------------------------------------------------------------
    # Phase 3: compute health metrics over FIXED-mode runs
    #          (token ratio uses BOTH modes)
    # -----------------------------------------------------------------------

    # Collect per-mode token lists and edit observations
    fixed_prompt_tokens: list[int] = []
    fixed_total_tokens: list[int] = []
    fixed_resolved: list[int] = []

    legacy_prompt_tokens: list[int] = []
    legacy_total_tokens: list[int] = []
    legacy_resolved: list[int] = []

    # Edit metrics computed over FIXED runs only
    total_edit_file_calls = 0
    failed_edit_file_calls = 0
    edit_path_index_failures = 0

    dup_issues: list[str] = []

    for cell in schedule:
        run_dir = runs_root / cell["run_id"]
        rows = _load_task_results(run_dir)
        mode = cell["tool_mode"]

        # Duplicate detection per mode
        task_ids_in_run = [r.get("task_id") for r in rows if r.get("task_id")]
        if len(task_ids_in_run) != len(set(task_ids_in_run)):
            from collections import Counter
            dup = [t for t, cnt in Counter(task_ids_in_run).items() if cnt > 1]
            dup_issues.append(f"Duplicate task_ids in {cell['run_id']}: {dup[:3]}")

        for row in rows:
            pt = row.get("prompt_tokens", 0) or 0
            tt = row.get("total_tokens", 0) or 0
            res = int(row.get("resolved", 0) or 0)
            if mode == "fixed":
                fixed_prompt_tokens.append(pt)
                fixed_total_tokens.append(tt)
                fixed_resolved.append(res)
            else:
                legacy_prompt_tokens.append(pt)
                legacy_total_tokens.append(tt)
                legacy_resolved.append(res)

        if mode == "fixed":
            trajs = _load_trajectories(run_dir)
            for traj in trajs:
                for obs in _collect_edit_observations(traj):
                    total_edit_file_calls += 1
                    if _is_edit_failure(obs):
                        failed_edit_file_calls += 1
                    if _is_path_index_failure(obs):
                        edit_path_index_failures += 1

    if dup_issues:
        return {
            "gate": "BLOCKED",
            "reason": dup_issues[0],
            "reasons": dup_issues,
            "metrics": {},
            "reported_deltas": {},
            "range_correctness_note": range_note,
        }

    # -----------------------------------------------------------------------
    # Phase 4: evaluate health criteria → GO / STOP
    # -----------------------------------------------------------------------

    stop_reasons: list[str] = []

    # 1. Path / index failures must be exactly 0
    if edit_path_index_failures > 0:
        stop_reasons.append(
            f"edit path/index failures == {edit_path_index_failures} (must be 0)"
        )

    # 2. Overall edit failure ratio
    if total_edit_file_calls == 0:
        stop_reasons.append(
            "total_edit_file_calls == 0 (undefined ratio — no edit activity observed; "
            "gate cannot confirm instrument health)"
        )
        edit_failure_ratio: float | None = None
    else:
        edit_failure_ratio = failed_edit_file_calls / total_edit_file_calls
        if edit_failure_ratio > 0.15:
            stop_reasons.append(
                f"edit failure ratio {edit_failure_ratio:.3f} > 0.15 threshold"
            )

    # 3. Token inflation (both prompt and total)
    def _safe_median(xs: list[int]) -> float:
        return statistics.median(xs) if xs else 0.0

    fixed_prompt_med = _safe_median(fixed_prompt_tokens)
    legacy_prompt_med = _safe_median(legacy_prompt_tokens)
    fixed_total_med = _safe_median(fixed_total_tokens)
    legacy_total_med = _safe_median(legacy_total_tokens)

    INFLATION_THRESHOLD = 1.5

    if legacy_prompt_med > 0 and fixed_prompt_med > INFLATION_THRESHOLD * legacy_prompt_med:
        stop_reasons.append(
            f"prompt token inflation {fixed_prompt_med:.1f} > "
            f"1.5 × legacy {legacy_prompt_med:.1f} = {INFLATION_THRESHOLD * legacy_prompt_med:.1f}"
        )
    if legacy_total_med > 0 and fixed_total_med > INFLATION_THRESHOLD * legacy_total_med:
        stop_reasons.append(
            f"total token inflation {fixed_total_med:.1f} > "
            f"1.5 × legacy {legacy_total_med:.1f} = {INFLATION_THRESHOLD * legacy_total_med:.1f}"
        )

    # -----------------------------------------------------------------------
    # Phase 5: resolve-rate / timeout deltas (reported, NOT gated)
    # -----------------------------------------------------------------------

    def _resolve_rate(xs: list[int]) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    fixed_rr = _resolve_rate(fixed_resolved)
    legacy_rr = _resolve_rate(legacy_resolved)

    reported_deltas = {
        "resolved_delta": round(fixed_rr - legacy_rr, 4),
        "fixed_resolve_rate": round(fixed_rr, 4),
        "legacy_resolve_rate": round(legacy_rr, 4),
        "note": "Resolve-rate delta is informational; it is not a gate criterion.",
    }

    # -----------------------------------------------------------------------
    # Build result
    # -----------------------------------------------------------------------

    metrics: dict[str, Any] = {
        "total_edit_file_calls": total_edit_file_calls,
        "failed_edit_file_calls": failed_edit_file_calls,
        "edit_failure_ratio": (
            round(edit_failure_ratio, 4) if edit_failure_ratio is not None else None
        ),
        "edit_path_index_failures": edit_path_index_failures,
        "fixed_prompt_tokens_median": round(fixed_prompt_med, 1),
        "legacy_prompt_tokens_median": round(legacy_prompt_med, 1),
        "fixed_total_tokens_median": round(fixed_total_med, 1),
        "legacy_total_tokens_median": round(legacy_total_med, 1),
        "prompt_inflation_ratio": (
            round(fixed_prompt_med / legacy_prompt_med, 3) if legacy_prompt_med > 0 else None
        ),
        "total_inflation_ratio": (
            round(fixed_total_med / legacy_total_med, 3) if legacy_total_med > 0 else None
        ),
    }

    gate = "STOP" if stop_reasons else "GO"

    return {
        "gate": gate,
        "metrics": metrics,
        "reported_deltas": reported_deltas,
        "reasons": stop_reasons,
        "range_correctness_note": range_note,
    }


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Compute A/B instrument-health gate.")
    parser.add_argument(
        "--runs-root",
        required=True,
        type=Path,
        help="Directory containing the 36 A/B run subdirectories.",
    )
    parser.add_argument(
        "--results-dir",
        required=True,
        type=Path,
        help="Directory for gate artefacts.",
    )
    args = parser.parse_args()

    result = ab_gate(runs_root=args.runs_root, results_dir=args.results_dir)
    print(json.dumps(result, indent=2))
