"""
Example usage of statistical analysis modules.

Demonstrates Tasks 14.1-14.4:
- Sequence-level aggregation
- Wilcoxon signed-rank test with Holm correction
- Bootstrap BCa confidence intervals
- Task-level GLMM

Per THESIS_FINAL_v5.md §15:
- Primary analysis: sequence-level (N=8 paired observations)
- Effect sizes + CIs are primary evidence
- p-values supplement but do not gate conclusions
"""

from pathlib import Path

from src.analysis import (
    aggregate_sequence_results,
    compute_all_contrasts_with_bootstrap,
    run_task_level_analysis,
)


def main():
    """Run complete statistical analysis pipeline."""
    # Paths
    runs_dir = Path("runs")
    results_dir = Path("results/aggregated")
    results_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("STATISTICAL ANALYSIS FOR MEMORY PRUNING EXPERIMENTS")
    print("=" * 80)

    # =========================================================================
    # Task 14.1: Sequence-level aggregation
    # =========================================================================
    print("\n[Task 14.1] Aggregating task results to sequence-level means...")

    sequence_aggregates = aggregate_sequence_results(
        runs_dir=runs_dir,
        output_path=results_dir / "sequence_aggregates.json",
    )

    print(f"✓ Aggregated {len(sequence_aggregates)} policies")
    for policy, sequences in sequence_aggregates.items():
        print(f"  - {policy}: {len(sequences)} sequences")

    # =========================================================================
    # Tasks 14.2 & 14.3: Wilcoxon + Holm + Bootstrap BCa
    # =========================================================================
    print("\n[Tasks 14.2 & 14.3] Running Wilcoxon tests with Holm correction...")
    print("                     Computing bootstrap BCa confidence intervals...")

    # Primary metric: CL-F1
    cl_f1_results = compute_all_contrasts_with_bootstrap(
        sequence_aggregates=sequence_aggregates,
        metric="mean_cl_f1",
        baseline_policy="full_memory",
        n_bootstrap=5000,
        random_seed=42,
    )

    print(f"\n✓ Completed {cl_f1_results['n_contrasts']} pre-registered contrasts")
    print(f"  Metric: {cl_f1_results['metric']}")
    print(f"  Baseline: {cl_f1_results['baseline_policy']}")

    print("\nResults:")
    print("-" * 80)
    for contrast in cl_f1_results["contrasts"]:
        policy = contrast["policy"]
        median_diff = contrast["median_diff"]
        r_rb = contrast["rank_biserial"]
        p_holm = contrast["holm_p_value"]
        sig = "***" if contrast["significant"] else "ns"

        bca = contrast["bootstrap_ci"]
        ci_lower = bca["ci_lower"]
        ci_upper = bca["ci_upper"]

        print(f"\n{policy} vs full_memory:")
        print(f"  Median Δ:     {median_diff:+.4f}")
        print(f"  95% BCa CI:   [{ci_lower:+.4f}, {ci_upper:+.4f}]")
        print(f"  Rank-biserial: {r_rb:+.3f}")
        print(f"  Holm p-value:  {p_holm:.4f} {sig}")

        # Interpretation
        if abs(r_rb) < 0.1:
            effect = "negligible"
        elif abs(r_rb) < 0.3:
            effect = "small"
        elif abs(r_rb) < 0.5:
            effect = "medium"
        else:
            effect = "large"
        print(f"  Effect size:   {effect}")

    # Secondary metrics: costs and efficiency
    print("\n" + "=" * 80)
    print("SECONDARY METRICS: COSTS AND EFFICIENCY")
    print("=" * 80)

    for metric in ["mean_total_cost", "mean_total_tokens", "mean_tool_calls"]:
        print(f"\n[Metric: {metric}]")
        results = compute_all_contrasts_with_bootstrap(
            sequence_aggregates=sequence_aggregates,
            metric=metric,
            baseline_policy="full_memory",
            n_bootstrap=5000,
            random_seed=42,
        )

        for contrast in results["contrasts"]:
            policy = contrast["policy"]
            median_diff = contrast["median_diff"]
            r_rb = contrast["rank_biserial"]
            bca = contrast["bootstrap_ci"]

            print(
                f"  {policy:20s}: Δ={median_diff:+10.2f}, "
                f"r_rb={r_rb:+.3f}, "
                f"CI=[{bca['ci_lower']:+.2f}, {bca['ci_upper']:+.2f}]"
            )

    # =========================================================================
    # Task 14.4: Task-level GLMM
    # =========================================================================
    print("\n" + "=" * 80)
    print("[Task 14.4] Fitting task-level GLMM (exploratory)")
    print("=" * 80)

    glmm_results = run_task_level_analysis(
        runs_dir=runs_dir,
        output_dir=results_dir / "glmm",
        use_r=False,  # Set to True if R + rpy2 available
    )

    print("\nData Summary:")
    summary = glmm_results["data_summary"]
    print(f"  Total tasks:        {summary['n_tasks']}")
    print(f"  Policies:           {summary['n_policies']}")
    print(f"  Sequences:          {summary['n_sequences']}")
    print(f"  Seeds:              {summary['n_seeds']}")
    print(f"  Overall success:    {summary['overall_success_rate']:.3f}")

    print("\nSuccess rate by policy:")
    for policy, rate in summary["success_rate_by_policy"].items():
        print(f"  {policy:20s}: {rate:.3f}")

    glmm = glmm_results["glmm_results"]
    if "error" in glmm:
        print(f"\n⚠ GLMM fitting failed: {glmm['error']}")
        print("  Note: For production analysis, use R's lme4::glmer")
    else:
        print(f"\n✓ GLMM converged: {glmm['converged']}")
        print(f"  Formula: {glmm['formula']}")
        print(f"  AIC: {glmm.get('aic', 'N/A')}")
        print(f"  BIC: {glmm.get('bic', 'N/A')}")

        if "fixed_effects" in glmm:
            print("\nFixed effects:")
            for param, stats in glmm["fixed_effects"].items():
                coef = stats["coefficient"]
                se = stats["std_err"]
                z = stats["z_value"]
                p = stats["p_value"]
                sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""
                print(f"  {param:30s}: β={coef:+.4f}, SE={se:.4f}, z={z:+.3f}, p={p:.4f} {sig}")

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"\nResults saved to: {results_dir}")
    print("\nNext steps:")
    print("  1. Review sequence_aggregates.json for per-sequence means")
    print("  2. Examine Wilcoxon + bootstrap results for effect sizes")
    print("  3. Check GLMM results for task-level patterns")
    print("  4. Generate plots and tables (Section 18)")
    print("  5. Conduct Pareto analysis (Section 16)")


if __name__ == "__main__":
    main()
