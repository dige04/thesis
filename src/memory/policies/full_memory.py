"""Full Memory policy implementation.

This module implements the Full Memory policy that stores all memories
without any pruning or archiving. This policy serves as an upper bound
baseline to measure the effect of unbounded memory accumulation.

**Validates: Requirements 9**

Design Principle:
The Full Memory policy provides a baseline to test whether unlimited memory
accumulation helps or hurts performance. By storing everything and never
pruning, we can measure whether "more memory is always better" or if there's
a point where memory accumulation degrades performance (analysis paralysis,
noise, retrieval quality degradation).

This policy uses shared_retrieve() for retrieval (identical scoring to all
other policies) but ignores all capacity limits during storage.

CRITICAL: Full Memory means "store everything; retrieve top-k under same
budget." It does NOT mean "append everything into prompt" (that would
confound memory policy with context length).
"""

from typing import TYPE_CHECKING, Any

from ..retriever import shared_retrieve
from .base import MemoryPolicy

if TYPE_CHECKING:
    from ..store import MemoryRecord, MemoryStore


class FullMemoryPolicy(MemoryPolicy):
    """Baseline policy that stores all memories without pruning.

    This policy serves as an upper bound baseline to measure the effect of
    unbounded memory accumulation. It stores all memory records without any
    limit and never prunes or archives memories.

    **Validates: Requirements 9**

    Acceptance Criteria:
    1. Uses shared_retrieve() with identical scoring to all other policies
    2. Stores all memory records without limit
    3. Never prunes or archives during maintenance
    4. Ignores max_records and max_storage_tokens configuration

    Attributes:
        name: Policy identifier "full_memory"

    Example:
        >>> policy = FullMemoryPolicy()
        >>> # Retrieval uses shared_retrieve (identical to other policies)
        >>> memories = policy.retrieve(task, store, top_k=5, token_budget=2000)
        >>> # Storage accepts all records
        >>> policy.write(store, record)  # Always stores
        >>> # Maintenance never prunes
        >>> policy.maintain(store)  # No-op (never prunes)
    """

    name = "full_memory"

    def retrieve(
        self,
        task: Any,
        memory_store: "MemoryStore",
        top_k: int,
        token_budget: int
    ) -> list[tuple[float, "MemoryRecord"]]:
        """Retrieve relevant memories using shared retrieval function.

        Uses the shared_retrieve() function to ensure IDENTICAL retrieval
        scoring across all policies. This is a frozen invariant (Requirement 6).

        The shared_retrieve() function implements:
        - Pure cosine similarity scoring (no bonuses or penalties)
        - Filtering by same repository and non-archived status
        - Top-k selection within token budget
        - Ascending sort (best item LAST for Lost-in-the-Middle mitigation)

        **Validates: Requirements 9.1**

        Args:
            task: The current task requiring memory retrieval. Contains repo,
                  issue_text, and other task metadata.
            memory_store: The persistent memory storage backend (SQLite + FAISS).
            top_k: Maximum number of memories to retrieve (typically 5).
            token_budget: Maximum total tokens allowed for retrieved memories
                         (typically 2000).

        Returns:
            A list of (score, MemoryRecord) tuples sorted in ascending order
            of relevance (lowest relevance first, highest relevance last).
            The list may be shorter than top_k if fewer memories exist or
            token budget constraints require dropping memories.

        Notes:
            - Retrieval scoring is IDENTICAL to all other policies
            - Full Memory may have more memories in the store than other policies,
              but retrieval still returns only top-k within token budget
            - This isolates the effect of "having more memories available" from
              "injecting more memories into the prompt"
        """
        return shared_retrieve(task, memory_store, top_k, token_budget, same_repo_only=True)

    def write(self, memory_store: "MemoryStore", record: "MemoryRecord") -> None:
        """Store all memory records without limit.

        The Full Memory policy stores every memory record without checking
        capacity limits. This allows unbounded memory accumulation to test
        whether "more memory is always better."

        **Validates: Requirements 9.2, 9.3**

        Args:
            memory_store: The persistent memory storage backend.
            record: The memory record to store. Contains all task experience:
                    identity, type, outcome, content, embeddings, metadata.

        Notes:
            - Ignores max_records configuration (stores all)
            - Ignores max_storage_tokens configuration (stores all)
            - Never rejects or discards records
            - Memory accumulation is unbounded (limited only by disk space)
        """
        # Store all records without checking capacity limits
        memory_store.add(record)

    def maintain(self, memory_store: "MemoryStore") -> None:
        """Perform no maintenance operations (never prune or archive).

        The Full Memory policy never prunes or archives memories. This method
        is a no-op to ensure all memories persist indefinitely.

        **Validates: Requirements 9.4**

        Args:
            memory_store: The persistent memory storage backend (ignored).

        Notes:
            - Never archives memories
            - Never prunes memories
            - Never consolidates memories
            - All memories remain active indefinitely
            - Memory count grows monotonically throughout the sequence
        """
        # No-op - never prune or archive
        return
