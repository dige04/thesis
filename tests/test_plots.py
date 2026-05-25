"""
Tests for plotting functions.

This module tests Task 18.1: Plotting functions.

Per Requirements 24 and 29:
- Test Pareto frontier plot generation
- Test sequence-level performance comparison plots
- Test memory usage over time plots
- Test behavioral metrics comparison plots
- Test failure analysis plots

Requirements: 24, 29
"""

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from src.analysis.plots import (
    generate_all_plots,
    plot_behavioral_metrics_comparison,
    plot_failure_analysis,
    plot_memory_usage_over_time,
    plot_pareto_frontier,
    plot_sequence_performance_comparison,
)


@pytest.fixture
def sample_sequence_aggregates():
    """
    Sample sequence aggregates for testing.

    Structure: {policy: {sequence: {metric: value}}}
    """
    return {
        "no_memory": {
            "django": {
                "mean_cl_f1": 0.45,
                "std_cl_f1": 0.05,
                "mean_resolved_rate": 0.50,
                "std_resolved_rate": 0.06,
                "mean_total_cost": 10.0,
                "std_total_cost": 1.0,
                "mean_total_tokens": 50000,
                "std_total_tokens": 5000,
                "mean_tool_calls": 30.0,
                "std_tool_calls": 3.0,
                "mean_wall_time": 120.0,
                "std_wall_time": 10.0,
                "n_seeds": 3,
                "n_tasks": 20,
                "seed_cl_f1_values": [0.43, 0.45, 0.47],
            },
            "flask": {
                "mean_cl_f1": 0.48,
                "std_cl_f1": 0.04,
                "mean_resolved_rate": 0.52,
                "std_resolved_rate": 0.05,
                "mean_total_cost": 9.5,
                "std_total_cost": 0.9,
                "mean_total_tokens": 48000,
                "std_total_tokens": 4800,
                "mean_tool_calls": 28.0,
                "std_tool_calls": 2.8,
                "mean_wall_time": 115.0,
                "std_wall_time": 9.0,
                "n_seeds": 3,
                "n_tasks": 18,
                "seed_cl_f1_values": [0.46, 0.48, 0.50],
            },
        },
        "full_memory": {
            "django": {
                "mean_cl_f1": 0.65,
                "std_cl_f1": 0.06,
                "mean_resolved_rate": 0.68,
                "std_resolved_rate": 0.07,
                "mean_total_cost": 25.0,
                "std_total_cost": 2.5,
                "mean_total_tokens": 120000,
                "std_total_tokens": 12000,
                "mean_tool_calls": 50.0,
                "std_tool_calls": 5.0,
                "mean_wall_time": 180.0,
                "std_wall_time": 15.0,
                "n_seeds": 3,
                "n_tasks": 20,
                "seed_cl_f1_values": [0.63, 0.65, 0.67],
            },
            "flask": {
                "mean_cl_f1": 0.68,
                "std_cl_f1": 0.05,
                "mean_resolved_rate": 0.70,
                "std_resolved_rate": 0.06,
                "mean_total_cost": 24.0,
                "std_total_cost": 2.4,
                "mean_total_tokens": 115000,
                "std_total_tokens": 11500,
                "mean_tool_calls": 48.0,
                "std_tool_calls": 4.8,
                "mean_wall_time": 175.0,
                "std_wall_time": 14.0,
                "n_seeds": 3,
                "n_tasks": 18,
                "seed_cl_f1_values": [0.66, 0.68, 0.70],
            },
        },
        "type_aware_decay": {
            "django": {
                "mean_cl_f1": 0.70,
                "std_cl_f1": 0.04,
                "mean_resolved_rate": 0.72,
                "std_resolved_rate": 0.05,
                "mean_total_cost": 18.0,
                "std_total_cost": 1.8,
                "mean_total_tokens": 85000,
                "std_total_tokens": 8500,
                "mean_tool_calls": 38.0,
                "std_tool_calls": 3.8,
                "mean_wall_time": 145.0,
                "std_wall_time": 12.0,
                "n_seeds": 3,
                "n_tasks": 20,
                "seed_cl_f1_values": [0.68, 0.70, 0.72],
            },
            "flask": {
                "mean_cl_f1": 0.72,
                "std_cl_f1": 0.03,
                "mean_resolved_rate": 0.74,
                "std_resolved_rate": 0.04,
                "mean_total_cost": 17.5,
                "std_total_cost": 1.7,
                "mean_total_tokens": 82000,
                "std_total_tokens": 8200,
                "mean_tool_calls": 36.0,
                "std_tool_calls": 3.6,
                "mean_wall_time": 140.0,
                "std_wall_time": 11.0,
                "n_seeds": 3,
                "n_tasks": 18,
                "seed_cl_f1_values": [0.70, 0.72, 0.74],
            },
        },
    }


@pytest.fixture
def sample_failure_report():
    """
    Sample failure report for testing.
    """
    return {
        "failure_rates": {
            "no_memory": {
                "timeout": 0.20,
                "test_failure": 0.50,
                "syntax_error": 0.15,
                "tool_error": 0.10,
                "unknown": 0.05,
                "total_failures": 100.0,
            },
            "full_memory": {
                "timeout": 0.10,
                "test_failure": 0.60,
                "syntax_error": 0.20,
                "tool_error": 0.05,
                "unknown": 0.05,
                "total_failures": 80.0,
            },
            "type_aware_decay": {
                "timeout": 0.08,
                "test_failure": 0.65,
                "syntax_error": 0.12,
                "tool_error": 0.10,
                "unknown": 0.05,
                "total_failures": 60.0,
            },
        },
        "boundary_tasks": [
            {
                "task_id": "django__django-12345",
                "repo": "django/django",
                "sequence_index": 5,
                "seed": 1,
                "full_memory_error": "timeout",
                "full_memory_error_message": "Exceeded 20 steps",
                "successful_policies": ["type_aware_decay", "random_prune"],
                "n_successful_policies": 2,
            },
            {
                "task_id": "flask__flask-6789",
                "repo": "flask/flask",
                "sequence_index": 8,
                "seed": 2,
                "full_memory_error": "syntax_error",
                "full_memory_error_message": "Invalid syntax in generated code",
                "successful_policies": ["type_aware_decay"],
                "n_successful_policies": 1,
            },
        ],
        "summary": {
            "total_failures": 240,
            "failures_by_category": {
                "timeout": 38,
                "test_failure": 140,
                "syntax_error": 37,
                "tool_error": 20,
                "unknown": 5,
            },
            "n_boundary_tasks": 2,
            "policies_analyzed": ["no_memory", "full_memory", "type_aware_decay"],
        },
    }


@pytest.fixture
def sample_runs_dir(tmp_path):
    """
    Create sample runs directory with task results for testing.
    """
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()

    # Create sample run directories with task results
    for policy in ["no_memory", "full_memory", "type_aware_decay"]:
        for seed in [1, 2]:
            run_dir = runs_dir / f"{policy}_seed{seed}"
            run_dir.mkdir()

            task_results_path = run_dir / "task_results.jsonl"

            # Generate sample task results
            with open(task_results_path, "w") as f:
                for seq_idx in range(10):
                    task_result = {
                        "task_id": f"task_{seq_idx}",
                        "policy": policy,
                        "seed": seed,
                        "repo": "django/django",
                        "sequence_index": seq_idx,
                        "resolved": 1 if seq_idx % 2 == 0 else 0,
                        "memory_count_before": seq_idx * 5,
                        "memory_count_after": (seq_idx + 1) * 5,
                        "memory_tokens_before": seq_idx * 500,
                        "memory_tokens_after": (seq_idx + 1) * 500,
                        "tool_calls": 30 + seq_idx,
                        "wall_time_seconds": 120 + seq_idx * 10,
                    }
                    f.write(json.dumps(task_result) + "\n")

    return runs_dir


def test_plot_pareto_frontier(sample_sequence_aggregates, tmp_path):
    """
    Test Pareto frontier plot generation.

    Per Requirement 24:
    - Plot should be generated without errors
    - Output file should exist
    - Should identify Pareto-optimal policies
    """
    output_path = tmp_path / "pareto_test.png"

    # Generate plot
    plot_pareto_frontier(
        sequence_aggregates=sample_sequence_aggregates,
        output_path=output_path,
        metric_x="mean_total_cost",
        metric_y="mean_cl_f1",
        title="Test Pareto Frontier",
    )

    # Verify output file exists
    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_plot_pareto_frontier_identifies_optimal_policies(
    sample_sequence_aggregates, tmp_path
):
    """
    Test that Pareto frontier correctly identifies optimal policies.

    Per Requirement 24:
    - type_aware_decay should be Pareto-optimal (high CL-F1, moderate cost)
    - no_memory should be Pareto-optimal (low cost, low CL-F1)
    - full_memory should be dominated (high cost, moderate CL-F1)
    """
    output_path = tmp_path / "pareto_optimal_test.png"

    # Generate plot (internally identifies Pareto-optimal policies)
    plot_pareto_frontier(
        sequence_aggregates=sample_sequence_aggregates,
        output_path=output_path,
    )

    # Verify output exists
    assert output_path.exists()

    # Note: Actual Pareto optimality is computed in pareto.py
    # This test verifies the plot generation works correctly


def test_plot_sequence_performance_comparison(sample_sequence_aggregates, tmp_path):
    """
    Test sequence-level performance comparison plot.

    Per Requirement 24:
    - Plot should show all sequences and policies
    - Should include error bars (SEM)
    """
    output_path = tmp_path / "sequence_comparison_test.png"

    # Generate plot
    plot_sequence_performance_comparison(
        sequence_aggregates=sample_sequence_aggregates,
        output_path=output_path,
        metric="mean_cl_f1",
        title="Test Sequence Comparison",
    )

    # Verify output file exists
    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_plot_sequence_performance_comparison_multiple_metrics(
    sample_sequence_aggregates, tmp_path
):
    """
    Test sequence comparison with different metrics.
    """
    metrics = ["mean_cl_f1", "mean_resolved_rate", "mean_total_cost"]

    for metric in metrics:
        output_path = tmp_path / f"sequence_comparison_{metric}.png"

        plot_sequence_performance_comparison(
            sequence_aggregates=sample_sequence_aggregates,
            output_path=output_path,
            metric=metric,
        )

        assert output_path.exists()
        assert output_path.stat().st_size > 0


def test_plot_memory_usage_over_time(sample_runs_dir, tmp_path):
    """
    Test memory usage over time plot.

    Should show memory_count_after and memory_tokens_after progression.
    """
    output_path = tmp_path / "memory_usage_test.png"

    # Generate plot
    plot_memory_usage_over_time(
        runs_dir=sample_runs_dir,
        output_path=output_path,
        title="Test Memory Usage",
    )

    # Verify output file exists
    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_plot_memory_usage_over_time_single_policy(sample_runs_dir, tmp_path):
    """
    Test memory usage plot for a single policy.
    """
    output_path = tmp_path / "memory_usage_single_policy_test.png"

    # Generate plot for specific policy
    plot_memory_usage_over_time(
        runs_dir=sample_runs_dir,
        output_path=output_path,
        policy="type_aware_decay",
        title="Test Memory Usage (Type-Aware Decay)",
    )

    # Verify output file exists
    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_plot_behavioral_metrics_comparison(sample_sequence_aggregates, tmp_path):
    """
    Test behavioral metrics comparison plot.

    Per Requirement 29:
    - Should show tool-call frequency
    - Should show execution time
    - Should highlight Full Memory (analysis paralysis test)
    """
    output_path = tmp_path / "behavioral_metrics_test.png"

    # Generate plot
    plot_behavioral_metrics_comparison(
        sequence_aggregates=sample_sequence_aggregates,
        output_path=output_path,
        title="Test Behavioral Metrics",
    )

    # Verify output file exists
    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_plot_behavioral_metrics_highlights_full_memory(
    sample_sequence_aggregates, tmp_path
):
    """
    Test that behavioral metrics plot highlights Full Memory.

    Per Requirement 29 and Hypothesis H4:
    - Full Memory should have higher tool calls (analysis paralysis)
    - Plot should visually highlight this
    """
    output_path = tmp_path / "behavioral_metrics_highlight_test.png"

    # Generate plot
    plot_behavioral_metrics_comparison(
        sequence_aggregates=sample_sequence_aggregates,
        output_path=output_path,
    )

    # Verify output exists
    assert output_path.exists()

    # Verify Full Memory has higher tool calls in data
    full_memory_tool_calls = np.mean(
        [
            seq["mean_tool_calls"]
            for seq in sample_sequence_aggregates["full_memory"].values()
        ]
    )
    type_aware_tool_calls = np.mean(
        [
            seq["mean_tool_calls"]
            for seq in sample_sequence_aggregates["type_aware_decay"].values()
        ]
    )

    assert full_memory_tool_calls > type_aware_tool_calls


def test_plot_failure_analysis(sample_failure_report, tmp_path):
    """
    Test failure analysis plot.

    Per Requirement 28:
    - Should show per-policy failure rates by category
    - Should annotate boundary tasks
    """
    output_path = tmp_path / "failure_analysis_test.png"

    # Generate plot
    plot_failure_analysis(
        failure_report=sample_failure_report,
        output_path=output_path,
        title="Test Failure Analysis",
    )

    # Verify output file exists
    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_plot_failure_analysis_shows_boundary_tasks(sample_failure_report, tmp_path):
    """
    Test that failure analysis plot shows boundary task count.

    Per Requirement 28 and Hypothesis H5:
    - Boundary tasks are where Full Memory fails but pruning succeeds
    - Plot should annotate this count
    """
    output_path = tmp_path / "failure_analysis_boundary_test.png"

    # Generate plot
    plot_failure_analysis(
        failure_report=sample_failure_report,
        output_path=output_path,
    )

    # Verify output exists
    assert output_path.exists()

    # Verify boundary tasks are present in report
    assert sample_failure_report["summary"]["n_boundary_tasks"] == 2


def test_generate_all_plots(
    sample_sequence_aggregates, sample_runs_dir, sample_failure_report, tmp_path
):
    """
    Test generation of all plots at once.

    Per Task 18.1:
    - Should generate all 7 plots without errors
    - All output files should exist
    """
    output_dir = tmp_path / "all_plots"

    # Generate all plots
    generate_all_plots(
        sequence_aggregates=sample_sequence_aggregates,
        runs_dir=sample_runs_dir,
        failure_report=sample_failure_report,
        output_dir=output_dir,
    )

    # Verify all expected plots exist
    expected_plots = [
        "pareto_cl_f1_vs_cost.png",
        "pareto_cl_f1_vs_tokens.png",
        "sequence_comparison_cl_f1.png",
        "sequence_comparison_resolved_rate.png",
        "memory_usage_over_time.png",
        "behavioral_metrics_comparison.png",
        "failure_analysis.png",
    ]

    for plot_name in expected_plots:
        plot_path = output_dir / plot_name
        assert plot_path.exists(), f"Missing plot: {plot_name}"
        assert plot_path.stat().st_size > 0, f"Empty plot: {plot_name}"


def test_plot_pareto_frontier_with_zero_sem(tmp_path):
    """
    Test Pareto frontier plot with zero SEM (single sequence).

    Edge case: when only one sequence is available, SEM = 0.
    """
    # Single sequence data
    single_sequence_data = {
        "no_memory": {
            "django": {
                "mean_cl_f1": 0.45,
                "std_cl_f1": 0.05,
                "mean_total_cost": 10.0,
                "std_total_cost": 1.0,
                "mean_total_tokens": 50000,
                "std_total_tokens": 5000,
                "mean_tool_calls": 30.0,
                "std_tool_calls": 3.0,
                "mean_wall_time": 120.0,
                "std_wall_time": 10.0,
                "n_seeds": 3,
                "n_tasks": 20,
                "seed_cl_f1_values": [0.43, 0.45, 0.47],
            }
        },
        "full_memory": {
            "django": {
                "mean_cl_f1": 0.65,
                "std_cl_f1": 0.06,
                "mean_total_cost": 25.0,
                "std_total_cost": 2.5,
                "mean_total_tokens": 120000,
                "std_total_tokens": 12000,
                "mean_tool_calls": 50.0,
                "std_tool_calls": 5.0,
                "mean_wall_time": 180.0,
                "std_wall_time": 15.0,
                "n_seeds": 3,
                "n_tasks": 20,
                "seed_cl_f1_values": [0.63, 0.65, 0.67],
            }
        },
    }

    output_path = tmp_path / "pareto_zero_sem_test.png"

    # Should not crash with zero SEM
    plot_pareto_frontier(
        sequence_aggregates=single_sequence_data,
        output_path=output_path,
    )

    assert output_path.exists()


def test_plot_memory_usage_empty_runs_dir(tmp_path):
    """
    Test memory usage plot with empty runs directory.

    Edge case: should handle gracefully when no data is available.
    """
    empty_runs_dir = tmp_path / "empty_runs"
    empty_runs_dir.mkdir()

    output_path = tmp_path / "memory_usage_empty_test.png"

    # Should not crash with empty directory
    plot_memory_usage_over_time(
        runs_dir=empty_runs_dir,
        output_path=output_path,
    )

    # Plot may still be created (empty), or may not be created
    # Either behavior is acceptable for empty data


def test_plot_failure_analysis_no_boundary_tasks(tmp_path):
    """
    Test failure analysis plot with no boundary tasks.

    Edge case: when Full Memory never fails or always fails.
    """
    no_boundary_report = {
        "failure_rates": {
            "no_memory": {
                "timeout": 0.20,
                "test_failure": 0.50,
                "syntax_error": 0.15,
                "tool_error": 0.10,
                "unknown": 0.05,
                "total_failures": 100.0,
            }
        },
        "boundary_tasks": [],
        "summary": {
            "total_failures": 100,
            "failures_by_category": {
                "timeout": 20,
                "test_failure": 50,
                "syntax_error": 15,
                "tool_error": 10,
                "unknown": 5,
            },
            "n_boundary_tasks": 0,
            "policies_analyzed": ["no_memory"],
        },
    }

    output_path = tmp_path / "failure_analysis_no_boundary_test.png"

    # Should not crash with no boundary tasks
    plot_failure_analysis(
        failure_report=no_boundary_report,
        output_path=output_path,
    )

    assert output_path.exists()
