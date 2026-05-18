"""Unit tests for benchmark data models (Task and Sequence).

Tests validation logic for Task and Sequence dataclasses, including:
- Required field validation
- Minimum 15 tasks per sequence requirement
- Chronological ordering preservation
- Repository consistency
"""

import pytest

from src.benchmark.models import Sequence, Task


class TestTask:
    """Test suite for Task dataclass."""

    def test_valid_task_creation(self):
        """Test creating a valid task with all required fields."""
        task = Task(
            task_id="django__django-12345",
            repo="django/django",
            base_commit="abc123def456",
            issue_text="Fix QuerySet.exclude() bug",
            test_patch="diff --git a/tests/...",
            gold_patch="diff --git a/django/...",
            created_at="2023-01-15T10:30:00Z",
            sequence_index=0,
            difficulty_label="medium"
        )

        assert task.task_id == "django__django-12345"
        assert task.repo == "django/django"
        assert task.sequence_index == 0
        assert task.difficulty_label == "medium"

    def test_task_empty_task_id_raises_error(self):
        """Test that empty task_id raises ValueError."""
        with pytest.raises(ValueError, match="task_id cannot be empty"):
            Task(
                task_id="",
                repo="django/django",
                base_commit="abc123",
                issue_text="Issue",
                test_patch="patch",
                gold_patch="patch",
                created_at="2023-01-15T10:30:00Z",
                sequence_index=0,
                difficulty_label="easy"
            )

    def test_task_empty_repo_raises_error(self):
        """Test that empty repo raises ValueError."""
        with pytest.raises(ValueError, match="repo cannot be empty"):
            Task(
                task_id="task-1",
                repo="",
                base_commit="abc123",
                issue_text="Issue",
                test_patch="patch",
                gold_patch="patch",
                created_at="2023-01-15T10:30:00Z",
                sequence_index=0,
                difficulty_label="easy"
            )

    def test_task_empty_base_commit_raises_error(self):
        """Test that empty base_commit raises ValueError."""
        with pytest.raises(ValueError, match="base_commit cannot be empty"):
            Task(
                task_id="task-1",
                repo="django/django",
                base_commit="",
                issue_text="Issue",
                test_patch="patch",
                gold_patch="patch",
                created_at="2023-01-15T10:30:00Z",
                sequence_index=0,
                difficulty_label="easy"
            )

    def test_task_negative_sequence_index_raises_error(self):
        """Test that negative sequence_index raises ValueError."""
        with pytest.raises(ValueError, match="sequence_index must be non-negative"):
            Task(
                task_id="task-1",
                repo="django/django",
                base_commit="abc123",
                issue_text="Issue",
                test_patch="patch",
                gold_patch="patch",
                created_at="2023-01-15T10:30:00Z",
                sequence_index=-1,
                difficulty_label="easy"
            )

    def test_task_invalid_difficulty_label_raises_error(self):
        """Test that invalid difficulty_label raises ValueError."""
        with pytest.raises(ValueError, match="difficulty_label must be"):
            Task(
                task_id="task-1",
                repo="django/django",
                base_commit="abc123",
                issue_text="Issue",
                test_patch="patch",
                gold_patch="patch",
                created_at="2023-01-15T10:30:00Z",
                sequence_index=0,
                difficulty_label="invalid"
            )

    def test_task_all_difficulty_labels_valid(self):
        """Test that all three difficulty labels are accepted."""
        for difficulty in ["easy", "medium", "hard"]:
            task = Task(
                task_id="task-1",
                repo="django/django",
                base_commit="abc123",
                issue_text="Issue",
                test_patch="patch",
                gold_patch="patch",
                created_at="2023-01-15T10:30:00Z",
                sequence_index=0,
                difficulty_label=difficulty
            )
            assert task.difficulty_label == difficulty


class TestSequence:
    """Test suite for Sequence dataclass."""

    def _create_tasks(self, count: int, repo: str = "django/django") -> list[Task]:
        """Helper to create a list of valid tasks."""
        return [
            Task(
                task_id=f"task-{i}",
                repo=repo,
                base_commit=f"commit-{i}",
                issue_text=f"Issue {i}",
                test_patch=f"test patch {i}",
                gold_patch=f"gold patch {i}",
                created_at=f"2023-01-{i+1:02d}T10:00:00Z",
                sequence_index=i,
                difficulty_label="medium"
            )
            for i in range(count)
        ]

    def test_valid_sequence_creation(self):
        """Test creating a valid sequence with 15 tasks."""
        tasks = self._create_tasks(15)
        sequence = Sequence(
            sequence_name="django",
            repo="django/django",
            tasks=tasks,
            task_count=15
        )

        assert sequence.sequence_name == "django"
        assert sequence.repo == "django/django"
        assert len(sequence.tasks) == 15
        assert sequence.task_count == 15

    def test_sequence_minimum_15_tasks_requirement(self):
        """Test that sequences with fewer than 15 tasks raise ValueError.

        This enforces Requirement 1: "THE System SHALL validate that each
        sequence contains at least 15 tasks"
        """
        tasks = self._create_tasks(14)  # One less than minimum

        with pytest.raises(ValueError, match="must contain at least 15 tasks"):
            Sequence(
                sequence_name="django",
                repo="django/django",
                tasks=tasks,
                task_count=14
            )

    def test_sequence_exactly_15_tasks_valid(self):
        """Test that exactly 15 tasks is valid (boundary condition)."""
        tasks = self._create_tasks(15)
        sequence = Sequence(
            sequence_name="django",
            repo="django/django",
            tasks=tasks,
            task_count=15
        )
        assert len(sequence.tasks) == 15

    def test_sequence_more_than_15_tasks_valid(self):
        """Test that more than 15 tasks is valid."""
        tasks = self._create_tasks(20)
        sequence = Sequence(
            sequence_name="django",
            repo="django/django",
            tasks=tasks,
            task_count=20
        )
        assert len(sequence.tasks) == 20

    def test_sequence_empty_name_raises_error(self):
        """Test that empty sequence_name raises ValueError."""
        tasks = self._create_tasks(15)

        with pytest.raises(ValueError, match="sequence_name cannot be empty"):
            Sequence(
                sequence_name="",
                repo="django/django",
                tasks=tasks,
                task_count=15
            )

    def test_sequence_empty_repo_raises_error(self):
        """Test that empty repo raises ValueError."""
        tasks = self._create_tasks(15)

        with pytest.raises(ValueError, match="repo cannot be empty"):
            Sequence(
                sequence_name="django",
                repo="",
                tasks=tasks,
                task_count=15
            )

    def test_sequence_empty_tasks_raises_error(self):
        """Test that empty tasks list raises ValueError."""
        with pytest.raises(ValueError, match="tasks list cannot be empty"):
            Sequence(
                sequence_name="django",
                repo="django/django",
                tasks=[],
                task_count=0
            )

    def test_sequence_task_count_mismatch_raises_error(self):
        """Test that mismatched task_count raises ValueError."""
        tasks = self._create_tasks(15)

        with pytest.raises(ValueError, match="task_count.*does not match"):
            Sequence(
                sequence_name="django",
                repo="django/django",
                tasks=tasks,
                task_count=20  # Wrong count
            )

    def test_sequence_validates_all_tasks_same_repo(self):
        """Test that all tasks must belong to the same repository."""
        tasks = self._create_tasks(15)
        # Change one task's repo
        tasks[5] = Task(
            task_id="task-5",
            repo="flask/flask",  # Different repo
            base_commit="commit-5",
            issue_text="Issue 5",
            test_patch="test patch 5",
            gold_patch="gold patch 5",
            created_at="2023-01-06T10:00:00Z",
            sequence_index=5,
            difficulty_label="medium"
        )

        with pytest.raises(ValueError, match="has repo.*but sequence expects"):
            Sequence(
                sequence_name="django",
                repo="django/django",
                tasks=tasks,
                task_count=15
            )

    def test_sequence_validates_chronological_ordering(self):
        """Test that sequence_index must be chronologically ordered.

        This enforces Requirement 1: "THE System SHALL preserve the original
        chronological ordering of tasks within each sequence"
        """
        tasks = self._create_tasks(15)
        # Break chronological ordering
        tasks[5] = Task(
            task_id="task-5",
            repo="django/django",
            base_commit="commit-5",
            issue_text="Issue 5",
            test_patch="test patch 5",
            gold_patch="gold patch 5",
            created_at="2023-01-06T10:00:00Z",
            sequence_index=10,  # Wrong index (should be 5)
            difficulty_label="medium"
        )

        with pytest.raises(ValueError, match="expected.*for chronological ordering"):
            Sequence(
                sequence_name="django",
                repo="django/django",
                tasks=tasks,
                task_count=15
            )

    def test_sequence_preserves_task_order(self):
        """Test that task order is preserved in the sequence."""
        tasks = self._create_tasks(20)
        sequence = Sequence(
            sequence_name="django",
            repo="django/django",
            tasks=tasks,
            task_count=20
        )

        # Verify order is preserved
        for i, task in enumerate(sequence.tasks):
            assert task.sequence_index == i
            assert task.task_id == f"task-{i}"
