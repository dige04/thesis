"""
Plotting functions for memory pruning research analysis.

This module implements Task 18.1: Plotting functions.

Per Requirements 24 and 29:
- Generate CL-F1 vs cost Pareto frontier plot
- Generate sequence-level performance comparison plots
- Generate memory usage over time plots
- Generate behavioral metrics comparison plots
- Generate failure analysis plots

Requirements: 24, 29
"""

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from matplotlib.patches import Ellipse

# Set style for all plots
sns.set_style("whitegrid")
plt.rcParams["figure.figsize"] = (10, 7)
plt.rcParams["font.size"] = 10


def plot_pareto_frontier(
    sequence_aggregates: dict[str, dict[str, dict[str, Any]]],
    output_path: Path,
    metric_x: str = "mean_total_cost",
    metric_y: str = "mean_cl_f1",
    title: str | None = None,
) -> None:
    """
    Plot Pareto frontier with confidence ellipses.

    Per Requirement 24:
    - X-axis: total cost (USD)
    - Y-axis: CL-F1
    - Error bars: SEM from 3 seeds
    - Highlight Pareto-optimal policies

    Args:
        sequence_aggregates: Output from aggregate_sequence_results()
        output_path: Path to save plot
        metric_x: X-axis metric (cost, lower is better)
        metric_y: Y-axis metric (CL-F1, higher is better)
        title: Optional plot title
    """
    # Extract policy-level aggregates (mean across sequences)
    policy_points = []

    for policy, sequences in sequence_aggregates.items():
        # Aggregate across sequences
        x_values = [seq[metric_x] for seq in sequences.values()]
        y_values = [seq[metric_y] for seq in sequences.values()]

        mean_x = np.mean(x_values)
        mean_y = np.mean(y_values)

        # Standard error of the mean (SEM)
        sem_x = (
            np.std(x_values, ddof=1) / np.sqrt(len(x_values))
            if len(x_values) > 1
            else 0.0
        )
        sem_y = (
            np.std(y_values, ddof=1) / np.sqrt(len(y_values))
            if len(y_values) > 1
            else 0.0
        )

        policy_points.append(
            {
                "policy": policy,
                "x": mean_x,
                "y": mean_y,
                "x_sem": sem_x,
                "y_sem": sem_y,
            }
        )

    # Identify Pareto frontier
    pareto_optimal = []
    dominated = []

    for i, point_i in enumerate(policy_points):
        is_dominated = False

        for j, point_j in enumerate(policy_points):
            if i == j:
                continue

            # Check if point_j dominates point_i
            # Dominates if: lower cost AND higher performance
            if point_j["x"] < point_i["x"] and point_j["y"] > point_i["y"]:
                is_dominated = True
                break

        if is_dominated:
            dominated.append(point_i["policy"])
        else:
            pareto_optimal.append(point_i["policy"])

    # Create plot
    fig, ax = plt.subplots(figsize=(10, 7))

    # Plot each policy
    for point in policy_points:
        policy = point["policy"]
        x, y = point["x"], point["y"]
        x_sem, y_sem = point["x_sem"], point["y_sem"]

        # Color: Pareto-optimal in green, dominated in red
        color = "green" if policy in pareto_optimal else "red"
        marker = "o" if policy in pareto_optimal else "x"
        size = 150 if policy in pareto_optimal else 100

        # Plot point
        ax.scatter(x, y, c=color, marker=marker, s=size, alpha=0.7, label=policy)

        # Add error bars (SEM)
        ax.errorbar(
            x,
            y,
            xerr=x_sem,
            yerr=y_sem,
            fmt="none",
            ecolor=color,
            alpha=0.3,
            capsize=3,
        )

        # Add confidence ellipse (2 SEM ≈ 95% CI)
        if x_sem > 0 and y_sem > 0:
            ellipse = Ellipse(
                (x, y),
                width=2 * x_sem,
                height=2 * y_sem,
                facecolor=color,
                alpha=0.1,
                edgecolor=color,
                linewidth=1,
            )
            ax.add_patch(ellipse)

        # Annotate policy name
        ax.annotate(
            policy,
            (x, y),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=9,
            alpha=0.8,
        )

    # Labels and title
    ax.set_xlabel(f"{metric_x} (lower is better)", fontsize=12)
    ax.set_ylabel(f"{metric_y} (higher is better)", fontsize=12)

    if title:
        ax.set_title(title, fontsize=14, fontweight="bold")
    else:
        ax.set_title(
            "Pareto Frontier: Performance vs Cost", fontsize=14, fontweight="bold"
        )

    # Grid
    ax.grid(True, alpha=0.3, linestyle="--")

    # Legend
    from matplotlib.lines import Line2D

    legend_elements = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor="green",
            markersize=10,
            label="Pareto-optimal",
        ),
        Line2D(
            [0],
            [0],
            marker="x",
            color="w",
            markerfacecolor="red",
            markersize=10,
            label="Dominated",
        ),
    ]
    ax.legend(handles=legend_elements, loc="best", fontsize=10)

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"✓ Pareto frontier plot saved to {output_path}")


def plot_sequence_performance_comparison(
    sequence_aggregates: dict[str, dict[str, dict[str, Any]]],
    output_path: Path,
    metric: str = "mean_cl_f1",
    title: str | None = None,
) -> None:
    """
    Plot sequence-level performance comparison across policies.

    Per Requirement 24:
    - Compare performance metrics across all 8 sequences
    - Show mean ± SEM for each policy
    - Grouped bar chart or line plot

    Args:
        sequence_aggregates: Output from aggregate_sequence_results()
        output_path: Path to save plot
        metric: Metric to plot (e.g., "mean_cl_f1", "mean_resolved_rate")
        title: Optional plot title
    """
    # Extract data for plotting
    sequences = sorted(
        {seq for policy_seqs in sequence_aggregates.values() for seq in policy_seqs}
    )
    policies = sorted(sequence_aggregates.keys())

    # Prepare data matrix: policies × sequences
    data = np.zeros((len(policies), len(sequences)))
    errors = np.zeros((len(policies), len(sequences)))

    for i, policy in enumerate(policies):
        for j, sequence in enumerate(sequences):
            if sequence in sequence_aggregates[policy]:
                seq_data = sequence_aggregates[policy][sequence]
                data[i, j] = seq_data.get(metric, 0.0)

                # Compute SEM from seed values if available
                if "seed_cl_f1_values" in seq_data and metric == "mean_cl_f1":
                    seed_values = seq_data["seed_cl_f1_values"]
                    if len(seed_values) > 1:
                        errors[i, j] = np.std(seed_values, ddof=1) / np.sqrt(
                            len(seed_values)
                        )
                else:
                    # Use std if available
                    std_key = metric.replace("mean_", "std_")
                    if std_key in seq_data:
                        n_seeds = seq_data.get("n_seeds", 3)
                        errors[i, j] = seq_data[std_key] / np.sqrt(n_seeds)

    # Create grouped bar chart
    fig, ax = plt.subplots(figsize=(14, 7))

    x = np.arange(len(sequences))
    width = 0.8 / len(policies)

    for i, policy in enumerate(policies):
        offset = (i - len(policies) / 2) * width + width / 2
        ax.bar(
            x + offset,
            data[i],
            width,
            label=policy,
            yerr=errors[i],
            capsize=3,
            alpha=0.8,
        )

    # Labels and title
    ax.set_xlabel("Sequence", fontsize=12)
    ax.set_ylabel(metric.replace("_", " ").title(), fontsize=12)
    ax.set_xticks(x)
    ax.set_xticklabels(sequences, rotation=45, ha="right")

    if title:
        ax.set_title(title, fontsize=14, fontweight="bold")
    else:
        ax.set_title(
            f"Sequence-Level Performance Comparison: {metric}",
            fontsize=14,
            fontweight="bold",
        )

    ax.legend(loc="best", fontsize=9)
    ax.grid(True, alpha=0.3, linestyle="--", axis="y")

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"✓ Sequence performance comparison plot saved to {output_path}")


def plot_memory_usage_over_time(
    runs_dir: Path,
    output_path: Path,
    policy: str | None = None,
    title: str | None = None,
) -> None:
    """
    Plot memory usage over time (task sequence).

    Shows memory_count_after and memory_tokens_after progression
    across tasks for each policy.

    Args:
        runs_dir: Path to runs/ directory
        output_path: Path to save plot
        policy: Optional specific policy to plot (if None, plot all)
        title: Optional plot title
    """
    # Load task results grouped by policy
    policy_data: dict[str, list[dict[str, Any]]] = {}

    for run_dir in runs_dir.iterdir():
        if not run_dir.is_dir():
            continue

        task_results_path = run_dir / "task_results.jsonl"
        if not task_results_path.exists():
            continue

        with open(task_results_path) as f:
            for line in f:
                if not line.strip():
                    continue

                task_result = json.loads(line)
                pol = task_result["policy"]

                # Filter by policy if specified
                if policy and pol != policy:
                    continue

                if pol not in policy_data:
                    policy_data[pol] = []

                policy_data[pol].append(task_result)

    # Sort by sequence_index within each policy
    for pol in policy_data:
        policy_data[pol].sort(key=lambda x: x["sequence_index"])

    # Create subplots: memory count and memory tokens
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

    # Plot memory count over time
    for pol, tasks in sorted(policy_data.items()):
        sequence_indices = [t["sequence_index"] for t in tasks]
        memory_counts = [t.get("memory_count_after", 0) for t in tasks]

        ax1.plot(sequence_indices, memory_counts, marker="o", label=pol, alpha=0.7)

    ax1.set_xlabel("Task Sequence Index", fontsize=12)
    ax1.set_ylabel("Memory Count (after task)", fontsize=12)
    ax1.set_title("Memory Count Over Time", fontsize=13, fontweight="bold")
    ax1.legend(loc="best", fontsize=9)
    ax1.grid(True, alpha=0.3, linestyle="--")

    # Plot memory tokens over time
    for pol, tasks in sorted(policy_data.items()):
        sequence_indices = [t["sequence_index"] for t in tasks]
        memory_tokens = [t.get("memory_tokens_after", 0) for t in tasks]

        ax2.plot(sequence_indices, memory_tokens, marker="o", label=pol, alpha=0.7)

    ax2.set_xlabel("Task Sequence Index", fontsize=12)
    ax2.set_ylabel("Memory Tokens (after task)", fontsize=12)
    ax2.set_title("Memory Tokens Over Time", fontsize=13, fontweight="bold")
    ax2.legend(loc="best", fontsize=9)
    ax2.grid(True, alpha=0.3, linestyle="--")

    if title:
        fig.suptitle(title, fontsize=14, fontweight="bold", y=0.995)

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"✓ Memory usage over time plot saved to {output_path}")


def plot_behavioral_metrics_comparison(
    sequence_aggregates: dict[str, dict[str, dict[str, Any]]],
    output_path: Path,
    title: str | None = None,
) -> None:
    """
    Plot behavioral metrics comparison across policies.

    Per Requirement 29:
    - Compare tool-call frequency across policies
    - Compare syntax-error rates across policies
    - Test whether Full Memory has higher rates (analysis paralysis)

    Args:
        sequence_aggregates: Output from aggregate_sequence_results()
        output_path: Path to save plot
        title: Optional plot title
    """
    # Extract behavioral metrics
    policies = sorted(sequence_aggregates.keys())

    tool_calls_means = []
    tool_calls_sems = []
    wall_time_means = []
    wall_time_sems = []

    for policy in policies:
        sequences = sequence_aggregates[policy]

        # Aggregate tool calls across sequences
        tool_calls_values = [seq["mean_tool_calls"] for seq in sequences.values()]
        tool_calls_means.append(np.mean(tool_calls_values))
        tool_calls_sems.append(
            np.std(tool_calls_values, ddof=1) / np.sqrt(len(tool_calls_values))
            if len(tool_calls_values) > 1
            else 0.0
        )

        # Aggregate wall time across sequences
        wall_time_values = [seq["mean_wall_time"] for seq in sequences.values()]
        wall_time_means.append(np.mean(wall_time_values))
        wall_time_sems.append(
            np.std(wall_time_values, ddof=1) / np.sqrt(len(wall_time_values))
            if len(wall_time_values) > 1
            else 0.0
        )

    # Create subplots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Plot tool calls
    x = np.arange(len(policies))
    ax1.bar(x, tool_calls_means, yerr=tool_calls_sems, capsize=5, alpha=0.7)
    ax1.set_xlabel("Policy", fontsize=12)
    ax1.set_ylabel("Mean Tool Calls per Task", fontsize=12)
    ax1.set_title("Tool Call Frequency by Policy", fontsize=13, fontweight="bold")
    ax1.set_xticks(x)
    ax1.set_xticklabels(policies, rotation=45, ha="right")
    ax1.grid(True, alpha=0.3, linestyle="--", axis="y")

    # Highlight Full Memory if present
    if "full_memory" in policies:
        full_memory_idx = policies.index("full_memory")
        ax1.get_children()[full_memory_idx].set_color("red")
        ax1.get_children()[full_memory_idx].set_alpha(0.9)

    # Plot wall time
    ax2.bar(x, wall_time_means, yerr=wall_time_sems, capsize=5, alpha=0.7)
    ax2.set_xlabel("Policy", fontsize=12)
    ax2.set_ylabel("Mean Wall Time per Task (seconds)", fontsize=12)
    ax2.set_title("Execution Time by Policy", fontsize=13, fontweight="bold")
    ax2.set_xticks(x)
    ax2.set_xticklabels(policies, rotation=45, ha="right")
    ax2.grid(True, alpha=0.3, linestyle="--", axis="y")

    # Highlight Full Memory if present
    if "full_memory" in policies:
        full_memory_idx = policies.index("full_memory")
        ax2.get_children()[full_memory_idx].set_color("red")
        ax2.get_children()[full_memory_idx].set_alpha(0.9)

    if title:
        fig.suptitle(title, fontsize=14, fontweight="bold")

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"✓ Behavioral metrics comparison plot saved to {output_path}")


def plot_failure_analysis(
    failure_report: dict[str, Any],
    output_path: Path,
    title: str | None = None,
) -> None:
    """
    Plot failure analysis results.

    Per Requirement 28:
    - Show per-policy failure rates by category
    - Highlight boundary tasks (Full Memory fails, pruning succeeds)

    Args:
        failure_report: Output from generate_failure_analysis_report()
        output_path: Path to save plot
        title: Optional plot title
    """
    failure_rates = failure_report["failure_rates"]
    policies = sorted(failure_rates.keys())

    # Define failure categories
    categories = ["timeout", "test_failure", "syntax_error", "tool_error", "unknown"]

    # Prepare data matrix: policies × categories
    data = np.zeros((len(policies), len(categories)))

    for i, policy in enumerate(policies):
        rates = failure_rates[policy]
        for j, category in enumerate(categories):
            data[i, j] = rates.get(category, 0.0) * 100  # Convert to percentage

    # Create stacked bar chart
    fig, ax = plt.subplots(figsize=(12, 7))

    x = np.arange(len(policies))
    width = 0.6

    # Color palette for categories
    colors = ["#e74c3c", "#f39c12", "#f1c40f", "#3498db", "#95a5a6"]

    bottom = np.zeros(len(policies))
    for j, category in enumerate(categories):
        ax.bar(
            x,
            data[:, j],
            width,
            label=category.replace("_", " ").title(),
            bottom=bottom,
            color=colors[j],
            alpha=0.8,
        )
        bottom += data[:, j]

    # Labels and title
    ax.set_xlabel("Policy", fontsize=12)
    ax.set_ylabel("Failure Rate (%)", fontsize=12)
    ax.set_xticks(x)
    ax.set_xticklabels(policies, rotation=45, ha="right")

    if title:
        ax.set_title(title, fontsize=14, fontweight="bold")
    else:
        ax.set_title(
            "Failure Analysis by Policy and Category", fontsize=14, fontweight="bold"
        )

    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True, alpha=0.3, linestyle="--", axis="y")

    # Add boundary task count annotation
    boundary_count = failure_report["summary"]["n_boundary_tasks"]
    ax.text(
        0.02,
        0.98,
        f"Boundary tasks (Full Memory fails, pruning succeeds): {boundary_count}",
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment="top",
        bbox={"boxstyle": "round", "facecolor": "wheat", "alpha": 0.5},
    )

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"✓ Failure analysis plot saved to {output_path}")


def generate_all_plots(
    sequence_aggregates: dict[str, dict[str, dict[str, Any]]],
    runs_dir: Path,
    failure_report: dict[str, Any],
    output_dir: Path,
) -> None:
    """
    Generate all analysis plots.

    Per Task 18.1:
    - CL-F1 vs cost Pareto frontier
    - Sequence-level performance comparison
    - Memory usage over time
    - Behavioral metrics comparison
    - Failure analysis

    Args:
        sequence_aggregates: Output from aggregate_sequence_results()
        runs_dir: Path to runs/ directory
        failure_report: Output from generate_failure_analysis_report()
        output_dir: Path to save all plots
    """
    print("=" * 80)
    print("GENERATING ANALYSIS PLOTS")
    print("=" * 80)
    print()

    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Pareto frontier plots
    print("[1/7] Generating Pareto frontier: CL-F1 vs Cost...")
    plot_pareto_frontier(
        sequence_aggregates=sequence_aggregates,
        output_path=output_dir / "pareto_cl_f1_vs_cost.png",
        metric_x="mean_total_cost",
        metric_y="mean_cl_f1",
        title="Pareto Frontier: CL-F1 vs Total Cost",
    )

    print("[2/7] Generating Pareto frontier: CL-F1 vs Tokens...")
    plot_pareto_frontier(
        sequence_aggregates=sequence_aggregates,
        output_path=output_dir / "pareto_cl_f1_vs_tokens.png",
        metric_x="mean_total_tokens",
        metric_y="mean_cl_f1",
        title="Pareto Frontier: CL-F1 vs Total Tokens",
    )

    # 2. Sequence-level performance comparison
    print("[3/7] Generating sequence performance comparison: CL-F1...")
    plot_sequence_performance_comparison(
        sequence_aggregates=sequence_aggregates,
        output_path=output_dir / "sequence_comparison_cl_f1.png",
        metric="mean_cl_f1",
        title="Sequence-Level CL-F1 Comparison",
    )

    print("[4/7] Generating sequence performance comparison: Resolved Rate...")
    plot_sequence_performance_comparison(
        sequence_aggregates=sequence_aggregates,
        output_path=output_dir / "sequence_comparison_resolved_rate.png",
        metric="mean_resolved_rate",
        title="Sequence-Level Resolved Rate Comparison",
    )

    # 3. Memory usage over time
    print("[5/7] Generating memory usage over time plot...")
    plot_memory_usage_over_time(
        runs_dir=runs_dir,
        output_path=output_dir / "memory_usage_over_time.png",
        title="Memory Usage Over Time (All Policies)",
    )

    # 4. Behavioral metrics comparison
    print("[6/7] Generating behavioral metrics comparison...")
    plot_behavioral_metrics_comparison(
        sequence_aggregates=sequence_aggregates,
        output_path=output_dir / "behavioral_metrics_comparison.png",
        title="Behavioral Metrics: Tool Calls and Execution Time",
    )

    # 5. Failure analysis
    print("[7/7] Generating failure analysis plot...")
    plot_failure_analysis(
        failure_report=failure_report,
        output_path=output_dir / "failure_analysis.png",
        title="Failure Analysis by Policy and Category",
    )

    print()
    print("=" * 80)
    print(f"✓ All plots saved to {output_dir}")
    print("=" * 80)
