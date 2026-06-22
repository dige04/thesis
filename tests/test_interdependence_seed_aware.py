"""Seed-aware E7 memory-lift tests (Task 5 / D-5).

Tests that:
1. memory-lift is computed PAIRED within each seed, then averaged across seeds —
   NOT last-seed-wins (the old key shape {(policy,repo): {idx: resolved}}
   silently overwrites earlier seeds during iterdir()).
2. Cells where any expected seed is missing from either condition are DROPPED
   and reported in a sidecar, never silently averaged from whatever seeds happen
   to exist.
3. memory_lift_by_position accepts and preserves float inputs (no int() truncation),
   since per-seed-averaged resolved rates are fractional.

These tests MUST FAIL before the fix and PASS after.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts.run_analysis import stage_interdependence
from src.analysis.interdependence import memory_lift_by_position


# ---------------------------------------------------------------------------
# Helper: build a minimal run-dir tree for stage_interdependence tests.
# ---------------------------------------------------------------------------

def _make_run(
    runs_dir: Path,
    policy: str,
    repo: str,
    seed: int,
    resolved_by_index: dict[int, int],
) -> None:
    """Write a task_results.jsonl with controlled resolved values per index."""
    run_id = f"pilot_{policy}_{repo}_seed{seed}"
    rd = runs_dir / run_id
    rd.mkdir(parents=True, exist_ok=True)
    with open(rd / "task_results.jsonl", "w") as f:
        for idx, res in sorted(resolved_by_index.items()):
            f.write(json.dumps({
                "policy": policy,
                "repo": repo,
                "seed": seed,
                "sequence_index": idx,
                "resolved": res,
                "total_tokens": 1000,
                "memory_tokens_after": 0,
                "estimated_cost_usd": 0.0,
                "tool_calls": 5,
                "wall_time_seconds": 10.0,
            }) + "\n")


# ---------------------------------------------------------------------------
# Test 1 — last-seed-wins regression (the core bug).
#
# Three seeds with DIFFERENT resolved patterns for full_memory at idx 0.
# Seed 1: full=[1,0] no_mem=[0,0]  per-seed lift = +1
# Seed 2: full=[1,0] no_mem=[0,0]  per-seed lift = +1
# Seed 3: full=[0,0] no_mem=[0,0]  per-seed lift =  0
#
# Expected seed-averaged overall_lift = (1 + 1 + 0) / 3 = 0.667 (approx)
# Last-seed-wins (old bug) takes seed-3 only → overall_lift = 0.0
#
# The test asserts the seed-averaged value (≈ 0.667) and must fail on the
# last-seed-wins code, because that code returns 0.0.
# ---------------------------------------------------------------------------

def test_lift_is_seed_averaged_not_last_seed(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"

    # full_memory: seeds 1 & 2 resolve idx0, seed 3 does not
    _make_run(runs_dir, "full_memory", "myrepo", 1, {0: 1, 1: 0})
    _make_run(runs_dir, "full_memory", "myrepo", 2, {0: 1, 1: 0})
    _make_run(runs_dir, "full_memory", "myrepo", 3, {0: 0, 1: 0})

    # no_memory: all seeds never resolve anything
    _make_run(runs_dir, "no_memory",   "myrepo", 1, {0: 0, 1: 0})
    _make_run(runs_dir, "no_memory",   "myrepo", 2, {0: 0, 1: 0})
    _make_run(runs_dir, "no_memory",   "myrepo", 3, {0: 0, 1: 0})

    out_dir = tmp_path / "results"
    stage_interdependence(runs_dir, out_dir, curriculum=None)

    lift_csv = out_dir / "tables" / "memory_lift.csv"
    assert lift_csv.exists(), "memory_lift.csv was not written"

    rows = {r["repo"]: r for r in csv.DictReader(open(lift_csv))}
    assert "myrepo" in rows, f"myrepo missing from lift CSV; rows={list(rows)}"

    overall = float(rows["myrepo"]["overall_lift"])
    # Seed-averaged: (1+1+0)/3 resolved for full vs 0/3 for no_mem → lift ≈ 0.333
    # (idx0: full avg=2/3, no_mem avg=0 → +0.667; idx1: both avg=0 → 0; overall=(0.667+0)/2=0.333)
    # Last-seed-wins (bug): full=[0,0] no_mem=[0,0] → lift = 0.0
    assert overall == pytest.approx(1 / 3, abs=0.01), (
        f"overall_lift={overall!r}: expected seed-averaged ≈0.333 "
        f"(last-seed-wins would give 0.0 — if you see 0.0 the bug is still present)"
    )


# ---------------------------------------------------------------------------
# Test 2 — missing-seed cell dropped and reported in sidecar.
#
# "myrepo" has all 3 seeds for full_memory but only 2 for no_memory (seed 3
# missing).  That cell is INCOMPLETE → must be DROPPED from memory_lift.csv
# and listed in the dropped_incomplete sidecar.
# ---------------------------------------------------------------------------

def test_incomplete_cell_is_dropped_not_averaged(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"

    # full_memory: 3 seeds present
    for seed in (1, 2, 3):
        _make_run(runs_dir, "full_memory", "myrepo", seed, {0: 1, 1: 0})

    # no_memory: seed 3 MISSING — only 2 seeds
    for seed in (1, 2):
        _make_run(runs_dir, "no_memory",   "myrepo", seed, {0: 0, 1: 0})
    # seed 3 for no_memory deliberately NOT created

    out_dir = tmp_path / "results"
    stage_interdependence(runs_dir, out_dir, curriculum=None)

    lift_csv = out_dir / "tables" / "memory_lift.csv"
    # If the CSV exists it must NOT contain myrepo
    if lift_csv.exists():
        rows = {r["repo"]: r for r in csv.DictReader(open(lift_csv))}
        assert "myrepo" not in rows, (
            "myrepo should be DROPPED because no_memory is missing seed 3; "
            f"it was incorrectly included with {rows.get('myrepo')}"
        )

    # A dropped_incomplete sidecar must exist and list the dropped cell
    sidecar = out_dir / "tables" / "memory_lift_dropped.json"
    assert sidecar.exists(), (
        "dropped_incomplete sidecar (memory_lift_dropped.json) must be written "
        "when a cell is dropped; it was not found"
    )
    dropped = json.loads(sidecar.read_text())
    assert isinstance(dropped, list), f"sidecar must be a JSON list; got {type(dropped)}"
    repos_dropped = [d["repo"] for d in dropped]
    assert "myrepo" in repos_dropped, (
        f"myrepo must appear in dropped_incomplete; found {repos_dropped}"
    )


# ---------------------------------------------------------------------------
# Test 3 — memory_lift_by_position preserves floats (no int() truncation).
#
# When inputs are fractional averages (e.g. 2/3 ≈ 0.667), the per_position_lift
# values must remain floats, not be truncated to int.  The old code used
# int(full[i]) - int(no_memory[i]) which gives 0 for any fractional input < 1.
# ---------------------------------------------------------------------------

def test_memory_lift_preserves_float_inputs() -> None:
    """per_position_lift must remain float, not be truncated via int()."""
    # 2/3 ≈ 0.667 vs 0.0 → lift should be ≈ 0.667, not int(0.667)-int(0.0)=0
    no_mem = [0.0, 0.0]
    full   = [2 / 3, 1.0]
    result = memory_lift_by_position(no_mem, full)

    # per_position_lift[0] must be ≈ 0.667, not 0 (int truncation)
    assert result["per_position_lift"][0] == pytest.approx(2 / 3, abs=0.001), (
        f"per_position_lift[0]={result['per_position_lift'][0]!r}: "
        "expected ≈0.667; int() truncation gives 0 — if you see 0 the bug is still present"
    )
    assert result["overall_lift"] == pytest.approx(5 / 6, abs=0.001)


# ---------------------------------------------------------------------------
# Test 4 — n_seeds column in output CSV is auditable.
#
# When a complete cell (3 seeds) is correctly averaged, the memory_lift.csv
# must carry an n_seeds column equal to 3.
# ---------------------------------------------------------------------------

def test_lift_csv_carries_n_seeds_column(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"

    for seed in (1, 2, 3):
        _make_run(runs_dir, "full_memory", "myrepo", seed, {0: 1, 1: 1})
        _make_run(runs_dir, "no_memory",   "myrepo", seed, {0: 0, 1: 0})

    out_dir = tmp_path / "results"
    stage_interdependence(runs_dir, out_dir, curriculum=None)

    lift_csv = out_dir / "tables" / "memory_lift.csv"
    assert lift_csv.exists()
    rows = list(csv.DictReader(open(lift_csv)))
    assert rows, "memory_lift.csv is empty"
    assert "n_seeds" in rows[0], (
        f"n_seeds column missing from memory_lift.csv; columns={list(rows[0].keys())}"
    )
    assert int(rows[0]["n_seeds"]) == 3, (
        f"Expected n_seeds=3 for a complete cell; got {rows[0]['n_seeds']}"
    )
