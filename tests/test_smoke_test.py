"""Unit tests for smoke test functionality.

Tests for Task 19.2: Implement smoke test
"""

import json

import pytest

from src.benchmark.models import Sequence, Task
from src.benchmark.smoke_test import (
    SmokeTestResult,
    create_smoke_test_sequence,
    verify_docker_invocation,
    verify_logging_schemas,
)


class TestSmokeTestResult:
    """Tests for SmokeTestResult class."""

    def test_smoke_test_result_initialization(self):
        """Test that SmokeTestResult initializes with correct defaults."""
        result = SmokeTestResult()

        assert result.total_tasks == 0
        assert result.completed_tasks == 0
        assert result.resolved_tasks == 0
        assert result.pass_rate == 0.0
        assert result.docker_invoked is False
        assert result.logging_valid is False
        assert result.errors == []
        assert result.success is False

    def test_smoke_test_result_to_dict(self):
        """Test that SmokeTestResult converts to dictionary correctly."""
        result = SmokeTestResult()
        result.total_tasks = 3
        result.completed_tasks = 3
        result.resolved_tasks = 2
        result.pass_rate = 66.7
        result.docker_invoked = True
        result.logging_valid = True
        result.errors = ["test error"]
        result.success = True

        result_dict = result.to_dict()

        assert result_dict["total_tasks"] == 3
        assert result_dict["completed_tasks"] == 3
        assert result_dict["resolved_tasks"] == 2
        assert result_dict["pass_rate"] == 66.7
        assert result_dict["docker_invoked"] is True
        assert result_dict["logging_valid"] is True
        assert result_dict["errors"] == ["test error"]
        assert result_dict["success"] is True


class TestCreateSmokeTestSequence:
    """Tests for create_smoke_test_sequence function."""

    def test_create_smoke_test_sequence_with_3_tasks(self):
        """Test creating smoke test task list with first 3 tasks."""
        # Create full sequence with 15 tasks (minimum required)
        tasks = []
        for i in range(15):
            task = Task(
                task_id=f"test-{i}",
                repo="test/repo",
                base_commit="abc123",
                issue_text=f"Issue {i}",
                test_patch="",
                gold_patch="",
                created_at="2024-01-01T00:00:00Z",
                sequence_index=i,
                difficulty_label="easy",
            )
            tasks.append(task)

        full_sequence = Sequence(
            sequence_name="test_sequence",
            repo="test/repo",
            tasks=tasks,
            task_count=15,
        )

        # Create smoke test task list
        smoke_tasks = create_smoke_test_sequence(full_sequence, num_tasks=3)

        # Verify smoke tasks has only first 3 tasks
        assert len(smoke_tasks) == 3

        # Verify tasks are the first 3
        for i in range(3):
            assert smoke_tasks[i].task_id == f"test-{i}"
            assert smoke_tasks[i].sequence_index == i

    def test_create_smoke_test_sequence_insufficient_tasks(self):
        """Test that creating smoke test fails with insufficient tasks."""
        # Create sequence with only 15 tasks (minimum)
        tasks = []
        for i in range(15):
            task = Task(
                task_id=f"test-{i}",
                repo="test/repo",
                base_commit="abc123",
                issue_text=f"Issue {i}",
                test_patch="",
                gold_patch="",
                created_at="2024-01-01T00:00:00Z",
                sequence_index=i,
                difficulty_label="easy",
            )
            tasks.append(task)

        full_sequence = Sequence(
            sequence_name="test_sequence",
            repo="test/repo",
            tasks=tasks,
            task_count=15,
        )

        # Should raise ValueError when requesting more tasks than available
        with pytest.raises(ValueError, match="has only 15 tasks, need at least 20"):
            create_smoke_test_sequence(full_sequence, num_tasks=20)


class TestVerifyLoggingSchemas:
    """Tests for verify_logging_schemas function."""

    def test_verify_logging_schemas_all_valid(self, tmp_path):
        """Test that verify_logging_schemas passes with valid schemas."""
        # Create run directory structure
        run_dir = tmp_path / "test_run"
        run_dir.mkdir()

        # Create valid task_results.jsonl
        task_results_path = run_dir / "task_results.jsonl"
        task_result = {
            "run_id": "test_run",
            "policy": "no_memory",
            "seed": 42,
            "repo": "test/repo",
            "task_id": "test-1",
            "sequence_index": 0,
            "resolved": 1,
            "patch_generated": True,
            "patch_applied": True,
            "syntax_error": False,
            "timeout": False,
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "estimated_cost_usd": 0.01,
            "wall_time_seconds": 10.0,
            "tool_calls": 5,
            "test_runs": 1,
            "files_read": 2,
            "files_modified": 1,
            "syntax_error_rate": 0.0,
            "retrieved_memory_ids": [],
            "retrieved_memory_scores": [],
            "retrieved_memory_types": [],
            "retrieved_memory_ages": [],
            "memory_count_before": 0,
            "memory_count_after": 0,
            "memory_tokens_before": 0,
            "memory_tokens_after": 0,
            "task_difficulty": "easy",
            "error_message": None,
        }
        with open(task_results_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(task_result) + "\n")

        # Create valid memory_events.jsonl (can be empty)
        memory_events_path = run_dir / "memory_events.jsonl"
        memory_events_path.touch()

        # Create valid memory snapshots
        snapshots_dir = run_dir / "memory" / "snapshots"
        snapshots_dir.mkdir(parents=True)

        snapshot = {
            "step": 0,
            "boundary": "before_task",
            "active_records": [],
            "run_id": "test_run",
            "policy_name": "no_memory",
            "timestamp": "2024-01-01T00:00:00Z",
        }
        snapshot_path = snapshots_dir / "before_task_0.json"
        with open(snapshot_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f)

        # Verify schemas
        valid, errors = verify_logging_schemas(run_dir)

        assert valid is True
        assert len(errors) == 0

    def test_verify_logging_schemas_missing_task_results(self, tmp_path):
        """Test that verify_logging_schemas fails when task_results.jsonl is missing."""
        run_dir = tmp_path / "test_run"
        run_dir.mkdir()

        # Create other files but not task_results.jsonl
        memory_events_path = run_dir / "memory_events.jsonl"
        memory_events_path.touch()

        snapshots_dir = run_dir / "memory" / "snapshots"
        snapshots_dir.mkdir(parents=True)

        # Verify schemas
        valid, errors = verify_logging_schemas(run_dir)

        assert valid is False
        assert any("task_results.jsonl not found" in error for error in errors)

    def test_verify_logging_schemas_missing_required_field(self, tmp_path):
        """Test that verify_logging_schemas fails when required field is missing."""
        run_dir = tmp_path / "test_run"
        run_dir.mkdir()

        # Create task_results.jsonl with missing field
        task_results_path = run_dir / "task_results.jsonl"
        task_result = {
            "run_id": "test_run",
            "policy": "no_memory",
            # Missing "seed" field
            "repo": "test/repo",
            "task_id": "test-1",
        }
        with open(task_results_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(task_result) + "\n")

        # Create other files
        memory_events_path = run_dir / "memory_events.jsonl"
        memory_events_path.touch()

        snapshots_dir = run_dir / "memory" / "snapshots"
        snapshots_dir.mkdir(parents=True)

        # Verify schemas
        valid, errors = verify_logging_schemas(run_dir)

        assert valid is False
        assert any("missing fields" in error for error in errors)

    def test_verify_logging_schemas_missing_snapshots(self, tmp_path):
        """Test that verify_logging_schemas fails when snapshots are missing."""
        run_dir = tmp_path / "test_run"
        run_dir.mkdir()

        # Create valid task_results.jsonl
        task_results_path = run_dir / "task_results.jsonl"
        task_result = {
            "run_id": "test_run",
            "policy": "no_memory",
            "seed": 42,
            "repo": "test/repo",
            "task_id": "test-1",
            "sequence_index": 0,
            "resolved": 1,
            "patch_generated": True,
            "patch_applied": True,
            "syntax_error": False,
            "timeout": False,
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "estimated_cost_usd": 0.01,
            "wall_time_seconds": 10.0,
            "tool_calls": 5,
            "test_runs": 1,
            "files_read": 2,
            "files_modified": 1,
            "syntax_error_rate": 0.0,
            "retrieved_memory_ids": [],
            "retrieved_memory_scores": [],
            "retrieved_memory_types": [],
            "retrieved_memory_ages": [],
            "memory_count_before": 0,
            "memory_count_after": 0,
            "memory_tokens_before": 0,
            "memory_tokens_after": 0,
            "task_difficulty": "easy",
            "error_message": None,
        }
        with open(task_results_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(task_result) + "\n")

        # Create memory_events.jsonl
        memory_events_path = run_dir / "memory_events.jsonl"
        memory_events_path.touch()

        # Don't create snapshots directory

        # Verify schemas
        valid, errors = verify_logging_schemas(run_dir)

        assert valid is False
        assert any("snapshots" in error for error in errors)


class TestVerifyDockerInvocation:
    """Tests for verify_docker_invocation function."""

    def test_verify_docker_invocation_success(self, tmp_path):
        """Test that verify_docker_invocation passes when Docker was invoked."""
        run_dir = tmp_path / "test_run"
        run_dir.mkdir()

        # Create task_results.jsonl with patch generated and evaluated
        task_results_path = run_dir / "task_results.jsonl"
        task_result = {
            "patch_generated": True,
            "resolved": 1,
        }
        with open(task_results_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(task_result) + "\n")

        # Verify Docker invocation
        invoked, errors = verify_docker_invocation(run_dir)

        assert invoked is True
        assert len(errors) == 0

    def test_verify_docker_invocation_no_patch(self, tmp_path):
        """Test that verify_docker_invocation fails when no patch was generated."""
        run_dir = tmp_path / "test_run"
        run_dir.mkdir()

        # Create task_results.jsonl with no patch generated
        task_results_path = run_dir / "task_results.jsonl"
        task_result = {
            "patch_generated": False,
            "resolved": 0,
        }
        with open(task_results_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(task_result) + "\n")

        # Verify Docker invocation
        invoked, errors = verify_docker_invocation(run_dir)

        assert invoked is False
        assert any("No evidence of Docker evaluation" in error for error in errors)

    def test_verify_docker_invocation_missing_file(self, tmp_path):
        """Test that verify_docker_invocation fails when task_results.jsonl is missing."""
        run_dir = tmp_path / "test_run"
        run_dir.mkdir()

        # Don't create task_results.jsonl

        # Verify Docker invocation
        invoked, errors = verify_docker_invocation(run_dir)

        assert invoked is False
        assert any("task_results.jsonl not found" in error for error in errors)
