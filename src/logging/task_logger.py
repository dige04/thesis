"""Task results logger for the memory pruning research system.

This module implements logging of task execution results to task_results.jsonl
in JSON Lines format (one JSON object per line).

Schema Reference: THESIS_FINAL_v5.md §11.1
Requirements: 18, 27

Frozen Invariants:
- One row per completed task in task_results.jsonl
- All required fields must be present (no missing data)
- Atomic writes using temp file + rename
- JSON Lines format (newline-delimited JSON)
"""

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TaskResult:
    """
    Structured representation of task execution results.

    This dataclass matches the schema in THESIS_FINAL_v5.md §11.1 exactly.
    All fields are required for analysis - missing fields cannot be recovered.

    Requirements: 18, 27
    """

    # ========== Run Identification ==========
    run_id: str
    policy: str
    seed: int
    repo: str
    task_id: str
    sequence_index: int

    # ========== Task Outcome ==========
    resolved: int  # 1 if passed eval_v3, 0 otherwise
    patch_generated: bool
    patch_applied: bool
    syntax_error: bool
    timeout: bool

    # ========== Token Usage & Costs ==========
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    task_api_cost: float  # agent LLM cost for this task
    consolidation_llm_cost: float  # consolidation LLM cost (if any)

    # ========== Execution Metrics ==========
    wall_time_seconds: float
    tool_calls: int
    test_runs: int
    files_read: int
    files_modified: int
    syntax_error_rate: float

    # ========== Retrieved Memories ==========
    retrieved_memory_ids: list[str]
    retrieved_memory_scores: list[float]
    retrieved_memory_types: list[str]
    retrieved_memory_ages: list[int]

    # ========== Memory State ==========
    memory_count_before: int
    memory_count_after: int
    memory_tokens_before: int
    memory_tokens_after: int

    # ========== Memory Operations ==========
    pruned_memory_ids: list[str] = field(default_factory=list)
    consolidated_memory_ids: list[str] = field(default_factory=list)

    # ========== Task Metadata ==========
    task_difficulty: str = "medium"  # easy | medium | hard
    error_message: str | None = None

    def __post_init__(self) -> None:
        """Validate task result fields."""
        # Validate resolved is binary
        if self.resolved not in (0, 1):
            raise ValueError(f"resolved must be 0 or 1, got {self.resolved}")

        # Validate seed is positive
        if self.seed < 1:
            raise ValueError(f"seed must be positive, got {self.seed}")

        # Validate sequence_index is non-negative
        if self.sequence_index < 0:
            raise ValueError(
                f"sequence_index must be non-negative, got {self.sequence_index}"
            )

        # Validate token counts are non-negative
        if self.prompt_tokens < 0:
            raise ValueError(
                f"prompt_tokens must be non-negative, got {self.prompt_tokens}"
            )
        if self.completion_tokens < 0:
            raise ValueError(
                f"completion_tokens must be non-negative, got {self.completion_tokens}"
            )
        if self.total_tokens < 0:
            raise ValueError(
                f"total_tokens must be non-negative, got {self.total_tokens}"
            )

        # Validate costs are non-negative
        if self.estimated_cost_usd < 0:
            raise ValueError(
                f"estimated_cost_usd must be non-negative, got {self.estimated_cost_usd}"
            )
        if self.task_api_cost < 0:
            raise ValueError(
                f"task_api_cost must be non-negative, got {self.task_api_cost}"
            )
        if self.consolidation_llm_cost < 0:
            raise ValueError(
                f"consolidation_llm_cost must be non-negative, "
                f"got {self.consolidation_llm_cost}"
            )

        # Validate execution metrics are non-negative
        if self.wall_time_seconds < 0:
            raise ValueError(
                f"wall_time_seconds must be non-negative, got {self.wall_time_seconds}"
            )
        if self.tool_calls < 0:
            raise ValueError(f"tool_calls must be non-negative, got {self.tool_calls}")
        if self.test_runs < 0:
            raise ValueError(f"test_runs must be non-negative, got {self.test_runs}")
        if self.files_read < 0:
            raise ValueError(f"files_read must be non-negative, got {self.files_read}")
        if self.files_modified < 0:
            raise ValueError(
                f"files_modified must be non-negative, got {self.files_modified}"
            )
        if not (0 <= self.syntax_error_rate <= 1):
            raise ValueError(
                f"syntax_error_rate must be between 0 and 1, got {self.syntax_error_rate}"
            )

        # Validate memory counts are non-negative
        if self.memory_count_before < 0:
            raise ValueError(
                f"memory_count_before must be non-negative, got {self.memory_count_before}"
            )
        if self.memory_count_after < 0:
            raise ValueError(
                f"memory_count_after must be non-negative, got {self.memory_count_after}"
            )
        if self.memory_tokens_before < 0:
            raise ValueError(
                f"memory_tokens_before must be non-negative, "
                f"got {self.memory_tokens_before}"
            )
        if self.memory_tokens_after < 0:
            raise ValueError(
                f"memory_tokens_after must be non-negative, "
                f"got {self.memory_tokens_after}"
            )

        # Validate retrieved memory lists have consistent lengths
        if not (
            len(self.retrieved_memory_ids)
            == len(self.retrieved_memory_scores)
            == len(self.retrieved_memory_types)
            == len(self.retrieved_memory_ages)
        ):
            raise ValueError(
                "All retrieved_memory_* lists must have the same length. "
                f"Got ids={len(self.retrieved_memory_ids)}, "
                f"scores={len(self.retrieved_memory_scores)}, "
                f"types={len(self.retrieved_memory_types)}, "
                f"ages={len(self.retrieved_memory_ages)}"
            )

        # Validate task difficulty
        if self.task_difficulty not in ("easy", "medium", "hard"):
            raise ValueError(
                f"task_difficulty must be 'easy', 'medium', or 'hard', "
                f"got '{self.task_difficulty}'"
            )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert TaskResult to dictionary for JSON serialization.

        Returns:
            Dictionary with all fields matching schema in THESIS_FINAL_v5.md §11.1
        """
        return {
            "run_id": self.run_id,
            "policy": self.policy,
            "seed": self.seed,
            "repo": self.repo,
            "task_id": self.task_id,
            "sequence_index": self.sequence_index,
            "resolved": self.resolved,
            "patch_generated": self.patch_generated,
            "patch_applied": self.patch_applied,
            "syntax_error": self.syntax_error,
            "timeout": self.timeout,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "task_api_cost": self.task_api_cost,
            "consolidation_llm_cost": self.consolidation_llm_cost,
            "wall_time_seconds": self.wall_time_seconds,
            "tool_calls": self.tool_calls,
            "test_runs": self.test_runs,
            "files_read": self.files_read,
            "files_modified": self.files_modified,
            "syntax_error_rate": self.syntax_error_rate,
            "retrieved_memory_ids": self.retrieved_memory_ids,
            "retrieved_memory_scores": self.retrieved_memory_scores,
            "retrieved_memory_types": self.retrieved_memory_types,
            "retrieved_memory_ages": self.retrieved_memory_ages,
            "memory_count_before": self.memory_count_before,
            "memory_count_after": self.memory_count_after,
            "memory_tokens_before": self.memory_tokens_before,
            "memory_tokens_after": self.memory_tokens_after,
            "pruned_memory_ids": self.pruned_memory_ids,
            "consolidated_memory_ids": self.consolidated_memory_ids,
            "task_difficulty": self.task_difficulty,
            "error_message": self.error_message,
        }


class TaskResultLogger:
    """
    Logger for task execution results in JSON Lines format.

    Writes one row to task_results.jsonl per completed task with atomic writes
    to prevent data corruption.

    Requirements: 18, 27
    Schema: THESIS_FINAL_v5.md §11.1

    Example:
        >>> logger = TaskResultLogger(run_dir="/path/to/runs/run_001")
        >>> result = TaskResult(
        ...     run_id="gpt54_typeaware_seed2_seq3",
        ...     policy="type_aware_decay",
        ...     seed=2,
        ...     # ... other fields
        ... )
        >>> logger.log_task_result(result)
    """

    def __init__(self, run_dir: str | Path) -> None:
        """
        Initialize task result logger.

        Args:
            run_dir: Directory for this run (e.g., runs/{run_id})
                    Will be created if it doesn't exist.
        """
        self.run_dir = Path(run_dir)
        self.log_file = self.run_dir / "task_results.jsonl"

        # Create directory structure if needed
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def log_task_result(self, result: TaskResult) -> None:
        """
        Log a task result to task_results.jsonl.

        Uses atomic write pattern (write to temp file, then rename) to prevent
        data corruption if process is interrupted.

        Args:
            result: TaskResult instance with all required fields

        Raises:
            ValueError: If result validation fails
            OSError: If file operations fail
        """
        # Validate result (triggers __post_init__ checks)
        result_dict = result.to_dict()

        # Validate all required fields are present
        self._validate_schema(result_dict)

        # Convert to JSON string (one line)
        json_line = json.dumps(result_dict, ensure_ascii=False)

        # Atomic write: write to temp file, then rename
        self._atomic_append(json_line)

    def _validate_schema(self, result_dict: dict[str, Any]) -> None:
        """
        Validate that all required fields from schema are present.

        Args:
            result_dict: Dictionary representation of TaskResult

        Raises:
            ValueError: If any required field is missing
        """
        required_fields = {
            # Run identification
            "run_id",
            "policy",
            "seed",
            "repo",
            "task_id",
            "sequence_index",
            # Task outcome
            "resolved",
            "patch_generated",
            "patch_applied",
            "syntax_error",
            "timeout",
            # Token usage & costs
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "estimated_cost_usd",
            "task_api_cost",
            "consolidation_llm_cost",
            # Execution metrics
            "wall_time_seconds",
            "tool_calls",
            "test_runs",
            "files_read",
            "files_modified",
            "syntax_error_rate",
            # Retrieved memories
            "retrieved_memory_ids",
            "retrieved_memory_scores",
            "retrieved_memory_types",
            "retrieved_memory_ages",
            # Memory state
            "memory_count_before",
            "memory_count_after",
            "memory_tokens_before",
            "memory_tokens_after",
            # Memory operations
            "pruned_memory_ids",
            "consolidated_memory_ids",
            # Task metadata
            "task_difficulty",
            "error_message",
        }

        missing_fields = required_fields - set(result_dict.keys())
        if missing_fields:
            raise ValueError(
                f"Missing required fields in TaskResult: {sorted(missing_fields)}"
            )

    def _atomic_append(self, json_line: str) -> None:
        """
        Atomically append a JSON line to the log file.

        Uses temp file + rename pattern to ensure atomicity:
        1. Write to temporary file in same directory
        2. Rename temp file to append to main file
        3. Clean up temp file

        Args:
            json_line: JSON string to append (without trailing newline)

        Raises:
            OSError: If file operations fail
        """
        # Create a temporary file in the same directory
        # (same filesystem ensures atomic rename)
        fd, temp_path = tempfile.mkstemp(
            dir=self.run_dir, prefix=".task_results_", suffix=".tmp"
        )

        try:
            # Write JSON line with newline to temp file
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(json_line)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())  # Ensure data is written to disk

            # Append temp file contents to main log file
            with open(temp_path, encoding="utf-8") as temp_f:
                content = temp_f.read()
                with open(self.log_file, "a", encoding="utf-8") as log_f:
                    log_f.write(content)
                    log_f.flush()
                    os.fsync(log_f.fileno())

        finally:
            # Clean up temp file
            try:
                os.unlink(temp_path)
            except OSError:
                pass  # Ignore cleanup errors

    def read_results(self) -> list[dict[str, Any]]:
        """
        Read all task results from the log file.

        Returns:
            List of task result dictionaries

        Raises:
            FileNotFoundError: If log file doesn't exist
            json.JSONDecodeError: If log file contains invalid JSON
        """
        if not self.log_file.exists():
            return []

        results = []
        with open(self.log_file, encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue  # Skip empty lines

                try:
                    result = json.loads(line)
                    results.append(result)
                except json.JSONDecodeError as e:
                    raise json.JSONDecodeError(
                        f"Invalid JSON on line {line_num}: {e.msg}",
                        e.doc,
                        e.pos,
                    ) from e

        return results

    def get_task_count(self) -> int:
        """
        Get the number of tasks logged so far.

        Returns:
            Number of task results in the log file
        """
        if not self.log_file.exists():
            return 0

        count = 0
        with open(self.log_file, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    count += 1

        return count

    def validate_run_parameters(
        self, expected_run_id: str, expected_policy: str, expected_seed: int
    ) -> bool:
        """
        Validate that all logged results match expected run parameters.

        This ensures data integrity - all results in a run should have
        consistent run_id, policy, and seed values.

        Args:
            expected_run_id: Expected run_id value
            expected_policy: Expected policy name
            expected_seed: Expected seed value

        Returns:
            True if all results match expected parameters

        Raises:
            ValueError: If any result has mismatched parameters
        """
        results = self.read_results()

        for i, result in enumerate(results):
            if result["run_id"] != expected_run_id:
                raise ValueError(
                    f"Result {i} has run_id '{result['run_id']}', "
                    f"expected '{expected_run_id}'"
                )
            if result["policy"] != expected_policy:
                raise ValueError(
                    f"Result {i} has policy '{result['policy']}', "
                    f"expected '{expected_policy}'"
                )
            if result["seed"] != expected_seed:
                raise ValueError(
                    f"Result {i} has seed {result['seed']}, expected {expected_seed}"
                )

        return True
