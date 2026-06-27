"""Completion sentinels and run validation for the matrix experiment.

§3.7 contract: a run directory is considered complete ONLY when
``RUN_COMPLETED.json`` is present — written atomically AFTER
``validate_run_complete`` passes.  ``cost_summary.json`` remains one of the
artifacts validated by ``validate_run_complete`` but is no longer the sole
completion signal (it is written in a ``finally`` block and can be present
even for partial runs).

Sentinel schema
---------------
RUN_COMPLETED.json:
    experiment_sha, config_hash, manifest_hash, tool_mode,
    task_count, validated_at

RUN_FAILED.json:
    error_type, error_message, experiment_sha, tool_mode, failed_at

Both are written atomically via temp-file + os.replace.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_experiment_sha() -> str:
    """Return EXPERIMENT_SHA env var, or HEAD commit hash, or 'unknown'."""
    sha = os.environ.get("EXPERIMENT_SHA", "").strip()
    if sha:
        return sha
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Write *data* to *path* atomically (temp file + os.replace)."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# validate_run_complete
# ---------------------------------------------------------------------------


def validate_run_complete(
    run_dir: Path | str,
    manifest_entry: dict[str, Any],
) -> tuple[bool, list[str]]:
    """Validate that a run directory contains every mandatory artifact.

    Checks applied uniformly for ALL 6 policies (including no_memory, which
    still gets an empty memory.db/.faiss/snapshots):

    1. ``task_results.jsonl``: task-id set == manifest task_ids (no missing,
       no duplicates).
    2. ``trajectories/{task_id}.json`` for every task in the manifest.
    3. ``patches/{task_id}.patch`` for every task in the manifest.
    4. ``memory/snapshots/before_task_{k}.json`` + ``after_task_{k}.json``
       for k = 0..N-1 (sequence_index, 0-based).
    5. ``memory/memory.db`` and ``memory/memory.faiss``.
    6. ``memory_events.jsonl``.
    7. ``cost_summary.json``.

    Args:
        run_dir: Path to the run directory.
        manifest_entry: Dict with at least ``task_ids`` (list[str]).

    Returns:
        (ok, missing) where ``missing`` is a list of human-readable strings
        describing each missing or invalid artifact.
    """
    run_dir = Path(run_dir)
    task_ids: list[str] = manifest_entry.get("task_ids", [])
    n = len(task_ids)
    missing: list[str] = []

    # 1. task_results.jsonl: correct set, no dups
    task_results_file = run_dir / "task_results.jsonl"
    if not task_results_file.exists():
        missing.append("task_results.jsonl is missing")
    else:
        seen_ids: list[str] = []
        for line in task_results_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                tid = row.get("task_id", "")
                if tid:
                    seen_ids.append(tid)
            except json.JSONDecodeError:
                missing.append("task_results.jsonl contains invalid JSON line")

        seen_set = set(seen_ids)
        expected_set = set(task_ids)

        # Duplicates check (must happen before missing-IDs check)
        dup_ids = [t for t in seen_ids if seen_ids.count(t) > 1]
        dup_unique = list(dict.fromkeys(dup_ids))  # deduplicate while preserving order
        for dup in dup_unique:
            missing.append(f"task_results.jsonl: duplicate row for task_id={dup}")

        # Missing IDs
        for tid in sorted(expected_set - seen_set):
            missing.append(f"task_results.jsonl: missing row for task_id={tid}")

    # 2. trajectories/{task_id}.json
    traj_dir = run_dir / "trajectories"
    for tid in task_ids:
        traj_file = traj_dir / f"{tid}.json"
        if not traj_file.exists():
            missing.append(f"trajectories/{tid}.json is missing")

    # 3. patches/{task_id}.patch
    patches_dir = run_dir / "patches"
    for tid in task_ids:
        patch_file = patches_dir / f"{tid}.patch"
        if not patch_file.exists():
            missing.append(f"patches/{tid}.patch is missing")

    # 4. memory/snapshots/before_task_{k}.json + after_task_{k}.json
    snapshot_dir = run_dir / "memory" / "snapshots"
    for k in range(n):
        before = snapshot_dir / f"before_task_{k}.json"
        after = snapshot_dir / f"after_task_{k}.json"
        if not before.exists():
            missing.append(f"memory/snapshots/before_task_{k}.json is missing")
        if not after.exists():
            missing.append(f"memory/snapshots/after_task_{k}.json is missing")

    # 5. memory/memory.db and memory/memory.faiss
    mem_dir = run_dir / "memory"
    if not (mem_dir / "memory.db").exists():
        missing.append("memory/memory.db is missing")
    if not (mem_dir / "memory.faiss").exists():
        missing.append("memory/memory.faiss is missing")

    # 6. memory_events.jsonl
    if not (run_dir / "memory_events.jsonl").exists():
        missing.append("memory_events.jsonl is missing")

    # 7. cost_summary.json
    if not (run_dir / "cost_summary.json").exists():
        missing.append("cost_summary.json is missing")

    ok = len(missing) == 0
    return ok, missing


# ---------------------------------------------------------------------------
# write_completed
# ---------------------------------------------------------------------------


def write_completed(
    run_dir: Path | str,
    experiment_sha: str | None = None,
    config_hash: str | None = None,
    manifest_hash: str | None = None,
    tool_mode: str | None = None,
    task_count: int = 0,
) -> None:
    """Write RUN_COMPLETED.json atomically after successful validation.

    Only call this after ``validate_run_complete`` returns ``(True, [])``.
    Sourcing priority for optional args:
    - ``experiment_sha``: arg > ``EXPERIMENT_SHA`` env var > git HEAD
    - ``tool_mode``: arg > ``AGENT_TOOL_MODE`` env var > "fixed"
    """
    run_dir = Path(run_dir)
    sha = experiment_sha or _get_experiment_sha()
    mode = tool_mode or os.environ.get("AGENT_TOOL_MODE", "fixed")

    data: dict[str, Any] = {
        "experiment_sha": sha,
        "config_hash": config_hash or "",
        "manifest_hash": manifest_hash or "",
        "tool_mode": mode,
        "task_count": task_count,
        "validated_at": _utcnow(),
    }
    sentinel = run_dir / "RUN_COMPLETED.json"
    _atomic_write_json(sentinel, data)
    logger.info(f"Written RUN_COMPLETED.json for {run_dir.name}")


# ---------------------------------------------------------------------------
# write_failed
# ---------------------------------------------------------------------------


def write_failed(
    run_dir: Path | str,
    error_type: str,
    error_message: str,
    experiment_sha: str | None = None,
    tool_mode: str | None = None,
) -> None:
    """Write RUN_FAILED.json atomically at the run-level exception boundary.

    Call before re-raising the exception so the marker persists even if the
    process exits immediately afterwards.
    """
    run_dir = Path(run_dir)
    sha = experiment_sha or _get_experiment_sha()
    mode = tool_mode or os.environ.get("AGENT_TOOL_MODE", "fixed")

    data: dict[str, Any] = {
        "error_type": error_type,
        "error_message": error_message,
        "experiment_sha": sha,
        "tool_mode": mode,
        "failed_at": _utcnow(),
    }
    sentinel = run_dir / "RUN_FAILED.json"
    _atomic_write_json(sentinel, data)
    logger.info(f"Written RUN_FAILED.json for {run_dir.name}: {error_type}")


# ---------------------------------------------------------------------------
# is_run_complete
# ---------------------------------------------------------------------------


def is_run_complete(run_dir: Path | str) -> bool:
    """Return True iff ``RUN_COMPLETED.json`` exists in *run_dir*.

    This is the single gate that orchestrators (experiment_runner loops,
    pilot scripts) must check before counting a returned ``run_sequence()``
    call as a completed run.  A run that returned but whose directory is
    missing the sentinel was aborted or partially written — it must NOT be
    counted toward ``completed_runs`` and must remain eligible for reconcile.

    Do NOT re-implement the check inline; always call this function so that
    the definition stays in one place alongside ``write_completed`` /
    ``validate_run_complete``.
    """
    return (Path(run_dir) / "RUN_COMPLETED.json").exists()


# ---------------------------------------------------------------------------
# archive_prior_attempt
# ---------------------------------------------------------------------------


def archive_prior_attempt(run_dir: Path | str) -> None:
    """Move a run_dir that has a terminal failure (or no marker) to
    ``{run_dir}.attempt{k}/`` if it contains a ``RUN_FAILED.json`` or
    any leftover data from a prior run that did not produce
    ``RUN_COMPLETED.json``.

    A fresh empty directory (no ``RUN_FAILED.json`` AND no ``RUN_COMPLETED.json``
    AND no ``task_results.jsonl``) is left untouched.

    Invariant: after the call, ``run_dir`` either does not exist (was moved)
    or is a clean empty directory; no stale marker remains.
    """
    run_dir = Path(run_dir)
    if not run_dir.exists():
        return

    has_failed = (run_dir / "RUN_FAILED.json").exists()
    has_completed = (run_dir / "RUN_COMPLETED.json").exists()
    has_results = (run_dir / "task_results.jsonl").exists()

    # A successfully completed run must never be archived — it contains good data.
    # A fresh empty dir (no markers, no results) → nothing to archive.
    # Only archive if: has a FAILED marker, OR has prior data but no COMPLETED.
    if has_completed or (not has_failed and not has_results):
        return

    # Find the next free attempt slot
    k = 1
    while True:
        attempt_dir = run_dir.parent / f"{run_dir.name}.attempt{k}"
        if not attempt_dir.exists():
            break
        k += 1

    shutil.move(str(run_dir), str(attempt_dir))
    logger.info(f"Archived prior attempt of {run_dir.name} to {attempt_dir.name}")
