"""
Example usage of behavioral metrics analysis.

Demonstrates Task 16.2: Behavioral metrics.

Per THESIS_FINAL_v5.md §14.6 and H4:
- Tool calls per task
- Syntax error rate
- Test whether Full Memory induces analysis paralysis
"""

from pathlib import Path

from src.metrics import run_behavioral_analysis


def main():
    """Run complete behavioral metrics analysis pipeline."""
    # Paths
    runs_dir = Path("runs")
    results_dir = Path("results/behavioral")
    results_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("BEHAVIORAL METRICS ANALYSIS")
    print("Testing H4: Analysis Paralysis")
    print("=" * 80)

    # Run analysis
    results = run_behavioral_analysis(
        runs_dir=runs_dir,
        output_dir=results_dir,
    )

    # =========================================================================
    # Detailed Results
    # =========================================================================
    print("\n" + "=" * 80)
    print("DETAILED RESULTS")
    print("=" * 80)

    metrics = results["behavioral_metrics"]
    h4_test = results["analysis_paralysis_test"]

    # Per-policy metrics
    print("\nPer-Policy Behavioral Metrics:")
    print("-" * 80)

    for policy in sorted(metrics.keys()):
        m = metrics[policy]
        print(f"\n{policy}:")
        print(f"  Tool calls:        {m['mean_tool_calls']:6.2f} ± {m['std_tool_calls']:5.2f}")
        print(f"  Syntax error rate: {m['mean_syntax_error_rate']:6.4f} ± {m['std_syntax_error_rate']:6.4f}")
        print(f"  Files read:        {m['mean_files_read']:6.2f} ± {m['std_files_read']:5.2f}")
        print(f"  Test runs:         {m['mean_test_runs']:6.2f} ± {m['std_test_runs']:5.2f}")
        print(f"  Tasks:             {m['n_tasks']}")

    # H4 Test Results
    print("\n" + "=" * 80)
    print("H4: ANALYSIS PARALYSIS TEST")
    print("=" * 80)

    print("\nHypothesis H4:")
    print("  Full-memory accumulation induces measurable analysis paralysis")
    print("  (increased tool calls and syntax errors)")
    print("  which forgetting policies mitigate.")

    print("\nTool Calls: Full Memory vs Others")
    print("-" * 80)
    for test in h4_test["tool_calls_tests"]:
        policy = test["policy"]
        diff = test["median_diff"]
        p = test["p_value"]
        sig = "SIGNIFICANT" if test["significant"] else "not significant"

        print(f"{policy:25s}: Δ={diff:+6.2f}, p={p:.4f} ({sig})")

    print("\nSyntax Error Rate: Full Memory vs Others")
    print("-" * 80)
    for test in h4_test["syntax_error_tests"]:
        policy = test["policy"]
        diff = test["median_diff"]
        p = test["p_value"]
        sig = "SIGNIFICANT" if test["significant"] else "not significant"

        print(f"{policy:25s}: Δ={diff:+6.4f}, p={p:.4f} ({sig})")

    # Conclusion
    print("\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)

    conclusion = h4_test["conclusion"]
    print(f"\nH4 Supported: {conclusion['h4_supported']}")
    print(f"  Tool calls evidence:    {conclusion['tool_calls_evidence']}")
    print(f"  Syntax error evidence:  {conclusion['syntax_error_evidence']}")

    print(f"\n{conclusion['interpretation']}")

    # =========================================================================
    # Interpretation Guide
    # =========================================================================
    print("\n" + "=" * 80)
    print("INTERPRETATION GUIDE")
    print("=" * 80)

    print("\nWhat is Analysis Paralysis?")
    print("  - Agent makes excessive tool calls without progress")
    print("  - Higher syntax error rates (trial-and-error behavior)")
    print("  - Caused by overwhelming memory context")

    print("\nExpected Pattern if H4 is TRUE:")
    print("  - Full Memory: HIGH tool calls, HIGH syntax errors")
    print("  - Pruning policies: LOWER tool calls, LOWER syntax errors")
    print("  - Wilcoxon p < 0.05 for at least one pruning policy")

    print("\nExpected Pattern if H4 is FALSE:")
    print("  - No significant difference between Full Memory and pruning")
    print("  - Memory accumulation does NOT induce behavioral degradation")
    print("  - Forgetting is NOT necessary for behavioral efficiency")

    print("\nImplications:")
    if conclusion["h4_supported"]:
        print("  ✓ H4 SUPPORTED:")
        print("    - Memory accumulation has behavioral costs")
        print("    - Forgetting policies improve agent efficiency")
        print("    - Practical benefit beyond just correctness")
    else:
        print("  ✗ H4 NOT SUPPORTED:")
        print("    - No evidence of analysis paralysis")
        print("    - Full Memory does not degrade behavior")
        print("    - Forgetting benefits are purely correctness/cost")

    # =========================================================================
    # Next Steps
    # =========================================================================
    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)

    print("\n1. Review behavioral metrics CSV:")
    print(f"   {results_dir}/behavioral_metrics.csv")

    print("\n2. Visualize trends over time:")
    print("   - Plot tool calls vs sequence position")
    print("   - Plot syntax error rate vs sequence position")
    print("   - Check if Full Memory degrades over time")

    print("\n3. Correlate with memory size:")
    print("   - Does tool-call count increase with memory size?")
    print("   - Is there a threshold where paralysis begins?")

    print("\n4. Case studies:")
    print("   - Find specific tasks where Full Memory had excessive tool calls")
    print("   - Compare agent trajectories between policies")

    print(f"\n✓ Results saved to: {results_dir}")


if __name__ == "__main__":
    main()
