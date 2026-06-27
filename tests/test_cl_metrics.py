"""Tests for continual learning metrics.

Tests the CL metrics implementation for computing Plasticity, Stability, CL-F1,
Forward Transfer, and Backward Transfer from accuracy matrices.

Requirements: 19
"""

import json

import numpy as np
import pytest

from src.benchmark.cl_metrics import (
    AnchorProbeCLMetrics,
    CLMetrics,
    build_accuracy_matrix,
    compute_anchor_probe_cl_metrics,
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


# ---------------------------------------------------------------------------
# Anchor-probe CL metrics (THESIS_FINAL_v5.md §14.2 — PRIMARY estimator)
# ---------------------------------------------------------------------------


def test_anchor_probe_known_forgetting():
    """Anchor-probe metrics with hand-computed forgetting.

    Per §14.2:
      CL_Plasticity        = mean(a_{i,i} for all tasks i)
      end_acc              = mean(a_{i,T} for anchors i in A)
      forgetting_i         = max(a_{i,p} for probes p>=i) - a_{i,T}
      CL_Stability_anchor  = 1 - mean(forgetting_i for i in A)
      CL_F1                = 2*P*S / max(P+S, 1e-8)

    Construct T=10 with online diagonal having 6/10 resolved
    (Plasticity = 0.6). Anchors at the §14.2 positions for T=10:
      {ceil(T/10), ceil(3T/10), ceil(5T/10), ceil(7T/10), ceil(9T/10)}
      = {1, 3, 5, 7, 9}.
    Probe points for T=10:
      {ceil(T/4), ceil(T/2), ceil(3T/4), T} = {3, 5, 8, 10} but probe
    columns are passed explicitly (0-indexed columns the runner snapshots).
    """
    n_tasks = 10
    # Online diagonal a_{i,i}: resolve tasks 1,3,5,7,9 and task 0.
    online_resolved = [1, 0, 0, 1, 0, 1, 0, 1, 0, 1]
    # Plasticity = mean = 5/10? recount: indices resolved -> 0,3,5,7,9 = 5 -> 0.5
    # Actually: [1,0,0,1,0,1,0,1,0,1] -> ones at 0,3,5,7,9 = 5 ones -> 0.5

    anchor_indices = [1, 3, 5, 7, 9]
    # Use last column index 9 as the final probe T (0-indexed final task).
    final_probe = 9
    probe_points = [2, 4, 6, final_probe]

    # probed_accuracy[(i, p)] = a_{i,p} for i in A, p in probe_points, p >= i.
    # Anchor 1: peak 1.0 at some probe, final a_{1,9}=0.0 -> forgetting 1.0
    # Anchor 3: peak 1.0, final a_{3,9}=1.0 -> forgetting 0.0
    # Anchor 5: peak 1.0, final a_{5,9}=0.0 -> forgetting 1.0
    # Anchor 7: peak 1.0, final a_{7,9}=1.0 -> forgetting 0.0
    # Anchor 9: only final probe; a_{9,9}=1.0 -> forgetting 0.0
    probed_accuracy = {
        (1, 2): 1.0, (1, 4): 1.0, (1, 6): 0.0, (1, 9): 0.0,
        (3, 4): 1.0, (3, 6): 1.0, (3, 9): 1.0,
        (5, 6): 1.0, (5, 9): 0.0,
        (7, 9): 1.0,
        (9, 9): 1.0,
    }

    metrics = compute_anchor_probe_cl_metrics(
        online_resolved=online_resolved,
        anchor_indices=anchor_indices,
        probe_points=probe_points,
        probed_accuracy=probed_accuracy,
        n_tasks=n_tasks,
    )

    assert isinstance(metrics, AnchorProbeCLMetrics)
    # Plasticity = 5/10
    assert abs(metrics.plasticity - 0.5) < 1e-9
    # end_acc on anchors: a_{1,9}=0, a_{3,9}=1, a_{5,9}=0, a_{7,9}=1, a_{9,9}=1 -> 3/5
    assert abs(metrics.end_accuracy - 0.6) < 1e-9
    # forgetting per anchor: [1.0, 0.0, 1.0, 0.0, 0.0] -> mean 0.4
    # Stability = 1 - 0.4 = 0.6
    assert abs(metrics.stability - 0.6) < 1e-9
    # CL_F1 = 2*0.5*0.6/(0.5+0.6) = 0.6/1.1
    assert abs(metrics.cl_f1 - (2 * 0.5 * 0.6 / 1.1)) < 1e-9
    assert metrics.n_tasks == 10
    assert metrics.n_anchors == 5


def test_anchor_probe_no_forgetting_perfect_stability():
    """No forgetting -> Stability = 1.0, CL_F1 = harmonic mean with plasticity."""
    n_tasks = 4
    online_resolved = [1, 1, 1, 1]  # Plasticity = 1.0
    anchor_indices = [0, 1, 2, 3]
    probe_points = [1, 3]
    # Every anchor stays resolved at the final probe -> zero forgetting.
    probed_accuracy = {
        (0, 1): 1.0, (0, 3): 1.0,
        (1, 1): 1.0, (1, 3): 1.0,
        (2, 3): 1.0,
        (3, 3): 1.0,
    }

    metrics = compute_anchor_probe_cl_metrics(
        online_resolved=online_resolved,
        anchor_indices=anchor_indices,
        probe_points=probe_points,
        probed_accuracy=probed_accuracy,
        n_tasks=n_tasks,
    )

    assert metrics.plasticity == 1.0
    assert metrics.stability == 1.0
    assert metrics.cl_f1 == 1.0


def test_anchor_probe_complete_forgetting_zero_stability():
    """Total forgetting on every anchor -> Stability = 0.0 -> CL_F1 = 0.0."""
    n_tasks = 4
    online_resolved = [1, 1, 1, 1]  # Plasticity = 1.0
    anchor_indices = [0, 1]
    probe_points = [1, 3]
    # Anchor 0: peak 1.0 (at probe 1), final 0.0 -> forgetting 1.0
    # Anchor 1: peak 1.0 (at probe 1), final 0.0 -> forgetting 1.0
    probed_accuracy = {
        (0, 1): 1.0, (0, 3): 0.0,
        (1, 1): 1.0, (1, 3): 0.0,
    }

    metrics = compute_anchor_probe_cl_metrics(
        online_resolved=online_resolved,
        anchor_indices=anchor_indices,
        probe_points=probe_points,
        probed_accuracy=probed_accuracy,
        n_tasks=n_tasks,
    )

    assert metrics.plasticity == 1.0
    assert metrics.stability == 0.0
    # CL_F1 = 2*1*0 / max(1, 1e-8) = 0.0
    assert metrics.cl_f1 == 0.0


def test_anchor_probe_forgetting_clamped_nonnegative():
    """If a later probe exceeds the peak-before-final, forgetting is the
    max-over-probes minus final; a recovered anchor cannot yield negative
    forgetting because the final IS one of the probes (so max >= final)."""
    n_tasks = 3
    online_resolved = [1, 1, 1]
    anchor_indices = [0]
    probe_points = [1, 2]
    # Anchor 0 dropped at probe 1 then recovered at final probe 2.
    # max(a_{0,1}=0.0, a_{0,2}=1.0) = 1.0; final a_{0,2}=1.0 -> forgetting 0.0
    probed_accuracy = {(0, 1): 0.0, (0, 2): 1.0}

    metrics = compute_anchor_probe_cl_metrics(
        online_resolved=online_resolved,
        anchor_indices=anchor_indices,
        probe_points=probe_points,
        probed_accuracy=probed_accuracy,
        n_tasks=n_tasks,
    )

    assert metrics.stability == 1.0


def test_anchor_probe_to_dict():
    """AnchorProbeCLMetrics serializes to a JSON-friendly dict."""
    metrics = compute_anchor_probe_cl_metrics(
        online_resolved=[1, 0, 1, 1],
        anchor_indices=[0, 3],
        probe_points=[1, 3],
        probed_accuracy={(0, 1): 1.0, (0, 3): 1.0, (3, 3): 1.0},
        n_tasks=4,
    )
    d = metrics.to_dict()
    for key in (
        "plasticity",
        "stability",
        "cl_f1",
        "end_accuracy",
        "n_tasks",
        "n_anchors",
    ):
        assert key in d
    assert isinstance(d["cl_f1"], float)
    assert isinstance(d["n_tasks"], int)


def test_anchor_probe_empty_anchors_raises():
    """No anchors -> cannot estimate anchor stability."""
    with pytest.raises(ValueError, match="at least one anchor"):
        compute_anchor_probe_cl_metrics(
            online_resolved=[1, 1],
            anchor_indices=[],
            probe_points=[1],
            probed_accuracy={},
            n_tasks=2,
        )


def test_anchor_probe_missing_final_cell_raises():
    """A final-probe cell a_{i,T} is mandatory for each anchor."""
    with pytest.raises(ValueError, match="final-probe accuracy"):
        compute_anchor_probe_cl_metrics(
            online_resolved=[1, 1, 1],
            anchor_indices=[0],
            probe_points=[1, 2],
            probed_accuracy={(0, 1): 1.0},  # missing (0, 2) final cell
            n_tasks=3,
        )
