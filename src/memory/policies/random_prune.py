"""Random Prune memory policy.

This policy randomly selects memories to archive when capacity is exceeded,
isolating the volume effect (improvement from "less memory" alone, not "smarter memory").

**Validates: Requirements 10**

Purpose:
    Baseline to measure whether reducing memory volume improves performance,
    independent of semantic selection. If Random Prune outperforms Full Memory,
    it suggests that "less is more" even without intelligent selection.

Frozen Invariants (THESIS_FINAL_v5.md §0.1):
- Retrieval scoring = pure cosine similarity, identical across all 6 conditions (Invariant #5)
- 3 seeds for ALL 6 conditions (Invariant #2) - Random Prune uses seeded RNG
- Max 20 steps per task (Invariant #3)

Requirements: 10
Design: §2 Policy Specifications - Policy 2: Random Prune
"""

import logging
import random
from typing import TYPE_CHECKING, Any

from ..retriever import shared_retrieve
from .base import MemoryPolicy

if TYPE_CHECKING:
    from ..record import MemoryRecord
    from ..store import MemoryStore

logger = logging.getLogger(__name__)


class RandomPrunePolicy(MemoryPolicy):
    """Random pruning policy for memory management.

    **Validates: Requirements 10**

    This policy stores all incoming memories and randomly selects victims
    to archive when the active count exceeds max_records. Uses a seeded
    random number generator for reproducibility across runs.

    Behavior:
        1. Retrieval: Uses shared_retrieve() with identical scoring to all other policies
        2. Write: Stores all incoming memory records without filtering
        3. Maintain: When active count > max_records, randomly selects and archives
                    victims until count <= max_records

    Attributes:
        name: Policy identifier ("random_prune")
        seed: Random seed for reproducibility (one of 3 seeds per sequence-policy pair)
        max_records: Maximum number of active memories to retain
        rng: Seeded random number generator for victim selection

    Design Rationale:
        Random pruning isolates the volume effect from semantic selection.
        If Random Prune outperforms Full Memory, it demonstrates that reducing
        memory volume improves performance even without intelligent selection.
        This establishes a baseline for comparing semantic pruning policies
        (Type-Aware Decay, CLS Consolidation).

    Example:
        >>> policy = RandomPrunePolicy(seed=42, max_records=100)
        >>> # After task completion, if 105 memories exist:
        >>> policy.maintain(memory_store)
        >>> # Randomly archives 5 memories, leaving 100 active
    """

    name = "random_prune"

    def __init__(self, seed: int, max_records: int):
        """Initialize Random Prune policy with seeded RNG.

        Args:
            seed: Random seed for reproducibility (1, 2, or 3 in main experiment)
            max_records: Maximum number of active memories to retain (typically 100)

        Notes:
            - Seed ensures reproducibility: same seed + same sequence = same pruning
            - Different seeds produce different pruning sequences for statistical analysis
            - max_records is the capacity threshold that triggers pruning
        """
        self.seed = seed
        self.max_records = max_records

        # Initialize seeded RNG for reproducible victim selection
        # CRITICAL: Use Random() instance, not random.seed(), to avoid
        # interfering with other random operations in the system
        self.rng = random.Random(seed)

        logger.info(
            f"Initialized RandomPrunePolicy: seed={seed}, max_records={max_records}"
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

        Random Prune stores ALL incoming records without filtering.
        Pruning happens in maintain() after the record is stored.

        Args:
            memory_store: Persistent memory storage backend
            record: MemoryRecord to store (from reflection step)

        Notes:
            - No filtering at write time
            - All records stored regardless of type, outcome, or importance
            - Pruning deferred to maintain() phase
        """
        memory_store.add(record)

        logger.debug(
            f"Stored memory {record.memory_id} for task {record.task_id} "
            f"(type={record.memory_type}, outcome={record.outcome})"
        )

    def maintain(self, memory_store: "MemoryStore") -> None:
        """Perform random pruning if active count exceeds max_records.

        Algorithm:
            1. Count active (non-archived) records
            2. If count <= max_records, no action needed
            3. While count > max_records:
                a. Get all active records
                b. Randomly select one victim using seeded RNG
                c. Archive victim with reason="random_prune"
                d. Repeat until count <= max_records

        Args:
            memory_store: Persistent memory storage backend

        Notes:
            - Uses seeded RNG for reproducibility
            - Archives victims one at a time (not batch)
            - Archived records excluded from future retrieval
            - Preserves archived records for post-hoc analysis
            - No consideration of type, outcome, age, or importance

        Example:
            >>> # If 105 active memories and max_records=100:
            >>> policy.maintain(memory_store)
            >>> # Randomly archives 5 memories
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
            f"Random pruning: {active_count} active memories, "
            f"need to prune {num_to_prune} to reach {self.max_records}"
        )

        pruned_count = 0

        # The step at which this pruning happens = the current task (the latest
        # sequence_index among active records). Passing the VICTIM's own
        # sequence_index instead breaks the runner's archive-event delta
        # (archived_at_step must match the current step), so prunes go unlogged.
        current_step = max(
            (r.sequence_index for r in memory_store.active_records()), default=0
        )

        while memory_store.count_active() > self.max_records:
            # Get current active records
            active_records = memory_store.active_records()

            if not active_records:
                # Should never happen, but guard against infinite loop
                logger.error(
                    "No active records found during pruning. "
                    "This should never happen."
                )
                break

            # Randomly select victim using seeded RNG
            victim = self.rng.choice(active_records)

            # Archive victim
            memory_store.archive(
                memory_id=victim.memory_id,
                reason="random_prune",
                current_step=current_step
            )

            pruned_count += 1

            logger.debug(
                f"Archived memory {victim.memory_id} "
                f"(task={victim.task_id}, type={victim.memory_type}, "
                f"seq_idx={victim.sequence_index})"
            )

        final_count = memory_store.count_active()

        logger.info(
            f"Random pruning complete: pruned {pruned_count} memories, "
            f"final count={final_count}"
        )

        # Verify we reached the target
        assert final_count <= self.max_records, (
            f"Pruning failed: {final_count} > {self.max_records}. "
            f"This should never happen - bug in maintain()."
        )
