"""Tests for src/benchmark/completion.py — atomic sentinels + validate_run_complete.

TDD: these tests are written BEFORE the implementation and should FAIL initially.
"""
import json
import os
import time
from pathlib import Path

import pytest

from src.benchmark.completion import (
    archive_prior_attempt,
    validate_run_complete,
    write_completed,
    write_failed,
)

# ---------------------------------------------------------------------------
# Fixture builder — creates a minimal 2-task run dir with all artifacts
# ---------------------------------------------------------------------------

TASK_IDS = ["pkg__pkg-1", "pkg__pkg-2"]
MANIFEST_ENTRY = {"task_ids": TASK_IDS, "task_count": 2}


def _build_complete_run(run_dir: Path) -> Path:
    """Populate run_dir with every artifact validate_run_complete requires."""
    run_dir.mkdir(parents=True, exist_ok=True)

    # task_results.jsonl — one row per task (no dups)
    task_rows = [
        {"task_id": t, "resolved": 0, "timeout": False}
        for t in TASK_IDS
    ]
    with open(run_dir / "task_results.jsonl", "w") as f:
        for row in task_rows:
            f.write(json.dumps(row) + "\n")

    # trajectories/{task_id}.json
    traj_dir = run_dir / "trajectories"
    traj_dir.mkdir(parents=True, exist_ok=True)
    for t in TASK_IDS:
        (traj_dir / f"{t}.json").write_text(json.dumps({"steps": []}))

    # patches/{task_id}.patch
    patches_dir = run_dir / "patches"
    patches_dir.mkdir(parents=True, exist_ok=True)
    for t in TASK_IDS:
        (patches_dir / f"{t}.patch").write_text("")

    # memory/snapshots/before_task_{k}.json + after_task_{k}.json
    snapshot_dir = run_dir / "memory" / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    for k in range(len(TASK_IDS)):
        (snapshot_dir / f"before_task_{k}.json").write_text(json.dumps({"step": k}))
        (snapshot_dir / f"after_task_{k}.json").write_text(json.dumps({"step": k}))

    # memory/memory.db  and  memory/memory.faiss
    mem_dir = run_dir / "memory"
    (mem_dir / "memory.db").write_text("")
    (mem_dir / "memory.faiss").write_bytes(b"")

    # memory_events.jsonl
    (run_dir / "memory_events.jsonl").write_text("")

    # cost_summary.json
    (run_dir / "cost_summary.json").write_text(json.dumps({"total_tokens": 0}))

    return run_dir


# ---------------------------------------------------------------------------
# 1. validate_run_complete: ACCEPTS a complete run
# ---------------------------------------------------------------------------

def test_validate_accepts_complete_run(tmp_path):
    run_dir = _build_complete_run(tmp_path / "run")
    ok, missing = validate_run_complete(run_dir, MANIFEST_ENTRY)
    assert ok is True
    assert missing == []


# ---------------------------------------------------------------------------
# 2. validate_run_complete: REJECTS — missing a task row
# ---------------------------------------------------------------------------

def test_validate_rejects_missing_task_row(tmp_path):
    run_dir = _build_complete_run(tmp_path / "run")
    # Remove one row from task_results.jsonl
    rows = [
        {"task_id": TASK_IDS[0], "resolved": 0}
    ]
    with open(run_dir / "task_results.jsonl", "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")

    ok, missing = validate_run_complete(run_dir, MANIFEST_ENTRY)
    assert ok is False
    assert any("task_results" in m or TASK_IDS[1] in m for m in missing), missing


# ---------------------------------------------------------------------------
# 3. validate_run_complete: REJECTS — duplicate task row
# ---------------------------------------------------------------------------

def test_validate_rejects_duplicate_task_row(tmp_path):
    run_dir = _build_complete_run(tmp_path / "run")
    # Write duplicate row
    with open(run_dir / "task_results.jsonl", "a") as f:
        f.write(json.dumps({"task_id": TASK_IDS[0]}) + "\n")

    ok, missing = validate_run_complete(run_dir, MANIFEST_ENTRY)
    assert ok is False
    assert any("dup" in m.lower() or "duplicate" in m.lower() for m in missing), missing


# ---------------------------------------------------------------------------
# 4. validate_run_complete: REJECTS — missing trajectories/{task_id}.json
# ---------------------------------------------------------------------------

def test_validate_rejects_missing_trajectory(tmp_path):
    run_dir = _build_complete_run(tmp_path / "run")
    (run_dir / "trajectories" / f"{TASK_IDS[0]}.json").unlink()

    ok, missing = validate_run_complete(run_dir, MANIFEST_ENTRY)
    assert ok is False
    assert any("trajectories" in m or TASK_IDS[0] in m for m in missing), missing


# ---------------------------------------------------------------------------
# 5. validate_run_complete: REJECTS — missing patches/{task_id}.patch
# ---------------------------------------------------------------------------

def test_validate_rejects_missing_patch(tmp_path):
    run_dir = _build_complete_run(tmp_path / "run")
    (run_dir / "patches" / f"{TASK_IDS[1]}.patch").unlink()

    ok, missing = validate_run_complete(run_dir, MANIFEST_ENTRY)
    assert ok is False
    assert any("patch" in m.lower() for m in missing), missing


# ---------------------------------------------------------------------------
# 6. validate_run_complete: REJECTS — missing before_task snapshot
# ---------------------------------------------------------------------------

def test_validate_rejects_missing_before_snapshot(tmp_path):
    run_dir = _build_complete_run(tmp_path / "run")
    (run_dir / "memory" / "snapshots" / "before_task_0.json").unlink()

    ok, missing = validate_run_complete(run_dir, MANIFEST_ENTRY)
    assert ok is False
    assert any("before_task_0" in m for m in missing), missing


# ---------------------------------------------------------------------------
# 7. validate_run_complete: REJECTS — missing after_task snapshot
# ---------------------------------------------------------------------------

def test_validate_rejects_missing_after_snapshot(tmp_path):
    run_dir = _build_complete_run(tmp_path / "run")
    (run_dir / "memory" / "snapshots" / "after_task_1.json").unlink()

    ok, missing = validate_run_complete(run_dir, MANIFEST_ENTRY)
    assert ok is False
    assert any("after_task_1" in m for m in missing), missing


# ---------------------------------------------------------------------------
# 8. validate_run_complete: REJECTS — missing memory.db
# ---------------------------------------------------------------------------

def test_validate_rejects_missing_memory_db(tmp_path):
    run_dir = _build_complete_run(tmp_path / "run")
    (run_dir / "memory" / "memory.db").unlink()

    ok, missing = validate_run_complete(run_dir, MANIFEST_ENTRY)
    assert ok is False
    assert any("memory.db" in m for m in missing), missing


# ---------------------------------------------------------------------------
# 9. validate_run_complete: REJECTS — missing memory.faiss
# ---------------------------------------------------------------------------

def test_validate_rejects_missing_memory_faiss(tmp_path):
    run_dir = _build_complete_run(tmp_path / "run")
    (run_dir / "memory" / "memory.faiss").unlink()

    ok, missing = validate_run_complete(run_dir, MANIFEST_ENTRY)
    assert ok is False
    assert any("memory.faiss" in m for m in missing), missing


# ---------------------------------------------------------------------------
# 10. validate_run_complete: REJECTS — missing memory_events.jsonl
# ---------------------------------------------------------------------------

def test_validate_rejects_missing_memory_events(tmp_path):
    run_dir = _build_complete_run(tmp_path / "run")
    (run_dir / "memory_events.jsonl").unlink()

    ok, missing = validate_run_complete(run_dir, MANIFEST_ENTRY)
    assert ok is False
    assert any("memory_events" in m for m in missing), missing


# ---------------------------------------------------------------------------
# 11. write_completed: produces JSON with required keys, atomically
# ---------------------------------------------------------------------------

def test_write_completed_keys_and_atomic(tmp_path, monkeypatch):
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    monkeypatch.setenv("EXPERIMENT_SHA", "abc123")
    monkeypatch.setenv("AGENT_TOOL_MODE", "fixed")

    write_completed(
        run_dir=run_dir,
        experiment_sha="abc123",
        config_hash="cfg1",
        manifest_hash="mfst1",
        tool_mode="fixed",
        task_count=2,
    )

    sentinel = run_dir / "RUN_COMPLETED.json"
    assert sentinel.exists()

    data = json.loads(sentinel.read_text())
    for key in ("experiment_sha", "config_hash", "manifest_hash", "tool_mode",
                 "task_count", "validated_at"):
        assert key in data, f"missing key: {key}"

    assert data["experiment_sha"] == "abc123"
    assert data["task_count"] == 2


# ---------------------------------------------------------------------------
# 12. write_failed: produces JSON with required keys, atomically
# ---------------------------------------------------------------------------

def test_write_failed_keys_and_atomic(tmp_path, monkeypatch):
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    monkeypatch.setenv("EXPERIMENT_SHA", "abc123")

    write_failed(
        run_dir=run_dir,
        error_type="UsageLimitError",
        error_message="quota hit",
        experiment_sha="abc123",
        tool_mode="fixed",
    )

    sentinel = run_dir / "RUN_FAILED.json"
    assert sentinel.exists()

    data = json.loads(sentinel.read_text())
    for key in ("error_type", "error_message", "experiment_sha", "tool_mode", "failed_at"):
        assert key in data, f"missing key: {key}"

    assert data["error_type"] == "UsageLimitError"


# ---------------------------------------------------------------------------
# 13. archive_prior_attempt: moves failed dir to .attempt1/, fresh dir has no marker
# ---------------------------------------------------------------------------

def test_archive_prior_attempt_on_failed(tmp_path):
    run_dir = tmp_path / "run_abc"
    run_dir.mkdir()
    (run_dir / "RUN_FAILED.json").write_text(json.dumps({"error_type": "err"}))
    (run_dir / "task_results.jsonl").write_text("")

    archive_prior_attempt(run_dir)

    # Original dir should be gone (or empty — a fresh blank dir is OK)
    attempt_dir = tmp_path / "run_abc.attempt1"
    assert attempt_dir.exists(), "attempt1 dir not created"
    assert (attempt_dir / "RUN_FAILED.json").exists()


def test_archive_prior_attempt_increments_k(tmp_path):
    """If .attempt1 already exists, should go to .attempt2."""
    run_dir = tmp_path / "run_abc"
    run_dir.mkdir()
    (run_dir / "RUN_FAILED.json").write_text(json.dumps({"error_type": "err"}))
    (tmp_path / "run_abc.attempt1").mkdir()  # already taken

    archive_prior_attempt(run_dir)

    assert (tmp_path / "run_abc.attempt2").exists()


def test_archive_no_op_for_fresh_dir(tmp_path):
    """A run_dir with no terminal marker is freshly created — no archive."""
    run_dir = tmp_path / "run_fresh"
    run_dir.mkdir()
    # No RUN_FAILED.json, no RUN_COMPLETED.json

    archive_prior_attempt(run_dir)

    # Should NOT create attempt dirs
    assert not (tmp_path / "run_fresh.attempt1").exists()


# ---------------------------------------------------------------------------
# 14. validate_run_complete: REJECTS — missing cost_summary.json
# ---------------------------------------------------------------------------

def test_validate_rejects_missing_cost_summary(tmp_path):
    run_dir = _build_complete_run(tmp_path / "run")
    (run_dir / "cost_summary.json").unlink()

    ok, missing = validate_run_complete(run_dir, MANIFEST_ENTRY)
    assert ok is False
    assert any("cost_summary" in m for m in missing), missing


# ---------------------------------------------------------------------------
# 15. archive_prior_attempt: NEVER archives a dir that has RUN_COMPLETED.json
# ---------------------------------------------------------------------------

def test_archive_does_not_touch_completed_run(tmp_path):
    """A dir with RUN_COMPLETED.json must NEVER be archived (data loss guard)."""
    run_dir = tmp_path / "run_done"
    run_dir.mkdir()
    # Write both COMPLETED and FAILED (belt-and-suspenders check — COMPLETED wins)
    (run_dir / "RUN_COMPLETED.json").write_text(json.dumps({"task_count": 2}))
    (run_dir / "RUN_FAILED.json").write_text(json.dumps({"error_type": "err"}))
    (run_dir / "task_results.jsonl").write_text("")

    archive_prior_attempt(run_dir)

    # Original dir must still exist — not moved
    assert run_dir.exists(), "archive_prior_attempt moved a COMPLETED run — data loss!"
    assert not (tmp_path / "run_done.attempt1").exists(), (
        "archive_prior_attempt created an attempt dir for a COMPLETED run"
    )


def test_archive_does_not_touch_completed_run_no_failed_marker(tmp_path):
    """RUN_COMPLETED.json alone (no RUN_FAILED.json) is enough to protect the dir."""
    run_dir = tmp_path / "run_clean"
    run_dir.mkdir()
    (run_dir / "RUN_COMPLETED.json").write_text(json.dumps({"task_count": 3}))
    (run_dir / "task_results.jsonl").write_text("")

    archive_prior_attempt(run_dir)

    assert run_dir.exists(), "archive_prior_attempt moved a COMPLETED run"
    assert not (tmp_path / "run_clean.attempt1").exists()
