"""Data models for SWE-Bench-CL tasks and sequences.

This module defines the core data structures for representing tasks and sequences
from the SWE-Bench-CL benchmark dataset.
"""

from dataclasses import dataclass


@dataclass
class Task:
    """Represents a single coding task from SWE-Bench-CL.

    A task corresponds to a GitHub issue resolution problem with associated
    test patches and reference solutions.

    Attributes:
        task_id: Unique identifier (e.g., "django__django-12345")
        repo: Repository name (e.g., "django/django")
        base_commit: Git commit hash for the base state
        issue_text: GitHub issue description
        test_patch: Test file changes to validate the solution
        gold_patch: Reference solution patch
        created_at: ISO timestamp of issue creation
        sequence_index: Position in the sequence (0-indexed)
        difficulty_label: Task difficulty ("easy", "medium", or "hard")
    """

    task_id: str
    repo: str
    base_commit: str
    issue_text: str
    test_patch: str
    gold_patch: str
    created_at: str
    sequence_index: int
    difficulty_label: str

    def __post_init__(self) -> None:
        """Validate task fields after initialization."""
        if not self.task_id:
            raise ValueError("task_id cannot be empty")
        if not self.repo:
            raise ValueError("repo cannot be empty")
        if not self.base_commit:
            raise ValueError("base_commit cannot be empty")
        if self.sequence_index < 0:
            raise ValueError(f"sequence_index must be non-negative, got {self.sequence_index}")
        if self.difficulty_label not in ("easy", "medium", "hard"):
            raise ValueError(
                f"difficulty_label must be 'easy', 'medium', or 'hard', got '{self.difficulty_label}'"
            )


@dataclass
class Sequence:
    """Represents an ordered sequence of coding tasks from a single repository.

    A sequence contains chronologically ordered tasks from the same repository,
    forming a continual learning curriculum.

    Attributes:
        sequence_name: Name of the sequence (e.g., "django")
        repo: Repository name (e.g., "django/django")
        tasks: Ordered list of tasks (chronologically sorted)
        task_count: Number of tasks in the sequence
    """

    sequence_name: str
    repo: str
    tasks: list[Task]
    task_count: int

    def __post_init__(self) -> None:
        """Validate sequence fields after initialization.

        Enforces the minimum 15 tasks per sequence requirement from
        THESIS_FINAL_v5.md frozen decision #1.
        """
        if not self.sequence_name:
            raise ValueError("sequence_name cannot be empty")
        if not self.repo:
            raise ValueError("repo cannot be empty")
        if not self.tasks:
            raise ValueError("tasks list cannot be empty")

        # Requirement 1: Validate minimum 15 tasks per sequence
        if len(self.tasks) < 15:
            raise ValueError(
                f"Sequence '{self.sequence_name}' must contain at least 15 tasks, "
                f"got {len(self.tasks)}"
            )

        # Validate task_count matches actual task list length
        if self.task_count != len(self.tasks):
            raise ValueError(
                f"task_count ({self.task_count}) does not match actual tasks length ({len(self.tasks)})"
            )

        # Validate all tasks belong to the same repository
        for task in self.tasks:
            if task.repo != self.repo:
                raise ValueError(
                    f"Task {task.task_id} has repo '{task.repo}' but sequence expects '{self.repo}'"
                )

        # Validate chronological ordering by sequence_index
        for i, task in enumerate(self.tasks):
            if task.sequence_index != i:
                raise ValueError(
                    f"Task at position {i} has sequence_index {task.sequence_index}, "
                    f"expected {i} for chronological ordering"
                )
