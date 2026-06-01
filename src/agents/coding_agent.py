"""
Coding agent with hard execution limits.

This module implements the core coding agent with enforced limits:
- Max 20 steps per task (hard force-fail)
- Max 80 tool calls per task
- Max 5 test runs per task
- Max 20 minutes wall time
- Temperature=0 for all LLM calls (reproducibility)

Frozen decision from THESIS_FINAL_v5.md §0.1 #3:
"Max 20 steps per task, hard force-fail if exceeded"
"""

import time
from dataclasses import dataclass
from typing import Any

# Use the canonical AgentTimeoutError defined in src/errors.py. Re-exported here
# so existing imports (`from src.agents.coding_agent import AgentTimeoutError`)
# resolve to the single, authoritative exception with the full signature
# (message, task_id, limit_type, limit_value, actual_value). A previous local
# 3-arg definition caused a positional-arg mismatch at the raise sites below.
from src.errors import AgentTimeoutError


@dataclass
class AgentExecutionLimits:
    """
    Hard limits for agent execution.

    All limits are enforced with hard force-fail when exceeded.
    Frozen decisions from THESIS_FINAL_v5.md §0.1.
    """

    max_steps: int = 20                    # LOCKED - frozen decision #3
    max_tool_calls: int = 80               # LOCKED
    max_test_runs: int = 5                 # LOCKED
    max_wall_time_minutes: int = 20        # LOCKED
    temperature: float = 0.0               # LOCKED - frozen decision #26

    def __post_init__(self):
        """Validate that limits match frozen decisions."""
        if self.max_steps != 20:
            raise ValueError(
                f"max_steps must be 20 (frozen decision #3), got {self.max_steps}"
            )
        if self.temperature != 0.0:
            raise ValueError(
                f"temperature must be 0 (frozen decision #26), got {self.temperature}"
            )


@dataclass
class AgentExecutionState:
    """
    Tracks agent execution state for limit enforcement.
    """

    step_count: int = 0
    tool_call_count: int = 0
    test_run_count: int = 0
    start_time: float | None = None
    timeout: bool = False
    timeout_reason: str | None = None
    task_id: str | None = None

    def reset(self):
        """Reset state for new task."""
        self.step_count = 0
        self.tool_call_count = 0
        self.test_run_count = 0
        self.start_time = time.time()
        self.timeout = False
        self.timeout_reason = None
        self.task_id = None

    def elapsed_minutes(self) -> float:
        """Get elapsed time in minutes."""
        if self.start_time is None:
            return 0.0
        return (time.time() - self.start_time) / 60.0


class CodingAgent:
    """
    LangGraph-based coding agent with hard execution limits.

    This agent enforces all frozen decisions from THESIS_FINAL_v5.md:
    - Max 20 steps per task (hard force-fail)
    - Max 80 tool calls per task
    - Max 5 test runs per task
    - Max 20 minutes wall time
    - Temperature=0 for all LLM calls

    When any limit is exceeded, the agent force-fails the task and logs timeout=true.
    """

    def __init__(
        self,
        limits: AgentExecutionLimits | None = None,
        model: str = "gpt-5.4",
        summary_model: str = "gpt-4o-mini",
    ):
        """
        Initialize coding agent with execution limits.

        Args:
            limits: Execution limits (defaults to frozen decision values)
            model: Main LLM model for agent reasoning
            summary_model: Model for reflection and summarization
        """
        self.limits = limits or AgentExecutionLimits()
        self.model = model
        self.summary_model = summary_model
        self.state = AgentExecutionState()

        # Validate temperature is 0
        if self.limits.temperature != 0.0:
            raise ValueError(
                f"Temperature must be 0 for reproducibility (frozen decision #26), "
                f"got {self.limits.temperature}"
            )

    def _check_limits(self) -> None:
        """
        Check if any execution limit has been exceeded.

        Raises:
            AgentTimeoutError: If any limit is exceeded
        """
        # Check step limit (CRITICAL - frozen decision #3).
        # Counters are post-increment (count == steps taken so far). With ">",
        # 20 steps are allowed and the 21st force-fails — exactly the strict
        # "Max 20 steps" boundary required by Frozen Invariant #3.
        if self.state.step_count > self.limits.max_steps:
            self.state.timeout = True
            self.state.timeout_reason = "max_steps_exceeded"
            raise AgentTimeoutError(
                message=(
                    f"Agent exceeded max_steps limit: "
                    f"{self.state.step_count} > {self.limits.max_steps}"
                ),
                task_id=self.state.task_id,
                limit_type="max_steps",
                limit_value=self.limits.max_steps,
                actual_value=self.state.step_count,
            )

        # Check tool call limit
        if self.state.tool_call_count > self.limits.max_tool_calls:
            self.state.timeout = True
            self.state.timeout_reason = "max_tool_calls_exceeded"
            raise AgentTimeoutError(
                message=(
                    f"Agent exceeded max_tool_calls limit: "
                    f"{self.state.tool_call_count} > {self.limits.max_tool_calls}"
                ),
                task_id=self.state.task_id,
                limit_type="max_tool_calls",
                limit_value=self.limits.max_tool_calls,
                actual_value=self.state.tool_call_count,
            )

        # Check test run limit
        if self.state.test_run_count > self.limits.max_test_runs:
            self.state.timeout = True
            self.state.timeout_reason = "max_test_runs_exceeded"
            raise AgentTimeoutError(
                message=(
                    f"Agent exceeded max_test_runs limit: "
                    f"{self.state.test_run_count} > {self.limits.max_test_runs}"
                ),
                task_id=self.state.task_id,
                limit_type="max_test_runs",
                limit_value=self.limits.max_test_runs,
                actual_value=self.state.test_run_count,
            )

        # Check wall time limit (hard cap: >= is correct for a time threshold)
        elapsed = self.state.elapsed_minutes()
        if elapsed >= self.limits.max_wall_time_minutes:
            self.state.timeout = True
            self.state.timeout_reason = "max_wall_time_exceeded"
            raise AgentTimeoutError(
                message=(
                    f"Agent exceeded max_wall_time_minutes limit: "
                    f"{int(elapsed)} >= {self.limits.max_wall_time_minutes}"
                ),
                task_id=self.state.task_id,
                limit_type="max_wall_time_minutes",
                limit_value=self.limits.max_wall_time_minutes,
                actual_value=int(elapsed),
            )

    def _increment_step(self) -> None:
        """
        Increment step counter and check limits.

        This is called at the start of each agent step.
        """
        self.state.step_count += 1
        self._check_limits()

    def _increment_tool_call(self) -> None:
        """
        Increment tool call counter and check limits.

        This is called whenever the agent invokes a tool.
        """
        self.state.tool_call_count += 1
        self._check_limits()

    def _increment_test_run(self) -> None:
        """
        Increment test run counter and check limits.

        This is called whenever the agent runs tests.
        """
        self.state.test_run_count += 1
        self._check_limits()

    def execute_task(
        self,
        task: dict[str, Any],
        retrieved_memories: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Execute a single coding task with hard execution limits.

        Args:
            task: Task specification with task_id, repo, issue_text, etc.
            retrieved_memories: List of retrieved memory records for context

        Returns:
            Result dictionary with:
                - resolved: bool (whether task was successfully resolved)
                - patch: str (generated patch, if any)
                - timeout: bool (whether any limit was exceeded)
                - timeout_reason: str (which limit was exceeded, if any)
                - step_count: int (number of steps executed)
                - tool_call_count: int (number of tool calls made)
                - test_run_count: int (number of test runs executed)
                - wall_time_seconds: float (elapsed time in seconds)

        Raises:
            AgentTimeoutError: If any execution limit is exceeded
        """
        # Reset state for new task
        self.state.reset()
        self.state.task_id = task.get("task_id")

        try:
            # Check limits immediately to catch wall time issues
            self._check_limits()

            # TODO: Implement actual agent execution logic
            # This is a placeholder that will be filled in by tasks 9.1, 9.2, 9.4

            # For now, just demonstrate limit checking
            result = {
                "resolved": False,
                "patch": None,
                "timeout": False,
                "timeout_reason": None,
                "step_count": self.state.step_count,
                "tool_call_count": self.state.tool_call_count,
                "test_run_count": self.state.test_run_count,
                "wall_time_seconds": self.state.elapsed_minutes() * 60,
            }

            return result

        except AgentTimeoutError as e:
            # Log timeout and return failure result
            return {
                "resolved": False,
                "patch": None,
                "timeout": True,
                "timeout_reason": self.state.timeout_reason,
                "step_count": self.state.step_count,
                "tool_call_count": self.state.tool_call_count,
                "test_run_count": self.state.test_run_count,
                "wall_time_seconds": self.state.elapsed_minutes() * 60,
                "error": str(e),
            }

    def get_llm_config(self) -> dict[str, Any]:
        """
        Get LLM configuration with temperature=0 enforced.

        Returns:
            Configuration dict for LLM calls with temperature=0
        """
        return {
            "model": self.model,
            "temperature": self.limits.temperature,  # Always 0
        }

    def get_summary_llm_config(self) -> dict[str, Any]:
        """
        Get summary LLM configuration with temperature=0 enforced.

        Returns:
            Configuration dict for summary LLM calls with temperature=0
        """
        return {
            "model": self.summary_model,
            "temperature": self.limits.temperature,  # Always 0
        }


def create_agent_from_config(config: dict[str, Any]) -> CodingAgent:
    """
    Create a CodingAgent from configuration dictionary.

    Args:
        config: Configuration dict with 'agent' section

    Returns:
        Configured CodingAgent instance

    Raises:
        ValueError: If configuration violates frozen decisions
    """
    agent_config = config.get("agent", {})

    # Extract limits from config
    limits = AgentExecutionLimits(
        max_steps=agent_config.get("max_steps_per_task", 20),
        max_tool_calls=agent_config.get("max_tool_calls_per_task", 80),
        max_test_runs=agent_config.get("max_test_runs_per_task", 5),
        max_wall_time_minutes=agent_config.get("max_wall_time_minutes", 20),
        temperature=agent_config.get("temperature", 0.0),
    )

    # Create agent
    agent = CodingAgent(
        limits=limits,
        model=agent_config.get("main_model", "gpt-5.4"),
        summary_model=agent_config.get("summary_model", "gpt-4o-mini"),
    )

    return agent
