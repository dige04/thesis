"""Example usage of pilot mode for calibration.

This script demonstrates how to:
1. Run pilot experiment (2 sequences × 6 policies × 1 seed = 12 runs)
2. Analyze retrieval quality metrics
3. Update calibration parameters (top_k, max_context_tokens)
4. Lock calibration parameters after Week 4

Requirements: 30
"""

import logging
from pathlib import Path

from src.benchmark.experiment_runner import ExperimentRunner
from src.config.calibration import (
    analyze_pilot_results,
    generate_calibration_report,
    lock_calibration,
    update_calibration_params,
)
from src.config.loader import load_config

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def run_pilot_experiment_example():
    """Example: Run pilot experiment with retrieval quality logging."""
    logger.info("=== Running Pilot Experiment ===")

    # Load configuration with pilot mode enabled
    config = load_config()

    # Enable pilot mode
    config["experiment"]["pilot_mode"]["enabled"] = True
    config["experiment"]["pilot_mode"]["log_retrieval_quality"] = True

    # Initialize experiment runner
    runner = ExperimentRunner(
        config=config,
        curriculum_path="data/SWE-Bench-CL-Curriculum.json",
    )

    # Run pilot experiment (2 sequences × 6 policies × 1 seed = 12 runs)
    summary = runner.run_pilot_experiment(num_sequences=2)

    logger.info(
        f"Pilot experiment complete: "
        f"{summary.completed_runs}/{summary.total_runs} runs completed, "
        f"cost=${summary.total_cost_usd:.2f}"
    )

    return summary


def analyze_pilot_results_example():
    """Example: Analyze pilot results and generate recommendations."""
    logger.info("=== Analyzing Pilot Results ===")

    # Analyze retrieval quality metrics from pilot runs
    results_dir = Path("results/raw")
    analysis = analyze_pilot_results(results_dir)

    # Print overall metrics
    overall = analysis["overall_metrics"]
    logger.info(
        f"Overall metrics: "
        f"precision@k={overall.get('mean_precision_at_k', 0):.3f}, "
        f"recall@k={overall.get('mean_recall_at_k', 0):.3f}, "
        f"MRR={overall.get('mean_mrr', 0):.3f}, "
        f"NDCG@k={overall.get('mean_ndcg_at_k', 0):.3f}"
    )

    # Print recommendations
    recommendations = analysis["recommendations"]
    logger.info(
        f"Recommendations: "
        f"top_k={recommendations['top_k']}, "
        f"max_context_tokens={recommendations['max_context_tokens']}"
    )
    logger.info(f"Rationale: {recommendations['rationale']}")

    # Generate calibration report
    report_path = Path("results/calibration_report.json")
    generate_calibration_report(analysis, report_path)
    logger.info(f"Calibration report saved to {report_path}")

    return analysis


def update_calibration_params_example():
    """Example: Update calibration parameters based on pilot analysis."""
    logger.info("=== Updating Calibration Parameters ===")

    # Analyze pilot results first
    results_dir = Path("results/raw")
    analysis = analyze_pilot_results(results_dir)

    # Get recommendations
    recommendations = analysis["recommendations"]
    recommended_top_k = recommendations["top_k"]
    recommended_tokens = recommendations["max_context_tokens"]

    logger.info(
        f"Applying recommendations: "
        f"top_k={recommended_top_k}, "
        f"max_context_tokens={recommended_tokens}"
    )

    # Update configuration
    config_path = Path("configs/base.yaml")
    update_calibration_params(
        config_path=config_path,
        top_k=recommended_top_k,
        max_context_tokens=recommended_tokens,
    )

    logger.info("Calibration parameters updated successfully")


def update_type_aware_decay_params_example():
    """Example: Update Type-Aware Decay parameters after Week 4 pilot."""
    logger.info("=== Updating Type-Aware Decay Parameters ===")

    # Example: Adjust decay_d parameters based on Week 4 pilot analysis
    # (In practice, these would come from empirical analysis)
    new_type_params = {
        "architectural": {"base": 1.0, "decay": 0.05},  # Keep architectural high
        "api_change": {"base": 0.8, "decay": 0.12},  # Slightly slower decay
        "bug_fix": {"base": 0.6, "decay": 0.25},  # Keep default
        "test_update": {"base": 0.4, "decay": 0.35},  # Keep default
        "config": {"base": 0.3, "decay": 0.40},  # Keep default
    }

    logger.info(f"Updating type_aware_decay parameters: {new_type_params}")

    # Update configuration
    config_path = Path("configs/base.yaml")
    update_calibration_params(
        config_path=config_path, type_aware_decay_params=new_type_params
    )

    logger.info("Type-Aware Decay parameters updated successfully")


def lock_calibration_example():
    """Example: Lock calibration parameters after Week 4."""
    logger.info("=== Locking Calibration Parameters ===")

    # Lock calibration parameters (prevents further changes)
    config_path = Path("configs/base.yaml")
    lock_calibration(config_path)

    logger.info(
        "Calibration parameters locked. "
        "No further changes allowed for full 144-run experiment."
    )


def full_calibration_workflow_example():
    """Example: Complete calibration workflow from pilot to lock."""
    logger.info("=== Full Calibration Workflow ===")

    # Step 1: Run pilot experiment (Spike Week)
    logger.info("Step 1: Running pilot experiment...")
    run_pilot_experiment_example()

    # Step 2: Analyze results and update top_k, max_context_tokens
    logger.info("Step 2: Analyzing pilot results...")
    analyze_pilot_results_example()

    logger.info("Step 3: Updating top_k and max_context_tokens...")
    update_calibration_params_example()

    # Step 3: Run Week 4 pilot for Type-Aware Decay calibration
    logger.info("Step 4: (Week 4) Running second pilot for Type-Aware Decay...")
    # (Would run another pilot here)

    logger.info("Step 5: (Week 4) Updating Type-Aware Decay parameters...")
    update_type_aware_decay_params_example()

    # Step 4: Lock calibration parameters
    logger.info("Step 6: Locking calibration parameters...")
    lock_calibration_example()

    logger.info("Calibration workflow complete. Ready for full 144-run experiment.")


if __name__ == "__main__":
    # Run individual examples
    # run_pilot_experiment_example()
    # analyze_pilot_results_example()
    # update_calibration_params_example()
    # update_type_aware_decay_params_example()
    # lock_calibration_example()

    # Or run full workflow
    full_calibration_workflow_example()
