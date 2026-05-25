"""Continual Learning metrics for the memory pruning research system.

This module implements the construction of accuracy matrices and computation
of continual learning metrics (Plasticity, Stability, CL-F1, Forward Transfer,
Backward Transfer) as specified in THESIS_FINAL_v5.md §14.2.

Requirements: 19

Frozen Invariants:
- Accuracy matrix a_{i,j} where a_{i,j} is accuracy on task i after training through task j
- Plasticity = mean of diagonal elements (accuracy on current task immediately after learning)
- Stability = mean of lower-triangular elements (accuracy on past tasks after learning new tasks)
- CL-F1 = 2 × (Plasticity × Stability) / (Plasticity + Stability)
- Validate minimum learning occurred before computing CL metrics
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt


@dataclass
class CLMetrics:
    """
    Continual Learning metrics computed from accuracy matrix.

    All metrics follow THESIS_FINAL_v5.md §14.2 specifications.

    Attributes:
        plasticity: Mean of diagonal elements (ability to learn new tasks)
        stability: Mean of lower-triangular elements (retention of past tasks)
        cl_f1: Harmonic mean of plasticity and stability (primary metric)
        forward_transfer: Positive transfer from past to new tasks
        backward_transfer: Measure of catastrophic forgetting
        end_accuracy: Mean accuracy on all tasks at end of sequence
        mean_forgetting: Average forgetting across all tasks
        accuracy_matrix: Full a_{i,j} matrix (rows=tasks, cols=training steps)
        n_tasks: Number of tasks in the sequence
    """

    plasticity: float
    stability: float
    cl_f1: float
    forward_transfer: float
    backward_transfer: float
    end_accuracy: float
    mean_forgetting: float
    accuracy_matrix: npt.NDArray[np.float64]
    n_tasks: int

    def to_dict(self) -> dict[str, Any]:
        """
        Convert CLMetrics to dictionary for JSON serialization.

        Returns:
            Dictionary with all metrics and accuracy matrix as nested list
        """
        return {
            "plasticity": float(self.plasticity),
            "stability": float(self.stability),
            "cl_f1": float(self.cl_f1),
            "forward_transfer": float(self.forward_transfer),
            "backward_transfer": float(self.backward_transfer),
            "end_accuracy": float(self.end_accuracy),
            "mean_forgetting": float(self.mean_forgetting),
            "accuracy_matrix": self.accuracy_matrix.tolist(),
            "n_tasks": int(self.n_tasks),
        }


def load_task_results(run_dir: str | Path) -> list[dict[str, Any]]:
    """
    Load task results from task_results.jsonl file.

    Args:
        run_dir: Directory containing task_results.jsonl (e.g., runs/{run_id})

    Returns:
        List of task result dictionaries, ordered by sequence_index

    Raises:
        FileNotFoundError: If task_results.jsonl doesn't exist
        ValueError: If task_results.jsonl is empty or malformed
    """
    run_dir = Path(run_dir)
    results_file = run_dir / "task_results.jsonl"

    if not results_file.exists():
        raise FileNotFoundError(
            f"task_results.jsonl not found in {run_dir}. "
            f"Expected path: {results_file}"
        )

    results = []
    with open(results_file, encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue  # Skip empty lines

            try:
                result = json.loads(line)
                results.append(result)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Invalid JSON on line {line_num} in {results_file}: {e.msg}"
                ) from e

    if not results:
        raise ValueError(f"No task results found in {results_file}")

    # Sort by sequence_index to ensure chronological order
    results.sort(key=lambda r: r["sequence_index"])

    return results


def build_accuracy_matrix(
    task_results: list[dict[str, Any]],
) -> npt.NDArray[np.float64]:
    """
    Construct accuracy matrix a_{i,j} from task results.

    The accuracy matrix a_{i,j} represents the accuracy on task i after
    training through task j. In this implementation:
    - a_{i,j} = 1 if task i is resolved after training through task j
    - a_{i,j} = 0 if task i is not resolved after training through task j

    Matrix structure:
    - Rows: tasks (i = 0 to n-1)
    - Columns: training steps (j = 0 to n-1)
    - Diagonal a_{i,i}: accuracy on task i immediately after learning it (Plasticity)
    - Lower triangle a_{i,j} where j > i: accuracy on past task i after learning new task j (Stability)
    - Upper triangle a_{i,j} where j < i: not applicable (task i hasn't been seen yet)

    Args:
        task_results: List of task result dictionaries, ordered by sequence_index

    Returns:
        Accuracy matrix of shape (n_tasks, n_tasks)

    Raises:
        ValueError: If task_results is empty or has inconsistent sequence indices
    """
    if not task_results:
        raise ValueError("task_results cannot be empty")

    n_tasks = len(task_results)

    # Validate sequence indices are consecutive starting from 0
    for i, result in enumerate(task_results):
        if result["sequence_index"] != i:
            raise ValueError(
                f"Task at position {i} has sequence_index {result['sequence_index']}, "
                f"expected {i}. Tasks must be ordered chronologically."
            )

    # Initialize accuracy matrix with zeros
    # a_{i,j} = accuracy on task i after training through task j
    accuracy_matrix = np.zeros((n_tasks, n_tasks), dtype=np.float64)

    # Fill the matrix
    # For each task j (column), we know the accuracy on task j itself
    # In the standard SWE-Bench-CL setup, we only evaluate each task once
    # when it arrives, so we only have diagonal entries
    for j, result in enumerate(task_results):
        # Diagonal: accuracy on task j immediately after learning it
        accuracy_matrix[j, j] = float(result["resolved"])

        # In a full re-evaluation setup, we would re-run all previous tasks
        # after each new task to fill the lower triangle. For now, we assume
        # that if a task was resolved, it remains resolved (optimistic assumption).
        # This is a simplification - the full implementation would require
        # re-evaluation infrastructure.
        #
        # TODO: Implement full re-evaluation for accurate stability measurement
        # For now, we propagate diagonal values forward (assumes no forgetting)
        for i in range(j + 1):
            if accuracy_matrix[i, i] == 1.0:
                accuracy_matrix[i, j] = 1.0

    return accuracy_matrix


def validate_learning_occurred(
    accuracy_matrix: npt.NDArray[np.float64],
    min_diagonal_mean: float = 0.05,
) -> None:
    """
    Validate that minimum learning occurred before computing CL metrics.

    This prevents computing meaningless metrics when the agent failed to
    solve any tasks (all zeros matrix).

    Args:
        accuracy_matrix: Accuracy matrix of shape (n_tasks, n_tasks)
        min_diagonal_mean: Minimum required mean of diagonal elements

    Raises:
        ValueError: If learning threshold is not met
    """
    diagonal = np.diag(accuracy_matrix)
    diagonal_mean = np.mean(diagonal)

    if diagonal_mean < min_diagonal_mean:
        raise ValueError(
            f"Insufficient learning detected: mean diagonal accuracy = {diagonal_mean:.4f}, "
            f"required minimum = {min_diagonal_mean:.4f}. "
            f"Cannot compute meaningful CL metrics when agent fails to solve tasks."
        )


def compute_plasticity(accuracy_matrix: npt.NDArray[np.float64]) -> float:
    """
    Compute Plasticity as mean of diagonal elements.

    Plasticity measures the agent's ability to learn new tasks immediately
    when they arrive. Higher plasticity = better at learning new tasks.

    Formula: Plasticity = mean(a_{i,i})

    Args:
        accuracy_matrix: Accuracy matrix of shape (n_tasks, n_tasks)

    Returns:
        Plasticity score in [0, 1]
    """
    diagonal = np.diag(accuracy_matrix)
    return float(np.mean(diagonal))


def compute_stability(accuracy_matrix: npt.NDArray[np.float64]) -> float:
    """
    Compute Stability as mean of lower-triangular elements.

    Stability measures the agent's ability to retain knowledge of past tasks
    after learning new tasks. Higher stability = less catastrophic forgetting.

    Formula: Stability = mean(a_{i,j}) for all i < j (lower triangle)

    Args:
        accuracy_matrix: Accuracy matrix of shape (n_tasks, n_tasks)

    Returns:
        Stability score in [0, 1]

    Raises:
        ValueError: If matrix has fewer than 2 tasks (no lower triangle)
    """
    n_tasks = accuracy_matrix.shape[0]

    if n_tasks < 2:
        raise ValueError(
            f"Cannot compute stability with fewer than 2 tasks (got {n_tasks}). "
            f"Stability requires a lower-triangular region."
        )

    # Extract lower triangle (excluding diagonal)
    # Lower triangle: i > j (rows below diagonal)
    lower_triangle_indices = np.tril_indices(n_tasks, k=-1)
    lower_triangle = accuracy_matrix[lower_triangle_indices]

    if len(lower_triangle) == 0:
        raise ValueError("No lower-triangular elements found in accuracy matrix")

    return float(np.mean(lower_triangle))


def compute_cl_f1(plasticity: float, stability: float) -> float:
    """
    Compute CL-F1 as harmonic mean of Plasticity and Stability.

    CL-F1 is the primary continual learning metric. It balances the ability
    to learn new tasks (plasticity) with the ability to retain past knowledge
    (stability).

    Formula: CL-F1 = 2 × (Plasticity × Stability) / (Plasticity + Stability)

    Args:
        plasticity: Plasticity score in [0, 1]
        stability: Stability score in [0, 1]

    Returns:
        CL-F1 score in [0, 1]
    """
    denominator = plasticity + stability

    # Handle edge case: both plasticity and stability are zero
    if denominator < 1e-8:
        return 0.0

    return float(2.0 * plasticity * stability / denominator)


def compute_forward_transfer(accuracy_matrix: npt.NDArray[np.float64]) -> float:
    """
    Compute Forward Transfer as measure of positive transfer from past to new tasks.

    Forward transfer measures whether learning past tasks helps with learning
    new tasks. Positive forward transfer means the agent benefits from prior
    experience.

    Formula: FT = mean(a_{i,i}) - baseline_accuracy
    where baseline_accuracy is the expected accuracy without any prior learning.

    For now, we use a simple baseline of 0.0 (random agent), so FT = Plasticity.
    A more sophisticated implementation would compare against a no-memory baseline.

    Args:
        accuracy_matrix: Accuracy matrix of shape (n_tasks, n_tasks)

    Returns:
        Forward transfer score (can be negative if prior learning hurts)
    """
    # Simplified implementation: FT = Plasticity - baseline
    # Baseline = 0.0 (random agent with no learning)
    plasticity = compute_plasticity(accuracy_matrix)
    baseline = 0.0
    return float(plasticity - baseline)


def compute_backward_transfer(accuracy_matrix: npt.NDArray[np.float64]) -> float:
    """
    Compute Backward Transfer as measure of catastrophic forgetting.

    Backward transfer measures how much the agent forgets past tasks when
    learning new tasks. Negative backward transfer indicates catastrophic
    forgetting.

    Formula: BT = mean(a_{i,T} - a_{i,i}) for all i < T
    where T is the final task index.

    Positive BT: learning new tasks improves performance on old tasks (rare)
    Zero BT: no forgetting
    Negative BT: catastrophic forgetting

    Args:
        accuracy_matrix: Accuracy matrix of shape (n_tasks, n_tasks)

    Returns:
        Backward transfer score (negative = forgetting, positive = improvement)

    Raises:
        ValueError: If matrix has fewer than 2 tasks
    """
    n_tasks = accuracy_matrix.shape[0]

    if n_tasks < 2:
        raise ValueError(
            f"Cannot compute backward transfer with fewer than 2 tasks (got {n_tasks})"
        )

    # Compare final accuracy (last column) with initial accuracy (diagonal)
    final_column = accuracy_matrix[:, -1]  # a_{i,T} for all i
    diagonal = np.diag(accuracy_matrix)  # a_{i,i} for all i

    # Only consider tasks before the final task (i < T)
    forgetting_per_task = final_column[:-1] - diagonal[:-1]

    return float(np.mean(forgetting_per_task))


def compute_end_accuracy(accuracy_matrix: npt.NDArray[np.float64]) -> float:
    """
    Compute end-of-sequence accuracy as mean of final column.

    This measures the agent's performance on all tasks after completing
    the entire sequence.

    Formula: end_accuracy = mean(a_{i,T}) for all i

    Args:
        accuracy_matrix: Accuracy matrix of shape (n_tasks, n_tasks)

    Returns:
        End accuracy score in [0, 1]
    """
    final_column = accuracy_matrix[:, -1]
    return float(np.mean(final_column))


def compute_mean_forgetting(accuracy_matrix: npt.NDArray[np.float64]) -> float:
    """
    Compute mean forgetting across all tasks.

    Forgetting for task i is defined as:
    forgetting_i = max(a_{i,i..T}) - a_{i,T}

    This measures the maximum accuracy achieved on task i during the sequence
    minus the final accuracy on task i.

    Formula: mean_forgetting = mean(forgetting_i) for all i

    Args:
        accuracy_matrix: Accuracy matrix of shape (n_tasks, n_tasks)

    Returns:
        Mean forgetting score in [0, 1] (0 = no forgetting, 1 = complete forgetting)
    """
    n_tasks = accuracy_matrix.shape[0]
    forgetting_per_task = np.zeros(n_tasks)

    for i in range(n_tasks):
        # Maximum accuracy on task i from when it was learned to the end
        max_accuracy = np.max(accuracy_matrix[i, i:])
        # Final accuracy on task i
        final_accuracy = accuracy_matrix[i, -1]
        # Forgetting = drop from peak to final
        forgetting_per_task[i] = max_accuracy - final_accuracy

    return float(np.mean(forgetting_per_task))


def compute_cl_metrics(
    task_results: list[dict[str, Any]],
    validate_learning: bool = True,
    min_diagonal_mean: float = 0.05,
) -> CLMetrics:
    """
    Compute all continual learning metrics from task results.

    This is the main entry point for CL metrics computation. It:
    1. Builds the accuracy matrix from task results
    2. Validates that learning occurred (optional)
    3. Computes all CL metrics (Plasticity, Stability, CL-F1, FT, BT)

    Args:
        task_results: List of task result dictionaries, ordered by sequence_index
        validate_learning: Whether to validate minimum learning occurred
        min_diagonal_mean: Minimum required mean diagonal accuracy

    Returns:
        CLMetrics object with all computed metrics

    Raises:
        ValueError: If task_results is invalid or learning validation fails
    """
    # Build accuracy matrix
    accuracy_matrix = build_accuracy_matrix(task_results)

    # Validate learning occurred
    if validate_learning:
        validate_learning_occurred(accuracy_matrix, min_diagonal_mean)

    # Compute all metrics
    plasticity = compute_plasticity(accuracy_matrix)
    stability = compute_stability(accuracy_matrix)
    cl_f1 = compute_cl_f1(plasticity, stability)
    forward_transfer = compute_forward_transfer(accuracy_matrix)
    backward_transfer = compute_backward_transfer(accuracy_matrix)
    end_accuracy = compute_end_accuracy(accuracy_matrix)
    mean_forgetting = compute_mean_forgetting(accuracy_matrix)

    return CLMetrics(
        plasticity=plasticity,
        stability=stability,
        cl_f1=cl_f1,
        forward_transfer=forward_transfer,
        backward_transfer=backward_transfer,
        end_accuracy=end_accuracy,
        mean_forgetting=mean_forgetting,
        accuracy_matrix=accuracy_matrix,
        n_tasks=len(task_results),
    )


def compute_cl_metrics_from_run(
    run_dir: str | Path,
    validate_learning: bool = True,
    min_diagonal_mean: float = 0.05,
) -> CLMetrics:
    """
    Compute CL metrics directly from a run directory.

    Convenience function that loads task results and computes metrics in one call.

    Args:
        run_dir: Directory containing task_results.jsonl (e.g., runs/{run_id})
        validate_learning: Whether to validate minimum learning occurred
        min_diagonal_mean: Minimum required mean diagonal accuracy

    Returns:
        CLMetrics object with all computed metrics

    Raises:
        FileNotFoundError: If task_results.jsonl doesn't exist
        ValueError: If task results are invalid or learning validation fails
    """
    task_results = load_task_results(run_dir)
    return compute_cl_metrics(task_results, validate_learning, min_diagonal_mean)
