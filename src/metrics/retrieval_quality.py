"""Retrieval quality metrics for pilot mode calibration.

This module implements precision@k and recall@k metrics for evaluating
retrieval quality during pilot runs. These metrics help calibrate top_k
and max_context_tokens parameters.

**Validates: Requirements 30**

Key metrics:
- Precision@k: Proportion of retrieved memories that are relevant
- Recall@k: Proportion of relevant memories that are retrieved
- Mean Reciprocal Rank (MRR): Average reciprocal rank of first relevant item
- NDCG@k: Normalized Discounted Cumulative Gain at k

Relevance is determined by:
- Same repository (required)
- Similar memory type (architectural, api_change, bug_fix, test_update, config)
- Temporal proximity (recent memories more relevant)
- Success after retrieval (memories that led to task success)

Requirements: 30
Design: THESIS_FINAL_v5.md §30
"""

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class RetrievalQualityMetrics:
    """Retrieval quality metrics for a single task.

    Attributes:
        task_id: Task identifier
        k: Number of memories retrieved
        precision_at_k: Precision@k (relevant retrieved / k)
        recall_at_k: Recall@k (relevant retrieved / total relevant)
        mrr: Mean Reciprocal Rank of first relevant item
        ndcg_at_k: Normalized Discounted Cumulative Gain at k
        num_relevant_retrieved: Number of relevant memories retrieved
        num_relevant_total: Total number of relevant memories available
        num_retrieved: Total number of memories retrieved
    """

    task_id: str
    k: int
    precision_at_k: float
    recall_at_k: float
    mrr: float
    ndcg_at_k: float
    num_relevant_retrieved: int
    num_relevant_total: int
    num_retrieved: int


def compute_retrieval_quality(
    task: Any,
    retrieved_memories: list[dict[str, Any]],
    all_available_memories: list[dict[str, Any]],
    relevance_criteria: dict[str, Any] | None = None,
) -> RetrievalQualityMetrics:
    """Compute retrieval quality metrics for a task.

    Args:
        task: Task instance with task_id, repo, sequence_index
        retrieved_memories: List of retrieved memory dictionaries
        all_available_memories: List of all available memory dictionaries
        relevance_criteria: Optional criteria for determining relevance
            - same_repo: Whether to require same repository (default True)
            - same_type: Whether to require same memory type (default False)
            - temporal_window: Max age difference for relevance (default None)
            - success_only: Whether to only consider successful memories (default False)

    Returns:
        RetrievalQualityMetrics with computed metrics

    Notes:
        - Relevance is determined by same_repo (required) and optional criteria
        - If no relevant memories exist, precision and recall are 0.0
        - MRR is 0.0 if no relevant memories are retrieved
        - NDCG is 0.0 if no relevant memories exist
    """
    if relevance_criteria is None:
        relevance_criteria = {
            "same_repo": True,
            "same_type": False,
            "temporal_window": None,
            "success_only": False,
        }

    # Determine relevant memories from all available
    relevant_memory_ids = _get_relevant_memory_ids(
        task=task,
        all_memories=all_available_memories,
        criteria=relevance_criteria,
    )

    # Determine which retrieved memories are relevant
    retrieved_memory_ids = [mem.get("memory_id", "") for mem in retrieved_memories]
    relevant_retrieved = [
        mem_id for mem_id in retrieved_memory_ids if mem_id in relevant_memory_ids
    ]

    # Compute metrics
    k = len(retrieved_memories)
    num_relevant_retrieved = len(relevant_retrieved)
    num_relevant_total = len(relevant_memory_ids)
    num_retrieved = len(retrieved_memories)

    # Precision@k: relevant retrieved / k
    precision_at_k = num_relevant_retrieved / k if k > 0 else 0.0

    # Recall@k: relevant retrieved / total relevant
    recall_at_k = (
        num_relevant_retrieved / num_relevant_total if num_relevant_total > 0 else 0.0
    )

    # MRR: reciprocal rank of first relevant item
    mrr = _compute_mrr(retrieved_memory_ids, relevant_memory_ids)

    # NDCG@k: normalized discounted cumulative gain
    ndcg_at_k = _compute_ndcg(
        retrieved_memory_ids, relevant_memory_ids, k, num_relevant_total
    )

    return RetrievalQualityMetrics(
        task_id=task.task_id,
        k=k,
        precision_at_k=precision_at_k,
        recall_at_k=recall_at_k,
        mrr=mrr,
        ndcg_at_k=ndcg_at_k,
        num_relevant_retrieved=num_relevant_retrieved,
        num_relevant_total=num_relevant_total,
        num_retrieved=num_retrieved,
    )


def _get_relevant_memory_ids(
    task: Any,
    all_memories: list[dict[str, Any]],
    criteria: dict[str, Any],
) -> set[str]:
    """Determine which memories are relevant for a task.

    Args:
        task: Task instance
        all_memories: List of all available memory dictionaries
        criteria: Relevance criteria

    Returns:
        Set of relevant memory IDs
    """
    relevant_ids = set()

    for mem in all_memories:
        # Skip if memory is from future (not available at task time)
        if mem.get("sequence_index", 0) >= task.sequence_index:
            continue

        # Same repository (required)
        if criteria.get("same_repo", True):
            if mem.get("repo", "") != task.repo:
                continue

        # Same memory type (optional)
        if criteria.get("same_type", False):
            # Would need task type classification to compare
            # For now, skip this criterion
            pass

        # Temporal window (optional)
        if criteria.get("temporal_window") is not None:
            age = task.sequence_index - mem.get("sequence_index", 0)
            if age > criteria["temporal_window"]:
                continue

        # Success only (optional)
        if criteria.get("success_only", False):
            if mem.get("outcome", "") != "pass":
                continue

        # Memory is relevant
        relevant_ids.add(mem.get("memory_id", ""))

    return relevant_ids


def _compute_mrr(
    retrieved_ids: list[str],
    relevant_ids: set[str],
) -> float:
    """Compute Mean Reciprocal Rank.

    Args:
        retrieved_ids: List of retrieved memory IDs (in order)
        relevant_ids: Set of relevant memory IDs

    Returns:
        MRR score (0.0 if no relevant items retrieved)
    """
    for rank, mem_id in enumerate(retrieved_ids, start=1):
        if mem_id in relevant_ids:
            return 1.0 / rank
    return 0.0


def _compute_ndcg(
    retrieved_ids: list[str],
    relevant_ids: set[str],
    k: int,
    num_relevant_total: int,
) -> float:
    """Compute Normalized Discounted Cumulative Gain at k.

    Args:
        retrieved_ids: List of retrieved memory IDs (in order)
        relevant_ids: Set of relevant memory IDs
        k: Number of items to consider
        num_relevant_total: Total number of relevant items

    Returns:
        NDCG@k score (0.0 if no relevant items exist)
    """
    if num_relevant_total == 0:
        return 0.0

    # Compute DCG@k (binary relevance: 1 if relevant, 0 otherwise)
    dcg = 0.0
    for rank, mem_id in enumerate(retrieved_ids[:k], start=1):
        if mem_id in relevant_ids:
            # Binary relevance with log2 discount
            dcg += 1.0 / np.log2(rank + 1)

    # Compute ideal DCG@k (all relevant items at top)
    idcg = 0.0
    for rank in range(1, min(k, num_relevant_total) + 1):
        idcg += 1.0 / np.log2(rank + 1)

    # Normalize
    ndcg = dcg / idcg if idcg > 0 else 0.0

    return ndcg


def aggregate_retrieval_quality(
    metrics_list: list[RetrievalQualityMetrics],
) -> dict[str, float]:
    """Aggregate retrieval quality metrics across multiple tasks.

    Args:
        metrics_list: List of RetrievalQualityMetrics for multiple tasks

    Returns:
        Dictionary with aggregated metrics:
            - mean_precision_at_k: Mean precision@k
            - mean_recall_at_k: Mean recall@k
            - mean_mrr: Mean MRR
            - mean_ndcg_at_k: Mean NDCG@k
            - std_precision_at_k: Std dev of precision@k
            - std_recall_at_k: Std dev of recall@k
            - std_mrr: Std dev of MRR
            - std_ndcg_at_k: Std dev of NDCG@k
            - num_tasks: Number of tasks
    """
    if not metrics_list:
        return {
            "mean_precision_at_k": 0.0,
            "mean_recall_at_k": 0.0,
            "mean_mrr": 0.0,
            "mean_ndcg_at_k": 0.0,
            "std_precision_at_k": 0.0,
            "std_recall_at_k": 0.0,
            "std_mrr": 0.0,
            "std_ndcg_at_k": 0.0,
            "num_tasks": 0,
        }

    precision_values = [m.precision_at_k for m in metrics_list]
    recall_values = [m.recall_at_k for m in metrics_list]
    mrr_values = [m.mrr for m in metrics_list]
    ndcg_values = [m.ndcg_at_k for m in metrics_list]

    return {
        "mean_precision_at_k": float(np.mean(precision_values)),
        "mean_recall_at_k": float(np.mean(recall_values)),
        "mean_mrr": float(np.mean(mrr_values)),
        "mean_ndcg_at_k": float(np.mean(ndcg_values)),
        "std_precision_at_k": float(np.std(precision_values)),
        "std_recall_at_k": float(np.std(recall_values)),
        "std_mrr": float(np.std(mrr_values)),
        "std_ndcg_at_k": float(np.std(ndcg_values)),
        "num_tasks": len(metrics_list),
    }
