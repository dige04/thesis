"""Abstract base class for memory policies.

This module defines the MemoryPolicy interface that all memory management
policies must implement. The interface enforces three core operations:
retrieve, write, and maintain.

CRITICAL INVARIANT (Requirement 6):
All policies except No Memory MUST use shared_retrieve() for retrieval
to ensure identical scoring across all conditions. This isolates policy
differences to storage decisions only, not retrieval scoring.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..store import MemoryRecord, MemoryStore


class MemoryPolicy(ABC):
    """Abstract base class for memory management policies.

    All memory policies must inherit from this class and implement the three
    abstract methods: retrieve(), write(), and maintain().

    Attributes:
        name: A unique identifier for the policy (e.g., "no_memory", "full_memory").
              This name is used for logging, configuration, and result tracking.

    Design Principles:
        1. Retrieval scoring MUST be identical across all policies (except No Memory)
        2. Policy differences reflect storage decisions only (what to keep/prune)
        3. All policies operate on the same MemoryStore interface
        4. Policies are stateless except for configuration parameters
    """

    name: str

    @abstractmethod
    def retrieve(
        self,
        task: Any,
        memory_store: "MemoryStore",
        top_k: int,
        token_budget: int
    ) -> list["MemoryRecord"]:
        """Retrieve relevant memories for the given task.

        CRITICAL: All policies except No Memory MUST use the shared_retrieve()
        function to ensure identical retrieval scoring across conditions.
        This is a frozen invariant (Requirement 6, Design §2.6).

        The shared_retrieve() function implements:
        - Pure cosine similarity scoring (no bonuses or penalties)
        - Filtering by same repository and non-archived status
        - Top-k selection within token budget
        - Ascending sort (best item LAST for Lost-in-the-Middle mitigation)

        Args:
            task: The current task requiring memory retrieval. Contains repo,
                  issue_text, and other task metadata.
            memory_store: The persistent memory storage backend (SQLite + FAISS).
            top_k: Maximum number of memories to retrieve (typically 5).
            token_budget: Maximum total tokens allowed for retrieved memories
                         (typically 2000). Memories are dropped from lowest-scoring
                         if budget is exceeded.

        Returns:
            A list of MemoryRecord objects sorted in ascending order of relevance
            (lowest relevance first, highest relevance last). The list may be
            shorter than top_k if:
            - Fewer than top_k memories exist in the store
            - Token budget constraints require dropping memories
            - The policy is No Memory (returns empty list)

        Raises:
            NotImplementedError: If the subclass does not implement this method.

        Example:
            >>> # For all policies except No Memory:
            >>> from ..retriever import shared_retrieve
            >>> def retrieve(self, task, memory_store, top_k, token_budget):
            ...     return shared_retrieve(task, memory_store, top_k, token_budget)
        """
        pass

    @abstractmethod
    def write(self, memory_store: "MemoryStore", record: "MemoryRecord") -> None:
        """Store a new memory record.

        This method is called after each task completes and the reflection step
        generates a structured memory record. The policy decides whether to
        actually store the record or discard it.

        Typical implementations:
        - No Memory: Discards all records (no-op for API compatibility)
        - Full Memory: Stores all records without limit
        - Pruning policies: Store all records (pruning happens in maintain())

        Args:
            memory_store: The persistent memory storage backend.
            record: The MemoryRecord to store. Contains all task experience:
                    identity, type, outcome, content, embeddings, metadata.

        Raises:
            NotImplementedError: If the subclass does not implement this method.

        Example:
            >>> def write(self, memory_store, record):
            ...     memory_store.add(record)  # Store the record
        """
        pass

    @abstractmethod
    def maintain(self, memory_store: "MemoryStore") -> None:
        """Perform policy-specific maintenance after task completion.

        This method is called after write() to perform pruning, consolidation,
        or other memory management operations. The policy decides which memories
        to keep, archive, or consolidate based on its strategy.

        Typical implementations:
        - No Memory: No-op (nothing to maintain)
        - Full Memory: No-op (never prunes)
        - Random Prune: Randomly archive memories when exceeding max_records
        - Recency Prune: Archive oldest memories by sequence_index
        - Type-Aware Decay: Score memories and archive lowest-scoring
        - CLS Consolidation: Cluster and consolidate old memories every 5 tasks

        Args:
            memory_store: The persistent memory storage backend. Provides methods
                         for querying active records, archiving, and statistics.

        Raises:
            NotImplementedError: If the subclass does not implement this method.

        Example:
            >>> def maintain(self, memory_store):
            ...     # Prune if exceeding capacity
            ...     while memory_store.count_active() > self.max_records:
            ...         victim = select_victim(memory_store.active_records())
            ...         memory_store.archive(victim.memory_id, reason="policy_prune")
        """
        pass
