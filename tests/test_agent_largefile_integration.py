"""Integration tests for agent tools on realistic large-file inputs.

Task 4a — Part 1: offline integration cross-check at production conditions.

Tests:
1. read_file with a range past line 200 returns exactly those numbered lines
   (not the head), and whole-file read is budget-bounded with continuation hint.
2. _truncate_obs on ~30KB simulated pytest failure preserves the tail
   (failure summary) and len <= _MAX_OBS.
3. edit_file with /testbed/-style diff paths (applies) and cross-file diff (ValueError).
4. 1-2 task flow exercising MemoryStore + TrajectoryLogger under a tmp RUNS_ROOT:
   all four artifact types (task rows, trajectories, snapshots, memory.db/faiss) land
   under the single run_dir, nothing written to ./runs/.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.agents.langgraph_agent import AgentState, CodingAgent, _MAX_OBS, _truncate_obs
from src.agents.tools import MAX_READ_CHARS, AgentTools


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def large_file_repo(tmp_path):
    """Git repo with a file > 400 lines / > 12000 chars, committed."""
    repo = tmp_path
    os.system(f"cd {repo} && git init -q")
    os.system(f"cd {repo} && git config user.email 'test@test.com'")
    os.system(f"cd {repo} && git config user.name 'Test User'")

    # Build a file with 500 lines, each padded to ~35 chars so
    # 500 * ~40 bytes (numbered) >> 12000 chars budget.
    # Each raw line is "line_NNNN_pad_x_xxxxxxxxxxxxxxxxx" (~38 chars + newline)
    lines = [f"line_{i:04d}_pad_x_{'x' * 20}" for i in range(1, 501)]
    content = "\n".join(lines) + "\n"
    assert len(content) > 12000, "fixture must exceed MAX_READ_CHARS"
    assert len(lines) > 400, "fixture must exceed MAX_READ_LINES"

    (repo / "bigfile.py").write_text(content)
    (repo / "other.py").write_text("y = 2\n")
    os.system(f"cd {repo} && git add -A && git commit -q -m 'init'")
    return repo


@pytest.fixture
def agent_and_tools(large_file_repo):
    """Return a (CodingAgent, AgentTools, AgentState) triple for integration tests."""
    task_env = MagicMock()
    task_env.working_dir = large_file_repo

    config = {
        "agent": {
            "max_steps_per_task": 20,
            "max_tool_calls_per_task": 80,
            "max_test_runs_per_task": 5,
            "max_wall_time_seconds": 1200,
            "temperature": 0,
        },
        "memory": {"top_k": 5, "max_context_tokens": 2000},
    }
    memory_store = MagicMock()
    policy = MagicMock()

    with (
        patch("src.agents.langgraph_agent.get_chat_client"),
        patch("src.agents.langgraph_agent.main_model", return_value="test-model"),
    ):
        agent = CodingAgent(
            memory_store=memory_store,
            policy=policy,
            config=config,
            task_env=task_env,
        )

    tools = AgentTools(working_dir=str(large_file_repo))
    state = AgentState(
        task_id="test__task-001",
        repo="test/repo",
        base_commit="abc123",
        issue_text="Fix bug",
        sequence_index=0,
    )
    return agent, tools, state


# ---------------------------------------------------------------------------
# Bullet 1 — read_file range / budget / continuation hint
# ---------------------------------------------------------------------------


class TestReadFileLargeFile:
    """Integration cross-check: read_file on a production-sized file."""

    def test_ranged_read_past_line_200_returns_exact_range(
        self, large_file_repo, agent_and_tools, monkeypatch
    ):
        """read_file(start_line=250, end_line=260) via _execute_tool returns lines 250-260."""
        monkeypatch.setenv("AGENT_TOOL_MODE", "fixed")
        agent, tools, state = agent_and_tools

        obs = agent._execute_tool(
            tools, "read_file", {"path": "bigfile.py", "start_line": 250, "end_line": 260}, state
        )

        # Lines 250-260 must be present
        assert "250\t" in obs
        assert "260\t" in obs
        # Lines outside the range must NOT be present
        assert "249\t" not in obs
        assert "261\t" not in obs
        # Line number content spot-check
        assert "line_0250" in obs or "line_0249" in obs  # 1-indexed line 250 = array[249]

    def test_ranged_read_does_not_return_head(
        self, large_file_repo, agent_and_tools, monkeypatch
    ):
        """A ranged read past line 200 must NOT return line 1 content."""
        monkeypatch.setenv("AGENT_TOOL_MODE", "fixed")
        agent, tools, state = agent_and_tools

        obs = agent._execute_tool(
            tools, "read_file", {"path": "bigfile.py", "start_line": 300, "end_line": 310}, state
        )

        # Head lines must be absent
        assert "1\tline_0001" not in obs
        assert "300\t" in obs

    def test_whole_file_read_is_budget_bounded(
        self, large_file_repo, agent_and_tools, monkeypatch
    ):
        """Whole-file read on the large file must be <= MAX_READ_CHARS."""
        monkeypatch.setenv("AGENT_TOOL_MODE", "fixed")
        agent, tools, state = agent_and_tools

        obs = agent._execute_tool(tools, "read_file", {"path": "bigfile.py"}, state)

        assert len(obs) <= MAX_READ_CHARS, (
            f"Whole-file read must be budget-bounded; got {len(obs)} chars"
        )

    def test_whole_file_read_has_continuation_hint(
        self, large_file_repo, agent_and_tools, monkeypatch
    ):
        """Whole-file read on the large file must emit a continuation hint."""
        monkeypatch.setenv("AGENT_TOOL_MODE", "fixed")
        agent, tools, state = agent_and_tools

        obs = agent._execute_tool(tools, "read_file", {"path": "bigfile.py"}, state)

        assert "to continue" in obs.lower() or "read_file(path," in obs, (
            "Budget-capped read must include a continuation hint"
        )

    def test_ranged_read_files_tracked_in_state(
        self, large_file_repo, agent_and_tools, monkeypatch
    ):
        """_execute_tool must append the path to state.files_read."""
        monkeypatch.setenv("AGENT_TOOL_MODE", "fixed")
        agent, tools, state = agent_and_tools

        agent._execute_tool(
            tools, "read_file", {"path": "bigfile.py", "start_line": 100, "end_line": 110}, state
        )

        assert "bigfile.py" in state.files_read


# ---------------------------------------------------------------------------
# Bullet 2 — _truncate_obs on a ~30KB pytest failure
# ---------------------------------------------------------------------------


class TestTruncateObsLargeFailure:
    """_truncate_obs must preserve the failure tail on realistic output."""

    def _make_pytest_failure(self) -> str:
        """Build a ~30KB simulated pytest failure with the critical info at the tail."""
        # ~28KB of noise at the top (collected items, passing tests)
        header = "===== test session starts =====\n"
        passing = "".join(
            f"test_module.py::test_case_{i:04d} PASSED\n" for i in range(700)
        )
        # Failure summary at the end (the important tail)
        failure_tail = (
            "\n===== FAILURES =====\n"
            "FAILED test_module.py::test_critical_case - AssertionError: assert 42 == 99\n"
            "E   AssertionError: assert 42 == 99\n"
            "E   where 42 = some_function()\n"
            "short test summary info\n"
            "FAILED test_module.py::test_critical_case\n"
            "1 failed, 700 passed in 12.34s\n"
        )
        full = header + passing + failure_tail
        return full, failure_tail

    def test_failure_tail_survives_truncation(self, monkeypatch):
        """The failure assertion text at the END must survive _truncate_obs in fixed mode."""
        monkeypatch.setenv("AGENT_TOOL_MODE", "fixed")
        full, failure_tail = self._make_pytest_failure()
        assert len(full) > 20000, f"fixture too small: {len(full)}"

        out = _truncate_obs(full, mode="fixed")

        # Tail marker must survive
        assert "AssertionError: assert 42 == 99" in out
        assert "1 failed, 700 passed" in out

    def test_truncated_output_within_max_obs(self, monkeypatch):
        """Truncated output must fit within _MAX_OBS."""
        monkeypatch.setenv("AGENT_TOOL_MODE", "fixed")
        full, _ = self._make_pytest_failure()
        out = _truncate_obs(full, mode="fixed")
        assert len(out) <= _MAX_OBS, f"Truncated obs too large: {len(out)} > {_MAX_OBS}"

    def test_omitted_marker_present_for_large_input(self, monkeypatch):
        """Truncated output must include the 'chars omitted' marker."""
        monkeypatch.setenv("AGENT_TOOL_MODE", "fixed")
        full, _ = self._make_pytest_failure()
        out = _truncate_obs(full, mode="fixed")
        assert "omitted" in out

    def test_legacy_mode_head_truncates(self, monkeypatch):
        """In legacy mode, _truncate_obs head-truncates at 4000 chars (regression guard)."""
        monkeypatch.setenv("AGENT_TOOL_MODE", "legacy")
        from src.agents.tools import _LEGACY_OBS_CAP
        full, failure_tail = self._make_pytest_failure()

        out = _truncate_obs(full, mode="legacy")

        # legacy head-truncates → failure tail is gone
        assert len(out) <= _LEGACY_OBS_CAP
        assert "1 failed, 700 passed" not in out  # tail lost


# ---------------------------------------------------------------------------
# Bullet 3 — edit_file: /testbed/ paths apply, cross-file diff rejected
# ---------------------------------------------------------------------------


@pytest.fixture
def git_repo_edit(tmp_path):
    """Minimal git repo with m.py + other.py committed — mirrors test_agents_tools pattern."""
    repo = tmp_path
    os.system(f"cd {repo} && git init -q")
    os.system(f"cd {repo} && git config user.email 'test@test.com'")
    os.system(f"cd {repo} && git config user.name 'Test User'")
    (repo / "m.py").write_text("x = 1\n")
    (repo / "other.py").write_text("y = 2\n")
    os.system(f"cd {repo} && git add -A && git commit -q -m 'init'")
    return repo


class TestEditFileIntegration:
    """Integration cross-check for edit_file path normalisation + security."""

    def test_testbed_absolute_path_diff_applies(self, git_repo_edit, monkeypatch):
        """Diff with /testbed/ absolute paths (as container agent emits) must apply."""
        monkeypatch.setenv("AGENT_TOOL_MODE", "fixed")
        tools = AgentTools(str(git_repo_edit))
        diff = (
            "diff --git a/testbed/m.py b/testbed/m.py\n"
            "--- /testbed/m.py\n"
            "+++ /testbed/m.py\n"
            "@@ -1 +1 @@\n"
            "-x = 1\n"
            "+x = 99\n"
        )
        tools.edit_file("m.py", diff)
        assert (git_repo_edit / "m.py").read_text() == "x = 99\n"

    def test_cross_file_diff_raises_value_error(self, git_repo_edit, monkeypatch):
        """Diff touching other.py when path='m.py' must raise ValueError."""
        monkeypatch.setenv("AGENT_TOOL_MODE", "fixed")
        tools = AgentTools(str(git_repo_edit))
        diff = (
            "--- a/other.py\n"
            "+++ b/other.py\n"
            "@@ -1 +1 @@\n"
            "-y = 2\n"
            "+y = 99\n"
        )
        with pytest.raises(ValueError):
            tools.edit_file("m.py", diff)
        # m.py must be untouched
        assert (git_repo_edit / "m.py").read_text() == "x = 1\n"
        # other.py must be untouched
        assert (git_repo_edit / "other.py").read_text() == "y = 2\n"

    def test_standard_diff_applies(self, git_repo_edit, monkeypatch):
        """Standard a/b unified diff must apply correctly."""
        monkeypatch.setenv("AGENT_TOOL_MODE", "fixed")
        tools = AgentTools(str(git_repo_edit))
        diff = (
            "--- a/m.py\n"
            "+++ b/m.py\n"
            "@@ -1 +1 @@\n"
            "-x = 1\n"
            "+x = 42\n"
        )
        tools.edit_file("m.py", diff)
        assert (git_repo_edit / "m.py").read_text() == "x = 42\n"


# ---------------------------------------------------------------------------
# Bullet 4 — 1-2 task flow: all artifacts land under run_dir, not ./runs/
# ---------------------------------------------------------------------------


def _make_patched_memory_store(run_dir: Path, run_id: str = "test-run"):
    """Create a MemoryStore with network dependencies patched out."""
    from src.memory.store import MemoryStore

    with (
        patch("src.memory.store.OpenAI", return_value=MagicMock()),
        patch("src.memory.store.embedding_base_url", return_value="http://localhost"),
        patch("src.memory.store.embedding_api_key", return_value="x"),
        patch("src.memory.store.faiss") as mock_faiss,
    ):
        mock_index = MagicMock()
        mock_faiss.IndexFlatL2.return_value = mock_index
        store = MemoryStore(
            run_id=run_id,
            policy_name="no_memory",
            embedding_dim=768,
            embedding_model="nomic-embed-text-v2-moe",
            run_dir=run_dir,
        )
    return store


class TestArtifactRunDir:
    """All four artifact types must land under the injected run_dir, not ./runs/."""

    def test_memory_db_under_run_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        run_id = "test-run"
        run_dir = tmp_path / run_id
        store = _make_patched_memory_store(run_dir, run_id)

        assert store.db_path == run_dir / "memory" / "memory.db"
        assert store.db_path.exists()
        assert not (tmp_path / "runs").exists()

    def test_memory_faiss_under_run_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        run_id = "test-run"
        run_dir = tmp_path / run_id
        store = _make_patched_memory_store(run_dir, run_id)

        assert store.faiss_path == run_dir / "memory" / "memory.faiss"
        assert not (tmp_path / "runs").exists()

    def test_memory_snapshots_under_run_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        run_id = "test-run"
        run_dir = tmp_path / run_id
        store = _make_patched_memory_store(run_dir, run_id)

        assert store.snapshot_dir == run_dir / "memory" / "snapshots"
        assert store.snapshot_dir.exists()
        assert not (tmp_path / "runs").exists()

    def test_trajectory_under_run_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from src.logging.trajectory_logger import TrajectoryLogger

        run_id = "test-run"
        run_dir = tmp_path / run_id
        task_id = "repo__task-001"

        logger = TrajectoryLogger(
            run_id=run_id,
            task_id=task_id,
            policy="no_memory",
            seed=1,
            run_dir=run_dir,
        )
        logger.log_step(
            step=1,
            action="read_file",
            action_input={"path": "bigfile.py", "start_line": 250, "end_line": 260},
            observation_summary="250\tline_0250_pad...",
        )
        saved = logger.save()

        expected = run_dir / "trajectories" / f"{task_id}.json"
        assert saved == expected
        assert expected.exists()
        assert not (tmp_path / "runs").exists()

    def test_task_row_under_run_dir(self, tmp_path, monkeypatch):
        """TaskResultLogger must write task_results.jsonl under the injected run_dir."""
        monkeypatch.chdir(tmp_path)
        from src.logging.task_logger import TaskResult, TaskResultLogger

        run_id = "test-run"
        run_dir = tmp_path / run_id

        # TaskResultLogger takes run_dir; creates it and writes task_results.jsonl inside
        task_logger = TaskResultLogger(run_dir)
        task_result = TaskResult(
            run_id=run_id,
            policy="no_memory",
            seed=1,
            repo="test/repo",
            task_id="test__task-001",
            sequence_index=0,
            resolved=0,
            patch_generated=False,
            patch_applied=False,
            syntax_error=False,
            timeout=False,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            estimated_cost_usd=0.0,
            task_api_cost=0.0,
            consolidation_llm_cost=0.0,
            wall_time_seconds=1.5,
            tool_calls=3,
            test_runs=0,
            files_read=1,
            files_modified=0,
            syntax_error_rate=0.0,
            retrieved_memory_ids=[],
            retrieved_memory_scores=[],
            retrieved_memory_types=[],
            retrieved_memory_ages=[],
            memory_count_before=0,
            memory_count_after=0,
            memory_tokens_before=0,
            memory_tokens_after=0,
        )
        task_logger.log_task_result(task_result)

        log_path = run_dir / "task_results.jsonl"
        assert log_path.exists()
        rows = [json.loads(line) for line in log_path.read_text().strip().splitlines()]
        assert len(rows) == 1
        assert rows[0]["task_id"] == "test__task-001"
        assert not (tmp_path / "runs").exists()

    def test_all_four_artifacts_under_single_run_dir(self, tmp_path, monkeypatch):
        """End-to-end: all four artifact types land under the same run_dir."""
        monkeypatch.chdir(tmp_path)
        from src.logging.task_logger import TaskResult, TaskResultLogger
        from src.logging.trajectory_logger import TrajectoryLogger

        run_id = "run-e2e"
        run_dir = tmp_path / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # 1. MemoryStore (memory.db + faiss + snapshots)
        store = _make_patched_memory_store(run_dir, run_id)

        # 2. TrajectoryLogger
        traj_logger = TrajectoryLogger(
            run_id=run_id,
            task_id="repo__task-e2e",
            policy="no_memory",
            seed=1,
            run_dir=run_dir,
        )
        traj_logger.log_step(
            step=1, action="read_file",
            action_input={"path": "bigfile.py"},
            observation_summary="# bigfile.py (lines 1-200 of 500...)",
        )
        traj_path = traj_logger.save()

        # 3. TaskResultLogger
        task_logger = TaskResultLogger(run_dir)
        task_result = TaskResult(
            run_id=run_id, policy="no_memory", seed=1,
            repo="test/repo", task_id="repo__task-e2e", sequence_index=0,
            resolved=0, patch_generated=False, patch_applied=False,
            syntax_error=False, timeout=False,
            prompt_tokens=0, completion_tokens=0, total_tokens=0,
            estimated_cost_usd=0.0, task_api_cost=0.0, consolidation_llm_cost=0.0,
            wall_time_seconds=0.5, tool_calls=1, test_runs=0, files_read=1,
            files_modified=0, syntax_error_rate=0.0,
            retrieved_memory_ids=[], retrieved_memory_scores=[],
            retrieved_memory_types=[], retrieved_memory_ages=[],
            memory_count_before=0, memory_count_after=0,
            memory_tokens_before=0, memory_tokens_after=0,
        )
        task_logger.log_task_result(task_result)
        log_path = run_dir / "task_results.jsonl"

        # Assert all artifacts are under run_dir
        assert store.db_path.parent.parent == run_dir
        assert store.faiss_path.parent.parent == run_dir
        assert store.snapshot_dir.parent.parent == run_dir
        assert traj_path.parent.parent == run_dir
        assert log_path.parent == run_dir

        # The critical invariant: no ./runs/ was created
        assert not (tmp_path / "runs").exists(), (
            "'./runs/' must not exist when run_dir is injected"
        )
