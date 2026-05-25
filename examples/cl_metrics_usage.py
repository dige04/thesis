"""Example usage of CL metrics computation.

This example demonstrates how to:
1. Load task results from task_results.jsonl
2. Build accuracy matrix
3. Compute all CL metrics (Plasticity, Stability, CL-F1, FT, BT)
4. Interpret results

Requirements: 19
"""

import json
from pathlib import Path

import numpy as np

from src.benchmark.cl_metrics import (
    build_accuracy_matrix,
    compute_cl_metrics_from_run,
    load_task_results,
)


def create_example_run():
    """Create an example run directory with task results."""
    run_dir = Path("runs/example_cl_metrics")
    run_dir.mkdir(parents=True, exist_ok=True)

    # Example: 5-task sequence with varying success rates
    task_results = [
        {
            "run_id": "gpt54_typeaware_seed1_django",
            "policy": "type_aware_decay",
            "seed": 1,
            "repo": "django/django",
            "task_id": "django__django-11001",
            "sequence_index": 0,
            "resolved": 1,  # Task 0: SUCCESS
            "patch_generated": True,
            "patch_applied": True,
            "syntax_error": False,
            "timeout": False,
            "prompt_tokens": 2500,
            "completion_tokens": 800,
            "total_tokens": 3300,
            "estimated_cost_usd": 0.025,
            "task_api_cost": 0.025,
            "consolidation_llm_cost": 0.0,
            "wall_time_seconds": 180.0,
            "tool_calls": 15,
            "test_runs": 3,
            "files_read": 8,
            "files_modified": 3,
            "syntax_error_rate": 0.0,
            "retrieved_memory_ids": [],
            "retrieved_memory_scores": [],
            "retrieved_memory_types": [],
            "retrieved_memory_ages": [],
            "memory_count_before": 0,
            "memory_count_after": 1,
            "memory_tokens_before": 0,
            "memory_tokens_after": 450,
            "pruned_memory_ids": [],
            "consolidated_memory_ids": [],
            "task_difficulty": "medium",
            "error_message": None,
        },
        {
            "run_id": "gpt54_typeaware_seed1_django",
            "policy": "type_aware_decay",
            "seed": 1,
            "repo": "django/django",
            "task_id": "django__django-11045",
            "sequence_index": 1,
            "resolved": 1,  # Task 1: SUCCESS
            "patch_generated": True,
            "patch_applied": True,
            "syntax_error": False,
            "timeout": False,
            "prompt_tokens": 2800,
            "completion_tokens": 900,
            "total_tokens": 3700,
            "estimated_cost_usd": 0.028,
            "task_api_cost": 0.028,
            "consolidation_llm_cost": 0.0,
            "wall_time_seconds": 200.0,
            "tool_calls": 18,
            "test_runs": 4,
            "files_read": 10,
            "files_modified": 4,
            "syntax_error_rate": 0.05,
            "retrieved_memory_ids": ["mem_001"],
            "retrieved_memory_scores": [0.82],
            "retrieved_memory_types": ["bug_fix"],
            "retrieved_memory_ages": [1],
            "memory_count_before": 1,
            "memory_count_after": 2,
            "memory_tokens_before": 450,
            "memory_tokens_after": 920,
            "pruned_memory_ids": [],
            "consolidated_memory_ids": [],
            "task_difficulty": "medium",
            "error_message": None,
        },
        {
            "run_id": "gpt54_typeaware_seed1_django",
            "policy": "type_aware_decay",
            "seed": 1,
            "repo": "django/django",
            "task_id": "django__django-11179",
            "sequence_index": 2,
            "resolved": 0,  # Task 2: FAILED
            "patch_generated": True,
            "patch_applied": True,
            "syntax_error": False,
            "timeout": False,
            "prompt_tokens": 3200,
            "completion_tokens": 1000,
            "total_tokens": 4200,
            "estimated_cost_usd": 0.032,
            "task_api_cost": 0.032,
            "consolidation_llm_cost": 0.0,
            "wall_time_seconds": 250.0,
            "tool_calls": 22,
            "test_runs": 5,
            "files_read": 12,
            "files_modified": 5,
            "syntax_error_rate": 0.09,
            "retrieved_memory_ids": ["mem_001", "mem_002"],
            "retrieved_memory_scores": [0.78, 0.71],
            "retrieved_memory_types": ["bug_fix", "api_change"],
            "retrieved_memory_ages": [2, 1],
            "memory_count_before": 2,
            "memory_count_after": 3,
            "memory_tokens_before": 920,
            "memory_tokens_after": 1400,
            "pruned_memory_ids": [],
            "consolidated_memory_ids": [],
            "task_difficulty": "hard",
            "error_message": "Test failed: expected 200, got 404",
        },
        {
            "run_id": "gpt54_typeaware_seed1_django",
            "policy": "type_aware_decay",
            "seed": 1,
            "repo": "django/django",
            "task_id": "django__django-11283",
            "sequence_index": 3,
            "resolved": 1,  # Task 3: SUCCESS
            "patch_generated": True,
            "patch_applied": True,
            "syntax_error": False,
            "timeout": False,
            "prompt_tokens": 2900,
            "completion_tokens": 850,
            "total_tokens": 3750,
            "estimated_cost_usd": 0.029,
            "task_api_cost": 0.029,
            "consolidation_llm_cost": 0.0,
            "wall_time_seconds": 190.0,
            "tool_calls": 16,
            "test_runs": 3,
            "files_read": 9,
            "files_modified": 3,
            "syntax_error_rate": 0.0,
            "retrieved_memory_ids": ["mem_001", "mem_003"],
            "retrieved_memory_scores": [0.85, 0.68],
            "retrieved_memory_types": ["bug_fix", "test_update"],
            "retrieved_memory_ages": [3, 1],
            "memory_count_before": 3,
            "memory_count_after": 4,
            "memory_tokens_before": 1400,
            "memory_tokens_after": 1850,
            "pruned_memory_ids": [],
            "consolidated_memory_ids": [],
            "task_difficulty": "medium",
            "error_message": None,
        },
        {
            "run_id": "gpt54_typeaware_seed1_django",
            "policy": "type_aware_decay",
            "seed": 1,
            "repo": "django/django",
            "task_id": "django__django-11422",
            "sequence_index": 4,
            "resolved": 1,  # Task 4: SUCCESS
            "patch_generated": True,
            "patch_applied": True,
            "syntax_error": False,
            "timeout": False,
            "prompt_tokens": 3100,
            "completion_tokens": 950,
            "total_tokens": 4050,
            "estimated_cost_usd": 0.031,
            "task_api_cost": 0.031,
            "consolidation_llm_cost": 0.002,
            "wall_time_seconds": 210.0,
            "tool_calls": 19,
            "test_runs": 4,
            "files_read": 11,
            "files_modified": 4,
            "syntax_error_rate": 0.0,
            "retrieved_memory_ids": ["mem_001", "mem_004", "mem_005"],
            "retrieved_memory_scores": [0.88, 0.75, 0.62],
            "retrieved_memory_types": ["bug_fix", "api_change", "architectural"],
            "retrieved_memory_ages": [4, 1, 1],
            "memory_count_before": 4,
            "memory_count_after": 5,
            "memory_tokens_before": 1850,
            "memory_tokens_after": 2300,
            "pruned_memory_ids": [],
            "consolidated_memory_ids": [],
            "task_difficulty": "easy",
            "error_message": None,
        },
    ]

    # Write to task_results.jsonl
    results_file = run_dir / "task_results.jsonl"
    with open(results_file, "w", encoding="utf-8") as f:
        for result in task_results:
            f.write(json.dumps(result) + "\n")

    print(f"Created example run at: {run_dir}")
    print(f"Task results: {results_file}")
    print(f"Number of tasks: {len(task_results)}")
    print(f"Resolved tasks: {sum(r['resolved'] for r in task_results)}/{len(task_results)}")
    print()

    return run_dir


def example_1_load_and_build_matrix():
    """Example 1: Load task results and build accuracy matrix."""
    print("=" * 80)
    print("EXAMPLE 1: Load Task Results and Build Accuracy Matrix")
    print("=" * 80)

    # Create example run
    run_dir = create_example_run()

    # Load task results
    print("Loading task results...")
    task_results = load_task_results(run_dir)
    print(f"Loaded {len(task_results)} task results")
    print()

    # Build accuracy matrix
    print("Building accuracy matrix...")
    accuracy_matrix = build_accuracy_matrix(task_results)
    print(f"Accuracy matrix shape: {accuracy_matrix.shape}")
    print()

    # Display matrix
    print("Accuracy Matrix a_{i,j}:")
    print("(rows = tasks, columns = training steps)")
    print("a_{i,j} = accuracy on task i after training through task j")
    print()
    print(accuracy_matrix)
    print()

    # Explain diagonal
    print("Diagonal elements (Plasticity):")
    diagonal = np.diag(accuracy_matrix)
    for i, acc in enumerate(diagonal):
        status = "RESOLVED" if acc == 1.0 else "FAILED"
        print(f"  Task {i}: {acc:.1f} ({status})")
    print()

    # Explain lower triangle
    print("Lower triangle elements (Stability):")
    print("(accuracy on past tasks after learning new tasks)")
    n_tasks = accuracy_matrix.shape[0]
    for i in range(n_tasks):
        for j in range(i + 1, n_tasks):
            print(f"  a[{i},{j}] = {accuracy_matrix[i, j]:.1f} (task {i} after learning task {j})")
    print()


def example_2_compute_all_metrics():
    """Example 2: Compute all CL metrics."""
    print("=" * 80)
    print("EXAMPLE 2: Compute All CL Metrics")
    print("=" * 80)

    # Create example run
    run_dir = create_example_run()

    # Compute all metrics
    print("Computing CL metrics...")
    metrics = compute_cl_metrics_from_run(run_dir, validate_learning=True)
    print()

    # Display all metrics
    print("Continual Learning Metrics:")
    print("-" * 80)
    print(f"Plasticity:         {metrics.plasticity:.4f}")
    print("  → Ability to learn new tasks immediately")
    print(f"  → Mean of diagonal elements: {np.diag(metrics.accuracy_matrix)}")
    print()

    print(f"Stability:          {metrics.stability:.4f}")
    print("  → Ability to retain past tasks after learning new tasks")
    print("  → Mean of lower-triangular elements")
    print()

    print(f"CL-F1:              {metrics.cl_f1:.4f}")
    print("  → PRIMARY METRIC: Harmonic mean of Plasticity and Stability")
    print("  → Formula: 2 × (P × S) / (P + S)")
    print()

    print(f"Forward Transfer:   {metrics.forward_transfer:.4f}")
    print("  → Positive transfer from past to new tasks")
    print("  → Positive = prior learning helps, Negative = prior learning hurts")
    print()

    print(f"Backward Transfer:  {metrics.backward_transfer:.4f}")
    print("  → Measure of catastrophic forgetting")
    print("  → Positive = improvement, Zero = no forgetting, Negative = forgetting")
    print()

    print(f"End Accuracy:       {metrics.end_accuracy:.4f}")
    print("  → Mean accuracy on all tasks at end of sequence")
    print()

    print(f"Mean Forgetting:    {metrics.mean_forgetting:.4f}")
    print("  → Average forgetting across all tasks")
    print("  → 0 = no forgetting, 1 = complete forgetting")
    print()

    print(f"Number of Tasks:    {metrics.n_tasks}")
    print()


def example_3_interpret_results():
    """Example 3: Interpret CL metrics results."""
    print("=" * 80)
    print("EXAMPLE 3: Interpret CL Metrics Results")
    print("=" * 80)

    # Create example run
    run_dir = create_example_run()

    # Compute metrics
    metrics = compute_cl_metrics_from_run(run_dir, validate_learning=True)
    print()

    # Interpretation guide
    print("Interpretation Guide:")
    print("-" * 80)
    print()

    # Plasticity interpretation
    print("1. PLASTICITY (Ability to Learn New Tasks)")
    print(f"   Score: {metrics.plasticity:.4f}")
    if metrics.plasticity >= 0.8:
        print("   ✓ EXCELLENT: Agent learns most new tasks successfully")
    elif metrics.plasticity >= 0.6:
        print("   ✓ GOOD: Agent learns majority of new tasks")
    elif metrics.plasticity >= 0.4:
        print("   ⚠ MODERATE: Agent struggles with some tasks")
    else:
        print("   ✗ POOR: Agent fails to learn most tasks")
    print()

    # Stability interpretation
    print("2. STABILITY (Ability to Retain Past Tasks)")
    print(f"   Score: {metrics.stability:.4f}")
    if metrics.stability >= 0.8:
        print("   ✓ EXCELLENT: Minimal catastrophic forgetting")
    elif metrics.stability >= 0.6:
        print("   ✓ GOOD: Some forgetting but mostly retained")
    elif metrics.stability >= 0.4:
        print("   ⚠ MODERATE: Significant forgetting of past tasks")
    else:
        print("   ✗ POOR: Severe catastrophic forgetting")
    print()

    # CL-F1 interpretation
    print("3. CL-F1 (PRIMARY METRIC)")
    print(f"   Score: {metrics.cl_f1:.4f}")
    if metrics.cl_f1 >= 0.7:
        print("   ✓ EXCELLENT: Strong continual learning performance")
    elif metrics.cl_f1 >= 0.5:
        print("   ✓ GOOD: Balanced learning and retention")
    elif metrics.cl_f1 >= 0.3:
        print("   ⚠ MODERATE: Room for improvement")
    else:
        print("   ✗ POOR: Weak continual learning")
    print()

    # Forward transfer interpretation
    print("4. FORWARD TRANSFER")
    print(f"   Score: {metrics.forward_transfer:.4f}")
    if metrics.forward_transfer > 0.1:
        print("   ✓ POSITIVE: Prior learning helps with new tasks")
    elif metrics.forward_transfer > -0.1:
        print("   → NEUTRAL: Prior learning has minimal effect")
    else:
        print("   ✗ NEGATIVE: Prior learning hurts new task performance")
    print()

    # Backward transfer interpretation
    print("5. BACKWARD TRANSFER")
    print(f"   Score: {metrics.backward_transfer:.4f}")
    if metrics.backward_transfer > 0.1:
        print("   ✓ POSITIVE: Learning new tasks improves old task performance (rare)")
    elif metrics.backward_transfer > -0.1:
        print("   ✓ NEUTRAL: Minimal forgetting")
    else:
        print("   ✗ NEGATIVE: Catastrophic forgetting detected")
    print()

    # Overall assessment
    print("OVERALL ASSESSMENT:")
    print("-" * 80)
    if metrics.cl_f1 >= 0.6 and metrics.backward_transfer > -0.2:
        print("✓ This policy shows strong continual learning with minimal forgetting.")
        print("  Recommended for production use.")
    elif metrics.cl_f1 >= 0.4:
        print("⚠ This policy shows moderate continual learning performance.")
        print("  Consider tuning hyperparameters or trying different policy.")
    else:
        print("✗ This policy shows weak continual learning performance.")
        print("  Significant improvements needed.")
    print()


def example_4_compare_policies():
    """Example 4: Compare multiple policies using CL metrics."""
    print("=" * 80)
    print("EXAMPLE 4: Compare Multiple Policies")
    print("=" * 80)
    print()

    # Simulate metrics for different policies
    policies = {
        "No Memory": {
            "plasticity": 0.45,
            "stability": 0.40,
            "cl_f1": 0.42,
        },
        "Full Memory": {
            "plasticity": 0.65,
            "stability": 0.55,
            "cl_f1": 0.60,
        },
        "Random Prune": {
            "plasticity": 0.62,
            "stability": 0.58,
            "cl_f1": 0.60,
        },
        "Type-Aware Decay": {
            "plasticity": 0.70,
            "stability": 0.65,
            "cl_f1": 0.67,
        },
        "CLS Consolidation": {
            "plasticity": 0.68,
            "stability": 0.62,
            "cl_f1": 0.65,
        },
    }

    print("Policy Comparison (Simulated Results):")
    print("-" * 80)
    print(f"{'Policy':<20} {'Plasticity':>12} {'Stability':>12} {'CL-F1':>12}")
    print("-" * 80)

    for policy, metrics in policies.items():
        print(
            f"{policy:<20} {metrics['plasticity']:>12.4f} "
            f"{metrics['stability']:>12.4f} {metrics['cl_f1']:>12.4f}"
        )

    print()

    # Find best policy
    best_policy = max(policies.items(), key=lambda x: x[1]["cl_f1"])
    print(f"Best Policy (by CL-F1): {best_policy[0]} (CL-F1 = {best_policy[1]['cl_f1']:.4f})")
    print()

    # Analysis
    print("Analysis:")
    print("-" * 80)
    print("• Type-Aware Decay achieves highest CL-F1 (0.67)")
    print("  → Semantic pruning preserves useful memories while reducing noise")
    print()
    print("• Full Memory and Random Prune tie on CL-F1 (0.60)")
    print("  → Volume reduction alone may be sufficient")
    print()
    print("• No Memory shows lowest CL-F1 (0.42)")
    print("  → Persistent memory provides clear benefit")
    print()


def main():
    """Run all examples."""
    example_1_load_and_build_matrix()
    print("\n" * 2)

    example_2_compute_all_metrics()
    print("\n" * 2)

    example_3_interpret_results()
    print("\n" * 2)

    example_4_compare_policies()


if __name__ == "__main__":
    main()
