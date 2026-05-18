"""Shared retrieval function for memory policies.

This module implements the shared_retrieve() function that provides IDENTICAL
retrieval scoring across all 6 memory policies (except No Memory).

Frozen Invariants (THESIS_FINAL_v5.md §0.1):
- Retrieval scoring = pure cosine similarity, identical across all 6 conditions (Invariant #5)
- Injection order = relevance-sorted, best item LAST (Lost-in-the-Middle fix) (Invariant #6)
- Same-repo retrieval only in main experiment (Invariant #16)

Requirements: 6, 7
Design: §2 Components and Interfaces, §6 Shared Retrieval Function
"""

import logging
from typing import Any

from .record import MemoryRecord
from .store import MemoryStore

logger = logging.getLogger(__name__)


def shared_retrieve(
    task: Any,
    memory_store: MemoryStore,
    top_k: int,
    token_budget: int,
    same_repo_only: bool = True
) -> list[tuple[float, MemoryRecord]]:
    """
    Pure cosine similarity retrieval - IDENTICAL across all 6 policies.

    This function implements the core retrieval logic that is shared by all
    memory policies (except No Memory). It ensures that policy differences
    reflect storage decisions only, not retrieval scoring differences.

    Algorithm:
    1. Build query from task.repo + task.issue_text
    2. Embed query using OpenAI embedding model
    3. Filter candidates: same repo (if enabled), not archived
    4. Score with pure cosine similarity (NO bonuses/penalties)
    5. Sort descending, take top-k
    6. Drop lowest-scoring until within token_budget
    7. Return sorted ascending (best LAST for injection)

    Args:
        task: Task object with attributes:
            - repo: Repository name (e.g., "django/django")
            - issue_text: GitHub issue description
        memory_store: MemoryStore instance for this run
        top_k: Maximum number of memories to retrieve
        token_budget: Maximum total tokens for retrieved memories
        same_repo_only: Whether to restrict retrieval to same repository
                       (default: True for main experiment)

    Returns:
        List of (similarity_score, MemoryRecord) tuples, sorted ascending
        by relevance (best item LAST for Lost-in-the-Middle mitigation)

    Notes:
        - Pure cosine similarity scoring (NO adjustments for type, outcome, age, use_count)
        - Filters by same repository and non-archived status
        - Enforces token budget by dropping lowest-scoring memories
        - Guarantees final result fits within token_budget (no partial items)
        - Returns empty list if no candidates or all exceed budget
        - Used by all policies except No Memory (which returns empty list directly)

    Frozen Invariants:
        - Retrieval scoring MUST be identical across all 6 conditions
        - NO bonuses or penalties based on memory_type, outcome, age, or retrieval_count
        - Injection order: best item LAST (ascending sort by relevance)

    Example:
        >>> task = Task(repo="django/django", issue_text="Fix QuerySet.exclude bug")
        >>> memories = shared_retrieve(task, store, top_k=5, token_budget=2000)
        >>> # memories[0] has lowest relevance (injected first)
        >>> # memories[-1] has highest relevance (injected last)
    """
    # Build query text from task
    query_text = _build_query_text(task)

    # Generate embedding for query
    query_vector = memory_store._generate_embedding(query_text)

    # Perform FAISS cosine similarity search
    # This filters by repo and is_archived=False internally
    repo = task.repo if same_repo_only else None
    scored_memories = memory_store.search(
        query_vector=query_vector,
        top_k=top_k,
        repo=repo,
        same_repo_only=same_repo_only
    )

    if not scored_memories:
        logger.info(
            f"No memories found for task {task.task_id} "
            f"(repo={task.repo}, same_repo_only={same_repo_only})"
        )
        return []

    # Enforce token budget by dropping lowest-scoring memories
    # This guarantees the final result fits within budget
    budget_compliant = _trim_to_token_budget(scored_memories, token_budget)

    if not budget_compliant:
        logger.warning(
            f"No memories fit within token budget {token_budget} "
            f"for task {task.task_id}"
        )
        return []

    # Sort ascending by relevance (best LAST for Lost-in-the-Middle mitigation)
    # Requirement 7: Highest-relevance memory injected last in prompt
    budget_compliant.sort(key=lambda x: x[0], reverse=False)

    logger.info(
        f"Retrieved {len(budget_compliant)} memories for task {task.task_id}: "
        f"scores=[{budget_compliant[0][0]:.3f}..{budget_compliant[-1][0]:.3f}], "
        f"types={[m.memory_type for _, m in budget_compliant]}"
    )

    return budget_compliant


def _build_query_text(task: Any) -> str:
    """Build query text from task for embedding.

    Args:
        task: Task object with repo and issue_text attributes

    Returns:
        Query text formatted as "Repository: {repo}\nIssue: {issue_text}"

    Notes:
        - Simple concatenation of repo and issue
        - No additional metadata included
        - Matches the format used in design document
    """
    return f"Repository: {task.repo}\nIssue: {task.issue_text}"


def _trim_to_token_budget(
    scored_memories: list[tuple[float, MemoryRecord]],
    token_budget: int
) -> list[tuple[float, MemoryRecord]]:
    """Trim memories to fit within token budget.

    Drops lowest-scoring memories until the total token count is within budget.
    Guarantees that the final result fits entirely within the budget (no partial items).

    Args:
        scored_memories: List of (score, MemoryRecord) tuples, sorted descending by score
        token_budget: Maximum total tokens allowed

    Returns:
        List of (score, MemoryRecord) tuples that fit within budget,
        maintaining descending score order

    Notes:
        - Drops entire memories (not truncated)
        - Drops lowest-scoring first (preserves highest-scoring)
        - Returns empty list if even the highest-scoring memory exceeds budget
        - Uses embedding_text token_length from MemoryRecord

    Algorithm:
        1. Start with all memories sorted descending by score
        2. Calculate total tokens
        3. While over budget, drop the lowest-scoring memory
        4. Return remaining memories

    Example:
        >>> memories = [(0.9, mem1), (0.8, mem2), (0.7, mem3)]  # descending
        >>> # If mem1 + mem2 fit but mem1 + mem2 + mem3 exceeds budget
        >>> result = _trim_to_token_budget(memories, budget=1000)
        >>> # Returns [(0.9, mem1), (0.8, mem2)]
    """
    if not scored_memories:
        return []

    # Calculate total tokens for all memories
    total_tokens = sum(record.token_length for _, record in scored_memories)

    # If within budget, return all
    if total_tokens <= token_budget:
        return scored_memories

    # Need to drop memories - start from lowest-scoring (end of list)
    # scored_memories is sorted descending, so we drop from the end
    result = scored_memories.copy()

    while result and total_tokens > token_budget:
        # Drop the lowest-scoring memory (last in descending order)
        _, dropped = result.pop()
        total_tokens -= dropped.token_length

        logger.debug(
            f"Dropped memory {dropped.memory_id} (score={_:.3f}, "
            f"tokens={dropped.token_length}) to fit budget. "
            f"Remaining: {len(result)} memories, {total_tokens} tokens"
        )

    # Verify final result is within budget
    final_tokens = sum(record.token_length for _, record in result)
    assert final_tokens <= token_budget, (
        f"Token budget violation: {final_tokens} > {token_budget}. "
        f"This should never happen - bug in _trim_to_token_budget."
    )

    if not result:
        logger.warning(
            f"All memories exceed token budget {token_budget}. "
            f"Even the highest-scoring memory has {scored_memories[0][1].token_length} tokens."
        )

    return result


def format_memory_for_prompt(
    scored_memories: list[tuple[float, MemoryRecord]],
    include_metadata: bool = True
) -> str:
    """Format retrieved memories for injection into agent prompt.

    This function is used by the agent to render memories in the prompt
    with traceability metadata (memory_id, rank, similarity, age, type).

    Args:
        scored_memories: List of (score, MemoryRecord) tuples, sorted ascending
                        (best LAST for Lost-in-the-Middle mitigation)
        include_metadata: Whether to include metadata header for each memory

    Returns:
        Formatted string ready for prompt injection

    Notes:
        - Assumes scored_memories is already sorted ascending (best LAST)
        - Renders each memory with its embedding_text content
        - Includes metadata for traceability: memory_id, rank, similarity, age, type
        - Rank 1 = lowest relevance (injected first)
        - Rank N = highest relevance (injected last, immediately before task)

    Example:
        >>> memories = [(0.7, mem1), (0.8, mem2), (0.9, mem3)]  # ascending
        >>> prompt = format_memory_for_prompt(memories)
        >>> # mem1 appears first (rank 1, lowest relevance)
        >>> # mem3 appears last (rank 3, highest relevance)
    """
    if not scored_memories:
        return ""

    formatted_parts = []

    for rank, (score, record) in enumerate(scored_memories, start=1):
        if include_metadata:
            # Calculate age (not stored in record, would need current step)
            # For now, just use sequence_index as a proxy
            metadata = (
                f"[Memory {rank}/{len(scored_memories)} | "
                f"ID: {record.memory_id} | "
                f"Similarity: {score:.3f} | "
                f"Type: {record.memory_type} | "
                f"Task: {record.sequence_index}]"
            )
            formatted_parts.append(metadata)

        # Include the embedding text (Issue + Error + Diff)
        formatted_parts.append(record.embedding_text)
        formatted_parts.append("")  # Blank line separator

    return "\n".join(formatted_parts)
