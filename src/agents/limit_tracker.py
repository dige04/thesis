"""
Execution limit tracker for agent system.

This module implements hard limits on agent execution to ensure reproducibility
and prevent runaway costs. All limits are FROZEN INVARIANTS and must not be
modified without explicit approval.

Frozen invariants:
- Max 20 steps per task (FROZEN INVARIANT)
- Max 80 tool calls per task
- Max 5 test runs per task
- Max 20 minutes wall time per task
- Temperature=0 for ALL LLM calls (FROZEN INVARIANT)

When any limit is exceeded:
- Stop execution immediately
- Mark task as failed
- Log timeout=true in task results
- Record which limit was exceeded
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class LimitType(Enum):
    """Types of execution limits that can be exceeded."""

    STEPS = "max_steps"
    TOOL_CALLS = "max_tool_calls"
    TEST_RUNS = "max_test_runs"
    WALL_TIME = "max_wall_time"


@dataclass
class LimitTracker:
    """
    Tracks execution limits during agent task execution.

    This class monitors all hard limits and provides methods to check
    if any limit has been exceeded. When a limit is exceeded, it records
    which limit was violated for logging purposes.

    Frozen invariants:
    - max_steps = 20 (FROZEN INVARIANT - never change)
    - max_tool_calls = 80
    - max_test_runs = 5
    - max_wall_time_seconds = 1200 (20 minutes)

    Attributes:
        max_steps: Maximum number of agent steps (FROZEN at 20)
        max_tool_calls: Maximum number of tool invocations
        max_test_runs: Maximum number of test executions
        max_wall_time_seconds: Maximum wall clock time in seconds
        step_count: Current number of steps taken
        tool_call_count: Current number of tool calls made
        test_run_count: Current number of test runs executed
        start_time: Timestamp when tracking started
        limit_exceeded: Whether any limit has been exceeded
        exceeded_limit_type: Which limit was exceeded (if any)
    """

    # Hard limits (FROZEN INVARIANTS)
    max_steps: int = 20  # FROZEN INVARIANT - DO NOT CHANGE
    max_tool_calls: int = 80
    max_test_runs: int = 5
    max_wall_time_seconds: int = 1200  # 20 minutes

    # Current counts
    step_count: int = 0
    tool_call_count: int = 0
    test_run_count: int = 0
    start_time: float = field(default_factory=time.time)

    # Limit violation tracking
    limit_exceeded: bool = False
    exceeded_limit_type: LimitType | None = None

    def __post_init__(self) -> None:
        """Validate that frozen invariants are not violated."""
        if self.max_steps != 20:
            raise ValueError(
                f"FROZEN INVARIANT VIOLATION: max_steps must be 20, got {self.max_steps}. "
                "This is a frozen invariant from THESIS_FINAL_v5.md §0.1 #3."
            )

    def increment_step(self) -> bool:
        """
        Increment step count and check if limit exceeded.

        Returns:
            True if limit exceeded, False otherwise
        """
        self.step_count += 1

        if self.step_count > self.max_steps:
            self.limit_exceeded = True
            self.exceeded_limit_type = LimitType.STEPS
            return True

        return False

    def increment_tool_call(self) -> bool:
        """
        Increment tool call count and check if limit exceeded.

        Returns:
            True if limit exceeded, False otherwise
        """
        self.tool_call_count += 1

        if self.tool_call_count > self.max_tool_calls:
            self.limit_exceeded = True
            self.exceeded_limit_type = LimitType.TOOL_CALLS
            return True

        return False

    def increment_test_run(self) -> bool:
        """
        Increment test run count and check if limit exceeded.

        Returns:
            True if limit exceeded, False otherwise
        """
        self.test_run_count += 1

        if self.test_run_count > self.max_test_runs:
            self.limit_exceeded = True
            self.exceeded_limit_type = LimitType.TEST_RUNS
            return True

        return False

    def check_wall_time(self) -> bool:
        """
        Check if wall time limit has been exceeded.

        Returns:
            True if limit exceeded, False otherwise
        """
        elapsed = time.time() - self.start_time

        if elapsed > self.max_wall_time_seconds:
            self.limit_exceeded = True
            self.exceeded_limit_type = LimitType.WALL_TIME
            return True

        return False

    def check_any_limit_exceeded(self) -> bool:
        """
        Check if any limit has been exceeded.

        This method checks all limits and returns True if any has been
        exceeded. It also checks wall time, which is not automatically
        checked on every operation.

        Returns:
            True if any limit exceeded, False otherwise
        """
        # Check wall time (not automatically checked elsewhere)
        if self.check_wall_time():
            return True

        # Return current limit_exceeded status
        return self.limit_exceeded

    def get_elapsed_time(self) -> float:
        """
        Get elapsed wall time in seconds.

        Returns:
            Elapsed time in seconds since tracking started
        """
        return time.time() - self.start_time

    def get_status(self) -> dict[str, Any]:
        """
        Get current status of all limits.

        Returns:
            Dictionary with current counts, limits, and exceeded status
        """
        return {
            "step_count": self.step_count,
            "max_steps": self.max_steps,
            "tool_call_count": self.tool_call_count,
            "max_tool_calls": self.max_tool_calls,
            "test_run_count": self.test_run_count,
            "max_test_runs": self.max_test_runs,
            "elapsed_time_seconds": self.get_elapsed_time(),
            "max_wall_time_seconds": self.max_wall_time_seconds,
            "limit_exceeded": self.limit_exceeded,
            "exceeded_limit_type": self.exceeded_limit_type.value if self.exceeded_limit_type else None,
        }

    def get_failure_reason(self) -> str:
        """
        Get human-readable failure reason if limit exceeded.

        Returns:
            String describing which limit was exceeded, or empty string if none
        """
        if not self.limit_exceeded or not self.exceeded_limit_type:
            return ""

        if self.exceeded_limit_type == LimitType.STEPS:
            return f"Exceeded maximum steps: {self.step_count} > {self.max_steps}"
        elif self.exceeded_limit_type == LimitType.TOOL_CALLS:
            return f"Exceeded maximum tool calls: {self.tool_call_count} > {self.max_tool_calls}"
        elif self.exceeded_limit_type == LimitType.TEST_RUNS:
            return f"Exceeded maximum test runs: {self.test_run_count} > {self.max_test_runs}"
        elif self.exceeded_limit_type == LimitType.WALL_TIME:
            elapsed = self.get_elapsed_time()
            return f"Exceeded maximum wall time: {elapsed:.1f}s > {self.max_wall_time_seconds}s"

        return "Unknown limit exceeded"

    def reset(self) -> None:
        """
        Reset all counters and tracking state.

        This should be called at the start of each new task.
        """
        self.step_count = 0
        self.tool_call_count = 0
        self.test_run_count = 0
        self.start_time = time.time()
        self.limit_exceeded = False
        self.exceeded_limit_type = None


def validate_temperature(temperature: float) -> None:
    """
    Validate that temperature is a legitimate frozen value (0 or 1).

    AMENDMENT 2026-06-14 (advisor-approved; disclose in Methods): the original
    frozen invariant was temperature=0 for reproducibility. The active provider
    (Kimi For Coding via CLIProxyAPI) serves reasoning models that ONLY accept
    temperature=1, so the experiment runs at 1. The invariant's real purpose —
    temperature held CONSTANT across all 6 conditions x 3 seeds — is preserved by
    sourcing one config value; only the constant changed (0 -> 1). temperature=0
    remains valid for determinism-capable providers (keeps the code reversible).

    Args:
        temperature: Temperature value to validate

    Raises:
        ValueError: If temperature is not exactly 0 or 1
    """
    if temperature not in (0, 1):
        raise ValueError(
            f"FROZEN INVARIANT: temperature must be 0 or 1 (held constant across "
            f"conditions), got {temperature}. 0=determinism providers, 1=reasoning "
            "providers (Kimi). See THESIS_FINAL_v5.md §0.1 + the 2026-06-14 amendment."
        )
