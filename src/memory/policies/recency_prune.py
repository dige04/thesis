"""Recency Prune memory policy.

This policy implements FIFO (First-In-First-Out) pruning based on task sequence order.
When capacity is exceeded, the oldest memories (by sequence_index) are archived first.

**Validates: Requirements 11**

Purpose:
    Test whether recency alone is sufficient for effective memory management.
    This policy assumes that recent task experiences are more relevant than
    older ones, implementing a simple temporal decay without semantic scoring.

Frozen Invariants (THESIS_FINAL_v5.md §0.1):
- Retrieval scoring = pure cosine similarity, identical across all 6 conditions (Invariant #5)
- Archive based on sequence_index (chronological order), not created_at timestamp
- Deterministic pruning (no randomness)

Requirements: 11
Design: §2 Policy Specifications - Policy 3: Recency Prune
"""

import logging
from typing import TYPE_CHECKING, Any

from ..retriever import shared_retrieve
from .base import MemoryPolicy

if TYPE_CHECKING:
    from ..record import MemoryRecord
    from ..store import MemoryStore

logger = logging.getLogger(__name__)


class RecencyPrunePolicy(MemoryPolicy):
    """Recency-based pruning policy for memory management.

    **Validates: Requirements 11**

    This policy stores all incoming memories and archives the oldest memories
    (by sequence_index) when the active count exceeds max_records. Implements
    FIFO (First-In-First-Out) pruning based on task chronological order.

    Behavior:
        1. Retrieval: Uses shared_retrieve() with identical scoring to all other policies
        2. Write: Stores all incoming memory records without filtering
        3. Maintain: When active count > max_records, archives oldest memories by
                    sequence_index until count <= max_records

    Attributes:
        name: Policy identifier ("recency_prune")
        max_records: Maximum number of active memories to retain

    Design Rationale:
        Recency pruning tests whether temporal proximity alone is sufficient
        for effective memory management. This policy assumes that recent task
        experiences are more relevant than older ones, without considering
        semantic content, memory type, or retrieval patterns.

        If Recency Prune outperforms Random Prune, it suggests that temporal
        structure matters. If it underperforms Type-Aware Decay, it suggests
        that semantic prioritization provides additional value beyond recency.

    Key Differences from Random Prune:
        - Deterministic (no randomness, no seed required)
        - Preserves recent memories (temporal bias)
        - Archives oldest memories first (FIFO order)

    Example:
        >>> policy = RecencyPrunePolicy(max_records=100)
        >>> # After task 105, if 105 memories exist:
        >>> policy.maintain(memory_store)
        >>> # Archives memories from tasks 1-5 (oldest 5)
        >>> # Retains memories from tasks 6-105 (most recent 100)
    """

    name = "recency_prune"

    def __init__(self, max_records: int):
        """Initialize Recency Prune policy.

        Args:
            max_records: Maximum number of active memories to retain (typically 100)

        Notes:
            - No seed required (deterministic pruning)
            - max_records is the capacity threshold that triggers pruning
            - Pruning is based on sequence_index (chronological order)
        """
        self.max_records = max_records

        logger.info(
            f"Initialized RecencyPrunePolicy: max_records={max_records}"
        )

    def retrieve(
        self,
        task: Any,
        memory_store: "MemoryStore",
        top_k: int,
        token_budget: int
    ) -> list[tuple[float, "MemoryRecord"]]:
        """Retrieve relevant memories using shared retrieval function.

        CRITICAL: Uses shared_retrieve() to ensure identical retrieval scoring
        across all 6 policies. This is a frozen invariant (Requirement 6).

        **Validates: Requirements 11.1**

        Args:
            task: Current task requiring memory retrieval
            memory_store: Persistent memory storage backend
            top_k: Maximum number of memories to retrieve
            token_budget: Maximum total tokens for retrieved memories

        Returns:
            List of (similarity_score, MemoryRecord) tuples, sorted ascending
            by relevance (best item LAST for Lost-in-the-Middle mitigation)

        Notes:
            - Pure cosine similarity scoring (no bonuses or penalties)
            - Filters by same repository and non-archived status
            - Enforces token budget by dropping lowest-scoring memories
            - Returns empty list if no candidates or all exceed budget
        """
        return shared_retrieve(task, memory_store, top_k, token_budget)

    def write(self, memory_store: "MemoryStore", record: "MemoryRecord") -> None:
        """Store a new memory record.

        Recency Prune stores ALL incoming records without filtering.
        Pruning happens in maintain() after the record is stored.

        **Validates: Requirements 11.2**

        Args:
            memory_store: Persistent memory storage backend
            record: MemoryRecord to store (from reflection step)

        Notes:
            - No filtering at write time
            - All records stored regardless of type, outcome, or age
            - Pruning deferred to maintain() phase
        """
        memory_store.add(record)

        logger.debug(
            f"Stored memory {record.memory_id} for task {record.task_id} "
            f"(type={record.memory_type}, outcome={record.outcome}, "
            f"seq_idx={record.sequence_index})"
        )

    def maintain(self, memory_store: "MemoryStore") -> None:
        """Perform recency-based pruning if active count exceeds max_records.

        Archives the oldest memories (by sequence_index) until the active count
        is at or below max_records. Retains the most recent memories.

        **Validates: Requirements 11.3, 11.4**

        Algorithm:
            1. Count active (non-archived) records
            2. If count <= max_records, no action needed
            3. Sort active records by sequence_index ascending (oldest first)
            4. Archive oldest records until count <= max_records
            5. Retain the max_records most recent memories

        Args:
            memory_store: Persistent memory storage backend

        Notes:
            - Deterministic pruning (no randomness)
            - Archives based on sequence_index (chronological order), NOT created_at
            - Archived records excluded from future retrieval
            - Preserves archived records for post-hoc analysis
            - No consideration of type, outcome, or importance

        Example:
            >>> # If 105 active memories and max_records=100:
            >>> # Memories from tasks 1-105 exist
            >>> policy.maintain(memory_store)
            >>> # Archives memories from tasks 1-5 (oldest 5)
            >>> # Retains memories from tasks 6-105 (most recent 100)
            >>> assert memory_store.count_active() == 100
        """
        active_count = memory_store.count_active()

        if active_count <= self.max_records:
            # No pruning needed
            logger.debug(
                f"No pruning needed: {active_count} <= {self.max_records}"
            )
            return

        # Need to prune
        num_to_prune = active_count - self.max_records

        logger.info(
            f"Recency pruning: {active_count} active memories, "
            f"need to prune {num_to_prune} to reach {self.max_records}"
        )

        # Get all active records and sort by sequence_index ascending (oldest first)
        active_records = memory_store.active_records()
        active_records.sort(key=lambda r: r.sequence_index, reverse=False)

        # Archive the oldest memories (first num_to_prune records)
        victims = active_records[:num_to_prune]

        pruned_count = 0

        for victim in victims:
            memory_store.archive(
                memory_id=victim.memory_id,
                reason="recency_prune",
                current_step=victim.sequence_index
            )

            pruned_count += 1

            logger.debug(
                f"Archived memory {victim.memory_id} "
                f"(task={victim.task_id}, type={victim.memory_type}, "
                f"seq_idx={victim.sequence_index})"
            )

        final_count = memory_store.count_active()

        logger.info(
            f"Recency pruning complete: pruned {pruned_count} memories, "
            f"final count={final_count}"
        )

        # Verify we reached the target
        assert final_count <= self.max_records, (
            f"Pruning failed: {final_count} > {self.max_records}. "
            f"This should never happen - bug in maintain()."
        )

        # Verify we retained the most recent memories
        if final_count > 0:
            remaining_records = memory_store.active_records()
            min_seq_idx = min(r.sequence_index for r in remaining_records)
            max_seq_idx = max(r.sequence_index for r in remaining_records)

            logger.debug(
                f"Retained memories from sequence_index {min_seq_idx} to {max_seq_idx}"
            )
