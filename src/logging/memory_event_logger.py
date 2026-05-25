"""
Memory event logger for tracking all memory operations.

This module implements logging for memory write, archive, and consolidate operations
to memory_events.jsonl in JSON Lines format.

Schema (THESIS_FINAL_v5.md §11.2):
{
  "event_id": "evt_00342",
  "step": 17,
  "policy": "cls_consolidation",
  "event_type": "consolidate",
  "memory_id": "MEM-042",
  "replacement_id": "MEM-CONS-007",
  "task_id": "django__django-12345",
  "repo": "django/django",
  "reason": "cls_consolidated",
  "metadata": {"source_count": 4, "summary_tokens": 312},
  "timestamp": "2026-05-17T10:23:01Z"
}

Event types: write, archive, consolidate

Frozen Invariants:
- Atomic appends to JSONL file (one event per line)
- All required fields must be present
- Event IDs are unique and sequential
- Timestamps in ISO 8601 format

Requirements: 18
Design: §11.2 Memory Events Schema
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

# Type alias for event types
EventType = Literal["write", "archive", "consolidate"]


class MemoryEventLogger:
    """
    Logger for memory operations (write, archive, consolidate).

    This class provides atomic append operations to memory_events.jsonl,
    tracking all memory lifecycle events for behavioral analysis.

    Attributes:
        log_file_path: Path to memory_events.jsonl file
        policy_name: Name of the active memory policy
        event_counter: Counter for generating sequential event IDs

    Requirements: 18
    """

    def __init__(self, log_file_path: Path | str, policy_name: str):
        """
        Initialize memory event logger.

        Args:
            log_file_path: Path to memory_events.jsonl file
            policy_name: Name of the active memory policy

        Raises:
            ValueError: If policy_name is empty
        """
        if not policy_name:
            raise ValueError("policy_name cannot be empty")

        self.log_file_path = Path(log_file_path)
        self.policy_name = policy_name
        self.event_counter = 0

        # Ensure parent directory exists
        self.log_file_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize file if it doesn't exist
        if not self.log_file_path.exists():
            self.log_file_path.touch()

    def log_event(
        self,
        event_type: EventType,
        memory_id: str,
        step: int,
        task_id: str,
        repo: str,
        reason: str,
        replacement_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Log a memory event to memory_events.jsonl.

        This method performs an atomic append operation, writing one JSON object
        per line in JSON Lines format.

        Args:
            event_type: Type of event (write, archive, consolidate)
            memory_id: ID of the memory being operated on
            step: Current sequence step (task index)
            task_id: ID of the current task
            repo: Repository name (e.g., "django/django")
            reason: Reason for the event (e.g., "random_prune", "cls_consolidated")
            replacement_id: ID of replacement memory (for consolidation only)
            metadata: Additional event-specific metadata

        Returns:
            Generated event_id

        Raises:
            ValueError: If required fields are missing or invalid

        Example:
            >>> logger = MemoryEventLogger("runs/run_001/memory_events.jsonl", "type_aware_decay")
            >>> logger.log_event(
            ...     event_type="write",
            ...     memory_id="MEM-001",
            ...     step=5,
            ...     task_id="django__django-12345",
            ...     repo="django/django",
            ...     reason="task_completed",
            ...     metadata={"token_length": 1234}
            ... )
            'evt_00001'
        """
        # Validate required fields
        if not event_type:
            raise ValueError("event_type cannot be empty")
        if event_type not in ("write", "archive", "consolidate"):
            raise ValueError(
                f"Invalid event_type '{event_type}'. "
                f"Must be one of: write, archive, consolidate"
            )
        if not memory_id:
            raise ValueError("memory_id cannot be empty")
        if step < 0:
            raise ValueError(f"step must be non-negative, got {step}")
        if not task_id:
            raise ValueError("task_id cannot be empty")
        if not repo:
            raise ValueError("repo cannot be empty")
        if not reason:
            raise ValueError("reason cannot be empty")

        # Validate consolidation-specific requirements
        if event_type == "consolidate" and not replacement_id:
            raise ValueError(
                "replacement_id is required for consolidate events"
            )

        # Generate unique event ID
        self.event_counter += 1
        event_id = f"evt_{self.event_counter:05d}"

        # Build event record
        event = {
            "event_id": event_id,
            "step": step,
            "policy": self.policy_name,
            "event_type": event_type,
            "memory_id": memory_id,
            "replacement_id": replacement_id,
            "task_id": task_id,
            "repo": repo,
            "reason": reason,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        # Atomic append to JSONL file
        self._append_event(event)

        return event_id

    def log_write(
        self,
        memory_id: str,
        step: int,
        task_id: str,
        repo: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Log a memory write event.

        Convenience method for logging write operations.

        Args:
            memory_id: ID of the memory being written
            step: Current sequence step
            task_id: ID of the current task
            repo: Repository name
            metadata: Additional metadata (e.g., token_length, memory_type)

        Returns:
            Generated event_id

        Example:
            >>> logger.log_write(
            ...     memory_id="MEM-001",
            ...     step=5,
            ...     task_id="django__django-12345",
            ...     repo="django/django",
            ...     metadata={"memory_type": "bug_fix", "token_length": 1234}
            ... )
            'evt_00001'
        """
        return self.log_event(
            event_type="write",
            memory_id=memory_id,
            step=step,
            task_id=task_id,
            repo=repo,
            reason="task_completed",
            metadata=metadata,
        )

    def log_archive(
        self,
        memory_id: str,
        step: int,
        task_id: str,
        repo: str,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Log a memory archive event.

        Convenience method for logging archive operations (pruning).

        Args:
            memory_id: ID of the memory being archived
            step: Current sequence step
            task_id: ID of the current task
            repo: Repository name
            reason: Reason for archiving (e.g., "random_prune", "recency_prune",
                   "type_aware_decay", "budget_exceeded")
            metadata: Additional metadata (e.g., importance_score, age)

        Returns:
            Generated event_id

        Example:
            >>> logger.log_archive(
            ...     memory_id="MEM-001",
            ...     step=10,
            ...     task_id="django__django-12346",
            ...     repo="django/django",
            ...     reason="random_prune",
            ...     metadata={"age": 5, "use_count": 2}
            ... )
            'evt_00002'
        """
        return self.log_event(
            event_type="archive",
            memory_id=memory_id,
            step=step,
            task_id=task_id,
            repo=repo,
            reason=reason,
            metadata=metadata,
        )

    def log_consolidate(
        self,
        memory_id: str,
        replacement_id: str,
        step: int,
        task_id: str,
        repo: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Log a memory consolidation event.

        Convenience method for logging consolidation operations where multiple
        memories are replaced by a single consolidated summary.

        Args:
            memory_id: ID of the source memory being consolidated
            replacement_id: ID of the new consolidated memory
            step: Current sequence step
            task_id: ID of the current task
            repo: Repository name
            metadata: Additional metadata (e.g., source_count, summary_tokens,
                     cluster_id)

        Returns:
            Generated event_id

        Example:
            >>> logger.log_consolidate(
            ...     memory_id="MEM-001",
            ...     replacement_id="MEM-CONS-001",
            ...     step=15,
            ...     task_id="django__django-12347",
            ...     repo="django/django",
            ...     metadata={"source_count": 4, "summary_tokens": 312}
            ... )
            'evt_00003'
        """
        return self.log_event(
            event_type="consolidate",
            memory_id=memory_id,
            step=step,
            task_id=task_id,
            repo=repo,
            reason="cls_consolidated",
            replacement_id=replacement_id,
            metadata=metadata,
        )

    def _append_event(self, event: dict[str, Any]) -> None:
        """
        Atomically append event to JSONL file.

        Args:
            event: Event dictionary to append

        Note:
            Uses 'a' mode for atomic append. Each event is written as a single
            line in JSON Lines format.
        """
        with open(self.log_file_path, "a", encoding="utf-8") as f:
            json.dump(event, f, ensure_ascii=False)
            f.write("\n")

    def get_event_count(self) -> int:
        """
        Get the total number of events logged.

        Returns:
            Number of events in the log file

        Example:
            >>> logger.get_event_count()
            42
        """
        if not self.log_file_path.exists():
            return 0

        count = 0
        with open(self.log_file_path, encoding="utf-8") as f:
            for _ in f:
                count += 1
        return count

    def read_events(
        self,
        event_type: EventType | None = None,
        memory_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Read events from the log file with optional filtering.

        Args:
            event_type: Filter by event type (optional)
            memory_id: Filter by memory ID (optional)

        Returns:
            List of event dictionaries matching the filters

        Example:
            >>> logger.read_events(event_type="archive")
            [{'event_id': 'evt_00002', 'event_type': 'archive', ...}]
        """
        if not self.log_file_path.exists():
            return []

        events = []
        with open(self.log_file_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    event = json.loads(line)

                    # Apply filters
                    if event_type and event.get("event_type") != event_type:
                        continue
                    if memory_id and event.get("memory_id") != memory_id:
                        continue

                    events.append(event)

        return events

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"MemoryEventLogger(policy={self.policy_name}, "
            f"log_file={self.log_file_path}, "
            f"events={self.event_counter})"
        )
