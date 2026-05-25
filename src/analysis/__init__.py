"""Statistical analysis and result aggregation for memory pruning experiments."""

from .aggregate_results import aggregate_sequence_results, aggregate_task_results
from .feature_importance import (
    compute_vif,
    compute_weak_label,
    prepare_features,
    prepare_memory_retrieval_data,
    run_feature_importance_analysis,
    train_helpful_harmful_classifier,
)
from .glmm import (
    fit_glmm,
    fit_glmm_with_r,
    prepare_task_level_data,
    run_task_level_analysis,
)
from .pareto import (
    compute_cost_normalized_metrics,
    compute_pareto_frontier,
    plot_pareto_frontier,
    run_pareto_analysis,
)
from .result_tables import (
    generate_all_result_tables,
    generate_cost_breakdown_table,
    generate_effect_size_table,
    generate_performance_summary_table,
    generate_statistical_test_table,
    print_table_summary,
)
from .statistical_tests import (
    compute_all_contrasts_with_bootstrap,
    compute_rank_biserial,
    holm_correction,
    run_bootstrap_bca,
    run_wilcoxon_with_holm,
)

__all__ = [
    "aggregate_sequence_results",
    "aggregate_task_results",
    "compute_rank_biserial",
    "run_bootstrap_bca",
    "run_wilcoxon_with_holm",
    "holm_correction",
    "compute_all_contrasts_with_bootstrap",
    "fit_glmm",
    "fit_glmm_with_r",
    "prepare_task_level_data",
    "run_task_level_analysis",
    "compute_vif",
    "compute_weak_label",
    "prepare_features",
    "prepare_memory_retrieval_data",
    "run_feature_importance_analysis",
    "train_helpful_harmful_classifier",
    "compute_pareto_frontier",
    "plot_pareto_frontier",
    "compute_cost_normalized_metrics",
    "run_pareto_analysis",
    "generate_statistical_test_table",
    "generate_effect_size_table",
    "generate_performance_summary_table",
    "generate_cost_breakdown_table",
    "generate_all_result_tables",
    "print_table_summary",
]
