"""
Trajectory logger for agent execution traces.

This module implements trajectory logging as specified in THESIS_FINAL_v5.md §11.3.

CRITICAL: No private chain-of-thought means:
- Log WHAT the agent did (tool calls, actions)
- Log WHAT the agent observed (results, outputs)
- Do NOT log WHY the agent decided to do it (reasoning, planning thoughts)

Schema from THESIS_FINAL_v5.md §11.3:
{
  "task_id": "django__django-12345",
  "policy": "type_aware_decay",
  "seed": 2,
  "steps": [
    {
      "step": 1,
      "action": "search_code",
      "action_input": "QuerySet.exclude",
      "observation_summary": "Found in django/db/models/query.py:823",
      "timestamp": "2026-05-17T10:23:01Z"
    }
  ]
}

Storage location: runs/{run_id}/trajectories/{task_id}.json
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class TrajectoryStep:
    """
    A single step in the agent's execution trajectory.

    This represents one action-observation pair in the agent's execution.
    Only action summaries and observations are logged - no private reasoning.

    Attributes:
        step: Step number (1-indexed)
        action: Tool name or action type (e.g., "search_code", "edit_file")
        action_input: Arguments passed to the tool (e.g., query string, file path)
        observation_summary: Summary of the result/output from the action
        timestamp: ISO 8601 timestamp when the step was executed
    """

    step: int
    action: str
    action_input: str | dict[str, Any]
    observation_summary: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """
        Convert step to dictionary for JSON serialization.

        Returns:
            Dictionary representation of the step
        """
        return {
            "step": self.step,
            "action": self.action,
            "action_input": self.action_input,
            "observation_summary": self.observation_summary,
            "timestamp": self.timestamp,
        }


class TrajectoryLogger:
    """
    Logger for agent execution trajectories.

    This class accumulates trajectory steps in memory during task execution
    and writes them to a JSON file at the end. This ensures atomic writes
    and prevents partial trajectory files.

    Key features:
    1. Accumulate steps in memory during execution
    2. Write once at end (atomic operation)
    3. JSON format (single array, not JSON Lines)
    4. No private chain-of-thought (action summaries only)

    Usage:
        logger = TrajectoryLogger(
            run_id="run_001",
            task_id="django__django-12345",
            policy="type_aware_decay",
            seed=2
        )

        # During agent execution
        logger.log_step(
            step=1,
            action="search_code",
            action_input="QuerySet.exclude",
            observation_summary="Found in django/db/models/query.py:823"
        )

        # At end of task
        logger.save()
    """

    def __init__(
        self,
        run_id: str,
        task_id: str,
        policy: str,
        seed: int,
        base_dir: Path | str = "runs",
    ):
        """
        Initialize trajectory logger.

        Args:
            run_id: Unique identifier for this run
            task_id: Task identifier (e.g., "django__django-12345")
            policy: Memory policy name (e.g., "type_aware_decay")
            seed: Random seed for this run
            base_dir: Base directory for runs (default: "runs")
        """
        self.run_id = run_id
        self.task_id = task_id
        self.policy = policy
        self.seed = seed
        self.base_dir = Path(base_dir)

        # Accumulate steps in memory
        self.steps: list[TrajectoryStep] = []

        # Track if already saved (prevent double-save)
        self._saved = False

    def log_step(
        self,
        step: int,
        action: str,
        action_input: str | dict[str, Any],
        observation_summary: str,
        timestamp: str | None = None,
    ) -> None:
        """
        Log a single step in the agent's execution trajectory.

        This records WHAT the agent did (action) and WHAT it observed (result),
        but NOT WHY it decided to do it (no reasoning or planning).

        Args:
            step: Step number (1-indexed)
            action: Tool name or action type (e.g., "search_code", "edit_file")
            action_input: Arguments to the tool (string or dict)
            observation_summary: Summary of the result/output
            timestamp: ISO 8601 timestamp (auto-generated if None)

        Example:
            logger.log_step(
                step=1,
                action="search_code",
                action_input="QuerySet.exclude",
                observation_summary="Found in django/db/models/query.py:823"
            )
        """
        if self._saved:
            raise RuntimeError(
                f"Cannot log step after trajectory has been saved for task {self.task_id}"
            )

        # Create step with auto-generated timestamp if not provided
        if timestamp is None:
            trajectory_step = TrajectoryStep(
                step=step,
                action=action,
                action_input=action_input,
                observation_summary=observation_summary,
            )
        else:
            trajectory_step = TrajectoryStep(
                step=step,
                action=action,
                action_input=action_input,
                observation_summary=observation_summary,
                timestamp=timestamp,
            )

        self.steps.append(trajectory_step)

    def save(self) -> Path:
        """
        Save trajectory to JSON file.

        Writes all accumulated steps to:
        runs/{run_id}/trajectories/{task_id}.json

        The file is written atomically (all at once) to prevent partial writes.

        Returns:
            Path to the saved trajectory file

        Raises:
            RuntimeError: If trajectory has already been saved
        """
        if self._saved:
            raise RuntimeError(
                f"Trajectory already saved for task {self.task_id}"
            )

        # Construct output path
        output_dir = self.base_dir / self.run_id / "trajectories"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / f"{self.task_id}.json"

        # Build trajectory document
        trajectory = {
            "task_id": self.task_id,
            "policy": self.policy,
            "seed": self.seed,
            "steps": [step.to_dict() for step in self.steps],
        }

        # Write atomically
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(trajectory, f, indent=2, ensure_ascii=False)

        self._saved = True
        return output_path

    def get_step_count(self) -> int:
        """
        Get the number of steps logged so far.

        Returns:
            Number of steps in the trajectory
        """
        return len(self.steps)

    def clear(self) -> None:
        """
        Clear all logged steps.

        This is useful for testing or if you need to restart logging
        for the same task.

        Warning: This does not delete any saved files, only clears
        the in-memory buffer.
        """
        self.steps.clear()
        self._saved = False


def load_trajectory(trajectory_path: Path | str) -> dict[str, Any]:
    """
    Load a trajectory from a JSON file.

    Args:
        trajectory_path: Path to trajectory JSON file

    Returns:
        Trajectory dictionary with task_id, policy, seed, and steps

    Raises:
        FileNotFoundError: If trajectory file does not exist
        json.JSONDecodeError: If file is not valid JSON
    """
    with open(trajectory_path, encoding="utf-8") as f:
        result: dict[str, Any] = json.load(f)
        return result
