"""Tests for the smoke harness check logic (offline — no network).

Task 4a — Part 2b: test the evaluate_smoke_trajectory() pure function
against fixture trajectories.

These tests run ENTIRELY OFFLINE. They import only ``scripts.run_smoke``
(specifically ``evaluate_smoke_trajectory``) and exercise it against
hand-crafted fixture trajectories.

Any test that would invoke the real LLM (i.e., calls ``run_smoke()``)
is marked ``@pytest.mark.skip(reason="network; run in Task 4b")``.
"""
from __future__ import annotations

import pytest

from scripts.run_smoke import evaluate_smoke_trajectory


# ---------------------------------------------------------------------------
# Fixture trajectory builders
# ---------------------------------------------------------------------------


def _make_step(
    action: str,
    action_input: dict,
    observation_summary: str = "",
) -> dict:
    return {
        "action": action,
        "action_input": action_input,
        "observation_summary": observation_summary,
    }


def _good_trajectory(target_line: int = 6700) -> list[dict]:
    """A trajectory that satisfies all 4 checks."""
    return [
        # Ranged read that reaches the target region
        _make_step(
            "read_file",
            {"path": "sympy/core/basic.py", "start_line": 6600, "end_line": 6800},
            f"# sympy/core/basic.py (lines 6600-6800 of 7000)\n6600\tdef _eval_rewrite(self):",
        ),
        # A search step (non-read, resets repeat-read window)
        _make_step(
            "search_code",
            {"query": "_eval_rewrite", "file_pattern": "*.py"},
            '[{"file": "sympy/core/basic.py", "line": 6701, "content": "..."}]',
        ),
        # Successful edit
        _make_step(
            "edit_file",
            {"path": "sympy/core/basic.py", "diff": "--- a/sympy/core/basic.py\n..."},
            "Edited sympy/core/basic.py",
        ),
        # Finish
        _make_step("finish", {}, "acknowledged"),
    ]


def _good_result() -> dict:
    return {
        "termination_reason": "finished_tool",
        "patch_generated": True,
        "tool_mode": "fixed",
    }


def _good_task_meta(target_line: int = 6700) -> dict:
    return {
        "task_id": "sympy__sympy-13091",
        "repo": "sympy/sympy",
        "target_file": "sympy/core/basic.py",
        "approx_hunk_start_line": target_line,
    }


# ---------------------------------------------------------------------------
# Test: good trajectory passes all checks
# ---------------------------------------------------------------------------


class TestGoodTrajectoryPasses:
    def test_all_checks_pass(self):
        result = evaluate_smoke_trajectory(
            _good_trajectory(), _good_result(), _good_task_meta()
        )
        assert result["passed"] is True
        assert result["failures"] == []

    def test_ranged_read_check_passes(self):
        result = evaluate_smoke_trajectory(
            _good_trajectory(), _good_result(), _good_task_meta()
        )
        assert result["checks"]["ranged_read_reaching_target"] is True

    def test_no_repeat_loop_check_passes(self):
        result = evaluate_smoke_trajectory(
            _good_trajectory(), _good_result(), _good_task_meta()
        )
        assert result["checks"]["no_identical_repeat_read_loop"] is True

    def test_successful_edit_check_passes(self):
        result = evaluate_smoke_trajectory(
            _good_trajectory(), _good_result(), _good_task_meta()
        )
        assert result["checks"]["at_least_one_successful_edit"] is True

    def test_termination_reason_check_passes(self):
        result = evaluate_smoke_trajectory(
            _good_trajectory(), _good_result(), _good_task_meta()
        )
        assert result["checks"]["termination_reason_recorded"] is True


# ---------------------------------------------------------------------------
# Test: identical-repeat read loop is detected
# ---------------------------------------------------------------------------


class TestIdenticalRepeatReadLoopFails:
    def _repeat_read_trajectory(self) -> list[dict]:
        """Two consecutive identical read_file calls (the loop defect)."""
        return [
            # First read of the range
            _make_step(
                "read_file",
                {"path": "sympy/core/basic.py", "start_line": 6600, "end_line": 6800},
                "# sympy/core/basic.py (lines 6600-6800 of 7000)\n...",
            ),
            # Identical second read — no progress (stuck)
            _make_step(
                "read_file",
                {"path": "sympy/core/basic.py", "start_line": 6600, "end_line": 6800},
                "# sympy/core/basic.py (lines 6600-6800 of 7000)\n...",
            ),
            # Eventually edits and finishes
            _make_step("edit_file", {"path": "sympy/core/basic.py", "diff": "..."}, "Edited sympy/core/basic.py"),
            _make_step("finish", {}, "acknowledged"),
        ]

    def test_repeat_loop_check_fails(self):
        result = evaluate_smoke_trajectory(
            self._repeat_read_trajectory(),
            _good_result(),
            _good_task_meta(),
        )
        assert result["checks"]["no_identical_repeat_read_loop"] is False

    def test_overall_result_fails(self):
        result = evaluate_smoke_trajectory(
            self._repeat_read_trajectory(),
            _good_result(),
            _good_task_meta(),
        )
        assert result["passed"] is False

    def test_failure_message_mentions_consecutive(self):
        result = evaluate_smoke_trajectory(
            self._repeat_read_trajectory(),
            _good_result(),
            _good_task_meta(),
        )
        assert any("consecutive" in f.lower() or "identical" in f.lower() for f in result["failures"])

    def test_non_consecutive_identical_reads_are_ok(self):
        """Same read_file args but separated by a non-read step: should NOT fail."""
        trajectory = [
            _make_step(
                "read_file",
                {"path": "sympy/core/basic.py", "start_line": 6600, "end_line": 6800},
                "...",
            ),
            # A search step breaks the consecutive sequence
            _make_step("search_code", {"query": "foo"}, "[]"),
            # Same read again — but NOT consecutive
            _make_step(
                "read_file",
                {"path": "sympy/core/basic.py", "start_line": 6600, "end_line": 6800},
                "...",
            ),
            _make_step("edit_file", {"path": "sympy/core/basic.py", "diff": "..."}, "Edited sympy/core/basic.py"),
            _make_step("finish", {}, "acknowledged"),
        ]
        result = evaluate_smoke_trajectory(
            trajectory,
            _good_result(),
            _good_task_meta(),
        )
        assert result["checks"]["no_identical_repeat_read_loop"] is True


# ---------------------------------------------------------------------------
# Test: missing successful edit
# ---------------------------------------------------------------------------


class TestMissingSuccessfulEditFails:
    def _no_edit_trajectory(self) -> list[dict]:
        return [
            _make_step(
                "read_file",
                {"path": "sympy/core/basic.py", "start_line": 6600, "end_line": 6800},
                "...",
            ),
            # edit_file that ERRORED — not a success
            _make_step(
                "edit_file",
                {"path": "sympy/core/basic.py", "diff": "bad diff"},
                "ERROR: tool 'edit_file' failed: Could not apply the diff",
            ),
            _make_step("finish", {}, "acknowledged"),
        ]

    def test_failed_edit_does_not_satisfy_check(self):
        result = evaluate_smoke_trajectory(
            self._no_edit_trajectory(),
            _good_result(),
            _good_task_meta(),
        )
        assert result["checks"]["at_least_one_successful_edit"] is False

    def test_overall_result_fails(self):
        result = evaluate_smoke_trajectory(
            self._no_edit_trajectory(),
            _good_result(),
            _good_task_meta(),
        )
        assert result["passed"] is False

    def test_write_file_also_satisfies_edit_check(self):
        """write_file success observation counts as a successful modification."""
        trajectory = [
            _make_step(
                "read_file",
                {"path": "sympy/core/basic.py", "start_line": 6600, "end_line": 6800},
                "...",
            ),
            _make_step(
                "write_file",
                {"path": "sympy/core/basic.py", "content": "# new content"},
                "Wrote sympy/core/basic.py",
            ),
            _make_step("finish", {}, "acknowledged"),
        ]
        result = evaluate_smoke_trajectory(
            trajectory,
            _good_result(),
            _good_task_meta(),
        )
        assert result["checks"]["at_least_one_successful_edit"] is True


# ---------------------------------------------------------------------------
# Test: missing termination_reason
# ---------------------------------------------------------------------------


class TestMissingTerminationReason:
    def test_none_termination_reason_fails(self):
        result = evaluate_smoke_trajectory(
            _good_trajectory(),
            {"termination_reason": None},
            _good_task_meta(),
        )
        assert result["checks"]["termination_reason_recorded"] is False

    def test_empty_string_termination_reason_fails(self):
        result = evaluate_smoke_trajectory(
            _good_trajectory(),
            {"termination_reason": ""},
            _good_task_meta(),
        )
        assert result["checks"]["termination_reason_recorded"] is False

    def test_missing_key_termination_reason_fails(self):
        result = evaluate_smoke_trajectory(
            _good_trajectory(),
            {},  # no termination_reason key
            _good_task_meta(),
        )
        assert result["checks"]["termination_reason_recorded"] is False

    def test_step_limit_termination_reason_passes(self):
        result = evaluate_smoke_trajectory(
            _good_trajectory(),
            {"termination_reason": "step_limit"},
            _good_task_meta(),
        )
        assert result["checks"]["termination_reason_recorded"] is True


# ---------------------------------------------------------------------------
# Test: ranged read not reaching target
# ---------------------------------------------------------------------------


class TestRangedReadNotReachingTarget:
    def _head_only_trajectory(self, target_line: int = 6700) -> list[dict]:
        """Agent only reads the head of the file (never near target_line)."""
        return [
            # Whole-file read (no start_line → doesn't count as ranged-to-target)
            _make_step(
                "read_file",
                {"path": "sympy/core/basic.py"},
                "# sympy/core/basic.py (lines 1-200 of 7000; budget cap) ...\n",
            ),
            # Another head read
            _make_step(
                "read_file",
                {"path": "sympy/core/basic.py", "start_line": 1, "end_line": 100},
                "...",
            ),
            _make_step("edit_file", {"path": "sympy/core/basic.py", "diff": "..."}, "Edited sympy/core/basic.py"),
            _make_step("finish", {}, "acknowledged"),
        ]

    def test_head_only_reads_fail_ranged_check(self):
        result = evaluate_smoke_trajectory(
            self._head_only_trajectory(target_line=6700),
            _good_result(),
            _good_task_meta(target_line=6700),
        )
        assert result["checks"]["ranged_read_reaching_target"] is False

    def test_overall_result_fails(self):
        result = evaluate_smoke_trajectory(
            self._head_only_trajectory(target_line=6700),
            _good_result(),
            _good_task_meta(target_line=6700),
        )
        assert result["passed"] is False

    def test_no_target_line_skips_check(self):
        """If approx_hunk_start_line=0 or absent, ranged check should be tolerant."""
        # With target_line=0, any read with start_line set satisfies
        # start > 0 - MAX_READ_LINES (= start > -400), which is always true.
        result = evaluate_smoke_trajectory(
            _good_trajectory(target_line=6700),
            _good_result(),
            {"task_id": "some-task", "approx_hunk_start_line": 0},
        )
        # We just verify no exception is raised and the key exists
        assert "ranged_read_reaching_target" in result["checks"]

    def test_large_end_line_head_read_still_fails(self):
        """A read(start=1, end=9999) covers the range on paper but the 400-line
        cap means the agent never sees line 6700. The tightened check requires
        start_line > target - MAX_READ_LINES, so this must FAIL."""
        trajectory = [
            # Agent asks for lines 1-9999 but only gets 1-400 (budget cap)
            _make_step(
                "read_file",
                {"path": "sympy/core/basic.py", "start_line": 1, "end_line": 9999},
                "# sympy/core/basic.py (lines 1-400 of 7000; budget cap)\n...",
            ),
            _make_step("edit_file", {"path": "sympy/core/basic.py", "diff": "..."}, "Edited sympy/core/basic.py"),
            _make_step("finish", {}, "acknowledged"),
        ]
        result = evaluate_smoke_trajectory(
            trajectory,
            _good_result(),
            _good_task_meta(target_line=6700),
        )
        # start=1 is NOT > 6700 - 400 = 6300, so this must fail
        assert result["checks"]["ranged_read_reaching_target"] is False


# ---------------------------------------------------------------------------
# Test: task_id propagated to result
# ---------------------------------------------------------------------------


def test_task_id_propagated_to_result():
    meta = _good_task_meta()
    result = evaluate_smoke_trajectory(_good_trajectory(), _good_result(), meta)
    assert result["task_id"] == meta["task_id"]


# ---------------------------------------------------------------------------
# Test: empty trajectory fails edit + ranged checks
# ---------------------------------------------------------------------------


def test_empty_trajectory_fails_multiple_checks():
    result = evaluate_smoke_trajectory([], _good_result(), _good_task_meta())
    assert result["passed"] is False
    assert result["checks"]["ranged_read_reaching_target"] is False
    assert result["checks"]["at_least_one_successful_edit"] is False


# ---------------------------------------------------------------------------
# Network-only tests (skipped in offline suite)
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="network; run in Task 4b")
def test_run_smoke_network():
    """Full smoke run on real tasks — skipped offline, executed in Task 4b."""
    from scripts.run_smoke import run_smoke
    results = run_smoke()
    # All 3 tasks should pass
    assert all(r["passed"] for r in results.values()), (
        "Some smoke tasks failed checks: "
        + str({tid: r["failures"] for tid, r in results.items() if not r["passed"]})
    )


@pytest.mark.skip(reason="network; run in Task 4b")
def test_run_completed_json_written_on_pass():
    """RUN_COMPLETED.json sentinel is written for passing tasks — network run only."""
    import tempfile
    from pathlib import Path
    from scripts.run_smoke import run_smoke

    with tempfile.TemporaryDirectory() as tmpdir:
        results = run_smoke(runs_root=tmpdir)
        for task_id, r in results.items():
            if r["passed"]:
                run_dir = Path(r["run_dir"])
                assert (run_dir / "RUN_COMPLETED.json").exists(), (
                    f"RUN_COMPLETED.json missing for {task_id}"
                )
