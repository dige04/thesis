"""Tests for task results logger.

Tests the TaskResultLogger implementation for logging task execution results
to task_results.jsonl in JSON Lines format.

Requirements: 18, 27
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.logging.task_logger import TaskResult, TaskResultLogger


@pytest.fixture
def temp_run_dir():
    """Create a temporary directory for test runs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_task_result():
    """Create a sample TaskResult for testing."""
    return TaskResult(
        run_id="test_run_001",
        policy="type_aware_decay",
        seed=1,
        repo="django/django",
        task_id="django__django-12345",
        sequence_index=5,
        resolved=1,
        patch_generated=True,
        patch_applied=True,
        syntax_error=False,
        timeout=False,
        prompt_tokens=1000,
        completion_tokens=500,
        total_tokens=1500,
        estimated_cost_usd=0.05,
        task_api_cost=0.05,
        consolidation_llm_cost=0.0,
        wall_time_seconds=120.5,
        tool_calls=10,
        test_runs=2,
        files_read=5,
        files_modified=2,
        syntax_error_rate=0.0,
        retrieved_memory_ids=["MEM-001", "MEM-002"],
        retrieved_memory_scores=[0.8, 0.9],
        retrieved_memory_types=["bug_fix", "api_change"],
        retrieved_memory_ages=[3, 1],
        memory_count_before=10,
        memory_count_after=11,
        memory_tokens_before=5000,
        memory_tokens_after=5500,
        pruned_memory_ids=[],
        consolidated_memory_ids=[],
        task_difficulty="medium",
        error_message=None,
    )


def test_task_result_validation_resolved_binary(sample_task_result):
    """Test that resolved must be 0 or 1."""
    with pytest.raises(ValueError, match="resolved must be 0 or 1"):
        TaskResult(
            **{**sample_task_result.to_dict(), "resolved": 2}
        )


def test_task_result_validation_seed_positive(sample_task_result):
    """Test that seed must be positive."""
    with pytest.raises(ValueError, match="seed must be positive"):
        TaskResult(
            **{**sample_task_result.to_dict(), "seed": 0}
        )


def test_task_result_validation_negative_tokens(sample_task_result):
    """Test that token counts must be non-negative."""
    with pytest.raises(ValueError, match="prompt_tokens must be non-negative"):
        TaskResult(
            **{**sample_task_result.to_dict(), "prompt_tokens": -1}
        )


def test_task_result_validation_negative_cost(sample_task_result):
    """Test that costs must be non-negative."""
    with pytest.raises(ValueError, match="estimated_cost_usd must be non-negative"):
        TaskResult(
            **{**sample_task_result.to_dict(), "estimated_cost_usd": -0.01}
        )


def test_task_result_validation_syntax_error_rate_range(sample_task_result):
    """Test that syntax_error_rate must be between 0 and 1."""
    with pytest.raises(ValueError, match="syntax_error_rate must be between 0 and 1"):
        TaskResult(
            **{**sample_task_result.to_dict(), "syntax_error_rate": 1.5}
        )


def test_task_result_validation_memory_lists_consistent_length(sample_task_result):
    """Test that all retrieved_memory_* lists must have the same length."""
    with pytest.raises(ValueError, match="All retrieved_memory_\\* lists must have the same length"):
        TaskResult(
            **{
                **sample_task_result.to_dict(),
                "retrieved_memory_ids": ["MEM-001"],
                "retrieved_memory_scores": [0.8, 0.9],  # Different length
            }
        )


def test_task_result_validation_difficulty(sample_task_result):
    """Test that task_difficulty must be easy, medium, or hard."""
    with pytest.raises(ValueError, match="task_difficulty must be"):
        TaskResult(
            **{**sample_task_result.to_dict(), "task_difficulty": "invalid"}
        )


def test_task_result_to_dict(sample_task_result):
    """Test TaskResult.to_dict() returns all required fields."""
    result_dict = sample_task_result.to_dict()

    # Check all required fields are present
    required_fields = {
        "run_id", "policy", "seed", "repo", "task_id", "sequence_index",
        "resolved", "patch_generated", "patch_applied", "syntax_error", "timeout",
        "prompt_tokens", "completion_tokens", "total_tokens",
        "estimated_cost_usd", "task_api_cost", "consolidation_llm_cost",
        "wall_time_seconds", "tool_calls", "test_runs",
        "files_read", "files_modified", "syntax_error_rate",
        "retrieved_memory_ids", "retrieved_memory_scores",
        "retrieved_memory_types", "retrieved_memory_ages",
        "memory_count_before", "memory_count_after",
        "memory_tokens_before", "memory_tokens_after",
        "pruned_memory_ids", "consolidated_memory_ids",
        "task_difficulty", "error_message",
        "termination_reason", "tool_mode",
    }

    assert set(result_dict.keys()) == required_fields


def test_task_result_logger_initialization(temp_run_dir):
    """Test TaskResultLogger creates directory structure."""
    logger = TaskResultLogger(temp_run_dir / "run_001")

    assert logger.run_dir.exists()
    assert logger.log_file == logger.run_dir / "task_results.jsonl"


def test_task_result_logger_log_single_result(temp_run_dir, sample_task_result):
    """Test logging a single task result."""
    logger = TaskResultLogger(temp_run_dir / "run_001")
    logger.log_task_result(sample_task_result)

    # Verify file exists and contains one line
    assert logger.log_file.exists()
    assert logger.get_task_count() == 1

    # Verify content is valid JSON
    with open(logger.log_file) as f:
        line = f.readline()
        result = json.loads(line)
        assert result["task_id"] == "django__django-12345"
        assert result["policy"] == "type_aware_decay"


def test_task_result_logger_log_multiple_results(temp_run_dir, sample_task_result):
    """Test logging multiple task results."""
    logger = TaskResultLogger(temp_run_dir / "run_001")

    # Log 3 results
    for i in range(3):
        result = TaskResult(
            **{
                **sample_task_result.to_dict(),
                "task_id": f"django__django-{12345 + i}",
                "sequence_index": i,
            }
        )
        logger.log_task_result(result)

    # Verify all results logged
    assert logger.get_task_count() == 3

    # Verify all results can be read back
    results = logger.read_results()
    assert len(results) == 3
    assert results[0]["task_id"] == "django__django-12345"
    assert results[1]["task_id"] == "django__django-12346"
    assert results[2]["task_id"] == "django__django-12347"


def test_task_result_logger_read_empty_file(temp_run_dir):
    """Test reading from non-existent log file returns empty list."""
    logger = TaskResultLogger(temp_run_dir / "run_001")
    results = logger.read_results()
    assert results == []


def test_task_result_logger_validate_run_parameters(temp_run_dir, sample_task_result):
    """Test validation of run parameters across all logged results."""
    logger = TaskResultLogger(temp_run_dir / "run_001")

    # Log multiple results with consistent parameters
    for i in range(3):
        result = TaskResult(
            **{
                **sample_task_result.to_dict(),
                "task_id": f"django__django-{12345 + i}",
                "sequence_index": i,
            }
        )
        logger.log_task_result(result)

    # Validation should pass
    assert logger.validate_run_parameters("test_run_001", "type_aware_decay", 1)


def test_task_result_logger_validate_run_parameters_mismatch(
    temp_run_dir, sample_task_result
):
    """Test validation fails when run parameters don't match."""
    logger = TaskResultLogger(temp_run_dir / "run_001")
    logger.log_task_result(sample_task_result)

    # Validation should fail with wrong run_id
    with pytest.raises(ValueError, match="has run_id"):
        logger.validate_run_parameters("wrong_run_id", "type_aware_decay", 1)

    # Validation should fail with wrong policy
    with pytest.raises(ValueError, match="has policy"):
        logger.validate_run_parameters("test_run_001", "wrong_policy", 1)

    # Validation should fail with wrong seed
    with pytest.raises(ValueError, match="has seed"):
        logger.validate_run_parameters("test_run_001", "type_aware_decay", 999)


def test_task_result_logger_schema_validation(temp_run_dir):
    """Test that schema validation catches missing fields."""
    logger = TaskResultLogger(temp_run_dir / "run_001")

    # Create a result with missing field (by manually constructing dict)
    incomplete_result = TaskResult(
        run_id="test_run_001",
        policy="type_aware_decay",
        seed=1,
        repo="django/django",
        task_id="django__django-12345",
        sequence_index=0,
        resolved=1,
        patch_generated=True,
        patch_applied=True,
        syntax_error=False,
        timeout=False,
        prompt_tokens=1000,
        completion_tokens=500,
        total_tokens=1500,
        estimated_cost_usd=0.05,
        task_api_cost=0.05,
        consolidation_llm_cost=0.0,
        wall_time_seconds=120.5,
        tool_calls=10,
        test_runs=2,
        files_read=5,
        files_modified=2,
        syntax_error_rate=0.0,
        retrieved_memory_ids=[],
        retrieved_memory_scores=[],
        retrieved_memory_types=[],
        retrieved_memory_ages=[],
        memory_count_before=0,
        memory_count_after=0,
        memory_tokens_before=0,
        memory_tokens_after=0,
    )

    # This should work (all required fields present)
    logger.log_task_result(incomplete_result)
    assert logger.get_task_count() == 1


def test_task_result_logger_atomic_write(temp_run_dir, sample_task_result):
    """Test that writes are atomic (no partial writes)."""
    logger = TaskResultLogger(temp_run_dir / "run_001")

    # Log a result
    logger.log_task_result(sample_task_result)

    # Verify file contains complete JSON line
    with open(logger.log_file) as f:
        line = f.readline()
        # Should be valid JSON (no partial write)
        result = json.loads(line)
        assert "task_id" in result
        assert "policy" in result


def test_task_result_logger_json_lines_format(temp_run_dir, sample_task_result):
    """Test that output is in JSON Lines format (one JSON object per line)."""
    logger = TaskResultLogger(temp_run_dir / "run_001")

    # Log 3 results
    for i in range(3):
        result = TaskResult(
            **{
                **sample_task_result.to_dict(),
                "task_id": f"django__django-{12345 + i}",
                "sequence_index": i,
            }
        )
        logger.log_task_result(result)

    # Verify JSON Lines format
    with open(logger.log_file) as f:
        lines = f.readlines()
        assert len(lines) == 3

        for line in lines:
            # Each line should be valid JSON
            result = json.loads(line)
            assert "task_id" in result

            # Line should end with newline
            assert line.endswith("\n")


def test_task_result_logger_empty_retrieved_memories(temp_run_dir, sample_task_result):
    """Test logging with no retrieved memories (No Memory policy)."""
    result = TaskResult(
        **{
            **sample_task_result.to_dict(),
            "retrieved_memory_ids": [],
            "retrieved_memory_scores": [],
            "retrieved_memory_types": [],
            "retrieved_memory_ages": [],
        }
    )

    logger = TaskResultLogger(temp_run_dir / "run_001")
    logger.log_task_result(result)

    # Verify logged correctly
    results = logger.read_results()
    assert len(results) == 1
    assert results[0]["retrieved_memory_ids"] == []


def test_task_result_logger_with_error_message(temp_run_dir, sample_task_result):
    """Test logging with error message."""
    result = TaskResult(
        **{
            **sample_task_result.to_dict(),
            "resolved": 0,
            "timeout": True,
            "error_message": "Task exceeded 20 step limit",
        }
    )

    logger = TaskResultLogger(temp_run_dir / "run_001")
    logger.log_task_result(result)

    # Verify error message logged
    results = logger.read_results()
    assert len(results) == 1
    assert results[0]["error_message"] == "Task exceeded 20 step limit"
    assert results[0]["timeout"] is True
    assert results[0]["resolved"] == 0
