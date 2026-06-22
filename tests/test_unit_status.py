"""Tests for scripts/unit_status.py — unit_status() helper.

TDD: these tests should FAIL before scripts/unit_status.py exists and PASS after.

Four cases:
  1. RUN_COMPLETED.json present  -> "complete"  (skip)
  2. RUN_FAILED.json present     -> "failed"    (re-queue)
  3. dir exists, neither marker  -> "incomplete" (re-queue)
  4. dir absent entirely         -> "incomplete" (re-queue)
"""
import json
from pathlib import Path

import pytest

from scripts.unit_status import unit_status


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_run_dir(base: Path, run_id: str) -> Path:
    d = base / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# 1. RUN_COMPLETED.json present -> "complete"
# ---------------------------------------------------------------------------


def test_status_complete(tmp_path):
    run_id = "full_memory_django_django_sequence_seed1"
    run_dir = _make_run_dir(tmp_path, run_id)
    (run_dir / "RUN_COMPLETED.json").write_text(
        json.dumps({"validated_at": "2026-06-22T00:00:00+00:00"})
    )

    assert unit_status(run_id, tmp_path) == "complete"


# ---------------------------------------------------------------------------
# 2. RUN_FAILED.json present (no RUN_COMPLETED.json) -> "failed"
# ---------------------------------------------------------------------------


def test_status_failed(tmp_path):
    run_id = "recency_prune_sympy_sympy_sequence_seed2"
    run_dir = _make_run_dir(tmp_path, run_id)
    (run_dir / "RUN_FAILED.json").write_text(
        json.dumps({"error_type": "UsageLimitError", "failed_at": "2026-06-22T01:00:00+00:00"})
    )

    assert unit_status(run_id, tmp_path) == "failed"


# ---------------------------------------------------------------------------
# 3. Dir exists, neither marker -> "incomplete"
# ---------------------------------------------------------------------------


def test_status_incomplete_dir_exists(tmp_path):
    run_id = "type_aware_decay_pytest-dev_pytest_sequence_seed3"
    _make_run_dir(tmp_path, run_id)
    # No RUN_COMPLETED.json, no RUN_FAILED.json

    assert unit_status(run_id, tmp_path) == "incomplete"


# ---------------------------------------------------------------------------
# 4. Dir absent entirely -> "incomplete"
# ---------------------------------------------------------------------------


def test_status_incomplete_dir_absent(tmp_path):
    run_id = "no_memory_astropy_astropy_sequence_seed1"
    # Do NOT create the directory

    assert unit_status(run_id, tmp_path) == "incomplete"


# ---------------------------------------------------------------------------
# 5. Boundary: RUN_COMPLETED takes priority over RUN_FAILED (shouldn't happen
#    in practice but we want deterministic precedence)
# ---------------------------------------------------------------------------


def test_status_completed_takes_priority_over_failed(tmp_path):
    run_id = "cls_consolidation_matplotlib_matplotlib_sequence_seed2"
    run_dir = _make_run_dir(tmp_path, run_id)
    (run_dir / "RUN_COMPLETED.json").write_text(json.dumps({"validated_at": "x"}))
    (run_dir / "RUN_FAILED.json").write_text(json.dumps({"error_type": "x"}))

    assert unit_status(run_id, tmp_path) == "complete"


# ---------------------------------------------------------------------------
# 6. CLI: calling the module as __main__ prints the status to stdout
# ---------------------------------------------------------------------------


def test_cli_prints_status(tmp_path, capsys):
    """unit_status.py can be invoked as a module from the shell."""
    import subprocess, sys, os

    run_id = "random_prune_sphinx-doc_sphinx_sequence_seed1"
    run_dir = tmp_path / run_id
    run_dir.mkdir()
    (run_dir / "RUN_COMPLETED.json").write_text(json.dumps({"validated_at": "x"}))

    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parent.parent / "scripts" / "unit_status.py"),
            run_id,
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "complete"
