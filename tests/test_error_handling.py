"""Unit tests for comprehensive error handling.

This module tests all error handling paths specified in task 17.2:
1. Repository checkout failure handling (fail entire sequence)
2. Docker container failure handling (log as evaluation error)
3. Type classifier failure handling (fail reflection step)
4. Embedding size violation handling (truncate patch_summary)
5. Memory budget violation handling (drop lowest-scoring memories)
6. Agent timeout handling (force-fail, log timeout=true)
7. Configuration validation failure handling (fail fast)

Requirements: 2, 4, 5, 6, 14, 15, 17, 26
"""

import pytest
from unittest.mock import Mock, MagicMock
from src.errors import (
    RepositoryCheckoutError,
    DockerEvaluationError,
    ClassifierError,
    EmbeddingSizeError,
    MemoryBudgetError,
    AgentTimeoutError,
    ConfigValidationError,
    ConfigFrozenError,
    ReflectionError,
    handle_repository_checkout_failure,
    handle_docker_failure,
    handle_classifier_failure,
    handle_embedding_size_violation,
    handle_memory_budget_violation,
    handle_agent_timeout,
    handle_config_validation_failure,
    handle_reflection_failure,
    is_recoverable_error,
    log_error_for_analysis,
)


# ============================================================================
# Repository Checkout Error Handling Tests (Requirement 2)
# ============================================================================


def test_repository_checkout_error_fails_sequence():
    """Test that repository checkout errors fail the entire sequence."""
    original_error = Exception("Git checkout failed")
    
    with pytest.raises(RepositoryCheckoutError) as exc_info:
        handle_repository_checkout_failure(
            error=original_error,
            task_id="test-task-1",
            repo="django/django",
            sequence_name="django",
            run_id="test-run-1"
        )
    
    error = exc_info.value
    assert error.task_id == "test-task-1"
    assert error.repo == "django/django"
    assert "Git checkout failed" in str(error)


def test_repository_checkout_error_is_not_recoverable():
    """Test that repository checkout errors are not recoverable."""
    error = RepositoryCheckoutError("Checkout failed", task_id="test-1", repo="test/repo")
    assert not is_recoverable_error(error)


# ============================================================================
# Docker Container Error Handling Tests (Requirement 17)
# ============================================================================


def test_docker_failure_returns_failed_result():
    """Test that Docker failures return failed evaluation result."""
    original_error = Exception("Container crashed")
    
    result = handle_docker_failure(
        error=original_error,
        task_id="test-task-1",
        error_type="container_crash"
    )
    
    assert result["success"] is False
    assert result["passed"] is False
    assert result["task_id"] == "test-task-1"
    assert result["error_type"] == "container_crash"
    assert result["docker_failure"] is True
    assert "Container crashed" in result["error"]


def test_docker_error_is_recoverable():
    """Test that Docker errors are recoverable."""
    error = DockerEvaluationError(
        "Docker failed",
        task_id="test-1",
        error_type="timeout"
    )
    assert is_recoverable_error(error)


# ============================================================================
# Type Classifier Error Handling Tests (Requirement 5, 15)
# ============================================================================


def test_classifier_failure_raises_error():
    """Test that classifier failures raise ClassifierError."""
    original_error = Exception("API timeout")
    
    with pytest.raises(ClassifierError) as exc_info:
        handle_classifier_failure(
            error=original_error,
            task_id="test-task-1",
            retry_count=2
        )
    
    error = exc_info.value
    assert error.task_id == "test-task-1"
    assert error.retry_count == 2
    assert "API timeout" in str(error)


def test_classifier_error_is_recoverable():
    """Test that classifier errors are recoverable."""
    error = ClassifierError("Classification failed", task_id="test-1")
    assert is_recoverable_error(error)


# ============================================================================
# Embedding Size Violation Handling Tests (Requirement 4)
# ============================================================================


def test_embedding_size_violation_raises_error():
    """Test that embedding size violations raise EmbeddingSizeError."""
    with pytest.raises(EmbeddingSizeError) as exc_info:
        handle_embedding_size_violation(
            token_count=8000,
            task_id="test-task-1",
            original_text="x" * 10000,
            limit=7500
        )
    
    error = exc_info.value
    assert error.token_count == 8000
    assert error.limit == 7500
    assert error.task_id == "test-task-1"


def test_embedding_size_error_is_recoverable():
    """Test that embedding size errors are recoverable."""
    error = EmbeddingSizeError(
        "Size exceeded",
        token_count=8000,
        limit=7500,
        task_id="test-1"
    )
    assert is_recoverable_error(error)


# ============================================================================
# Memory Budget Violation Handling Tests (Requirement 6)
# ============================================================================


def test_memory_budget_drops_lowest_scoring():
    """Test that memory budget violations drop lowest-scoring memories."""
    # Create mock memories with different scores and token lengths
    memories = [
        (0.9, Mock(memory_id="mem-1", token_length=500)),
        (0.7, Mock(memory_id="mem-2", token_length=500)),
        (0.5, Mock(memory_id="mem-3", token_length=500)),
        (0.3, Mock(memory_id="mem-4", token_length=500)),
    ]
    
    # Budget allows only 3 memories (1500 tokens)
    result = handle_memory_budget_violation(
        memories=memories,
        token_budget=1500,
        task_id="test-task-1"
    )
    
    # Should drop lowest-scoring memory (0.3)
    assert len(result) == 3
    assert all(m[0] >= 0.5 for m in result)
    
    # Should be sorted ascending (best LAST)
    scores = [m[0] for m in result]
    assert scores == sorted(scores)


def test_memory_budget_returns_empty_if_single_exceeds():
    """Test that memory budget raises error if single memory exceeds budget."""
    memories = [
        (0.9, Mock(memory_id="mem-1", token_length=2000)),
    ]
    
    with pytest.raises(MemoryBudgetError) as exc_info:
        handle_memory_budget_violation(
            memories=memories,
            token_budget=1500,
            task_id="test-task-1"
        )
    
    error = exc_info.value
    assert error.required_tokens == 2000
    assert error.budget == 1500


def test_memory_budget_returns_all_if_within_budget():
    """Test that memory budget returns all memories if within budget."""
    memories = [
        (0.9, Mock(memory_id="mem-1", token_length=300)),
        (0.7, Mock(memory_id="mem-2", token_length=300)),
        (0.5, Mock(memory_id="mem-3", token_length=300)),
    ]
    
    result = handle_memory_budget_violation(
        memories=memories,
        token_budget=1500,
        task_id="test-task-1"
    )
    
    # Should return all memories
    assert len(result) == 3


def test_memory_budget_error_is_recoverable():
    """Test that memory budget errors are recoverable."""
    error = MemoryBudgetError(
        "Budget exceeded",
        required_tokens=2000,
        budget=1500,
        task_id="test-1"
    )
    assert is_recoverable_error(error)


# ============================================================================
# Agent Timeout Handling Tests (Requirement 14)
# ============================================================================


def test_agent_timeout_returns_failed_result():
    """Test that agent timeouts return failed result with timeout=true."""
    result = handle_agent_timeout(
        task_id="test-task-1",
        limit_type="steps",
        limit_value=20,
        actual_value=21
    )
    
    assert result["timeout"] is True
    assert result["timeout_type"] == "steps"
    assert result["limit_value"] == 20
    assert result["actual_value"] == 21
    assert result["resolved"] is False
    assert result["patch_generated"] is False
    assert "steps limit of 20 exceeded" in result["error_message"]


def test_agent_timeout_error_is_recoverable():
    """Test that agent timeout errors are recoverable."""
    error = AgentTimeoutError(
        "Timeout",
        task_id="test-1",
        limit_type="steps",
        limit_value=20,
        actual_value=21
    )
    assert is_recoverable_error(error)


# ============================================================================
# Configuration Validation Error Handling Tests (Requirement 26)
# ============================================================================


def test_config_validation_failure_raises_error():
    """Test that configuration validation failures raise ConfigValidationError."""
    validation_errors = [
        "max_context_tokens must be positive",
        "top_k must be positive"
    ]
    
    with pytest.raises(ConfigValidationError) as exc_info:
        handle_config_validation_failure(
            validation_errors=validation_errors,
            config_path="configs/base.yaml"
        )
    
    error = exc_info.value
    assert error.validation_errors == validation_errors
    assert "max_context_tokens" in str(error)
    assert "top_k" in str(error)


def test_config_validation_error_is_not_recoverable():
    """Test that config validation errors are not recoverable."""
    error = ConfigValidationError("Validation failed", validation_errors=[])
    assert not is_recoverable_error(error)


def test_config_frozen_error_is_not_recoverable():
    """Test that config frozen errors are not recoverable."""
    error = ConfigFrozenError("Config is frozen")
    assert not is_recoverable_error(error)


# ============================================================================
# Reflection Error Handling Tests (Requirement 15)
# ============================================================================


def test_reflection_failure_raises_error_if_not_continue():
    """Test that reflection failures raise ReflectionError if continue_on_failure=False."""
    original_error = Exception("Reflection failed")
    
    with pytest.raises(ReflectionError) as exc_info:
        handle_reflection_failure(
            error=original_error,
            task_id="test-task-1",
            continue_on_failure=False
        )
    
    error = exc_info.value
    assert error.task_id == "test-task-1"
    assert "Reflection failed" in str(error)


def test_reflection_failure_continues_if_allowed():
    """Test that reflection failures continue if continue_on_failure=True."""
    original_error = Exception("Reflection failed")
    
    # Should not raise
    handle_reflection_failure(
        error=original_error,
        task_id="test-task-1",
        continue_on_failure=True
    )


def test_reflection_error_is_recoverable():
    """Test that reflection errors are recoverable."""
    error = ReflectionError("Reflection failed", task_id="test-1")
    assert is_recoverable_error(error)


# ============================================================================
# Error Logging for Analysis Tests
# ============================================================================


def test_log_error_for_analysis_includes_all_fields():
    """Test that error logging includes all required fields."""
    error = AgentTimeoutError(
        "Timeout",
        task_id="test-1",
        limit_type="steps",
        limit_value=20,
        actual_value=21
    )
    
    record = log_error_for_analysis(
        error=error,
        task_id="test-1",
        sequence_name="django",
        run_id="test-run-1",
        error_category="timeout"
    )
    
    assert record["task_id"] == "test-1"
    assert record["sequence_name"] == "django"
    assert record["run_id"] == "test-run-1"
    assert record["error_category"] == "timeout"
    assert record["error_type"] == "AgentTimeoutError"
    assert record["is_recoverable"] is True
    assert record["limit_type"] == "steps"
    assert record["limit_value"] == 20
    assert record["actual_value"] == 21


def test_log_error_for_analysis_handles_different_error_types():
    """Test that error logging handles different error types correctly."""
    # Test with RepositoryCheckoutError
    error = RepositoryCheckoutError(
        "Checkout failed",
        task_id="test-1",
        repo="django/django"
    )
    
    record = log_error_for_analysis(
        error=error,
        task_id="test-1",
        sequence_name="django",
        run_id="test-run-1",
        error_category="repository_error"
    )
    
    assert record["error_type"] == "RepositoryCheckoutError"
    assert record["repo"] == "django/django"
    assert record["is_recoverable"] is False


# ============================================================================
# Integration Tests
# ============================================================================


def test_error_handling_preserves_frozen_invariants():
    """Test that error handling preserves frozen invariants."""
    # Test that max_steps=20 is enforced even in error cases
    result = handle_agent_timeout(
        task_id="test-1",
        limit_type="steps",
        limit_value=20,  # Frozen invariant
        actual_value=21
    )
    
    assert result["limit_value"] == 20


def test_error_handling_supports_failure_analysis():
    """Test that error handling supports failure analysis (Requirement 28)."""
    # Create various error types
    errors = [
        AgentTimeoutError("Timeout", "task-1", "steps", 20, 21),
        DockerEvaluationError("Docker failed", "task-2", "container_crash"),
        ClassifierError("Classification failed", "task-3"),
    ]
    
    # Log all errors for analysis
    records = [
        log_error_for_analysis(
            error=e,
            task_id=f"task-{i}",
            sequence_name="django",
            run_id="test-run-1",
            error_category="test"
        )
        for i, e in enumerate(errors, 1)
    ]
    
    # Verify all records have required fields for analysis
    for record in records:
        assert "task_id" in record
        assert "error_category" in record
        assert "error_type" in record
        assert "is_recoverable" in record
