"""Tests for continual learning metrics.

Tests the CL metrics implementation for computing Plasticity, Stability, CL-F1,
Forward Transfer, and Backward Transfer from accuracy matrices.

Requirements: 19
"""

import json

import numpy as np
import pytest

from src.benchmark.cl_metrics import (
    CLMetrics,
    build_accuracy_matrix,
    compute_backward_transfer,
    compute_cl_f1,
    compute_cl_metrics,
    compute_cl_metrics_from_run,
    compute_end_accuracy,
    compute_forward_transfer,
    compute_mean_forgetting,
    compute_plasticity,
    compute_stability,
    load_task_results,
    validate_learning_occurred,
)


@pytest.fixture
def sample_task_results():
    """Create sample task results for testing."""
    return [
        {
            "run_id": "test_run_001",
            "policy": "type_aware_decay",
            "seed": 1,
            "repo": "django/django",
            "task_id": "django__django-001",
            "sequence_index": 0,
            "resolved": 1,  # Task 0 resolved
            "patch_generated": True,
            "patch_applied": True,
            "syntax_error": False,
            "timeout": False,
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "total_tokens": 1500,
            "estimated_cost_usd": 0.01,
            "task_api_cost": 0.01,
            "consolidation_llm_cost": 0.0,
            "wall_time_seconds": 120.0,
            "tool_calls": 10,
            "test_runs": 2,
            "files_read": 5,
            "files_modified": 2,
            "syntax_error_rate": 0.0,
            "retrieved_memory_ids": [],
            "retrieved_memory_scores": [],
            "retrieved_memory_types": [],
            "retrieved_memory_ages": [],
            "memory_count_before": 0,
            "memory_count_after": 1,
            "memory_tokens_before": 0,
            "memory_tokens_after": 500,
            "pruned_memory_ids": [],
            "consolidated_memory_ids": [],
            "task_difficulty": "medium",
            "error_message": None,
        },
        {
            "run_id": "test_run_001",
            "policy": "type_aware_decay",
            "seed": 1,
            "repo": "django/django",
            "task_id": "django__django-002",
            "sequence_index": 1,
            "resolved": 1,  # Task 1 resolved
            "patch_generated": True,
            "patch_applied": True,
            "syntax_error": False,
            "timeout": False,
            "prompt_tokens": 1200,
            "completion_tokens": 600,
            "total_tokens": 1800,
            "estimated_cost_usd": 0.012,
            "task_api_cost": 0.012,
            "consolidation_llm_cost": 0.0,
            "wall_time_seconds": 150.0,
            "tool_calls": 12,
            "test_runs": 3,
            "files_read": 6,
            "files_modified": 3,
            "syntax_error_rate": 0.0,
            "retrieved_memory_ids": ["mem_001"],
            "retrieved_memory_scores": [0.85],
            "retrieved_memory_types": ["bug_fix"],
            "retrieved_memory_ages": [1],
            "memory_count_before": 1,
            "memory_count_after": 2,
            "memory_tokens_before": 500,
            "memory_tokens_after": 1000,
            "pruned_memory_ids": [],
            "consolidated_memory_ids": [],
            "task_difficulty": "medium",
            "error_message": None,
        },
        {
            "run_id": "test_run_001",
            "policy": "type_aware_decay",
            "seed": 1,
            "repo": "django/django",
            "task_id": "django__django-003",
            "sequence_index": 2,
            "resolved": 0,  # Task 2 failed
            "patch_generated": True,
            "patch_applied": True,
            "syntax_error": False,
            "timeout": False,
            "prompt_tokens": 1500,
            "completion_tokens": 700,
            "total_tokens": 2200,
            "estimated_cost_usd": 0.015,
            "task_api_cost": 0.015,
            "consolidation_llm_cost": 0.0,
            "wall_time_seconds": 180.0,
            "tool_calls": 15,
            "test_runs": 4,
            "files_read": 8,
            "files_modified": 4,
            "syntax_error_rate": 0.0,
            "retrieved_memory_ids": ["mem_001", "mem_002"],
            "retrieved_memory_scores": [0.82, 0.75],
            "retrieved_memory_types": ["bug_fix", "api_change"],
            "retrieved_memory_ages": [2, 1],
            "memory_count_before": 2,
            "memory_count_after": 3,
            "memory_tokens_before": 1000,
            "memory_tokens_after": 1500,
            "pruned_memory_ids": [],
            "consolidated_memory_ids": [],
            "task_difficulty": "hard",
            "error_message": "Test failed: assertion error",
        },
    ]


@pytest.fixture
def temp_run_dir(tmp_path):
    """Create a temporary run directory."""
    return tmp_path / "runs"


def test_load_task_results(temp_run_dir, sample_task_results):
    """Test loading task results from task_results.jsonl."""
    run_dir = temp_run_dir / "run_001"
    run_dir.mkdir(parents=True)

    # Write task results to file
    results_file = run_dir / "task_results.jsonl"
    with open(results_file, "w", encoding="utf-8") as f:
        for result in sample_task_results:
            f.write(json.dumps(result) + "\n")

    # Load results
    loaded_results = load_task_results(run_dir)

    assert len(loaded_results) == 3
    assert loaded_results[0]["task_id"] == "django__django-001"
    assert loaded_results[1]["task_id"] == "django__django-002"
    assert loaded_results[2]["task_id"] == "django__django-003"


def test_load_task_results_file_not_found(temp_run_dir):
    """Test loading from non-existent directory raises FileNotFoundError."""
    run_dir = temp_run_dir / "nonexistent"

    with pytest.raises(FileNotFoundError, match="task_results.jsonl not found"):
        load_task_results(run_dir)


def test_load_task_results_empty_file(temp_run_dir):
    """Test loading from empty file raises ValueError."""
    run_dir = temp_run_dir / "run_001"
    run_dir.mkdir(parents=True)

    # Create empty file
    results_file = run_dir / "task_results.jsonl"
    results_file.touch()

    with pytest.raises(ValueError, match="No task results found"):
        load_task_results(run_dir)


def test_load_task_results_invalid_json(temp_run_dir):
    """Test loading invalid JSON raises ValueError."""
    run_dir = temp_run_dir / "run_001"
    run_dir.mkdir(parents=True)

    # Write invalid JSON
    results_file = run_dir / "task_results.jsonl"
    with open(results_file, "w", encoding="utf-8") as f:
        f.write("not valid json\n")

    with pytest.raises(ValueError, match="Invalid JSON on line"):
        load_task_results(run_dir)


def test_build_accuracy_matrix(sample_task_results):
    """Test building accuracy matrix from task results."""
    accuracy_matrix = build_accuracy_matrix(sample_task_results)

    # Check shape
    assert accuracy_matrix.shape == (3, 3)

    # Check diagonal (immediate accuracy on each task)
    assert accuracy_matrix[0, 0] == 1.0  # Task 0 resolved
    assert accuracy_matrix[1, 1] == 1.0  # Task 1 resolved
    assert accuracy_matrix[2, 2] == 0.0  # Task 2 failed

    # Check that resolved tasks propagate forward (optimistic assumption)
    assert accuracy_matrix[0, 1] == 1.0  # Task 0 still resolved after task 1
    assert accuracy_matrix[0, 2] == 1.0  # Task 0 still resolved after task 2
    assert accuracy_matrix[1, 2] == 1.0  # Task 1 still resolved after task 2


def test_build_accuracy_matrix_empty_results():
    """Test building matrix from empty results raises ValueError."""
    with pytest.raises(ValueError, match="task_results cannot be empty"):
        build_accuracy_matrix([])


def test_build_accuracy_matrix_inconsistent_indices(sample_task_results):
    """Test building matrix with inconsistent sequence indices raises ValueError."""
    # Modify sequence index to be inconsistent
    bad_results = sample_task_results.copy()
    bad_results[1]["sequence_index"] = 5  # Should be 1

    with pytest.raises(ValueError, match="expected 1"):
        build_accuracy_matrix(bad_results)


def test_validate_learning_occurred():
    """Test validation passes when sufficient learning occurred."""
    # Matrix with good learning (2/3 tasks resolved)
    accuracy_matrix = np.array(
        [[1.0, 1.0, 1.0], [0.0, 1.0, 1.0], [0.0, 0.0, 0.0]], dtype=np.float64
    )

    # Should not raise
    validate_learning_occurred(accuracy_matrix, min_diagonal_mean=0.05)


def test_validate_learning_occurred_fails():
    """Test validation fails when insufficient learning occurred."""
    # Matrix with no learning (all zeros)
    accuracy_matrix = np.zeros((3, 3), dtype=np.float64)

    with pytest.raises(ValueError, match="Insufficient learning detected"):
        validate_learning_occurred(accuracy_matrix, min_diagonal_mean=0.05)


def test_compute_plasticity():
    """Test computing plasticity from accuracy matrix."""
    # Matrix with 2/3 tasks resolved immediately
    accuracy_matrix = np.array(
        [[1.0, 1.0, 1.0], [0.0, 1.0, 1.0], [0.0, 0.0, 0.0]], dtype=np.float64
    )

    plasticity = compute_plasticity(accuracy_matrix)

    # Plasticity = mean of diagonal = (1.0 + 1.0 + 0.0) / 3 = 0.667
    assert abs(plasticity - 0.6667) < 0.001


def test_compute_plasticity_perfect():
    """Test computing plasticity with perfect learning."""
    # All tasks resolved immediately
    accuracy_matrix = np.array(
        [[1.0, 1.0, 1.0], [0.0, 1.0, 1.0], [0.0, 0.0, 1.0]], dtype=np.float64
    )

    plasticity = compute_plasticity(accuracy_matrix)

    assert plasticity == 1.0


def test_compute_plasticity_zero():
    """Test computing plasticity with no learning."""
    # No tasks resolved
    accuracy_matrix = np.zeros((3, 3), dtype=np.float64)

    plasticity = compute_plasticity(accuracy_matrix)

    assert plasticity == 0.0


def test_compute_stability():
    """Test computing stability from accuracy matrix."""
    # Matrix with some forgetting
    # Task 0 resolved, stays resolved
    # Task 1 resolved, stays resolved
    # Task 2 failed
    accuracy_matrix = np.array(
        [[1.0, 1.0, 1.0], [0.0, 1.0, 1.0], [0.0, 0.0, 0.0]], dtype=np.float64
    )

    stability = compute_stability(accuracy_matrix)

    # Lower triangle: a[1,0]=0.0, a[2,0]=0.0, a[2,1]=0.0
    # Stability = mean([0.0, 0.0, 0.0]) = 0.0
    assert stability == 0.0


def test_compute_stability_perfect():
    """Test computing stability with perfect retention."""
    # All tasks resolved and retained
    accuracy_matrix = np.array(
        [[1.0, 1.0, 1.0], [0.0, 1.0, 1.0], [0.0, 0.0, 1.0]], dtype=np.float64
    )

    # Manually set lower triangle to show perfect retention
    accuracy_matrix[1, 0] = 1.0  # Task 0 still resolved after task 1
    accuracy_matrix[2, 0] = 1.0  # Task 0 still resolved after task 2
    accuracy_matrix[2, 1] = 1.0  # Task 1 still resolved after task 2

    stability = compute_stability(accuracy_matrix)

    # Lower triangle: a[1,0]=1.0, a[2,0]=1.0, a[2,1]=1.0
    # Stability = mean([1.0, 1.0, 1.0]) = 1.0
    assert stability == 1.0


def test_compute_stability_single_task():
    """Test computing stability with single task raises ValueError."""
    # Single task has no lower triangle
    accuracy_matrix = np.array([[1.0]], dtype=np.float64)

    with pytest.raises(ValueError, match="fewer than 2 tasks"):
        compute_stability(accuracy_matrix)


def test_compute_cl_f1():
    """Test computing CL-F1 from plasticity and stability."""
    plasticity = 0.8
    stability = 0.6

    cl_f1 = compute_cl_f1(plasticity, stability)

    # CL-F1 = 2 * (0.8 * 0.6) / (0.8 + 0.6) = 2 * 0.48 / 1.4 = 0.6857
    assert abs(cl_f1 - 0.6857) < 0.001


def test_compute_cl_f1_perfect():
    """Test computing CL-F1 with perfect scores."""
    plasticity = 1.0
    stability = 1.0

    cl_f1 = compute_cl_f1(plasticity, stability)

    assert cl_f1 == 1.0


def test_compute_cl_f1_zero():
    """Test computing CL-F1 with zero scores."""
    plasticity = 0.0
    stability = 0.0

    cl_f1 = compute_cl_f1(plasticity, stability)

    assert cl_f1 == 0.0


def test_compute_cl_f1_one_zero():
    """Test computing CL-F1 when one score is zero."""
    plasticity = 0.8
    stability = 0.0

    cl_f1 = compute_cl_f1(plasticity, stability)

    # CL-F1 = 2 * (0.8 * 0.0) / (0.8 + 0.0) = 0.0
    assert cl_f1 == 0.0


def test_compute_forward_transfer():
    """Test computing forward transfer."""
    # Matrix with good learning
    accuracy_matrix = np.array(
        [[1.0, 1.0, 1.0], [0.0, 1.0, 1.0], [0.0, 0.0, 0.8]], dtype=np.float64
    )

    forward_transfer = compute_forward_transfer(accuracy_matrix)

    # FT = Plasticity - baseline = (1.0 + 1.0 + 0.8) / 3 - 0.0 = 0.933
    assert abs(forward_transfer - 0.9333) < 0.001


def test_compute_backward_transfer():
    """Test computing backward transfer."""
    # Matrix with some forgetting
    accuracy_matrix = np.array(
        [[1.0, 1.0, 0.8],  # Task 0: resolved, then forgot a bit
         [0.0, 1.0, 0.9],  # Task 1: resolved, then forgot a bit
         [0.0, 0.0, 1.0]], # Task 2: resolved
        dtype=np.float64
    )

    backward_transfer = compute_backward_transfer(accuracy_matrix)

    # BT = mean(final - diagonal for i < T)
    # Task 0: 0.8 - 1.0 = -0.2
    # Task 1: 0.9 - 1.0 = -0.1
    # BT = mean([-0.2, -0.1]) = -0.15
    assert abs(backward_transfer - (-0.15)) < 0.001


def test_compute_backward_transfer_no_forgetting():
    """Test computing backward transfer with no forgetting."""
    # All tasks retained perfectly
    accuracy_matrix = np.array(
        [[1.0, 1.0, 1.0], [0.0, 1.0, 1.0], [0.0, 0.0, 1.0]], dtype=np.float64
    )

    backward_transfer = compute_backward_transfer(accuracy_matrix)

    # BT = mean([1.0 - 1.0, 1.0 - 1.0]) = 0.0
    assert backward_transfer == 0.0


def test_compute_backward_transfer_single_task():
    """Test computing backward transfer with single task raises ValueError."""
    accuracy_matrix = np.array([[1.0]], dtype=np.float64)

    with pytest.raises(ValueError, match="fewer than 2 tasks"):
        compute_backward_transfer(accuracy_matrix)


def test_compute_end_accuracy():
    """Test computing end-of-sequence accuracy."""
    # Matrix with final column showing end accuracy
    accuracy_matrix = np.array(
        [[1.0, 1.0, 0.8], [0.0, 1.0, 0.9], [0.0, 0.0, 1.0]], dtype=np.float64
    )

    end_accuracy = compute_end_accuracy(accuracy_matrix)

    # End accuracy = mean of final column = (0.8 + 0.9 + 1.0) / 3 = 0.9
    assert abs(end_accuracy - 0.9) < 0.001


def test_compute_mean_forgetting():
    """Test computing mean forgetting."""
    # Matrix with some forgetting
    accuracy_matrix = np.array(
        [[1.0, 1.0, 0.8],  # Task 0: peak 1.0, final 0.8, forgetting 0.2
         [0.0, 1.0, 0.9],  # Task 1: peak 1.0, final 0.9, forgetting 0.1
         [0.0, 0.0, 1.0]], # Task 2: peak 1.0, final 1.0, forgetting 0.0
        dtype=np.float64
    )

    mean_forgetting = compute_mean_forgetting(accuracy_matrix)

    # Mean forgetting = (0.2 + 0.1 + 0.0) / 3 = 0.1
    assert abs(mean_forgetting - 0.1) < 0.001


def test_compute_mean_forgetting_no_forgetting():
    """Test computing mean forgetting with no forgetting."""
    # All tasks retained perfectly
    accuracy_matrix = np.array(
        [[1.0, 1.0, 1.0], [0.0, 1.0, 1.0], [0.0, 0.0, 1.0]], dtype=np.float64
    )

    mean_forgetting = compute_mean_forgetting(accuracy_matrix)

    assert mean_forgetting == 0.0


def test_compute_cl_metrics(sample_task_results):
    """Test computing all CL metrics from task results."""
    metrics = compute_cl_metrics(sample_task_results, validate_learning=False)

    # Check all metrics are computed
    assert isinstance(metrics, CLMetrics)
    assert 0.0 <= metrics.plasticity <= 1.0
    assert 0.0 <= metrics.stability <= 1.0
    assert 0.0 <= metrics.cl_f1 <= 1.0
    assert metrics.n_tasks == 3
    assert metrics.accuracy_matrix.shape == (3, 3)

    # Check specific values based on sample data
    # Diagonal: [1.0, 1.0, 0.0] -> Plasticity = 0.667
    assert abs(metrics.plasticity - 0.6667) < 0.001


def test_compute_cl_metrics_with_validation(sample_task_results):
    """Test computing CL metrics with learning validation."""
    # Should pass validation (2/3 tasks resolved)
    metrics = compute_cl_metrics(sample_task_results, validate_learning=True)

    assert metrics.plasticity > 0.05


def test_compute_cl_metrics_validation_fails():
    """Test computing CL metrics fails validation with no learning."""
    # All tasks failed
    failed_results = [
        {
            "run_id": "test_run_001",
            "policy": "no_memory",
            "seed": 1,
            "repo": "django/django",
            "task_id": f"django__django-{i:03d}",
            "sequence_index": i,
            "resolved": 0,
            "patch_generated": False,
            "patch_applied": False,
            "syntax_error": False,
            "timeout": False,
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "total_tokens": 1500,
            "estimated_cost_usd": 0.01,
            "task_api_cost": 0.01,
            "consolidation_llm_cost": 0.0,
            "wall_time_seconds": 120.0,
            "tool_calls": 10,
            "test_runs": 2,
            "files_read": 5,
            "files_modified": 2,
            "syntax_error_rate": 0.0,
            "retrieved_memory_ids": [],
            "retrieved_memory_scores": [],
            "retrieved_memory_types": [],
            "retrieved_memory_ages": [],
            "memory_count_before": 0,
            "memory_count_after": 0,
            "memory_tokens_before": 0,
            "memory_tokens_after": 0,
            "pruned_memory_ids": [],
            "consolidated_memory_ids": [],
            "task_difficulty": "hard",
            "error_message": "All tasks failed",
        }
        for i in range(3)
    ]

    with pytest.raises(ValueError, match="Insufficient learning detected"):
        compute_cl_metrics(failed_results, validate_learning=True)


def test_compute_cl_metrics_from_run(temp_run_dir, sample_task_results):
    """Test computing CL metrics directly from run directory."""
    run_dir = temp_run_dir / "run_001"
    run_dir.mkdir(parents=True)

    # Write task results to file
    results_file = run_dir / "task_results.jsonl"
    with open(results_file, "w", encoding="utf-8") as f:
        for result in sample_task_results:
            f.write(json.dumps(result) + "\n")

    # Compute metrics from run directory
    metrics = compute_cl_metrics_from_run(run_dir, validate_learning=False)

    assert isinstance(metrics, CLMetrics)
    assert metrics.n_tasks == 3


def test_cl_metrics_to_dict(sample_task_results):
    """Test converting CLMetrics to dictionary."""
    metrics = compute_cl_metrics(sample_task_results, validate_learning=False)

    metrics_dict = metrics.to_dict()

    # Check all fields are present
    assert "plasticity" in metrics_dict
    assert "stability" in metrics_dict
    assert "cl_f1" in metrics_dict
    assert "forward_transfer" in metrics_dict
    assert "backward_transfer" in metrics_dict
    assert "end_accuracy" in metrics_dict
    assert "mean_forgetting" in metrics_dict
    assert "accuracy_matrix" in metrics_dict
    assert "n_tasks" in metrics_dict

    # Check types
    assert isinstance(metrics_dict["plasticity"], float)
    assert isinstance(metrics_dict["accuracy_matrix"], list)
    assert isinstance(metrics_dict["n_tasks"], int)

    # Check accuracy matrix is serializable
    assert len(metrics_dict["accuracy_matrix"]) == 3
    assert len(metrics_dict["accuracy_matrix"][0]) == 3
