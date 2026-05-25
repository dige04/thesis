"""
Behavioral metrics for analysis paralysis detection.

This module implements Task 16.2: Behavioral metrics.

Per THESIS_FINAL_v5.md §14.6 and H4:
- Tool calls per task
- Syntax error rate
- Test whether Full Memory induces analysis paralysis
- Forgetting policies should mitigate behavioral degradation
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats


def compute_behavioral_metrics(
    runs_dir: Path,
) -> pd.DataFrame:
    """
    Compute behavioral metrics per task.

    Per THESIS_FINAL_v5.md §14.6:
    - tool_calls_per_task
    - syntax_error_rate = n_syntax_errors / n_tool_calls
    - files_read_per_task
    - test_runs_per_task

    Args:
        runs_dir: Path to runs/ directory

    Returns:
        DataFrame with columns:
        - task_id, policy, seed, sequence, sequence_index
        - tool_calls, syntax_errors, syntax_error_rate
        - files_read, files_modified, test_runs
    """
    records = []

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
                task = json.loads(line)

                tool_calls = task.get("tool_calls", 0)
                syntax_errors = task.get("syntax_error", 0)  # Count of syntax errors
                syntax_error_rate = task.get("syntax_error_rate", 0.0)

                records.append(
                    {
                        "task_id": task["task_id"],
                        "policy": task["policy"],
                        "seed": task["seed"],
                        "sequence": task["repo"],
                        "sequence_index": task["sequence_index"],
                        "tool_calls": tool_calls,
                        "syntax_errors": syntax_errors,
                        "syntax_error_rate": syntax_error_rate,
                        "files_read": task.get("files_read", 0),
                        "files_modified": task.get("files_modified", 0),
                        "test_runs": task.get("test_runs", 0),
                    }
                )

    return pd.DataFrame(records)


def aggregate_behavioral_metrics(
    behavioral_df: pd.DataFrame,
) -> dict[str, dict[str, float]]:
    """
    Aggregate behavioral metrics per policy.

    Per THESIS_FINAL_v5.md §14.6:
    - Mean tool-call count per policy
    - Mean syntax-error rate per policy
    - Test whether Full Memory has higher values

    Args:
        behavioral_df: Output from compute_behavioral_metrics()

    Returns:
        Dict mapping policy to aggregated metrics
    """
    aggregated = {}

    for policy in behavioral_df["policy"].unique():
        policy_df = behavioral_df[behavioral_df["policy"] == policy]

        aggregated[policy] = {
            "mean_tool_calls": float(policy_df["tool_calls"].mean()),
            "std_tool_calls": float(policy_df["tool_calls"].std()),
            "mean_syntax_error_rate": float(policy_df["syntax_error_rate"].mean()),
            "std_syntax_error_rate": float(policy_df["syntax_error_rate"].std()),
            "mean_files_read": float(policy_df["files_read"].mean()),
            "std_files_read": float(policy_df["files_read"].std()),
            "mean_test_runs": float(policy_df["test_runs"].mean()),
            "std_test_runs": float(policy_df["test_runs"].std()),
            "n_tasks": len(policy_df),
        }

    return aggregated


def test_analysis_paralysis(
    behavioral_df: pd.DataFrame,
    baseline_policy: str = "full_memory",
    comparison_policies: list[str] | None = None,
) -> dict[str, Any]:
    """
    Test H4: Full Memory induces analysis paralysis.

    Per THESIS_FINAL_v5.md H4:
    - Full-memory accumulation induces measurable analysis paralysis
    - Increased tool calls and syntax errors
    - Forgetting policies mitigate this

    Args:
        behavioral_df: Output from compute_behavioral_metrics()
        baseline_policy: Baseline policy (default: "full_memory")
        comparison_policies: Policies to compare against baseline

    Returns:
        Dict with:
        - tool_calls_tests: Wilcoxon tests for tool calls
        - syntax_error_tests: Wilcoxon tests for syntax error rate
        - conclusion: Whether H4 is supported
    """
    if comparison_policies is None:
        comparison_policies = [
            "no_memory",
            "random_prune",
            "recency_prune",
            "type_aware_decay",
            "cls_consolidation",
        ]

    # Extract baseline values (sequence-level means)
    baseline_df = behavioral_df[behavioral_df["policy"] == baseline_policy]
    baseline_tool_calls = (
        baseline_df.groupby("sequence")["tool_calls"].mean().values
    )
    baseline_syntax_rate = (
        baseline_df.groupby("sequence")["syntax_error_rate"].mean().values
    )

    tool_calls_tests = []
    syntax_error_tests = []

    for policy in comparison_policies:
        if policy not in behavioral_df["policy"].values:
            continue

        policy_df = behavioral_df[behavioral_df["policy"] == policy]

        # Sequence-level means
        policy_tool_calls = policy_df.groupby("sequence")["tool_calls"].mean().values
        policy_syntax_rate = (
            policy_df.groupby("sequence")["syntax_error_rate"].mean().values
        )

        # Ensure same sequences
        common_sequences = set(baseline_df["sequence"].unique()) & set(
            policy_df["sequence"].unique()
        )
        if len(common_sequences) < 3:
            continue

        # Wilcoxon signed-rank test
        # H4: Full Memory has HIGHER tool calls and syntax errors
        # Alternative: "greater" (baseline > policy)
        tool_calls_stat, tool_calls_p = stats.wilcoxon(
            baseline_tool_calls,
            policy_tool_calls,
            alternative="greater",
        )

        syntax_stat, syntax_p = stats.wilcoxon(
            baseline_syntax_rate,
            policy_syntax_rate,
            alternative="greater",
        )

        # Median difference
        tool_calls_diff = np.median(baseline_tool_calls - policy_tool_calls)
        syntax_diff = np.median(baseline_syntax_rate - policy_syntax_rate)

        tool_calls_tests.append(
            {
                "policy": policy,
                "baseline": baseline_policy,
                "median_diff": float(tool_calls_diff),
                "statistic": float(tool_calls_stat),
                "p_value": float(tool_calls_p),
                "significant": tool_calls_p < 0.05,
            }
        )

        syntax_error_tests.append(
            {
                "policy": policy,
                "baseline": baseline_policy,
                "median_diff": float(syntax_diff),
                "statistic": float(syntax_stat),
                "p_value": float(syntax_p),
                "significant": syntax_p < 0.05,
            }
        )

    # Conclusion: H4 supported if Full Memory has significantly higher values
    # for at least one pruning policy
    h4_supported_tool_calls = any(t["significant"] for t in tool_calls_tests)
    h4_supported_syntax = any(t["significant"] for t in syntax_error_tests)

    conclusion = {
        "h4_supported": h4_supported_tool_calls or h4_supported_syntax,
        "tool_calls_evidence": h4_supported_tool_calls,
        "syntax_error_evidence": h4_supported_syntax,
        "interpretation": "",
    }

    if conclusion["h4_supported"]:
        conclusion["interpretation"] = (
            "H4 SUPPORTED: Full Memory induces measurable analysis paralysis. "
            "Forgetting policies mitigate behavioral degradation."
        )
    else:
        conclusion["interpretation"] = (
            "H4 NOT SUPPORTED: No significant evidence of analysis paralysis. "
            "Full Memory does not induce higher tool calls or syntax errors."
        )

    return {
        "tool_calls_tests": tool_calls_tests,
        "syntax_error_tests": syntax_error_tests,
        "conclusion": conclusion,
    }


def run_behavioral_analysis(
    runs_dir: Path,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Run complete behavioral metrics analysis.

    Args:
        runs_dir: Path to runs/ directory
        output_dir: Optional path to save results

    Returns:
        Dict with:
        - behavioral_metrics: Per-policy aggregated metrics
        - analysis_paralysis_test: H4 test results
    """
    print("=" * 80)
    print("BEHAVIORAL METRICS ANALYSIS")
    print("Testing H4: Analysis Paralysis")
    print("=" * 80)

    # Compute behavioral metrics
    print("\n[1/3] Computing behavioral metrics per task...")
    behavioral_df = compute_behavioral_metrics(runs_dir)

    print(f"  Total tasks: {len(behavioral_df)}")
    print(f"  Policies: {behavioral_df['policy'].nunique()}")

    # Aggregate per policy
    print("\n[2/3] Aggregating per policy...")
    aggregated = aggregate_behavioral_metrics(behavioral_df)

    print("\nMean Tool Calls per Policy:")
    for policy, metrics in sorted(
        aggregated.items(), key=lambda x: x[1]["mean_tool_calls"], reverse=True
    ):
        print(
            f"  {policy:25s}: {metrics['mean_tool_calls']:6.2f} ± {metrics['std_tool_calls']:5.2f}"
        )

    print("\nMean Syntax Error Rate per Policy:")
    for policy, metrics in sorted(
        aggregated.items(), key=lambda x: x[1]["mean_syntax_error_rate"], reverse=True
    ):
        print(
            f"  {policy:25s}: {metrics['mean_syntax_error_rate']:6.4f} ± {metrics['std_syntax_error_rate']:6.4f}"
        )

    # Test H4: Analysis Paralysis
    print("\n[3/3] Testing H4: Analysis Paralysis...")
    h4_test = test_analysis_paralysis(
        behavioral_df=behavioral_df,
        baseline_policy="full_memory",
    )

    print("\nTool Calls Tests (Full Memory vs Others):")
    for test in h4_test["tool_calls_tests"]:
        sig = "***" if test["significant"] else "ns"
        print(
            f"  {test['policy']:25s}: Δ={test['median_diff']:+6.2f}, p={test['p_value']:.4f} {sig}"
        )

    print("\nSyntax Error Rate Tests (Full Memory vs Others):")
    for test in h4_test["syntax_error_tests"]:
        sig = "***" if test["significant"] else "ns"
        print(
            f"  {test['policy']:25s}: Δ={test['median_diff']:+6.4f}, p={test['p_value']:.4f} {sig}"
        )

    print("\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    print(f"\n{h4_test['conclusion']['interpretation']}")

    # Save results
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save behavioral metrics
        behavioral_df.to_csv(output_dir / "behavioral_metrics.csv", index=False)

        # Save aggregated results
        results = {
            "aggregated_metrics": aggregated,
            "h4_test": {
                "tool_calls_tests": h4_test["tool_calls_tests"],
                "syntax_error_tests": h4_test["syntax_error_tests"],
                "conclusion": h4_test["conclusion"],
            },
        }

        with open(output_dir / "behavioral_analysis_results.json", "w") as f:
            json.dump(results, f, indent=2)

        print(f"\n✓ Results saved to {output_dir}")

    return {
        "behavioral_metrics": aggregated,
        "analysis_paralysis_test": h4_test,
    }
