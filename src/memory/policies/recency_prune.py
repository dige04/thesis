"""Recency Prune memory policy.

This policy retains only the most recent memories, archiving the oldest
memories by sequence_index when capacity is exceeded.

**Validates: Requirements 11**

Purpose:
    Test whether recency alone is sufficient for effective memory management.
    This policy implements a simple FIFO (First-In-First-Out) strategy where
    older memories are discarded in favor of newer ones.

Frozen Invariants (THESIS_FINAL_v5.md §0.1):
- Retrieval scoring = pure cosine similarity, identical across all 6 conditions (Invariant #5)
- Max 20 steps per task (Invariant #3)

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
    by sequence_index when the active count exceeds max_records. Retains only
    the max_records most recent memories.

    Behavior:
        1. Retrieval: Uses shared_retrieve() with identical scoring to all other policies
        2. Write: Stores all incoming memory records without filtering
        3. Maintain: When active count > max_records, archives oldest memories
                    by sequence_index until count <= max_records

    Attributes:
        name: Policy identifier ("recency_prune")
        max_records: Maximum number of active memories to retain

    Design Rationale:
        Recency pruning tests the hypothesis that recent memories are more
        relevant than old ones for sequential coding tasks. This is a simple
        heuristic that doesn't require semantic analysis or scoring.

        If Recency Prune performs well, it suggests that temporal locality
        is a strong signal for memory relevance in coding tasks. If it
        performs poorly, it suggests that older memories can remain relevant
        (e.g., architectural decisions, API patterns).

    Example:
        >>> policy = RecencyPrunePolicy(max_records=100)
        >>> # After task 105 completes, if 105 memories exist:
        >>> policy.maintain(memory_store)
        >>> # Archives memories from tasks 1-5, retains tasks 101-105
    """

    name = "recency_prune"

    def __init__(self, max_records: int):
        """Initialize Recency Prune policy.

        Args:
            max_records: Maximum number of active memories to retain (typically 100)

        Notes:
            - max_records is the capacity threshold that triggers pruning
            - Pruning is deterministic (always archives oldest by sequence_index)
            - No randomness involved (unlike Random Prune)
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

        Algorithm:
            1. Count active (non-archived) records
            2. If count <= max_records, no action needed
            3. If count > max_records:
                a. Get all active records
                b. Sort by sequence_index ascending (oldest first)
                c. Archive oldest records until count <= max_records
                d. Retain max_records most recent memories

        Args:
            memory_store: Persistent memory storage backend

        Notes:
            - Deterministic pruning (always archives oldest by sequence_index)
            - Archives victims in batch (not one at a time)
            - Archived records excluded from future retrieval
            - Preserves archived records for post-hoc analysis
            - No consideration of type, outcome, or importance
            - Only considers temporal ordering (sequence_index)

        Example:
            >>> # If 105 active memories and max_records=100:
            >>> policy.maintain(memory_store)
            >>> # Archives 5 oldest memories (lowest sequence_index)
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
        active_records.sort(key=lambda r: r.sequence_index)

        # Archive the oldest records (first num_to_prune in sorted list)
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
