"""Example usage of ExperimentRunner.

This script demonstrates how to use the ExperimentRunner to execute:
1. Full experiment (144 runs: 8 sequences × 6 policies × 3 seeds)
2. Pilot experiment (12 runs: 2 sequences × 6 policies × 1 seed)
3. Specific combination (1 run: specific sequence-policy-seed)

Requirements: 16
Design: THESIS_FINAL_v5.md §12, §16
"""

import logging
import sys
from pathlib import Path

import yaml

from src.benchmark.experiment_runner import ExperimentRunner

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("experiment_runner.log"),
    ],
)

logger = logging.getLogger(__name__)


def load_config(config_path: str = "configs/base.yaml") -> dict:
    """Load configuration from YAML file.

    Args:
        config_path: Path to configuration file

    Returns:
        Configuration dictionary
    """
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config


def run_full_experiment():
    """Execute full experiment: 144 runs (8 sequences × 6 policies × 3 seeds).

    This is the main experiment for the thesis. It will take several days
    to complete and cost several hundred dollars in API calls.

    Expected output:
    - 144 run result files in results/raw/
    - 144 run directories in runs/ with task results, memory events, trajectories, snapshots
    - experiment_summary.json in results/raw/
    """
    logger.info("=" * 80)
    logger.info("FULL EXPERIMENT: 144 runs")
    logger.info("=" * 80)

    # Load configuration
    config = load_config()

    # Initialize experiment runner
    runner = ExperimentRunner(
        config=config,
        curriculum_path="data/SWE-Bench-CL-Curriculum.json",
    )

    # Execute full experiment
    summary = runner.run_full_experiment()

    # Print summary
    logger.info("=" * 80)
    logger.info("EXPERIMENT SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total runs: {summary.total_runs}")
    logger.info(f"Completed: {summary.completed_runs}")
    logger.info(f"Failed: {summary.failed_runs}")
    logger.info(f"Total wall time: {summary.total_wall_time:.1f}s ({summary.total_wall_time / 3600:.1f}h)")
    logger.info(f"Total cost: ${summary.total_cost_usd:.2f}")
    logger.info(f"Start time: {summary.start_time}")
    logger.info(f"End time: {summary.end_time}")

    if summary.failed_run_ids:
        logger.warning(f"Failed runs: {summary.failed_run_ids}")

    logger.info("=" * 80)


def run_pilot_experiment():
    """Execute pilot experiment: 12 runs (2 sequences × 6 policies × 1 seed).

    This is used for calibration during Spike Week and Week 4.
    It runs quickly (hours instead of days) and costs much less.

    Expected output:
    - 12 run result files in results/raw/
    - 12 run directories in runs/
    - experiment_summary.json in results/raw/
    """
    logger.info("=" * 80)
    logger.info("PILOT EXPERIMENT: 12 runs (2 sequences × 6 policies × 1 seed)")
    logger.info("=" * 80)

    # Load configuration
    config = load_config()

    # Initialize experiment runner
    runner = ExperimentRunner(
        config=config,
        curriculum_path="data/SWE-Bench-CL-Curriculum.json",
    )

    # Execute pilot experiment
    summary = runner.run_pilot_experiment(num_sequences=2)

    # Print summary
    logger.info("=" * 80)
    logger.info("PILOT SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total runs: {summary.total_runs}")
    logger.info(f"Completed: {summary.completed_runs}")
    logger.info(f"Failed: {summary.failed_runs}")
    logger.info(f"Total wall time: {summary.total_wall_time:.1f}s ({summary.total_wall_time / 60:.1f}m)")
    logger.info(f"Total cost: ${summary.total_cost_usd:.2f}")

    if summary.failed_run_ids:
        logger.warning(f"Failed runs: {summary.failed_run_ids}")

    logger.info("=" * 80)


def run_specific_combination():
    """Execute specific sequence-policy-seed combination.

    This is useful for:
    - Debugging a specific configuration
    - Re-running a failed run
    - Testing a single condition

    Expected output:
    - 1 run result file in results/raw/
    - 1 run directory in runs/
    """
    logger.info("=" * 80)
    logger.info("SPECIFIC COMBINATION: django × type_aware_decay × seed=1")
    logger.info("=" * 80)

    # Load configuration
    config = load_config()

    # Initialize experiment runner
    runner = ExperimentRunner(
        config=config,
        curriculum_path="data/SWE-Bench-CL-Curriculum.json",
    )

    # Execute specific combination
    result = runner.run_specific_combination(
        sequence_name="django",
        policy_name="type_aware_decay",
        seed=1,
    )

    # Print result
    logger.info("=" * 80)
    logger.info("RUN RESULT")
    logger.info("=" * 80)
    logger.info(f"Run ID: {result.run_id}")
    logger.info(f"Sequence: {result.sequence_name}")
    logger.info(f"Policy: {result.policy_name}")
    logger.info(f"Seed: {result.seed}")
    logger.info(f"Total tasks: {result.total_tasks}")
    logger.info(f"Resolved: {result.resolved_tasks}")
    logger.info(f"Failed: {result.failed_tasks}")
    logger.info(f"Timeout: {result.timeout_tasks}")
    logger.info(f"Wall time: {result.total_wall_time:.1f}s")
    logger.info(f"Cost: ${result.total_cost_usd:.2f}")

    if result.error_message:
        logger.error(f"Error: {result.error_message}")

    logger.info("=" * 80)


def main():
    """Main entry point for experiment runner examples."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run experiments with ExperimentRunner"
    )
    parser.add_argument(
        "mode",
        choices=["full", "pilot", "specific"],
        help="Experiment mode: full (144 runs), pilot (12 runs), or specific (1 run)",
    )

    args = parser.parse_args()

    if args.mode == "full":
        run_full_experiment()
    elif args.mode == "pilot":
        run_pilot_experiment()
    elif args.mode == "specific":
        run_specific_combination()


if __name__ == "__main__":
    main()
