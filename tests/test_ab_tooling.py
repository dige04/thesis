"""Tests for scripts/ab_schedule.py and scripts/ab_gate.py (Task 5e).

TDD: these tests are written BEFORE the implementation and should FAIL initially.
Run with:
    .venv/bin/pytest tests/test_ab_tooling.py -v
    .venv/bin/pytest tests/ -k "ab_" -q
"""
from __future__ import annotations

import json
import os
import statistics
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Expected A/B schedule constants
# ---------------------------------------------------------------------------
SEQUENCES = [
    "pytest-dev_pytest_sequence",
    "scikit-learn_scikit-learn_sequence",
]
POLICIES = ["no_memory", "full_memory", "recency_prune"]
SEEDS = [1, 2, 3]
TOOL_MODES = ["legacy", "fixed"]
EXPECTED_CELL_COUNT = len(SEQUENCES) * len(POLICIES) * len(SEEDS) * len(TOOL_MODES)  # 36


# ---------------------------------------------------------------------------
# Helpers — minimal run-dir builder
# ---------------------------------------------------------------------------

TASK_IDS = ["pkg__pkg-1", "pkg__pkg-2"]


def _build_run_dir(
    root: Path,
    run_id: str,
    policy: str,
    seed: int,
    sequence: str,
    tool_mode: str,
    task_ids: list[str] = TASK_IDS,
    resolved: list[int] | None = None,
    prompt_tokens: int = 1000,
    total_tokens: int = 1200,
    edit_observations: list[str] | None = None,
    write_completed_sentinel: bool = True,
    write_failed_sentinel: bool = False,
) -> Path:
    """Build a minimal run directory with the required structure.

    Args:
        root: parent directory under which run_id dir is created.
        run_id: name for the run directory.
        edit_observations: list of observation_summary strings to inject as
            edit_file trajectory steps.  Defaults to one success per task.
        write_completed_sentinel: if True, write RUN_COMPLETED.json.
        write_failed_sentinel: if True, write RUN_FAILED.json instead.
    """
    if resolved is None:
        resolved = [0] * len(task_ids)
    if edit_observations is None:
        edit_observations = [f"Edited src/mod.py"] * len(task_ids)

    run_dir = root / run_id
    run_dir.mkdir(parents=True)

    # ── task_results.jsonl ───────────────────────────────────────────────
    with open(run_dir / "task_results.jsonl", "w") as f:
        for i, tid in enumerate(task_ids):
            row = {
                "task_id": tid,
                "resolved": resolved[i],
                "prompt_tokens": prompt_tokens,
                "total_tokens": total_tokens,
                "policy": policy,
                "seed": seed,
                "tool_mode": tool_mode,
            }
            f.write(json.dumps(row) + "\n")

    # ── trajectories/{task_id}.json ──────────────────────────────────────
    traj_dir = run_dir / "trajectories"
    traj_dir.mkdir()
    for i, tid in enumerate(task_ids):
        obs = edit_observations[i] if i < len(edit_observations) else "Edited src/mod.py"
        traj = {
            "task_id": tid,
            "policy": policy,
            "seed": seed,
            "steps": [
                {
                    "step": 1,
                    "action": "read_file",
                    "action_input": {"path": "src/mod.py"},
                    "observation_summary": "line1\nline2\n",
                },
                {
                    "step": 2,
                    "action": "edit_file",
                    "action_input": {"path": "src/mod.py", "diff": "@@..."},
                    "observation_summary": obs,
                },
            ],
        }
        (traj_dir / f"{tid}.json").write_text(json.dumps(traj))

    # ── patches/ ─────────────────────────────────────────────────────────
    patches_dir = run_dir / "patches"
    patches_dir.mkdir()
    for tid in task_ids:
        (patches_dir / f"{tid}.patch").write_text("")

    # ── memory/snapshots ─────────────────────────────────────────────────
    snapshot_dir = run_dir / "memory" / "snapshots"
    snapshot_dir.mkdir(parents=True)
    for k in range(len(task_ids)):
        (snapshot_dir / f"before_task_{k}.json").write_text("{}")
        (snapshot_dir / f"after_task_{k}.json").write_text("{}")
    mem_dir = run_dir / "memory"
    (mem_dir / "memory.db").write_text("")
    (mem_dir / "memory.faiss").write_bytes(b"")

    # ── memory_events.jsonl ──────────────────────────────────────────────
    (run_dir / "memory_events.jsonl").write_text("")

    # ── cost_summary.json ────────────────────────────────────────────────
    (run_dir / "cost_summary.json").write_text(json.dumps({"total_tokens": total_tokens}))

    # ── sentinels ────────────────────────────────────────────────────────
    if write_completed_sentinel:
        (run_dir / "RUN_COMPLETED.json").write_text(
            json.dumps({"tool_mode": tool_mode, "task_count": len(task_ids)})
        )
    if write_failed_sentinel:
        (run_dir / "RUN_FAILED.json").write_text(
            json.dumps({"error_type": "TestError", "error_message": "injected"})
        )

    return run_dir


def _build_full_ab_fixture(
    root: Path,
    task_ids: list[str] = TASK_IDS,
    prompt_tokens: int = 1000,
    total_tokens: int = 1200,
    edit_observations: list[str] | None = None,
) -> list[dict]:
    """Build all 36 A/B run dirs under *root* using ab_schedule-canonical run_ids."""
    from scripts.ab_schedule import ab_schedule

    schedule = ab_schedule(seed=20260622)
    for cell in schedule:
        obs = edit_observations
        _build_run_dir(
            root=root,
            run_id=cell["run_id"],
            policy=cell["policy"],
            seed=cell["seed"],
            sequence=cell["sequence_name"],
            tool_mode=cell["tool_mode"],
            task_ids=task_ids,
            prompt_tokens=prompt_tokens,
            total_tokens=total_tokens,
            edit_observations=obs,
        )
    return schedule


# ===========================================================================
# PART 1: ab_schedule tests
# ===========================================================================


class TestAbSchedule:
    def test_returns_exactly_36_cells(self):
        from scripts.ab_schedule import ab_schedule

        cells = ab_schedule(seed=20260622)
        assert len(cells) == EXPECTED_CELL_COUNT, (
            f"Expected {EXPECTED_CELL_COUNT} cells, got {len(cells)}"
        )

    def test_all_run_ids_unique(self):
        from scripts.ab_schedule import ab_schedule

        cells = ab_schedule(seed=20260622)
        run_ids = [c["run_id"] for c in cells]
        assert len(run_ids) == len(set(run_ids)), "run_ids are not unique"

    def test_run_id_contains_tool_mode(self):
        from scripts.ab_schedule import ab_schedule

        cells = ab_schedule(seed=20260622)
        for cell in cells:
            assert cell["tool_mode"] in cell["run_id"], (
                f"run_id '{cell['run_id']}' does not contain tool_mode '{cell['tool_mode']}'"
            )

    def test_each_cell_has_required_keys(self):
        from scripts.ab_schedule import ab_schedule

        cells = ab_schedule(seed=20260622)
        required = {"run_id", "policy", "sequence_name", "seed", "tool_mode"}
        for cell in cells:
            missing = required - set(cell.keys())
            assert not missing, f"Cell missing keys: {missing}"

    def test_deterministic_across_two_calls(self):
        from scripts.ab_schedule import ab_schedule

        cells_a = ab_schedule(seed=20260622)
        cells_b = ab_schedule(seed=20260622)
        assert cells_a == cells_b, "ab_schedule is not deterministic"

    def test_different_seed_gives_different_order(self):
        from scripts.ab_schedule import ab_schedule

        cells_a = ab_schedule(seed=20260622)
        cells_b = ab_schedule(seed=99999)
        # Same multiset, different order (with overwhelming probability)
        ids_a = [c["run_id"] for c in cells_a]
        ids_b = [c["run_id"] for c in cells_b]
        assert sorted(ids_a) == sorted(ids_b), "Different seeds must produce the same multiset of run_ids"
        # Extremely unlikely to be identical order (1/36! chance)
        assert ids_a != ids_b, "Different seeds should produce different ordering"

    def test_same_multiset_regardless_of_seed(self):
        """Canonical 36 cells present in every seed."""
        from scripts.ab_schedule import ab_schedule

        canonical = {c["run_id"] for c in ab_schedule(seed=20260622)}
        for seed in [1, 42, 20260622, 0]:
            cells = ab_schedule(seed=seed)
            assert len(cells) == EXPECTED_CELL_COUNT
            assert {c["run_id"] for c in cells} == canonical

    def test_correct_sequences(self):
        from scripts.ab_schedule import ab_schedule

        cells = ab_schedule(seed=20260622)
        seqs = {c["sequence_name"] for c in cells}
        assert seqs == set(SEQUENCES)

    def test_correct_policies(self):
        from scripts.ab_schedule import ab_schedule

        cells = ab_schedule(seed=20260622)
        policies = {c["policy"] for c in cells}
        assert policies == set(POLICIES)

    def test_correct_seeds(self):
        from scripts.ab_schedule import ab_schedule

        cells = ab_schedule(seed=20260622)
        seeds = {c["seed"] for c in cells}
        assert seeds == set(SEEDS)

    def test_correct_tool_modes(self):
        from scripts.ab_schedule import ab_schedule

        cells = ab_schedule(seed=20260622)
        modes = {c["tool_mode"] for c in cells}
        assert modes == set(TOOL_MODES)

    def test_cell_counts_balanced(self):
        """Each (policy, sequence, seed) pair appears exactly twice (legacy + fixed)."""
        from scripts.ab_schedule import ab_schedule

        cells = ab_schedule(seed=20260622)
        from collections import Counter

        keys = [(c["policy"], c["sequence_name"], c["seed"]) for c in cells]
        counter = Counter(keys)
        for key, count in counter.items():
            assert count == 2, f"Cell {key} appears {count} times (expected 2)"


# ===========================================================================
# PART 2: ab_gate BLOCKED cases
# ===========================================================================


class TestAbGateBlocked:
    def test_blocked_when_no_runs_at_all(self, tmp_path):
        from scripts.ab_gate import ab_gate

        result = ab_gate(runs_root=tmp_path / "runs", results_dir=tmp_path / "results")
        assert result["gate"] == "BLOCKED"
        assert "reason" in result or "reasons" in result

    def test_blocked_when_fewer_than_36_completed(self, tmp_path):
        """Only 18 of 36 runs are present — gate must block."""
        from scripts.ab_schedule import ab_schedule
        from scripts.ab_gate import ab_gate

        runs_root = tmp_path / "runs"
        schedule = ab_schedule(seed=20260622)
        # Build only first 18
        for cell in schedule[:18]:
            _build_run_dir(
                root=runs_root,
                run_id=cell["run_id"],
                policy=cell["policy"],
                seed=cell["seed"],
                sequence=cell["sequence_name"],
                tool_mode=cell["tool_mode"],
            )

        result = ab_gate(runs_root=runs_root, results_dir=tmp_path / "results")
        assert result["gate"] == "BLOCKED"

    def test_blocked_when_a_run_has_failed_sentinel(self, tmp_path):
        """Even if 36 runs exist, any RUN_FAILED.json → BLOCKED."""
        from scripts.ab_schedule import ab_schedule
        from scripts.ab_gate import ab_gate

        runs_root = tmp_path / "runs"
        schedule = ab_schedule(seed=20260622)
        # Build all 36, but inject RUN_FAILED into one
        for i, cell in enumerate(schedule):
            _build_run_dir(
                root=runs_root,
                run_id=cell["run_id"],
                policy=cell["policy"],
                seed=cell["seed"],
                sequence=cell["sequence_name"],
                tool_mode=cell["tool_mode"],
                write_completed_sentinel=(i != 0),
                write_failed_sentinel=(i == 0),
            )

        result = ab_gate(runs_root=runs_root, results_dir=tmp_path / "results")
        assert result["gate"] == "BLOCKED"

    def test_blocked_when_tasks_unpaired(self, tmp_path):
        """All 36 complete, but one legacy run has an extra task_id not in its fixed pair → BLOCKED."""
        from scripts.ab_schedule import ab_schedule
        from scripts.ab_gate import ab_gate

        runs_root = tmp_path / "runs"
        schedule = ab_schedule(seed=20260622)

        # Find the index of the first legacy cell so we can inject an extra task_id into it
        first_legacy_idx = next(i for i, c in enumerate(schedule) if c["tool_mode"] == "legacy")

        # Build all 36; add an extra task to the first legacy run only
        for i, cell in enumerate(schedule):
            task_ids = list(TASK_IDS)
            if i == first_legacy_idx:
                task_ids = task_ids + ["pkg__pkg-EXTRA"]
            _build_run_dir(
                root=runs_root,
                run_id=cell["run_id"],
                policy=cell["policy"],
                seed=cell["seed"],
                sequence=cell["sequence_name"],
                tool_mode=cell["tool_mode"],
                task_ids=task_ids,
            )

        result = ab_gate(runs_root=runs_root, results_dir=tmp_path / "results")
        assert result["gate"] == "BLOCKED"


# ===========================================================================
# PART 3: ab_gate GO cases
# ===========================================================================


class TestAbGateGo:
    def test_go_on_complete_paired_fixture(self, tmp_path):
        from scripts.ab_gate import ab_gate

        runs_root = tmp_path / "runs"
        _build_full_ab_fixture(
            root=runs_root,
            prompt_tokens=1000,
            total_tokens=1200,
        )
        result = ab_gate(runs_root=runs_root, results_dir=tmp_path / "results")
        assert result["gate"] == "GO", f"Expected GO, got {result}"

    def test_go_result_has_required_keys(self, tmp_path):
        from scripts.ab_gate import ab_gate

        runs_root = tmp_path / "runs"
        _build_full_ab_fixture(root=runs_root)
        result = ab_gate(runs_root=runs_root, results_dir=tmp_path / "results")
        assert "gate" in result
        assert "metrics" in result
        assert "reported_deltas" in result
        assert "reasons" in result

    def test_go_reports_resolve_and_timeout_deltas(self, tmp_path):
        from scripts.ab_gate import ab_gate

        runs_root = tmp_path / "runs"
        _build_full_ab_fixture(root=runs_root)
        result = ab_gate(runs_root=runs_root, results_dir=tmp_path / "results")
        assert "resolved_delta" in result["reported_deltas"] or "resolve" in str(
            result["reported_deltas"]
        )

    def test_go_metrics_edit_failure_count_and_ratio(self, tmp_path):
        from scripts.ab_gate import ab_gate

        runs_root = tmp_path / "runs"
        _build_full_ab_fixture(root=runs_root)
        result = ab_gate(runs_root=runs_root, results_dir=tmp_path / "results")
        m = result["metrics"]
        assert "edit_path_index_failures" in m
        assert "edit_failure_ratio" in m
        assert "total_edit_file_calls" in m

    def test_go_zero_path_index_failures_on_clean_fixture(self, tmp_path):
        """All observations are 'Edited <path>' → no path/index failures."""
        from scripts.ab_gate import ab_gate

        runs_root = tmp_path / "runs"
        _build_full_ab_fixture(
            root=runs_root,
            edit_observations=["Edited src/mod.py"] * len(TASK_IDS),
        )
        result = ab_gate(runs_root=runs_root, results_dir=tmp_path / "results")
        assert result["metrics"]["edit_path_index_failures"] == 0

    def test_go_notes_range_correctness_dependency(self, tmp_path):
        """ab_gate output must reference range-correctness test dependency."""
        from scripts.ab_gate import ab_gate

        runs_root = tmp_path / "runs"
        _build_full_ab_fixture(root=runs_root)
        result = ab_gate(runs_root=runs_root, results_dir=tmp_path / "results")
        result_str = json.dumps(result)
        assert "read_file" in result_str or "range" in result_str or "test_agents_tools" in result_str


# ===========================================================================
# PART 4: ab_gate STOP cases
# ===========================================================================


class TestAbGateStop:
    def test_stop_when_total_edit_file_is_zero(self, tmp_path):
        """No edit_file calls in any trajectory → gate must be STOP (not GO)."""
        from scripts.ab_schedule import ab_schedule
        from scripts.ab_gate import ab_gate

        runs_root = tmp_path / "runs"
        schedule = ab_schedule(seed=20260622)
        for cell in schedule:
            # Build run dirs with NO edit_file steps (read_file only)
            run_dir = runs_root / cell["run_id"]
            run_dir.mkdir(parents=True)
            (run_dir / "task_results.jsonl").write_text(
                json.dumps({
                    "task_id": TASK_IDS[0],
                    "resolved": 0,
                    "prompt_tokens": 1000,
                    "total_tokens": 1200,
                    "policy": cell["policy"],
                    "seed": cell["seed"],
                    "tool_mode": cell["tool_mode"],
                }) + "\n"
            )
            traj_dir = run_dir / "trajectories"
            traj_dir.mkdir()
            traj = {
                "task_id": TASK_IDS[0],
                "policy": cell["policy"],
                "seed": cell["seed"],
                "steps": [
                    {
                        "step": 1,
                        "action": "read_file",  # only read_file, no edit_file
                        "action_input": {"path": "src/mod.py"},
                        "observation_summary": "content",
                    }
                ],
            }
            (traj_dir / f"{TASK_IDS[0]}.json").write_text(json.dumps(traj))
            (run_dir / "RUN_COMPLETED.json").write_text(
                json.dumps({"tool_mode": cell["tool_mode"], "task_count": 1})
            )
            # Other required files (for validation to pass)
            patches_dir = run_dir / "patches"
            patches_dir.mkdir()
            (patches_dir / f"{TASK_IDS[0]}.patch").write_text("")
            snapshot_dir = run_dir / "memory" / "snapshots"
            snapshot_dir.mkdir(parents=True)
            (snapshot_dir / "before_task_0.json").write_text("{}")
            (snapshot_dir / "after_task_0.json").write_text("{}")
            mem_dir = run_dir / "memory"
            (mem_dir / "memory.db").write_text("")
            (mem_dir / "memory.faiss").write_bytes(b"")
            (run_dir / "memory_events.jsonl").write_text("")
            (run_dir / "cost_summary.json").write_text("{}")

        result = ab_gate(runs_root=runs_root, results_dir=tmp_path / "results")
        assert result["gate"] != "GO", (
            "total_edit_file==0 must not produce GO, got: " + json.dumps(result)
        )

    def test_stop_when_edit_failure_ratio_above_threshold(self, tmp_path):
        """edit_file failure ratio > 0.15 → gate is STOP."""
        from scripts.ab_gate import ab_gate

        runs_root = tmp_path / "runs"
        # Inject failure observations for > 15% of edit_file calls
        # We have 2 tasks per run × 36 runs = 72 edit_file calls (in fixed mode, used for metrics)
        # Set all edit_file observations to ERROR to push ratio to 1.0 > 0.15
        failure_obs = "ERROR: tool 'edit_file' failed: Could not apply the diff to src/mod.py: does not match index"
        _build_full_ab_fixture(
            root=runs_root,
            edit_observations=[failure_obs] * len(TASK_IDS),
        )
        result = ab_gate(runs_root=runs_root, results_dir=tmp_path / "results")
        assert result["gate"] == "STOP", (
            f"Expected STOP for high edit failure ratio, got: {result['gate']}"
        )

    def test_stop_when_edit_path_failures_nonzero(self, tmp_path):
        """Observations with '/testbed' absolute path → edit_path_index_failures > 0 → STOP."""
        from scripts.ab_gate import ab_gate

        runs_root = tmp_path / "runs"
        # One run with a /testbed path failure observation
        path_failure_obs = "ERROR: tool 'edit_file' failed: File not found: /testbed/src/mod.py"
        # Mix: most succeed, one has path failure
        obs_list = ["Edited src/mod.py", path_failure_obs]
        _build_full_ab_fixture(
            root=runs_root,
            edit_observations=obs_list,
        )
        result = ab_gate(runs_root=runs_root, results_dir=tmp_path / "results")
        assert result["gate"] == "STOP", (
            f"Expected STOP for path failures, got: {result['gate']} | metrics: {result.get('metrics')}"
        )

    def test_stop_when_token_inflation_too_high(self, tmp_path):
        """Fixed runs use >1.5× more prompt tokens than legacy → STOP."""
        from scripts.ab_schedule import ab_schedule
        from scripts.ab_gate import ab_gate

        runs_root = tmp_path / "runs"
        schedule = ab_schedule(seed=20260622)
        for cell in schedule:
            # Legacy: 1000 prompt tokens; Fixed: 2000 (= 2.0×, above 1.5×)
            if cell["tool_mode"] == "legacy":
                pt, tt = 1000, 1200
            else:
                pt, tt = 2001, 2400  # > 1.5 × legacy

            _build_run_dir(
                root=runs_root,
                run_id=cell["run_id"],
                policy=cell["policy"],
                seed=cell["seed"],
                sequence=cell["sequence_name"],
                tool_mode=cell["tool_mode"],
                prompt_tokens=pt,
                total_tokens=tt,
            )

        result = ab_gate(runs_root=runs_root, results_dir=tmp_path / "results")
        assert result["gate"] == "STOP", (
            f"Expected STOP for token inflation, got: {result['gate']} | metrics: {result.get('metrics')}"
        )
