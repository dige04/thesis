"""
Example usage of plotting functions.

This script demonstrates how to use the plotting functions from Task 18.1.

Requirements: 24, 29
"""

from pathlib import Path

from src.analysis.aggregate_results import aggregate_sequence_results
from src.analysis.failure_analysis import generate_failure_analysis_report
from src.analysis.plots import (
    generate_all_plots,
    plot_behavioral_metrics_comparison,
    plot_failure_analysis,
    plot_memory_usage_over_time,
    plot_pareto_frontier,
    plot_sequence_performance_comparison,
)


def example_generate_all_plots():
    """
    Example: Generate all analysis plots at once.

    This is the recommended way to generate plots after running experiments.
    """
    print("=" * 80)
    print("EXAMPLE: Generate All Plots")
    print("=" * 80)
    print()

    # Paths
    runs_dir = Path("runs")
    output_dir = Path("results/plots")

    # Step 1: Aggregate sequence results
    print("[1/3] Aggregating sequence results...")
    sequence_aggregates = aggregate_sequence_results(
        runs_dir=runs_dir,
        output_path=Path("results/aggregated/sequence_aggregates.json"),
    )

    # Step 2: Generate failure analysis report
    print("[2/3] Generating failure analysis report...")
    failure_report = generate_failure_analysis_report(
        runs_dir=runs_dir,
        output_path=Path("results/aggregated/failure_report.json"),
    )

    # Step 3: Generate all plots
    print("[3/3] Generating all plots...")
    generate_all_plots(
        sequence_aggregates=sequence_aggregates,
        runs_dir=runs_dir,
        failure_report=failure_report,
        output_dir=output_dir,
    )

    print()
    print("✓ All plots generated successfully!")
    print(f"✓ Plots saved to: {output_dir}")
    print()


def example_individual_plots():
    """
    Example: Generate individual plots separately.

    Use this approach when you need specific plots or custom configurations.
    """
    print("=" * 80)
    print("EXAMPLE: Generate Individual Plots")
    print("=" * 80)
    print()

    # Paths
    runs_dir = Path("runs")
    output_dir = Path("results/plots/custom")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load data
    sequence_aggregates = aggregate_sequence_results(runs_dir=runs_dir)
    failure_report = generate_failure_analysis_report(runs_dir=runs_dir)

    # 1. Pareto frontier: CL-F1 vs Cost
    print("[1/5] Generating Pareto frontier plot...")
    plot_pareto_frontier(
        sequence_aggregates=sequence_aggregates,
        output_path=output_dir / "pareto_cl_f1_vs_cost.png",
        metric_x="mean_total_cost",
        metric_y="mean_cl_f1",
        title="Pareto Frontier: CL-F1 vs Total Cost",
    )

    # 2. Sequence-level performance comparison
    print("[2/5] Generating sequence performance comparison...")
    plot_sequence_performance_comparison(
        sequence_aggregates=sequence_aggregates,
        output_path=output_dir / "sequence_comparison_cl_f1.png",
        metric="mean_cl_f1",
        title="Sequence-Level CL-F1 Comparison",
    )

    # 3. Memory usage over time
    print("[3/5] Generating memory usage plot...")
    plot_memory_usage_over_time(
        runs_dir=runs_dir,
        output_path=output_dir / "memory_usage_over_time.png",
        title="Memory Usage Over Time (All Policies)",
    )

    # 4. Behavioral metrics comparison
    print("[4/5] Generating behavioral metrics comparison...")
    plot_behavioral_metrics_comparison(
        sequence_aggregates=sequence_aggregates,
        output_path=output_dir / "behavioral_metrics_comparison.png",
        title="Behavioral Metrics: Tool Calls and Execution Time",
    )

    # 5. Failure analysis
    print("[5/5] Generating failure analysis plot...")
    plot_failure_analysis(
        failure_report=failure_report,
        output_path=output_dir / "failure_analysis.png",
        title="Failure Analysis by Policy and Category",
    )

    print()
    print("✓ Individual plots generated successfully!")
    print(f"✓ Plots saved to: {output_dir}")
    print()


def example_custom_pareto_plots():
    """
    Example: Generate custom Pareto frontier plots with different metrics.

    This demonstrates how to create Pareto plots for different metric pairs.
    """
    print("=" * 80)
    print("EXAMPLE: Custom Pareto Frontier Plots")
    print("=" * 80)
    print()

    # Paths
    runs_dir = Path("runs")
    output_dir = Path("results/plots/pareto")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load data
    sequence_aggregates = aggregate_sequence_results(runs_dir=runs_dir)

    # Different Pareto frontiers
    pareto_configs = [
        {
            "metric_x": "mean_total_cost",
            "metric_y": "mean_cl_f1",
            "title": "Pareto Frontier: CL-F1 vs Total Cost",
            "filename": "pareto_cl_f1_vs_cost.png",
        },
        {
            "metric_x": "mean_total_tokens",
            "metric_y": "mean_cl_f1",
            "title": "Pareto Frontier: CL-F1 vs Total Tokens",
            "filename": "pareto_cl_f1_vs_tokens.png",
        },
        {
            "metric_x": "mean_tool_calls",
            "metric_y": "mean_cl_f1",
            "title": "Pareto Frontier: CL-F1 vs Tool Calls",
            "filename": "pareto_cl_f1_vs_tool_calls.png",
        },
        {
            "metric_x": "mean_wall_time",
            "metric_y": "mean_cl_f1",
            "title": "Pareto Frontier: CL-F1 vs Wall Time",
            "filename": "pareto_cl_f1_vs_wall_time.png",
        },
    ]

    for i, config in enumerate(pareto_configs, 1):
        print(f"[{i}/{len(pareto_configs)}] Generating {config['filename']}...")
        plot_pareto_frontier(
            sequence_aggregates=sequence_aggregates,
            output_path=output_dir / config["filename"],
            metric_x=config["metric_x"],
            metric_y=config["metric_y"],
            title=config["title"],
        )

    print()
    print("✓ Custom Pareto plots generated successfully!")
    print(f"✓ Plots saved to: {output_dir}")
    print()


def example_policy_specific_memory_usage():
    """
    Example: Generate memory usage plots for specific policies.

    This demonstrates how to create focused plots for individual policies.
    """
    print("=" * 80)
    print("EXAMPLE: Policy-Specific Memory Usage Plots")
    print("=" * 80)
    print()

    # Paths
    runs_dir = Path("runs")
    output_dir = Path("results/plots/memory_by_policy")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Policies to plot
    policies = [
        "no_memory",
        "full_memory",
        "random_prune",
        "recency_prune",
        "type_aware_decay",
        "cls_consolidation",
    ]

    for i, policy in enumerate(policies, 1):
        print(f"[{i}/{len(policies)}] Generating memory usage plot for {policy}...")
        plot_memory_usage_over_time(
            runs_dir=runs_dir,
            output_path=output_dir / f"memory_usage_{policy}.png",
            policy=policy,
            title=f"Memory Usage Over Time: {policy.replace('_', ' ').title()}",
        )

    print()
    print("✓ Policy-specific memory usage plots generated successfully!")
    print(f"✓ Plots saved to: {output_dir}")
    print()


def example_multiple_metrics_comparison():
    """
    Example: Generate sequence comparison plots for multiple metrics.

    This demonstrates how to compare policies across different metrics.
    """
    print("=" * 80)
    print("EXAMPLE: Multiple Metrics Comparison")
    print("=" * 80)
    print()

    # Paths
    runs_dir = Path("runs")
    output_dir = Path("results/plots/metrics_comparison")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load data
    sequence_aggregates = aggregate_sequence_results(runs_dir=runs_dir)

    # Metrics to compare
    metrics = [
        ("mean_cl_f1", "CL-F1"),
        ("mean_resolved_rate", "Resolved Rate"),
        ("mean_total_cost", "Total Cost"),
        ("mean_tool_calls", "Tool Calls"),
        ("mean_wall_time", "Wall Time"),
    ]

    for i, (metric, label) in enumerate(metrics, 1):
        print(f"[{i}/{len(metrics)}] Generating comparison plot for {label}...")
        plot_sequence_performance_comparison(
            sequence_aggregates=sequence_aggregates,
            output_path=output_dir / f"sequence_comparison_{metric}.png",
            metric=metric,
            title=f"Sequence-Level {label} Comparison",
        )

    print()
    print("✓ Multiple metrics comparison plots generated successfully!")
    print(f"✓ Plots saved to: {output_dir}")
    print()


if __name__ == "__main__":
    print()
    print("=" * 80)
    print("PLOTTING FUNCTIONS USAGE EXAMPLES")
    print("=" * 80)
    print()
    print("This script demonstrates various ways to use the plotting functions.")
    print("Choose an example to run:")
    print()
    print("1. Generate all plots at once (recommended)")
    print("2. Generate individual plots separately")
    print("3. Generate custom Pareto frontier plots")
    print("4. Generate policy-specific memory usage plots")
    print("5. Generate multiple metrics comparison plots")
    print()

    choice = input("Enter choice (1-5): ").strip()

    if choice == "1":
        example_generate_all_plots()
    elif choice == "2":
        example_individual_plots()
    elif choice == "3":
        example_custom_pareto_plots()
    elif choice == "4":
        example_policy_specific_memory_usage()
    elif choice == "5":
        example_multiple_metrics_comparison()
    else:
        print("Invalid choice. Please run the script again and choose 1-5.")
