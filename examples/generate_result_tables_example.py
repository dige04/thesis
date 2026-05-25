"""
Example script demonstrating how to generate result tables.

This script shows how to use the result_tables module to generate
all required tables for the memory pruning research system.

Usage:
    python examples/generate_result_tables_example.py
"""

from pathlib import Path

from src.analysis.aggregate_results import aggregate_sequence_results
from src.analysis.result_tables import generate_all_result_tables, print_table_summary
from src.analysis.statistical_tests import compute_all_contrasts_with_bootstrap


def main():
    """Generate all result tables from experimental data."""
    # Paths
    runs_dir = Path("runs")
    results_dir = Path("results")
    tables_dir = results_dir / "tables"

    print("=" * 80)
    print("RESULT TABLES GENERATION EXAMPLE")
    print("=" * 80)

    # Step 1: Aggregate sequence-level results
    print("\n[Step 1] Aggregating sequence-level results...")
    sequence_aggregates = aggregate_sequence_results(
        runs_dir=runs_dir,
        output_path=results_dir / "sequence_aggregates.json",
    )
    print(f"  Loaded {len(sequence_aggregates)} policies")
    for policy, sequences in sequence_aggregates.items():
        print(f"    {policy}: {len(sequences)} sequences")

    # Step 2: Run statistical tests with bootstrap
    print("\n[Step 2] Running statistical tests with bootstrap...")
    wilcoxon_results = compute_all_contrasts_with_bootstrap(
        sequence_aggregates=sequence_aggregates,
        metric="mean_cl_f1",
        baseline_policy="full_memory",
        contrasts=[
            "random_prune",
            "recency_prune",
            "type_aware_decay",
            "cls_consolidation",
            "no_memory",
        ],
        n_bootstrap=5000,
        random_seed=42,
    )
    print(f"  Computed {wilcoxon_results['n_contrasts']} contrasts")

    # Step 3: Generate all result tables
    print("\n[Step 3] Generating result tables...")
    tables = generate_all_result_tables(
        sequence_aggregates=sequence_aggregates,
        wilcoxon_results=wilcoxon_results,
        output_dir=tables_dir,
    )

    # Step 4: Print table summary
    print_table_summary(tables)

    print("\n" + "=" * 80)
    print("DONE")
    print("=" * 80)
    print(f"\nAll tables saved to: {tables_dir}")
    print("\nGenerated files:")
    print(f"  - {tables_dir / 'statistical_tests.csv'}")
    print(f"  - {tables_dir / 'effect_sizes.csv'}")
    print(f"  - {tables_dir / 'performance_summary.csv'}")
    print(f"  - {tables_dir / 'cost_breakdown.csv'}")


if __name__ == "__main__":
    main()
