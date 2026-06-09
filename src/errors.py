"""Centralized error handling for the memory pruning research system.

This module defines custom exceptions and error handling utilities for all
components of the system. It implements comprehensive error handling as
specified in Requirements 2, 4, 5, 6, 14, 15, 17, 26.

Error Handling Strategy:
1. Repository checkout failures → Fail entire sequence
2. Docker container failures → Log as evaluation error
3. Type classifier failures → Fail reflection step
4. Embedding size violations → Truncate patch_summary
5. Memory budget violations → Drop lowest-scoring memories
6. Agent timeout → Force-fail, log timeout=true
7. Configuration validation failures → Fail fast

Requirements: 2, 4, 5, 6, 14, 15, 17, 26
Design: §17 Error Handling
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# Provider quota / usage-limit (FATAL — abort, do not continue)
# ============================================================================


class UsageLimitError(Exception):
    """Non-retryable provider quota / usage-limit / billing error.

    Examples: OpenCode ``GoUsageLimitError`` (HTTP 429, weekly cap), OpenAI
    ``insufficient_quota``. Unlike a transient rate-limit, this will NOT clear
    on retry within the run. It is FATAL: the sequence/experiment must ABORT
    immediately rather than churn through tasks that can no longer call the
    model — otherwise every remaining task records a silent, invalid
    0-resolved result (this exact failure corrupted half a pilot).
    """


def is_usage_limit_error(exc: BaseException) -> bool:
    """True if ``exc`` is a provider quota/usage-limit/billing error (fatal)."""
    text = str(exc).lower()
    name_markers = (
        "gousagelimiterror",
        "insufficient_quota",
        "usage limit reached",
        "weekly usage limit",
    )
    if any(m in text for m in name_markers):
        return True
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    return status == 429 and ("usage limit" in text or "quota" in text)


# ============================================================================
# Repository and Environment Errors (Requirement 2)
# ============================================================================


class RepositoryCheckoutError(Exception):
    """Raised when repository checkout fails.

    This error should cause the entire sequence run to fail immediately,
    as per Requirements.md #2: "IF repository checkout fails due to
    uncommitted changes or file system errors, THEN THE System SHALL
    fail the entire sequence run immediately."

    Attributes:
        task_id: Task identifier where failure occurred
        repo: Repository name
        reason: Detailed failure reason
    """

    def __init__(self, message: str, task_id: str | None = None, repo: str | None = None):
        super().__init__(message)
        self.task_id = task_id
        self.repo = repo
        self.reason = message


def handle_repository_checkout_failure(
    error: Exception,
    task_id: str,
    repo: str,
    sequence_name: str,
    run_id: str
) -> None:
    """Handle repository checkout failure by failing entire sequence.

    This function logs the failure and raises RepositoryCheckoutError
    to signal that the entire sequence run should be aborted.

    Args:
        error: The original exception that caused the failure
        task_id: Task identifier where failure occurred
        repo: Repository name
        sequence_name: Sequence name
        run_id: Run identifier

    Raises:
        RepositoryCheckoutError: Always raised to fail the sequence

    Requirements: 2
    """
    error_msg = (
        f"Repository checkout failed for task {task_id} in sequence {sequence_name} "
        f"(run_id={run_id}, repo={repo}): {error}"
    )
    logger.error(error_msg, exc_info=True)

    raise RepositoryCheckoutError(
        message=error_msg,
        task_id=task_id,
        repo=repo
    ) from error


# ============================================================================
# Docker and Evaluation Errors (Requirement 17)
# ============================================================================


class DockerEvaluationError(Exception):
    """Raised when Docker container evaluation fails.

    This error is logged as an evaluation error but does NOT fail the
    entire sequence. The task is marked as failed and execution continues.

    Attributes:
        task_id: Task identifier where failure occurred
        error_type: Type of Docker error (timeout, container_crash, etc.)
        details: Detailed error information
    """

    def __init__(self, message: str, task_id: str, error_type: str, details: str | None = None):
        super().__init__(message)
        self.task_id = task_id
        self.error_type = error_type
        self.details = details


def handle_docker_failure(
    error: Exception,
    task_id: str,
    error_type: str = "unknown"
) -> dict[str, Any]:
    """Handle Docker container failure gracefully.

    Logs the failure as an evaluation error and returns a failed
    evaluation result. The sequence continues with the next task.

    Args:
        error: The original exception that caused the failure
        task_id: Task identifier where failure occurred
        error_type: Type of Docker error (timeout, container_crash, network, etc.)

    Returns:
        Dictionary with evaluation result marked as failed:
        {
            "success": False,
            "passed": False,
            "error": error message,
            "error_type": error_type,
            "task_id": task_id
        }

    Requirements: 17
    """
    error_msg = f"Docker evaluation failed for task {task_id} ({error_type}): {error}"
    logger.error(error_msg, exc_info=True)

    return {
        "success": False,
        "passed": False,
        "error": error_msg,
        "error_type": error_type,
        "task_id": task_id,
        "docker_failure": True  # Flag for analysis
    }


# ============================================================================
# Type Classifier Errors (Requirement 5, 15)
# ============================================================================


class ClassifierError(Exception):
    """Raised when type classifier fails.

    This error signals that the reflection step should fail entirely
    rather than proceeding with an untyped memory record.

    Attributes:
        task_id: Task identifier where failure occurred
        retry_count: Number of retries attempted
        details: Detailed error information
    """

    def __init__(self, message: str, task_id: str | None = None, retry_count: int = 0):
        super().__init__(message)
        self.task_id = task_id
        self.retry_count = retry_count


def handle_classifier_failure(
    error: Exception,
    task_id: str,
    retry_count: int = 0
) -> None:
    """Handle type classifier failure by failing reflection step.

    This function logs the failure and raises ClassifierError to signal
    that the reflection step should fail entirely. No memory record
    should be written without type classification.

    Args:
        error: The original exception that caused the failure
        task_id: Task identifier where failure occurred
        retry_count: Number of retries attempted

    Raises:
        ClassifierError: Always raised to fail the reflection step

    Requirements: 5, 15
    """
    error_msg = (
        f"Type classifier failed for task {task_id} after {retry_count} retries: {error}"
    )
    logger.error(error_msg, exc_info=True)

    raise ClassifierError(
        message=error_msg,
        task_id=task_id,
        retry_count=retry_count
    ) from error


# ============================================================================
# Embedding Size Violations (Requirement 4)
# ============================================================================


class EmbeddingSizeError(Exception):
    """Raised when embedding text exceeds 7500 token limit.

    This error is raised AFTER truncation attempts fail. Normal truncation
    is handled automatically by construct_embedding_text().

    Attributes:
        token_count: Actual token count
        limit: Token limit (7500)
        task_id: Task identifier where violation occurred
    """

    def __init__(self, message: str, token_count: int, limit: int = 7500, task_id: str | None = None):
        super().__init__(message)
        self.token_count = token_count
        self.limit = limit
        self.task_id = task_id


def handle_embedding_size_violation(
    token_count: int,
    task_id: str,
    original_text: str,
    limit: int = 7500
) -> tuple[str, bool]:
    """Handle embedding size violation by truncating patch_summary.

    This function attempts to truncate the embedding text to fit within
    the 7500 token limit. If truncation fails, raises EmbeddingSizeError.

    Args:
        token_count: Current token count
        task_id: Task identifier
        original_text: Original embedding text
        limit: Token limit (default: 7500)

    Returns:
        Tuple of (truncated_text, was_truncated)

    Raises:
        EmbeddingSizeError: If truncation fails to bring text under limit

    Requirements: 4
    """
    logger.warning(
        f"Embedding size violation for task {task_id}: "
        f"{token_count} tokens exceeds limit of {limit}"
    )

    # This should be handled by construct_embedding_text() in embedding_utils.py
    # If we reach here, truncation has already been attempted and failed
    error_msg = (
        f"Embedding size violation for task {task_id}: "
        f"{token_count} tokens exceeds limit of {limit} even after truncation"
    )
    logger.error(error_msg)

    raise EmbeddingSizeError(
        message=error_msg,
        token_count=token_count,
        limit=limit,
        task_id=task_id
    )


# ============================================================================
# Memory Budget Violations (Requirement 6)
# ============================================================================


class MemoryBudgetError(Exception):
    """Raised when memory budget cannot be satisfied.

    This error is raised when dropping lowest-scoring memories still
    cannot bring the total within the token budget.

    Attributes:
        required_tokens: Required token count
        budget: Token budget limit
        task_id: Task identifier where violation occurred
    """

    def __init__(self, message: str, required_tokens: int, budget: int, task_id: str | None = None):
        super().__init__(message)
        self.required_tokens = required_tokens
        self.budget = budget
        self.task_id = task_id


def handle_memory_budget_violation(
    memories: list[tuple[float, Any]],
    token_budget: int,
    task_id: str
) -> list[tuple[float, Any]]:
    """Handle memory budget violation by dropping lowest-scoring memories.

    This function drops memories one by one (starting with lowest-scoring)
    until the total token count fits within the budget. Guarantees that
    the final result fits within the budget (no partial items).

    Args:
        memories: List of (similarity_score, MemoryRecord) tuples
        token_budget: Maximum token budget
        task_id: Task identifier

    Returns:
        List of memories that fit within budget (may be empty)

    Raises:
        MemoryBudgetError: If even a single memory exceeds the budget

    Requirements: 6
    """
    if not memories:
        return []

    # Sort by similarity score ascending (lowest first)
    sorted_memories = sorted(memories, key=lambda x: x[0])

    # Calculate total tokens
    def get_total_tokens(mem_list: list[tuple[float, Any]]) -> int:
        return sum(m[1].token_length for m in mem_list)

    total_tokens = get_total_tokens(sorted_memories)

    if total_tokens <= token_budget:
        # Already within budget
        return memories

    logger.warning(
        f"Memory budget violation for task {task_id}: "
        f"{total_tokens} tokens exceeds budget of {token_budget}"
    )

    # Drop lowest-scoring memories until within budget
    result = sorted_memories.copy()
    dropped_count = 0

    while result and get_total_tokens(result) > token_budget:
        dropped = result.pop(0)  # Remove lowest-scoring
        dropped_count += 1
        logger.debug(
            f"Dropped memory {dropped[1].memory_id} (score={dropped[0]:.3f}) "
            f"to fit budget"
        )

    final_tokens = get_total_tokens(result)

    # Check if we had to drop all memories (meaning even single memory exceeds budget)
    if dropped_count > 0 and len(result) == 0:
        # All memories were dropped, meaning even the best single memory exceeds budget
        # Get the token count of the smallest memory
        smallest_memory_tokens = min(m[1].token_length for m in sorted_memories)
        error_msg = (
            f"Memory budget violation for task {task_id}: "
            f"Even smallest memory requires {smallest_memory_tokens} tokens, exceeds budget of {token_budget}"
        )
        logger.error(error_msg)

        raise MemoryBudgetError(
            message=error_msg,
            required_tokens=smallest_memory_tokens,
            budget=token_budget,
            task_id=task_id
        )

    if final_tokens > token_budget:
        # This should not happen after the while loop, but check anyway
        error_msg = (
            f"Memory budget violation for task {task_id}: "
            f"Final result requires {final_tokens} tokens, exceeds budget of {token_budget}"
        )
        logger.error(error_msg)

        raise MemoryBudgetError(
            message=error_msg,
            required_tokens=final_tokens,
            budget=token_budget,
            task_id=task_id
        )

    logger.info(
        f"Dropped {dropped_count} memories to fit budget: "
        f"{total_tokens} → {final_tokens} tokens"
    )

    # Return in original order (best LAST for injection)
    return sorted(result, key=lambda x: x[0])


# ============================================================================
# Agent Timeout Errors (Requirement 14)
# ============================================================================


class AgentTimeoutError(Exception):
    """Raised when agent exceeds execution limits.

    This error signals that the agent should force-fail the task and
    log timeout=true in the results.

    Attributes:
        task_id: Task identifier where timeout occurred
        limit_type: Type of limit exceeded (steps, wall_time, tool_calls, test_runs)
        limit_value: The limit that was exceeded
        actual_value: The actual value that exceeded the limit
    """

    def __init__(
        self,
        message: str,
        task_id: str,
        limit_type: str,
        limit_value: int | float,
        actual_value: int | float
    ):
        super().__init__(message)
        self.task_id = task_id
        self.limit_type = limit_type
        self.limit_value = limit_value
        self.actual_value = actual_value


def handle_agent_timeout(
    task_id: str,
    limit_type: str,
    limit_value: int | float,
    actual_value: int | float
) -> dict[str, Any]:
    """Handle agent timeout by force-failing the task.

    This function logs the timeout and returns a result dictionary
    with timeout=true. The task is marked as failed and execution
    stops immediately.

    Args:
        task_id: Task identifier where timeout occurred
        limit_type: Type of limit exceeded (steps, wall_time, tool_calls, test_runs)
        limit_value: The limit that was exceeded
        actual_value: The actual value that exceeded the limit

    Returns:
        Dictionary with timeout result:
        {
            "task_id": task_id,
            "timeout": True,
            "timeout_type": limit_type,
            "limit_value": limit_value,
            "actual_value": actual_value,
            "resolved": False,
            "error_message": error message
        }

    Requirements: 14
    """
    error_msg = (
        f"Agent timeout for task {task_id}: "
        f"{limit_type} limit of {limit_value} exceeded (actual: {actual_value})"
    )
    logger.error(error_msg)

    return {
        "task_id": task_id,
        "timeout": True,
        "timeout_type": limit_type,
        "limit_value": limit_value,
        "actual_value": actual_value,
        "resolved": False,
        "patch_generated": False,
        "error_message": error_msg
    }


# ============================================================================
# Configuration Validation Errors (Requirement 26)
# ============================================================================


class ConfigValidationError(Exception):
    """Raised when configuration validation fails.

    This error signals that the system should fail fast before starting
    any runs. Configuration must be valid before execution begins.

    Attributes:
        validation_errors: List of validation error messages
    """

    def __init__(self, message: str, validation_errors: list[str] | None = None):
        super().__init__(message)
        self.validation_errors = validation_errors or []


class ConfigFrozenError(Exception):
    """Raised when attempting to modify frozen configuration.

    This error signals that calibration parameters are locked and
    cannot be modified after the calibration window.
    """

    pass


def handle_config_validation_failure(
    validation_errors: list[str],
    config_path: str
) -> None:
    """Handle configuration validation failure by failing fast.

    This function logs all validation errors and raises ConfigValidationError
    to prevent execution from starting with invalid configuration.

    Args:
        validation_errors: List of validation error messages
        config_path: Path to the configuration file

    Raises:
        ConfigValidationError: Always raised to fail fast

    Requirements: 26
    """
    error_msg = (
        f"Configuration validation failed for {config_path}:\n" +
        "\n".join(f"  - {e}" for e in validation_errors)
    )
    logger.error(error_msg)

    raise ConfigValidationError(
        message=error_msg,
        validation_errors=validation_errors
    )


# ============================================================================
# Reflection Errors (Requirement 15)
# ============================================================================


class ReflectionError(Exception):
    """Raised when reflection step fails.

    This error signals that memory record generation failed and the task
    should proceed without writing a memory record.

    Attributes:
        task_id: Task identifier where failure occurred
        reason: Detailed failure reason
    """

    def __init__(self, message: str, task_id: str | None = None):
        super().__init__(message)
        self.task_id = task_id


def handle_reflection_failure(
    error: Exception,
    task_id: str,
    continue_on_failure: bool = True
) -> None:
    """Handle reflection failure gracefully.

    This function logs the failure and optionally allows execution to
    continue without writing a memory record.

    Args:
        error: The original exception that caused the failure
        task_id: Task identifier where failure occurred
        continue_on_failure: Whether to continue execution (default: True)

    Raises:
        ReflectionError: If continue_on_failure is False

    Requirements: 15
    """
    error_msg = f"Reflection failed for task {task_id}: {error}"
    logger.error(error_msg, exc_info=True)

    if not continue_on_failure:
        raise ReflectionError(
            message=error_msg,
            task_id=task_id
        ) from error

    logger.warning(
        f"Continuing execution without memory record for task {task_id}"
    )


# ============================================================================
# Error Recovery Utilities
# ============================================================================


def is_recoverable_error(error: Exception) -> bool:
    """Determine if an error is recoverable.

    Recoverable errors allow execution to continue with the next task.
    Non-recoverable errors should fail the entire sequence.

    Args:
        error: The exception to check

    Returns:
        True if error is recoverable, False otherwise
    """
    # Non-recoverable errors (fail entire sequence)
    non_recoverable = (
        RepositoryCheckoutError,
        ConfigValidationError,
        ConfigFrozenError,
    )

    # Recoverable errors (continue with next task)
    recoverable = (
        DockerEvaluationError,
        ClassifierError,
        ReflectionError,
        AgentTimeoutError,
        EmbeddingSizeError,
        MemoryBudgetError,
    )

    if isinstance(error, non_recoverable):
        return False
    elif isinstance(error, recoverable):
        return True
    else:
        # Unknown error - treat as non-recoverable for safety
        return False


def log_error_for_analysis(
    error: Exception,
    task_id: str,
    sequence_name: str,
    run_id: str,
    error_category: str
) -> dict[str, Any]:
    """Log error information for post-hoc analysis.

    This function creates a structured error record that can be used
    for failure analysis (Requirement 28).

    Args:
        error: The exception that occurred
        task_id: Task identifier where error occurred
        sequence_name: Sequence name
        run_id: Run identifier
        error_category: Category of error (timeout, test_failure, syntax_error, tool_error, unknown)

    Returns:
        Dictionary with error information for logging
    """
    error_record = {
        "task_id": task_id,
        "sequence_name": sequence_name,
        "run_id": run_id,
        "error_category": error_category,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "is_recoverable": is_recoverable_error(error),
    }

    # Add error-specific attributes
    if isinstance(error, RepositoryCheckoutError):
        error_record["repo"] = error.repo
    elif isinstance(error, DockerEvaluationError):
        error_record["docker_error_type"] = error.error_type
        error_record["details"] = error.details
    elif isinstance(error, ClassifierError):
        error_record["retry_count"] = error.retry_count
    elif isinstance(error, AgentTimeoutError):
        error_record["limit_type"] = error.limit_type
        error_record["limit_value"] = error.limit_value
        error_record["actual_value"] = error.actual_value
    elif isinstance(error, EmbeddingSizeError):
        error_record["token_count"] = error.token_count
        error_record["limit"] = error.limit
    elif isinstance(error, MemoryBudgetError):
        error_record["required_tokens"] = error.required_tokens
        error_record["budget"] = error.budget

    logger.info(f"Logged error for analysis: {error_record}")

    return error_record
