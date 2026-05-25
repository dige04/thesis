"""
Example usage of Pareto frontier analysis.

Demonstrates Task 16.1: Pareto frontier analysis.

Per THESIS_FINAL_v5.md §17:
- Plot CL-F1 vs total cost for all 6 policies
- Identify Pareto-optimal policies
- Compute cost-normalized CL-F1
"""

from pathlib import Path

from src.analysis import aggregate_sequence_results, run_pareto_analysis


def main():
    """Run complete Pareto analysis pipeline."""
    # Paths
    runs_dir = Path("runs")
    results_dir = Path("results/pareto")
    results_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("PARETO FRONTIER ANALYSIS")
    print("=" * 80)

    # Aggregate to sequence level
    print("\n[Step 1] Aggregating to sequence-level means...")
    sequence_aggregates = aggregate_sequence_results(
        runs_dir=runs_dir,
        output_path=results_dir / "sequence_aggregates.json",
    )

    # Run Pareto analysis
    print("\n[Step 2] Computing Pareto frontiers...")
    pareto_results = run_pareto_analysis(
        sequence_aggregates=sequence_aggregates,
        output_dir=results_dir,
    )

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 80)
    print("PARETO ANALYSIS SUMMARY")
    print("=" * 80)

    # Primary: CL-F1 vs Cost
    print("\n[PRIMARY] CL-F1 vs Total Cost:")
    cl_f1_cost = pareto_results["cl_f1_vs_cost"]
    print(f"  Pareto-optimal policies: {cl_f1_cost['pareto_optimal']}")
    print(f"  Dominated policies:      {cl_f1_cost['dominated']}")

    # Resolved Rate vs Cost
    print("\n[SECONDARY] Resolved Rate vs Total Cost:")
    resolved_cost = pareto_results["resolved_vs_cost"]
    print(f"  Pareto-optimal policies: {resolved_cost['pareto_optimal']}")

    # CL-F1 vs Tokens
    print("\n[SECONDARY] CL-F1 vs Total Tokens:")
    cl_f1_tokens = pareto_results["cl_f1_vs_tokens"]
    print(f"  Pareto-optimal policies: {cl_f1_tokens['pareto_optimal']}")

    # CL-F1 vs Tool Calls (Efficiency)
    print("\n[SECONDARY] CL-F1 vs Tool Calls:")
    cl_f1_tools = pareto_results["cl_f1_vs_tool_calls"]
    print(f"  Pareto-optimal policies: {cl_f1_tools['pareto_optimal']}")

    # Cost-Normalized CL-F1
    print("\n[COST-NORMALIZED] CL-F1 per Dollar:")
    cost_normalized = pareto_results["cost_normalized"]
    for policy, value in sorted(cost_normalized.items(), key=lambda x: x[1], reverse=True):
        print(f"  {policy:25s}: {value:.6f}")

    # =========================================================================
    # Interpretation
    # =========================================================================
    print("\n" + "=" * 80)
    print("INTERPRETATION")
    print("=" * 80)

    print("\nPareto-Optimal Policies:")
    print("  These policies are NOT dominated on both axes")
    print("  (no other policy achieves both higher CL-F1 AND lower cost)")
    print("  → Practical recommendations for deployment")

    print("\nDominated Policies:")
    print("  These policies are strictly worse than at least one other")
    print("  → Not recommended unless other constraints apply")

    print("\nCost-Normalized CL-F1:")
    print("  Measures 'bang for buck' — CL-F1 per dollar spent")
    print("  → Useful for budget-constrained scenarios")

    # CLS Consolidation Check
    if "cls_consolidation" in cost_normalized:
        cls_value = cost_normalized["cls_consolidation"]
        type_aware_value = cost_normalized.get("type_aware_decay", 0)

        print("\n[CLS Consolidation Check]")
        print(f"  CLS cost-normalized:        {cls_value:.6f}")
        print(f"  Type-Aware cost-normalized: {type_aware_value:.6f}")

        if cls_value < type_aware_value:
            print("  → CLS FAILS Pareto test: higher cost, similar performance")
        else:
            print("  → CLS PASSES Pareto test: cost justified by performance")

    # =========================================================================
    # Next Steps
    # =========================================================================
    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)

    print("\n1. Review Pareto plots:")
    print(f"   - {results_dir}/pareto_cl_f1_vs_cost.png")
    print(f"   - {results_dir}/pareto_resolved_vs_cost.png")
    print(f"   - {results_dir}/pareto_cl_f1_vs_tokens.png")
    print(f"   - {results_dir}/pareto_cl_f1_vs_tool_calls.png")

    print("\n2. Identify practical recommendations:")
    print("   - Which policies are Pareto-optimal?")
    print("   - What trade-offs do they represent?")

    print("\n3. Consider deployment constraints:")
    print("   - Budget limits → cost-normalized CL-F1")
    print("   - Latency limits → tool calls")
    print("   - Token limits → total tokens")

    print(f"\n✓ Results saved to: {results_dir}")


if __name__ == "__main__":
    main()
