"""
Example usage of feature importance analysis.

Demonstrates Task 15.1: Helpful/harmful memory prediction.

Per THESIS_FINAL_v5.md §16:
- Unit of analysis: (task, retrieved_memory) pairs
- Primary metric: PR-AUC (NOT accuracy or ROC-AUC)
- VIF check for multicollinearity
- Class weights for imbalanced data
- Three-tier labeling system
"""

from pathlib import Path

from src.analysis import run_feature_importance_analysis


def main():
    """Run complete feature importance analysis pipeline."""
    # Paths
    runs_dir = Path("runs")
    results_dir = Path("results/feature_importance")
    results_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("FEATURE IMPORTANCE ANALYSIS")
    print("Helpful/Harmful Memory Prediction")
    print("=" * 80)

    # Run analysis
    results = run_feature_importance_analysis(
        runs_dir=runs_dir,
        output_dir=results_dir,
    )

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 80)
    print("ANALYSIS SUMMARY")
    print("=" * 80)

    summary = results["data_summary"]
    print(f"\nData:")
    print(f"  Total (task, memory) pairs: {summary['n_pairs']}")
    print(f"  Unique tasks: {summary['n_tasks']}")
    print(f"  Unique memories: {summary['n_memories']}")
    print(f"  Helpful rate: {summary['helpful_rate']:.3f}")

    print(f"\nLabel distribution:")
    for label, count in summary["label_distribution"].items():
        print(f"  {label:10s}: {count:6d} ({count/summary['n_pairs']*100:.1f}%)")

    # Logistic Regression results
    logistic = results["logistic_results"]
    print(f"\nLogistic Regression (Interpretable):")
    print(f"  PR-AUC:    {logistic['pr_auc']:.4f} ± {logistic['pr_auc_std']:.4f}")
    print(f"  Precision: {logistic['precision']:.4f}")
    print(f"  Recall:    {logistic['recall']:.4f}")
    print(f"  F1:        {logistic['f1']:.4f}")

    print(f"\n  Top 5 predictive features:")
    for i, row in enumerate(logistic["feature_importance"].head(5).to_dict("records")):
        feature = row["feature"]
        coef = row["coefficient"]
        print(f"    {i+1}. {feature:30s}: {coef:+.4f}")

    # GBM results
    gbm = results["gbm_results"]
    print(f"\nGradient Boosting Machine (Nonlinear):")
    print(f"  PR-AUC:    {gbm['pr_auc']:.4f} ± {gbm['pr_auc_std']:.4f}")
    print(f"  Precision: {gbm['precision']:.4f}")
    print(f"  Recall:    {gbm['recall']:.4f}")
    print(f"  F1:        {gbm['f1']:.4f}")

    print(f"\n  Top 5 important features:")
    for i, row in enumerate(gbm["feature_importance"].head(5).to_dict("records")):
        feature = row["feature"]
        importance = row["importance"]
        print(f"    {i+1}. {feature:30s}: {importance:.4f}")

    # Model comparison
    comparison = results["comparison"]
    print(f"\nModel Comparison:")
    print(f"  Best model: {comparison['best_model']}")
    print(f"  Logistic PR-AUC: {comparison['logistic_pr_auc']:.4f}")
    print(f"  GBM PR-AUC:      {comparison['gbm_pr_auc']:.4f}")

    # Interpretation
    print("\n" + "=" * 80)
    print("INTERPRETATION")
    print("=" * 80)

    print("\nKey Findings:")
    print("  1. PR-AUC is the primary metric (NOT accuracy)")
    print("     - Class imbalance: ~20% helpful memories")
    print("     - PR-AUC focuses on positive class performance")

    print("\n  2. VIF check ensures no multicollinearity")
    print("     - If VIF(age) or VIF(use_count) > 5:")
    print("       → Drop both, use retrieval_rate instead")

    print("\n  3. Class weights handle imbalance")
    print(f"     - Class 0 (not helpful): {logistic['class_weights'][0]:.3f}")
    print(f"     - Class 1 (helpful):     {logistic['class_weights'][1]:.3f}")

    print("\n  4. Feature importance reveals predictors")
    print("     - Logistic: interpretable coefficients")
    print("     - GBM: captures nonlinear relationships")

    print("\n  5. Memory labels are ASSOCIATED, not causal")
    print("     - Cannot claim 'memory X caused task success'")
    print("     - Can claim 'memory X associated with success'")
    print("     - Causal claims require matched-contrast case studies")

    # Next steps
    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)

    print("\n1. Manual labeling (Tier 2):")
    print("   - Sample 100-200 pairs stratified by policy, type, weak label")
    print("   - Two annotators for inter-rater reliability (Cohen's kappa)")
    print("   - Manual labels = gold standard for evaluation")

    print("\n2. Matched-contrast case studies (Tier 3):")
    print("   - Find task pairs where memory X helped in A, harmed in B")
    print("   - These support causal claims in Discussion chapter")

    print("\n3. Bootstrap confidence intervals:")
    print("   - 5000 iterations for PR-AUC")
    print("   - Report 95% BCa CI")

    print("\n4. Calibration curve:")
    print("   - Check if predicted probabilities are well-calibrated")
    print("   - Reliability diagram")

    print(f"\n✓ Results saved to: {results_dir}")


if __name__ == "__main__":
    main()
