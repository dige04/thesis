"""
Pareto frontier analysis for memory pruning experiments.

This module implements Task 16.1: Pareto frontier analysis.

Per THESIS_FINAL_v5.md §17:
- Plot CL-F1 vs total cost for all 6 policies
- Identify Pareto-optimal policies (not dominated on both axes)
- Add per-sequence error bars (3 seeds → SEM)
- Compute cost-normalized CL-F1 for CLS Consolidation
"""

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Ellipse


def compute_pareto_frontier(
    sequence_aggregates: dict[str, dict[str, dict[str, Any]]],
    metric_x: str = "mean_total_tokens",
    metric_y: str = "mean_cl_f1",
) -> dict[str, Any]:
    """
    Identify Pareto-optimal policies.

    Per THESIS_FINAL_v5.md §17:
    - Pareto-optimal: no other policy achieves both higher Y and lower X
    - These become the practical recommendations

    Args:
        sequence_aggregates: Output from aggregate_sequence_results()
        metric_x: X-axis metric (cost, lower is better)
        metric_y: Y-axis metric (CL-F1, higher is better)

    Returns:
        Dict with:
        - policy_points: List of (policy, x, y, x_sem, y_sem)
        - pareto_optimal: List of Pareto-optimal policy names
        - dominated: List of dominated policy names
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
        sem_x = np.std(x_values, ddof=1) / np.sqrt(len(x_values)) if len(x_values) > 1 else 0.0
        sem_y = np.std(y_values, ddof=1) / np.sqrt(len(y_values)) if len(y_values) > 1 else 0.0

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
    # A policy is Pareto-optimal if no other policy has both:
    # - Lower cost (x) AND higher performance (y)
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

    return {
        "policy_points": policy_points,
        "pareto_optimal": pareto_optimal,
        "dominated": dominated,
        "metric_x": metric_x,
        "metric_y": metric_y,
    }


def plot_pareto_frontier(
    pareto_data: dict[str, Any],
    output_path: Path | None = None,
    title: str | None = None,
) -> None:
    """
    Plot Pareto frontier with confidence ellipses.

    Per THESIS_FINAL_v5.md §17:
    - X-axis: total cost (USD)
    - Y-axis: CL-F1
    - Error bars: SEM from 3 seeds
    - Highlight Pareto-optimal policies

    Args:
        pareto_data: Output from compute_pareto_frontier()
        output_path: Optional path to save plot
        title: Optional plot title
    """
    policy_points = pareto_data["policy_points"]
    pareto_optimal = pareto_data["pareto_optimal"]
    metric_x = pareto_data["metric_x"]
    metric_y = pareto_data["metric_y"]

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
        ax.set_title("Pareto Frontier: Performance vs Cost", fontsize=14, fontweight="bold")

    # Grid
    ax.grid(True, alpha=0.3, linestyle="--")

    # Legend
    # Create custom legend entries
    from matplotlib.lines import Line2D

    legend_elements = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor="green", markersize=10, label="Pareto-optimal"),
        Line2D([0], [0], marker="x", color="w", markerfacecolor="red", markersize=10, label="Dominated"),
    ]
    ax.legend(handles=legend_elements, loc="best", fontsize=10)

    plt.tight_layout()

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        print(f"✓ Pareto plot saved to {output_path}")

    plt.close()


def compute_cost_normalized_metrics(
    sequence_aggregates: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, float]:
    """
    Compute cost-normalized CL-F1 for each policy.

    Per THESIS_FINAL_v5.md §17:
    - CL_F1_per_dollar = CL_F1 / total_cost_usd
    - If CLS matches Type-Aware Decay but costs 3× more, CLS fails Pareto test

    Args:
        sequence_aggregates: Output from aggregate_sequence_results()

    Returns:
        Dict mapping policy name to cost-normalized CL-F1
    """
    cost_normalized = {}

    for policy, sequences in sequence_aggregates.items():
        # Aggregate across sequences
        cl_f1_values = [seq["mean_cl_f1"] for seq in sequences.values()]
        cost_values = [seq["mean_total_cost"] for seq in sequences.values()]

        mean_cl_f1 = np.mean(cl_f1_values)
        mean_cost = np.mean(cost_values)

        # Cost-normalized CL-F1
        if mean_cost > 0:
            cost_normalized[policy] = mean_cl_f1 / mean_cost
        else:
            cost_normalized[policy] = 0.0

    return cost_normalized


def run_pareto_analysis(
    sequence_aggregates: dict[str, dict[str, dict[str, Any]]],
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Run complete Pareto analysis.

    Args:
        sequence_aggregates: Output from aggregate_sequence_results()
        output_dir: Optional path to save results

    Returns:
        Dict with:
        - cl_f1_vs_cost: Pareto frontier for CL-F1 vs cost
        - resolved_vs_cost: Pareto frontier for resolved rate vs cost
        - cl_f1_vs_tokens: Pareto frontier for CL-F1 vs tokens
        - cl_f1_vs_tool_calls: Pareto frontier for CL-F1 vs tool calls
        - cost_normalized: Cost-normalized CL-F1 per policy
    """
    print("=" * 80)
    print("PARETO FRONTIER ANALYSIS")
    print("=" * 80)

    # 1. CL-F1 vs Total Cost (PRIMARY)
    print("\n[1/4] CL-F1 vs Total Cost...")
    cl_f1_vs_cost = compute_pareto_frontier(
        sequence_aggregates=sequence_aggregates,
        metric_x="mean_total_cost",
        metric_y="mean_cl_f1",
    )

    print(f"  Pareto-optimal: {cl_f1_vs_cost['pareto_optimal']}")
    print(f"  Dominated: {cl_f1_vs_cost['dominated']}")

    if output_dir:
        plot_pareto_frontier(
            pareto_data=cl_f1_vs_cost,
            output_path=output_dir / "pareto_cl_f1_vs_cost.png",
            title="Pareto Frontier: CL-F1 vs Total Cost",
        )

    # 2. Resolved Rate vs Total Cost
    print("\n[2/4] Resolved Rate vs Total Cost...")
    resolved_vs_cost = compute_pareto_frontier(
        sequence_aggregates=sequence_aggregates,
        metric_x="mean_total_cost",
        metric_y="mean_resolved_rate",
    )

    print(f"  Pareto-optimal: {resolved_vs_cost['pareto_optimal']}")

    if output_dir:
        plot_pareto_frontier(
            pareto_data=resolved_vs_cost,
            output_path=output_dir / "pareto_resolved_vs_cost.png",
            title="Pareto Frontier: Resolved Rate vs Total Cost",
        )

    # 3. CL-F1 vs Total Tokens
    print("\n[3/4] CL-F1 vs Total Tokens...")
    cl_f1_vs_tokens = compute_pareto_frontier(
        sequence_aggregates=sequence_aggregates,
        metric_x="mean_total_tokens",
        metric_y="mean_cl_f1",
    )

    print(f"  Pareto-optimal: {cl_f1_vs_tokens['pareto_optimal']}")

    if output_dir:
        plot_pareto_frontier(
            pareto_data=cl_f1_vs_tokens,
            output_path=output_dir / "pareto_cl_f1_vs_tokens.png",
            title="Pareto Frontier: CL-F1 vs Total Tokens",
        )

    # 4. CL-F1 vs Tool Calls (Efficiency)
    print("\n[4/4] CL-F1 vs Tool Calls...")
    cl_f1_vs_tool_calls = compute_pareto_frontier(
        sequence_aggregates=sequence_aggregates,
        metric_x="mean_tool_calls",
        metric_y="mean_cl_f1",
    )

    print(f"  Pareto-optimal: {cl_f1_vs_tool_calls['pareto_optimal']}")

    if output_dir:
        plot_pareto_frontier(
            pareto_data=cl_f1_vs_tool_calls,
            output_path=output_dir / "pareto_cl_f1_vs_tool_calls.png",
            title="Pareto Frontier: CL-F1 vs Tool Calls",
        )

    # Cost-normalized CL-F1
    print("\n[Cost-Normalized CL-F1]")
    cost_normalized = compute_cost_normalized_metrics(sequence_aggregates)

    for policy, value in sorted(cost_normalized.items(), key=lambda x: x[1], reverse=True):
        print(f"  {policy:25s}: {value:.6f}")

    # Save results
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

        results = {
            "cl_f1_vs_cost": {
                k: v for k, v in cl_f1_vs_cost.items() if k != "policy_points"
            },
            "resolved_vs_cost": {
                k: v for k, v in resolved_vs_cost.items() if k != "policy_points"
            },
            "cl_f1_vs_tokens": {
                k: v for k, v in cl_f1_vs_tokens.items() if k != "policy_points"
            },
            "cl_f1_vs_tool_calls": {
                k: v for k, v in cl_f1_vs_tool_calls.items() if k != "policy_points"
            },
            "cost_normalized": cost_normalized,
        }

        with open(output_dir / "pareto_analysis_results.json", "w") as f:
            json.dump(results, f, indent=2)

        print(f"\n✓ Results saved to {output_dir}")

    return {
        "cl_f1_vs_cost": cl_f1_vs_cost,
        "resolved_vs_cost": resolved_vs_cost,
        "cl_f1_vs_tokens": cl_f1_vs_tokens,
        "cl_f1_vs_tool_calls": cl_f1_vs_tool_calls,
        "cost_normalized": cost_normalized,
    }
