"""
Result tables generation for memory pruning experiments.

This module implements Task 18.2: Implement result tables.

Per THESIS_FINAL_v5.md §15-17:
- Statistical test results tables (Wilcoxon + Holm correction)
- Effect size tables with confidence intervals (rank-biserial + BCa CI)
- Per-policy performance summary tables
- Cost breakdown tables

Requirements: 20, 21, 27
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def generate_statistical_test_table(
    wilcoxon_results: dict[str, Any],
    output_path: Path | None = None,
) -> pd.DataFrame:
    """
    Generate statistical test results table.

    Per THESIS_FINAL_v5.md §15.2:
    - Wilcoxon signed-rank test on N=8 sequence means
    - Holm correction for family-wise error rate control
    - Report: policy, n, statistic, p-value, Holm p-value, significance

    Args:
        wilcoxon_results: Output from run_wilcoxon_with_holm()
        output_path: Optional path to save table as CSV

    Returns:
        DataFrame with statistical test results
    """
    contrasts = wilcoxon_results["contrasts"]
    baseline = wilcoxon_results["baseline_policy"]
    metric = wilcoxon_results["metric"]

    rows = []
    for contrast in contrasts:
        rows.append(
            {
                "Policy": contrast["policy"],
                "Baseline": baseline,
                "N": contrast["n"],
                "Statistic": f"{contrast['statistic']:.2f}",
                "p-value": f"{contrast['p_value']:.4f}",
                "Holm p-value": f"{contrast['holm_p_value']:.4f}",
                "Significant": "Yes" if contrast["significant"] else "No",
            }
        )

    df = pd.DataFrame(rows)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        print(f"✓ Statistical test table saved to {output_path}")

    return df


def generate_effect_size_table(
    wilcoxon_results: dict[str, Any],
    output_path: Path | None = None,
) -> pd.DataFrame:
    """
    Generate effect size table with confidence intervals.

    Per THESIS_FINAL_v5.md §15.2:
    - Rank-biserial effect size r_rb
    - Median paired difference
    - Bootstrap BCa 95% confidence intervals (5000 iterations)
    - Interpretation: |r_rb| ≈ 0.1 small, ≈ 0.3 medium, ≈ 0.5 large

    Args:
        wilcoxon_results: Output from compute_all_contrasts_with_bootstrap()
        output_path: Optional path to save table as CSV

    Returns:
        DataFrame with effect sizes and confidence intervals
    """
    contrasts = wilcoxon_results["contrasts"]
    baseline = wilcoxon_results["baseline_policy"]
    metric = wilcoxon_results["metric"]

    rows = []
    for contrast in contrasts:
        # Extract bootstrap CI if available
        if "bootstrap_ci" in contrast:
            bca = contrast["bootstrap_ci"]
            ci_lower = bca["ci_lower"]
            ci_upper = bca["ci_upper"]
            ci_str = f"[{ci_lower:.4f}, {ci_upper:.4f}]"
        else:
            ci_str = "N/A"

        # Interpret effect size magnitude
        r_rb = abs(contrast["rank_biserial"])
        if r_rb < 0.1:
            magnitude = "Negligible"
        elif r_rb < 0.3:
            magnitude = "Small"
        elif r_rb < 0.5:
            magnitude = "Medium"
        else:
            magnitude = "Large"

        rows.append(
            {
                "Policy": contrast["policy"],
                "Baseline": baseline,
                "Median Diff": f"{contrast['median_diff']:.4f}",
                "Rank-Biserial r_rb": f"{contrast['rank_biserial']:.4f}",
                "Effect Size": magnitude,
                "95% BCa CI": ci_str,
                "Significant": "Yes" if contrast.get("significant", False) else "No",
            }
        )

    df = pd.DataFrame(rows)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        print(f"✓ Effect size table saved to {output_path}")

    return df


def generate_performance_summary_table(
    sequence_aggregates: dict[str, dict[str, dict[str, Any]]],
    output_path: Path | None = None,
) -> pd.DataFrame:
    """
    Generate per-policy performance summary table.

    Per THESIS_FINAL_v5.md §14-15:
    - Mean ± SD across sequences for each policy
    - Metrics: CL-F1, resolved rate, tool calls, wall time
    - N sequences, N seeds per sequence

    Args:
        sequence_aggregates: Output from aggregate_sequence_results()
        output_path: Optional path to save table as CSV

    Returns:
        DataFrame with per-policy performance summary
    """
    rows = []

    for policy, sequences in sequence_aggregates.items():
        # Aggregate across sequences
        cl_f1_values = [seq["mean_cl_f1"] for seq in sequences.values()]
        resolved_values = [seq["mean_resolved_rate"] for seq in sequences.values()]
        tool_calls_values = [seq["mean_tool_calls"] for seq in sequences.values()]
        wall_time_values = [seq["mean_wall_time"] for seq in sequences.values()]

        n_sequences = len(sequences)
        n_seeds = sequences[list(sequences.keys())[0]]["n_seeds"]

        rows.append(
            {
                "Policy": policy,
                "N Sequences": n_sequences,
                "N Seeds": n_seeds,
                "CL-F1 (Mean ± SD)": f"{np.mean(cl_f1_values):.4f} ± {np.std(cl_f1_values, ddof=1):.4f}",
                "Resolved Rate (Mean ± SD)": f"{np.mean(resolved_values):.4f} ± {np.std(resolved_values, ddof=1):.4f}",
                "Tool Calls (Mean ± SD)": f"{np.mean(tool_calls_values):.2f} ± {np.std(tool_calls_values, ddof=1):.2f}",
                "Wall Time (Mean ± SD)": f"{np.mean(wall_time_values):.1f} ± {np.std(wall_time_values, ddof=1):.1f}",
            }
        )

    df = pd.DataFrame(rows)

    # Sort by CL-F1 descending
    df["_sort_key"] = df["CL-F1 (Mean ± SD)"].apply(
        lambda x: float(x.split(" ± ")[0])
    )
    df = df.sort_values("_sort_key", ascending=False).drop(columns=["_sort_key"])

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        print(f"✓ Performance summary table saved to {output_path}")

    return df


def generate_cost_breakdown_table(
    sequence_aggregates: dict[str, dict[str, dict[str, Any]]],
    output_path: Path | None = None,
) -> pd.DataFrame:
    """
    Generate cost breakdown table.

    Per THESIS_FINAL_v5.md §17 and Requirement 27:
    - Total cost per policy (mean ± SD across sequences)
    - Total tokens per policy
    - Cost per task
    - Cost-normalized CL-F1 (CL-F1 / cost)

    Args:
        sequence_aggregates: Output from aggregate_sequence_results()
        output_path: Optional path to save table as CSV

    Returns:
        DataFrame with cost breakdown per policy
    """
    rows = []

    for policy, sequences in sequence_aggregates.items():
        # Aggregate across sequences
        cost_values = [seq["mean_total_cost"] for seq in sequences.values()]
        token_values = [seq["mean_total_tokens"] for seq in sequences.values()]
        cl_f1_values = [seq["mean_cl_f1"] for seq in sequences.values()]
        n_tasks_values = [seq["n_tasks"] for seq in sequences.values()]

        mean_cost = np.mean(cost_values)
        std_cost = np.std(cost_values, ddof=1)
        mean_tokens = np.mean(token_values)
        std_tokens = np.std(token_values, ddof=1)
        mean_cl_f1 = np.mean(cl_f1_values)
        mean_n_tasks = np.mean(n_tasks_values)

        # Cost per task
        cost_per_task = mean_cost / mean_n_tasks if mean_n_tasks > 0 else 0.0

        # Cost-normalized CL-F1
        cost_normalized_cl_f1 = mean_cl_f1 / mean_cost if mean_cost > 0 else 0.0

        rows.append(
            {
                "Policy": policy,
                "Total Cost (Mean ± SD)": f"${mean_cost:.2f} ± ${std_cost:.2f}",
                "Total Tokens (Mean ± SD)": f"{mean_tokens:.0f} ± {std_tokens:.0f}",
                "Cost per Task": f"${cost_per_task:.4f}",
                "CL-F1 per Dollar": f"{cost_normalized_cl_f1:.4f}",
            }
        )

    df = pd.DataFrame(rows)

    # Sort by total cost ascending
    df["_sort_key"] = df["Total Cost (Mean ± SD)"].apply(
        lambda x: float(x.split(" ± ")[0].replace("$", ""))
    )
    df = df.sort_values("_sort_key", ascending=True).drop(columns=["_sort_key"])

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        print(f"✓ Cost breakdown table saved to {output_path}")

    return df


def generate_all_result_tables(
    sequence_aggregates: dict[str, dict[str, dict[str, Any]]],
    wilcoxon_results: dict[str, Any],
    output_dir: Path,
) -> dict[str, pd.DataFrame]:
    """
    Generate all result tables for the experiment.

    This is the main entry point for Task 18.2.

    Args:
        sequence_aggregates: Output from aggregate_sequence_results()
        wilcoxon_results: Output from compute_all_contrasts_with_bootstrap()
        output_dir: Directory to save all tables

    Returns:
        Dict mapping table name to DataFrame
    """
    print("=" * 80)
    print("GENERATING RESULT TABLES")
    print("=" * 80)

    output_dir.mkdir(parents=True, exist_ok=True)

    tables = {}

    # 1. Statistical test results table
    print("\n[1/4] Statistical test results table...")
    tables["statistical_tests"] = generate_statistical_test_table(
        wilcoxon_results=wilcoxon_results,
        output_path=output_dir / "statistical_tests.csv",
    )

    # 2. Effect size table with confidence intervals
    print("\n[2/4] Effect size table...")
    tables["effect_sizes"] = generate_effect_size_table(
        wilcoxon_results=wilcoxon_results,
        output_path=output_dir / "effect_sizes.csv",
    )

    # 3. Per-policy performance summary table
    print("\n[3/4] Performance summary table...")
    tables["performance_summary"] = generate_performance_summary_table(
        sequence_aggregates=sequence_aggregates,
        output_path=output_dir / "performance_summary.csv",
    )

    # 4. Cost breakdown table
    print("\n[4/4] Cost breakdown table...")
    tables["cost_breakdown"] = generate_cost_breakdown_table(
        sequence_aggregates=sequence_aggregates,
        output_path=output_dir / "cost_breakdown.csv",
    )

    print(f"\n✓ All tables saved to {output_dir}")
    print("=" * 80)

    return tables


def print_table_summary(tables: dict[str, pd.DataFrame]) -> None:
    """
    Print a summary of all generated tables to console.

    Args:
        tables: Dict mapping table name to DataFrame
    """
    print("\n" + "=" * 80)
    print("TABLE SUMMARY")
    print("=" * 80)

    for table_name, df in tables.items():
        print(f"\n{table_name.upper().replace('_', ' ')}:")
        print("-" * 80)
        print(df.to_string(index=False))
        print()
