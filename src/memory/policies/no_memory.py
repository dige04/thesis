"""No Memory policy implementation.

This module implements the baseline No Memory policy that stores nothing
and retrieves nothing. This policy serves as a control condition to measure
the effect of memory versus no memory.

**Validates: Requirements 8**

Design Principle:
The No Memory policy provides a baseline to isolate the effect of persistent
memory on sequential task performance. By storing and retrieving nothing,
we can measure whether memory accumulation (in any form) provides value
compared to solving each task independently.

This is the only policy that does NOT use shared_retrieve(), because it
has no memories to retrieve from.
"""

from typing import TYPE_CHECKING, Any

from .base import MemoryPolicy

if TYPE_CHECKING:
    from ..store import MemoryRecord, MemoryStore


class NoMemoryPolicy(MemoryPolicy):
    """Baseline policy that stores nothing and retrieves nothing.

    This policy serves as a control condition to measure the effect of
    memory versus no memory. It discards all write requests and returns
    empty lists for all retrieval requests.

    **Validates: Requirements 8**

    Acceptance Criteria:
    1. Returns empty list for all retrieval requests
    2. Discards all memory write requests but returns success for API compatibility
    3. Performs no maintenance operations

    Attributes:
        name: Policy identifier "no_memory"

    Example:
        >>> policy = NoMemoryPolicy()
        >>> memories = policy.retrieve(task, store, top_k=5, token_budget=2000)
        >>> assert memories == []
        >>> policy.write(store, record)  # Discards silently
        >>> policy.maintain(store)  # No-op
    """

    name = "no_memory"

    def retrieve(
        self,
        task: Any,
        memory_store: "MemoryStore",
        top_k: int,
        token_budget: int
    ) -> list["MemoryRecord"]:
        """Return empty list for all retrieval requests.

        The No Memory policy has no memories to retrieve, so it always
        returns an empty list. This ensures the agent solves each task
        independently without any memory of past tasks.

        **Validates: Requirements 8.1**

        Args:
            task: The current task (ignored).
            memory_store: The memory storage backend (ignored).
            top_k: Maximum number of memories to retrieve (ignored).
            token_budget: Maximum tokens for retrieved memories (ignored).

        Returns:
            An empty list (no memories retrieved).
        """
        return []

    def write(self, memory_store: "MemoryStore", record: "MemoryRecord") -> None:
        """Discard all memory write requests.

        The No Memory policy does not store any memories. This method
        silently discards all write requests but returns success to
        maintain API compatibility with other policies.

        **Validates: Requirements 8.2**

        Args:
            memory_store: The memory storage backend (ignored).
            record: The memory record to discard (ignored).

        Returns:
            None (success acknowledgment for API compatibility).
        """
        # Discard silently - no storage, no logging
        return

    def maintain(self, memory_store: "MemoryStore") -> None:
        """Perform no maintenance operations.

        The No Memory policy has no memories to maintain, so this method
        is a no-op.

        **Validates: Requirements 8.3**

        Args:
            memory_store: The memory storage backend (ignored).

        Returns:
            None.
        """
        # No-op - nothing to maintain
        return
