"""
Unit tests for trajectory logger.

Tests the trajectory logging functionality as specified in THESIS_FINAL_v5.md §11.3.

Key requirements tested:
- Trajectory JSON file per task with action-observation pairs
- Fields: step, action, action_input, observation_summary, timestamp
- No private chain-of-thought (action summaries only)
- Storage: runs/{run_id}/trajectories/{task_id}.json
- Accumulate in memory, write once at end
- JSON format (single array, not JSON Lines)
"""

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.logging.trajectory_logger import (
    TrajectoryLogger,
    TrajectoryStep,
    load_trajectory,
)


class TestTrajectoryStep:
    """Test TrajectoryStep dataclass."""

    def test_trajectory_step_creation(self):
        """Test creating a trajectory step with all fields."""
        step = TrajectoryStep(
            step=1,
            action="search_code",
            action_input="QuerySet.exclude",
            observation_summary="Found in django/db/models/query.py:823",
            timestamp="2026-05-17T10:23:01Z",
        )

        assert step.step == 1
        assert step.action == "search_code"
        assert step.action_input == "QuerySet.exclude"
        assert step.observation_summary == "Found in django/db/models/query.py:823"
        assert step.timestamp == "2026-05-17T10:23:01Z"

    def test_trajectory_step_auto_timestamp(self):
        """Test that timestamp is auto-generated if not provided."""
        before = datetime.now(UTC)
        step = TrajectoryStep(
            step=1,
            action="search_code",
            action_input="QuerySet.exclude",
            observation_summary="Found in django/db/models/query.py:823",
        )
        after = datetime.now(UTC)

        # Parse timestamp and verify it's between before and after
        timestamp = datetime.fromisoformat(step.timestamp.replace("Z", "+00:00"))
        assert before <= timestamp <= after

    def test_trajectory_step_to_dict(self):
        """Test converting step to dictionary."""
        step = TrajectoryStep(
            step=1,
            action="search_code",
            action_input="QuerySet.exclude",
            observation_summary="Found in django/db/models/query.py:823",
            timestamp="2026-05-17T10:23:01Z",
        )

        step_dict = step.to_dict()

        assert step_dict == {
            "step": 1,
            "action": "search_code",
            "action_input": "QuerySet.exclude",
            "observation_summary": "Found in django/db/models/query.py:823",
            "timestamp": "2026-05-17T10:23:01Z",
        }

    def test_trajectory_step_dict_action_input(self):
        """Test step with dict action_input."""
        step = TrajectoryStep(
            step=1,
            action="edit_file",
            action_input={"file": "models.py", "line": 42},
            observation_summary="File edited successfully",
            timestamp="2026-05-17T10:23:01Z",
        )

        step_dict = step.to_dict()

        assert step_dict["action_input"] == {"file": "models.py", "line": 42}


class TestTrajectoryLogger:
    """Test TrajectoryLogger class."""

    def test_logger_initialization(self):
        """Test creating a trajectory logger."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = TrajectoryLogger(
                run_id="run_001",
                task_id="django__django-12345",
                policy="type_aware_decay",
                seed=2,
                base_dir=tmpdir,
            )

            assert logger.run_id == "run_001"
            assert logger.task_id == "django__django-12345"
            assert logger.policy == "type_aware_decay"
            assert logger.seed == 2
            assert logger.get_step_count() == 0
            assert not logger._saved

    def test_log_single_step(self):
        """Test logging a single step."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = TrajectoryLogger(
                run_id="run_001",
                task_id="django__django-12345",
                policy="type_aware_decay",
                seed=2,
                base_dir=tmpdir,
            )

            logger.log_step(
                step=1,
                action="search_code",
                action_input="QuerySet.exclude",
                observation_summary="Found in django/db/models/query.py:823",
            )

            assert logger.get_step_count() == 1
            assert logger.steps[0].step == 1
            assert logger.steps[0].action == "search_code"
            assert logger.steps[0].action_input == "QuerySet.exclude"
            assert logger.steps[0].observation_summary == "Found in django/db/models/query.py:823"

    def test_log_multiple_steps(self):
        """Test logging multiple steps."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = TrajectoryLogger(
                run_id="run_001",
                task_id="django__django-12345",
                policy="type_aware_decay",
                seed=2,
                base_dir=tmpdir,
            )

            logger.log_step(
                step=1,
                action="search_code",
                action_input="QuerySet.exclude",
                observation_summary="Found in django/db/models/query.py:823",
            )

            logger.log_step(
                step=2,
                action="read_file",
                action_input="django/db/models/query.py",
                observation_summary="File content retrieved",
            )

            logger.log_step(
                step=3,
                action="edit_file",
                action_input={"file": "query.py", "line": 823},
                observation_summary="File edited successfully",
            )

            assert logger.get_step_count() == 3
            assert logger.steps[0].step == 1
            assert logger.steps[1].step == 2
            assert logger.steps[2].step == 3

    def test_save_trajectory(self):
        """Test saving trajectory to JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = TrajectoryLogger(
                run_id="run_001",
                task_id="django__django-12345",
                policy="type_aware_decay",
                seed=2,
                base_dir=tmpdir,
            )

            logger.log_step(
                step=1,
                action="search_code",
                action_input="QuerySet.exclude",
                observation_summary="Found in django/db/models/query.py:823",
                timestamp="2026-05-17T10:23:01Z",
            )

            logger.log_step(
                step=2,
                action="read_file",
                action_input="django/db/models/query.py",
                observation_summary="File content retrieved",
                timestamp="2026-05-17T10:23:05Z",
            )

            # Save trajectory
            output_path = logger.save()

            # Verify file exists
            assert output_path.exists()
            assert output_path == Path(tmpdir) / "run_001" / "trajectories" / "django__django-12345.json"

            # Verify file content
            with open(output_path, encoding="utf-8") as f:
                trajectory = json.load(f)

            assert trajectory["task_id"] == "django__django-12345"
            assert trajectory["policy"] == "type_aware_decay"
            assert trajectory["seed"] == 2
            assert len(trajectory["steps"]) == 2

            assert trajectory["steps"][0]["step"] == 1
            assert trajectory["steps"][0]["action"] == "search_code"
            assert trajectory["steps"][0]["action_input"] == "QuerySet.exclude"
            assert trajectory["steps"][0]["observation_summary"] == "Found in django/db/models/query.py:823"
            assert trajectory["steps"][0]["timestamp"] == "2026-05-17T10:23:01Z"

            assert trajectory["steps"][1]["step"] == 2
            assert trajectory["steps"][1]["action"] == "read_file"

    def test_save_creates_directory(self):
        """Test that save() creates the trajectories directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = TrajectoryLogger(
                run_id="run_001",
                task_id="django__django-12345",
                policy="type_aware_decay",
                seed=2,
                base_dir=tmpdir,
            )

            logger.log_step(
                step=1,
                action="search_code",
                action_input="QuerySet.exclude",
                observation_summary="Found in django/db/models/query.py:823",
            )

            # Directory should not exist yet
            trajectories_dir = Path(tmpdir) / "run_001" / "trajectories"
            assert not trajectories_dir.exists()

            # Save should create it
            logger.save()
            assert trajectories_dir.exists()
            assert trajectories_dir.is_dir()

    def test_save_empty_trajectory(self):
        """Test saving trajectory with no steps."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = TrajectoryLogger(
                run_id="run_001",
                task_id="django__django-12345",
                policy="type_aware_decay",
                seed=2,
                base_dir=tmpdir,
            )

            # Save without logging any steps
            output_path = logger.save()

            # Verify file exists and has empty steps array
            with open(output_path, encoding="utf-8") as f:
                trajectory = json.load(f)

            assert trajectory["task_id"] == "django__django-12345"
            assert trajectory["steps"] == []

    def test_cannot_log_after_save(self):
        """Test that logging after save raises an error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = TrajectoryLogger(
                run_id="run_001",
                task_id="django__django-12345",
                policy="type_aware_decay",
                seed=2,
                base_dir=tmpdir,
            )

            logger.log_step(
                step=1,
                action="search_code",
                action_input="QuerySet.exclude",
                observation_summary="Found in django/db/models/query.py:823",
            )

            logger.save()

            # Attempting to log after save should raise error
            with pytest.raises(RuntimeError, match="Cannot log step after trajectory has been saved"):
                logger.log_step(
                    step=2,
                    action="read_file",
                    action_input="query.py",
                    observation_summary="File content",
                )

    def test_cannot_save_twice(self):
        """Test that saving twice raises an error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = TrajectoryLogger(
                run_id="run_001",
                task_id="django__django-12345",
                policy="type_aware_decay",
                seed=2,
                base_dir=tmpdir,
            )

            logger.log_step(
                step=1,
                action="search_code",
                action_input="QuerySet.exclude",
                observation_summary="Found in django/db/models/query.py:823",
            )

            logger.save()

            # Attempting to save again should raise error
            with pytest.raises(RuntimeError, match="Trajectory already saved"):
                logger.save()

    def test_clear_resets_logger(self):
        """Test that clear() resets the logger state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = TrajectoryLogger(
                run_id="run_001",
                task_id="django__django-12345",
                policy="type_aware_decay",
                seed=2,
                base_dir=tmpdir,
            )

            logger.log_step(
                step=1,
                action="search_code",
                action_input="QuerySet.exclude",
                observation_summary="Found in django/db/models/query.py:823",
            )

            assert logger.get_step_count() == 1

            logger.clear()

            assert logger.get_step_count() == 0
            assert not logger._saved

            # Should be able to log again after clear
            logger.log_step(
                step=1,
                action="read_file",
                action_input="query.py",
                observation_summary="File content",
            )

            assert logger.get_step_count() == 1

    def test_trajectory_no_private_thoughts(self):
        """
        Test that trajectory contains only action summaries, not private reasoning.

        This is a critical requirement from THESIS_FINAL_v5.md §11.3:
        "Do not store private model chain-of-thought. Only action summaries and observations."

        The test verifies that:
        1. Only action names are logged (e.g., "search_code", not "I think I should search")
        2. Only observation summaries are logged (e.g., "Found in file.py", not "This means...")
        3. No reasoning or planning fields exist in the schema
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = TrajectoryLogger(
                run_id="run_001",
                task_id="django__django-12345",
                policy="type_aware_decay",
                seed=2,
                base_dir=tmpdir,
            )

            # Log steps with only action summaries and observations
            logger.log_step(
                step=1,
                action="search_code",  # WHAT the agent did
                action_input="QuerySet.exclude",  # WHAT arguments
                observation_summary="Found in django/db/models/query.py:823",  # WHAT it observed
            )

            output_path = logger.save()

            # Load and verify schema
            with open(output_path, encoding="utf-8") as f:
                trajectory = json.load(f)

            # Verify only allowed fields exist
            allowed_top_level = {"task_id", "policy", "seed", "steps"}
            assert set(trajectory.keys()) == allowed_top_level

            # Verify step schema has no reasoning fields
            allowed_step_fields = {"step", "action", "action_input", "observation_summary", "timestamp"}
            for step in trajectory["steps"]:
                assert set(step.keys()) == allowed_step_fields

                # Verify no reasoning-related content
                forbidden_keywords = ["think", "reason", "plan", "decide", "because", "should"]
                for keyword in forbidden_keywords:
                    # Action should be a simple tool name, not a sentence
                    assert keyword not in step["action"].lower()


class TestLoadTrajectory:
    """Test load_trajectory function."""

    def test_load_trajectory(self):
        """Test loading a trajectory from file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create and save a trajectory
            logger = TrajectoryLogger(
                run_id="run_001",
                task_id="django__django-12345",
                policy="type_aware_decay",
                seed=2,
                base_dir=tmpdir,
            )

            logger.log_step(
                step=1,
                action="search_code",
                action_input="QuerySet.exclude",
                observation_summary="Found in django/db/models/query.py:823",
                timestamp="2026-05-17T10:23:01Z",
            )

            output_path = logger.save()

            # Load trajectory
            trajectory = load_trajectory(output_path)

            assert trajectory["task_id"] == "django__django-12345"
            assert trajectory["policy"] == "type_aware_decay"
            assert trajectory["seed"] == 2
            assert len(trajectory["steps"]) == 1
            assert trajectory["steps"][0]["step"] == 1
            assert trajectory["steps"][0]["action"] == "search_code"

    def test_load_nonexistent_trajectory(self):
        """Test loading a trajectory that doesn't exist."""
        with pytest.raises(FileNotFoundError):
            load_trajectory("/nonexistent/path/trajectory.json")

    def test_load_invalid_json(self):
        """Test loading a file with invalid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            invalid_file = Path(tmpdir) / "invalid.json"
            invalid_file.write_text("not valid json{")

            with pytest.raises(json.JSONDecodeError):
                load_trajectory(invalid_file)


class TestTrajectoryIntegration:
    """Integration tests for trajectory logging."""

    def test_complete_task_trajectory(self):
        """Test logging a complete task trajectory with multiple steps."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = TrajectoryLogger(
                run_id="run_001",
                task_id="django__django-12345",
                policy="type_aware_decay",
                seed=2,
                base_dir=tmpdir,
            )

            # Simulate a complete task execution
            logger.log_step(
                step=1,
                action="search_code",
                action_input="QuerySet.exclude",
                observation_summary="Found in django/db/models/query.py:823",
            )

            logger.log_step(
                step=2,
                action="read_file",
                action_input="django/db/models/query.py",
                observation_summary="File content retrieved, 1500 lines",
            )

            logger.log_step(
                step=3,
                action="edit_file",
                action_input={"file": "query.py", "start_line": 823, "end_line": 830},
                observation_summary="Modified exclude() method implementation",
            )

            logger.log_step(
                step=4,
                action="run_tests",
                action_input="tests/queries/test_exclude.py",
                observation_summary="3 tests passed, 1 test failed",
            )

            logger.log_step(
                step=5,
                action="edit_file",
                action_input={"file": "query.py", "line": 825},
                observation_summary="Fixed edge case handling",
            )

            logger.log_step(
                step=6,
                action="run_tests",
                action_input="tests/queries/test_exclude.py",
                observation_summary="All 4 tests passed",
            )

            # Save trajectory
            output_path = logger.save()

            # Verify complete trajectory
            trajectory = load_trajectory(output_path)

            assert len(trajectory["steps"]) == 6
            assert trajectory["steps"][0]["action"] == "search_code"
            assert trajectory["steps"][1]["action"] == "read_file"
            assert trajectory["steps"][2]["action"] == "edit_file"
            assert trajectory["steps"][3]["action"] == "run_tests"
            assert trajectory["steps"][4]["action"] == "edit_file"
            assert trajectory["steps"][5]["action"] == "run_tests"

            # Verify all steps have required fields
            for step in trajectory["steps"]:
                assert "step" in step
                assert "action" in step
                assert "action_input" in step
                assert "observation_summary" in step
                assert "timestamp" in step

    def test_multiple_tasks_same_run(self):
        """Test logging trajectories for multiple tasks in the same run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Task 1
            logger1 = TrajectoryLogger(
                run_id="run_001",
                task_id="django__django-12345",
                policy="type_aware_decay",
                seed=2,
                base_dir=tmpdir,
            )

            logger1.log_step(
                step=1,
                action="search_code",
                action_input="QuerySet.exclude",
                observation_summary="Found in query.py",
            )

            path1 = logger1.save()

            # Task 2
            logger2 = TrajectoryLogger(
                run_id="run_001",
                task_id="django__django-67890",
                policy="type_aware_decay",
                seed=2,
                base_dir=tmpdir,
            )

            logger2.log_step(
                step=1,
                action="search_code",
                action_input="Model.save",
                observation_summary="Found in models.py",
            )

            path2 = logger2.save()

            # Verify both files exist
            assert path1.exists()
            assert path2.exists()
            assert path1 != path2

            # Verify both are in the same run directory
            assert path1.parent == path2.parent
            assert path1.parent == Path(tmpdir) / "run_001" / "trajectories"

            # Verify content is different
            traj1 = load_trajectory(path1)
            traj2 = load_trajectory(path2)

            assert traj1["task_id"] == "django__django-12345"
            assert traj2["task_id"] == "django__django-67890"
            assert traj1["steps"][0]["action_input"] == "QuerySet.exclude"
            assert traj2["steps"][0]["action_input"] == "Model.save"
