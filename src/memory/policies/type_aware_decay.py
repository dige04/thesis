"""Type-Aware Decay memory policy.

This policy scores memories using Anderson-Schooler power-law decay with
type-specific parameters, archiving the lowest-scoring memories when capacity
is exceeded.

**Validates: Requirements 12**

Purpose:
    Test whether semantic prioritization (type-aware decay) outperforms random
    pruning. If Type-Aware Decay outperforms Random Prune, it demonstrates that
    WHAT is forgotten matters beyond simply reducing volume.

Frozen Invariants (THESIS_FINAL_v5.md §0.1):
- Retrieval scoring = pure cosine similarity, identical across all 6 conditions (Invariant #5)
- Type-Aware Decay formula = multiplicative Anderson-Schooler: 
  `score = base_value(type) × age^(-d(type)) × (1+retrieval_count)^0.5` (Invariant #8)
- Type-specific parameters locked from THESIS_FINAL_v5.md §8 P4 (Invariant #23)
- Archive lowest-scoring memories first (Requirement 12.5)

Requirements: 12
Design: §2 Policy Specifications - Policy 4: Type-Aware Decay
"""

import logging
from typing import TYPE_CHECKING, Any

from ..retriever import shared_retrieve
from .base import MemoryPolicy

if TYPE_CHECKING:
    from ..record import MemoryRecord
    from ..store import MemoryStore

logger = logging.getLogger(__name__)


# Type-specific parameters (LOCKED from THESIS_FINAL_v5.md §8 P4)
# Format: memory_type -> (base_value, decay_d, tier)
# These parameters are frozen after Week 4 calibration
TYPE_PARAMS = {
    #               base_value   decay_d   tier
    "architectural":   (1.0,       0.05,   "Sacred"),
    "api_change":      (0.8,       0.15,   "Critical"),
    "bug_fix":         (0.6,       0.25,   "Important"),
    "test_update":     (0.4,       0.35,   "Expendable"),
    "config":          (0.3,       0.40,   "Expendable"),
}


class TypeAwareDecayPolicy(MemoryPolicy):
    """Type-aware decay policy using Anderson-Schooler power-law formula.

    **Validates: Requirements 12**

    This policy stores all incoming memories and scores them using a cognitive-
    inspired forgetting curve. When capacity is exceeded, it archives the
    lowest-scoring memories.

    Behavior:
        1. Retrieval: Uses shared_retrieve() with identical scoring to all other policies
        2. Write: Stores all incoming memory records without filtering
        3. Maintain: When active count > max_records, computes importance_score
                    for each memory using Anderson-Schooler power-law formula,
                    then archives lowest-scoring memories

    Scoring Formula (Anderson & Schooler 1991):
        importance_score = base_value(type) × age^(-decay_d(type)) × (1 + use_count)^0.5

    Where:
        - base_value(type): Type-specific base importance (architectural=1.0, config=0.3)
        - age: Tasks since creation (current_step - sequence_index)
        - decay_d(type): Type-specific decay rate (architectural=0.05, config=0.40)
        - use_count: Number of times memory was retrieved (= retrieval_count)
        - 0.5 exponent: Sub-linear frequency effect (doubling retrievals ≠ doubling value)

    Type Parameters (LOCKED):
        - architectural: base=1.0, decay=0.05 (Sacred - decays slowest)
        - api_change:    base=0.8, decay=0.15 (Critical)
        - bug_fix:       base=0.6, decay=0.25 (Important)
        - test_update:   base=0.4, decay=0.35 (Expendable)
        - config:        base=0.3, decay=0.40 (Expendable - decays fastest)

    Attributes:
        name: Policy identifier ("type_aware_decay")
        max_records: Maximum number of active memories to retain
        FREQUENCY_EXPONENT: Sub-linear frequency exponent (0.5)

    Design Rationale:
        The Anderson-Schooler power-law formula is cognitively grounded:
        P(need) ∝ t^(-d) is the optimal forgetting curve, not an arbitrary
        linear sum. Type-specific decay rates reflect failure-mode tiers:
        architectural memories (Sacred) decay slowly, config memories
        (Expendable) decay quickly.

    CRITICAL: Does NOT use success_after_retrieval_count or
    failure_after_retrieval_count in scoring. Those are downstream associated
    labels (Frozen Decision #14), not causal predictors.

    Example:
        >>> policy = TypeAwareDecayPolicy(max_records=100)
        >>> # After task 50, if 105 memories exist:
        >>> policy.maintain(memory_store)
        >>> # Computes importance_score for each memory:
        >>> # - architectural memory from task 10: 1.0 × 40^(-0.05) × (1+3)^0.5 = high
        >>> # - config memory from task 45: 0.3 × 5^(-0.40) × (1+1)^0.5 = low
        >>> # Archives 5 lowest-scoring memories, leaving 100 highest-scoring
    """

    name = "type_aware_decay"
    FREQUENCY_EXPONENT = 0.5  # Sub-linear: doubling retrievals ≠ doubling value

    def __init__(self, max_records: int):
        """Initialize Type-Aware Decay policy.

        Args:
            max_records: Maximum number of active memories to retain (typically 100)

        Notes:
            - max_records is the capacity threshold that triggers pruning
            - Type parameters are LOCKED from THESIS_FINAL_v5.md §8 P4
            - Pruning is deterministic (no randomness, no seed needed)
            - Archives lowest-scoring memories first
        """
        self.max_records = max_records

        logger.info(
            f"Initialized TypeAwareDecayPolicy: max_records={max_records}, "
            f"frequency_exponent={self.FREQUENCY_EXPONENT}"
        )
        logger.debug(f"Type parameters: {TYPE_PARAMS}")

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

        Type-Aware Decay stores ALL incoming records without filtering.
        Scoring and pruning happen in maintain() after the record is stored.

        Args:
            memory_store: Persistent memory storage backend
            record: MemoryRecord to store (from reflection step)

        Notes:
            - No filtering at write time
            - All records stored regardless of type, outcome, or importance
            - Scoring deferred to maintain() phase
        """
        memory_store.add(record)

        logger.debug(
            f"Stored memory {record.memory_id} for task {record.task_id} "
            f"(type={record.memory_type}, outcome={record.outcome}, "
            f"seq_idx={record.sequence_index})"
        )

    def maintain(self, memory_store: "MemoryStore") -> None:
        """Perform type-aware decay pruning if active count exceeds max_records.

        CRITICAL: Computes importance_score using Anderson-Schooler power-law
        formula with type-specific parameters. Archives lowest-scoring memories.

        Algorithm:
            1. Count active (non-archived) records
            2. Get all active records and current step (max sequence_index)
            3. For each record, compute importance_score:
               score = base_value(type) × age^(-decay_d(type)) × (1 + use_count)^0.5
            4. If count <= max_records, no pruning needed (but scores are updated)
            5. If count > max_records, sort by score ascending (lowest first)
            6. Archive the lowest-scoring (count - max_records) memories
            7. Retain the max_records highest-scoring memories

        Args:
            memory_store: Persistent memory storage backend

        Notes:
            - Deterministic pruning (no randomness)
            - Archives lowest-scoring memories first
            - Archived records excluded from future retrieval
            - Preserves archived records for post-hoc analysis
            - Updates importance_score field for all active records (even when no pruning)

        Example:
            >>> # If 105 active memories and max_records=100:
            >>> # Memory A: architectural, age=40, use_count=3
            >>> # score_A = 1.0 × 40^(-0.05) × (1+3)^0.5 = 1.0 × 0.726 × 2.0 = 1.452
            >>> # Memory B: config, age=5, use_count=1
            >>> # score_B = 0.3 × 5^(-0.40) × (1+1)^0.5 = 0.3 × 0.455 × 1.414 = 0.193
            >>> policy.maintain(memory_store)
            >>> # Archives 5 lowest-scoring memories (including B, not A)
            >>> # Retains 100 highest-scoring memories
            >>> assert memory_store.count_active() == 100
        """
        active_count = memory_store.count_active()

        if active_count == 0:
            # No records to maintain
            logger.debug("No records to maintain")
            return

        # Get all active records and compute current step
        active_records = memory_store.active_records()
        current_step = max(r.sequence_index for r in active_records)

        logger.debug(f"Current step: {current_step}")

        # Determine if pruning is needed
        needs_pruning = active_count > self.max_records
        num_to_prune = active_count - self.max_records if needs_pruning else 0

        if needs_pruning:
            logger.info(
                f"Type-aware decay pruning: {active_count} active memories, "
                f"need to prune {num_to_prune} to reach {self.max_records}"
            )
        else:
            logger.debug(
                f"No pruning needed: {active_count} <= {self.max_records}, "
                f"but updating importance scores"
            )

        # Compute importance_score for each record
        scored = []
        for record in active_records:
            # Get type-specific parameters (default to config if unknown type)
            base, decay, tier = TYPE_PARAMS.get(
                record.memory_type,
                (0.3, 0.40, "Expendable")
            )

            # Compute age (tasks since creation)
            age = max(1, current_step - record.sequence_index)

            # Get retrieval count
            retrieval = record.use_count

            # Anderson & Schooler power-law formula
            score = base * (age ** -decay) * ((1 + retrieval) ** self.FREQUENCY_EXPONENT)

            # Update record's importance_score field
            record.importance_score = score
            memory_store.update_importance_score(record.memory_id, score)

            scored.append((score, record))

            logger.debug(
                f"Scored memory {record.memory_id}: "
                f"type={record.memory_type} (base={base}, decay={decay}, tier={tier}), "
                f"age={age}, use_count={retrieval}, score={score:.4f}"
            )

        # Sort by score ascending (lowest first)
        scored.sort(key=lambda x: x[0])

        # Archive the lowest-scoring num_to_prune memories (only if pruning needed)
        if needs_pruning:
            pruned_count = 0
            for score, record in scored[:num_to_prune]:
                memory_store.archive(
                    memory_id=record.memory_id,
                    reason="type_aware_decay",
                    current_step=current_step
                )

                pruned_count += 1

                logger.debug(
                    f"Archived memory {record.memory_id} "
                    f"(task={record.task_id}, type={record.memory_type}, "
                    f"score={score:.4f}, seq_idx={record.sequence_index})"
                )

            final_count = memory_store.count_active()

            logger.info(
                f"Type-aware decay pruning complete: pruned {pruned_count} memories, "
                f"final count={final_count}"
            )

            # Verify we reached the target
            assert final_count <= self.max_records, (
                f"Pruning failed: {final_count} > {self.max_records}. "
                f"This should never happen - bug in maintain()."
            )

            # Verify we pruned the correct number
            assert pruned_count == num_to_prune, (
                f"Pruned {pruned_count} memories but expected {num_to_prune}. "
                f"This should never happen - bug in maintain()."
            )
        else:
            logger.debug(
                f"Importance scores updated for {len(scored)} memories, no pruning performed"
            )
