"""Calibration utilities for updating hyperparameters after pilot runs.

This module provides utilities for analyzing pilot run results and updating
calibration parameters (top_k, max_context_tokens, type_aware_decay parameters).

**Validates: Requirements 30**

Key functions:
- analyze_pilot_results: Analyze retrieval quality metrics from pilot runs
- recommend_top_k: Recommend optimal top_k based on precision/recall trade-off
- recommend_max_context_tokens: Recommend optimal token budget
- update_type_aware_decay_params: Update decay_d parameters per type
- lock_calibration: Lock all calibration parameters after Week 4

Requirements: 30
Design: THESIS_FINAL_v5.md §30
"""

import json
import logging
from pathlib import Path
from typing import Any

from src.config.loader import ConfigLoader
from src.errors import ConfigFrozenError

logger = logging.getLogger(__name__)


def analyze_pilot_results(
    results_dir: Path | str,
    policy_filter: str | None = None,
) -> dict[str, Any]:
    """Analyze retrieval quality metrics from pilot runs.

    Args:
        results_dir: Directory containing pilot run results
        policy_filter: Optional policy name to filter results

    Returns:
        Dictionary with analysis results:
            - per_policy_metrics: Metrics aggregated per policy
            - overall_metrics: Metrics aggregated across all policies
            - recommendations: Recommended parameter updates

    Raises:
        FileNotFoundError: If results directory doesn't exist
    """
    results_dir = Path(results_dir)
    if not results_dir.exists():
        raise FileNotFoundError(f"Results directory not found: {results_dir}")

    # Collect all retrieval quality metrics files
    metrics_files = list(results_dir.glob("**/retrieval_quality_metrics.json"))

    if not metrics_files:
        logger.warning(f"No retrieval quality metrics found in {results_dir}")
        return {
            "per_policy_metrics": {},
            "overall_metrics": {},
            "recommendations": {},
        }

    # Aggregate metrics per policy
    per_policy_metrics = {}

    for metrics_file in metrics_files:
        with open(metrics_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        policy_name = data.get("policy_name", "unknown")

        # Filter by policy if requested
        if policy_filter and policy_name != policy_filter:
            continue

        if policy_name not in per_policy_metrics:
            per_policy_metrics[policy_name] = {
                "runs": [],
                "aggregated": {},
            }

        per_policy_metrics[policy_name]["runs"].append(data["aggregated_metrics"])

    # Compute mean metrics per policy
    for policy_name, policy_data in per_policy_metrics.items():
        runs = policy_data["runs"]
        if not runs:
            continue

        # Average across runs
        policy_data["aggregated"] = {
            "mean_precision_at_k": sum(r["mean_precision_at_k"] for r in runs)
            / len(runs),
            "mean_recall_at_k": sum(r["mean_recall_at_k"] for r in runs) / len(runs),
            "mean_mrr": sum(r["mean_mrr"] for r in runs) / len(runs),
            "mean_ndcg_at_k": sum(r["mean_ndcg_at_k"] for r in runs) / len(runs),
            "num_runs": len(runs),
        }

    # Compute overall metrics (average across all policies)
    if per_policy_metrics:
        all_aggregated = [
            policy_data["aggregated"]
            for policy_data in per_policy_metrics.values()
            if policy_data["aggregated"]
        ]

        overall_metrics = {
            "mean_precision_at_k": sum(a["mean_precision_at_k"] for a in all_aggregated)
            / len(all_aggregated),
            "mean_recall_at_k": sum(a["mean_recall_at_k"] for a in all_aggregated)
            / len(all_aggregated),
            "mean_mrr": sum(a["mean_mrr"] for a in all_aggregated) / len(all_aggregated),
            "mean_ndcg_at_k": sum(a["mean_ndcg_at_k"] for a in all_aggregated)
            / len(all_aggregated),
            "num_policies": len(all_aggregated),
        }
    else:
        overall_metrics = {}

    # Generate recommendations
    recommendations = _generate_recommendations(overall_metrics)

    logger.info(
        f"Analyzed {len(metrics_files)} pilot runs: "
        f"mean_precision@k={overall_metrics.get('mean_precision_at_k', 0):.3f}, "
        f"mean_recall@k={overall_metrics.get('mean_recall_at_k', 0):.3f}"
    )

    return {
        "per_policy_metrics": per_policy_metrics,
        "overall_metrics": overall_metrics,
        "recommendations": recommendations,
    }


def _generate_recommendations(overall_metrics: dict[str, Any]) -> dict[str, Any]:
    """Generate parameter recommendations based on metrics.

    Args:
        overall_metrics: Overall aggregated metrics

    Returns:
        Dictionary with recommendations:
            - top_k: Recommended top_k value
            - max_context_tokens: Recommended token budget
            - rationale: Explanation of recommendations
    """
    if not overall_metrics:
        return {
            "top_k": 5,  # Default
            "max_context_tokens": 2000,  # Default
            "rationale": "No metrics available, using defaults",
        }

    precision = overall_metrics.get("mean_precision_at_k", 0.0)
    recall = overall_metrics.get("mean_recall_at_k", 0.0)

    # Simple heuristic: if recall is low (<0.5), consider increasing top_k
    # If precision is low (<0.3), consider decreasing top_k
    current_k = 5  # Assume current default

    if recall < 0.5 and precision > 0.3:
        recommended_k = min(10, current_k + 2)
        rationale = (
            f"Low recall ({recall:.2f}) suggests increasing top_k to retrieve more relevant items. "
            f"Precision ({precision:.2f}) is acceptable."
        )
    elif precision < 0.3 and recall > 0.5:
        recommended_k = max(3, current_k - 1)
        rationale = (
            f"Low precision ({precision:.2f}) suggests decreasing top_k to reduce noise. "
            f"Recall ({recall:.2f}) is acceptable."
        )
    else:
        recommended_k = current_k
        rationale = (
            f"Current top_k={current_k} appears balanced: "
            f"precision={precision:.2f}, recall={recall:.2f}"
        )

    # Token budget: roughly 400 tokens per memory item
    recommended_tokens = recommended_k * 400

    return {
        "top_k": recommended_k,
        "max_context_tokens": recommended_tokens,
        "rationale": rationale,
    }


def update_calibration_params(
    config_path: str | Path,
    top_k: int | None = None,
    max_context_tokens: int | None = None,
    type_aware_decay_params: dict[str, dict[str, float]] | None = None,
) -> None:
    """Update calibration parameters in configuration.

    Args:
        config_path: Path to base configuration file
        top_k: New top_k value (optional)
        max_context_tokens: New max_context_tokens value (optional)
        type_aware_decay_params: New type-specific decay parameters (optional)
            Format: {"architectural": {"base": 1.0, "decay": 0.05}, ...}

    Raises:
        ConfigFrozenError: If calibration parameters are already frozen
    """
    loader = ConfigLoader(str(config_path))
    loader.load()

    # Update top_k
    if top_k is not None:
        logger.info(f"Updating top_k: {loader.get('memory', 'top_k')} -> {top_k}")
        loader.update_calibration_param(("memory", "top_k"), top_k)

    # Update max_context_tokens
    if max_context_tokens is not None:
        logger.info(
            f"Updating max_context_tokens: "
            f"{loader.get('memory', 'max_context_tokens')} -> {max_context_tokens}"
        )
        loader.update_calibration_param(
            ("memory", "max_context_tokens"), max_context_tokens
        )

    # Update type-aware decay parameters
    if type_aware_decay_params is not None:
        logger.info(f"Updating type_aware_decay parameters: {type_aware_decay_params}")
        loader.update_calibration_param(
            ("policies", "type_aware_decay", "type_params"), type_aware_decay_params
        )

    # Save updated configuration
    config_path = Path(config_path)
    with open(config_path, "w", encoding="utf-8") as f:
        import yaml

        yaml.dump(loader.to_dict(), f, default_flow_style=False, sort_keys=False)

    logger.info(f"Updated calibration parameters in {config_path}")


def lock_calibration(config_path: str | Path) -> None:
    """Lock calibration parameters after Week 4.

    This prevents further modifications to top_k, max_context_tokens,
    and type_aware_decay parameters for the full 144-run experiment.

    Args:
        config_path: Path to base configuration file
    """
    loader = ConfigLoader(str(config_path))
    loader.load()
    loader.freeze_calibration_params()

    # Update pilot_mode.calibration_locked flag in config
    config = loader.to_dict()
    if "experiment" not in config:
        config["experiment"] = {}
    if "pilot_mode" not in config["experiment"]:
        config["experiment"]["pilot_mode"] = {}
    config["experiment"]["pilot_mode"]["calibration_locked"] = True

    # Save updated configuration
    config_path = Path(config_path)
    with open(config_path, "w", encoding="utf-8") as f:
        import yaml

        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    logger.info(f"Locked calibration parameters in {config_path}")


def generate_calibration_report(
    analysis_results: dict[str, Any],
    output_path: str | Path,
) -> None:
    """Generate a calibration report from pilot analysis results.

    Args:
        analysis_results: Results from analyze_pilot_results()
        output_path: Path to save report (JSON format)
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(analysis_results, f, indent=2)

    logger.info(f"Generated calibration report: {output_path}")
