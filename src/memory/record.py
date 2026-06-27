"""
MemoryRecord dataclass for the memory pruning research system.

This module defines the core MemoryRecord structure that captures task experience
with orthogonal type and outcome dimensions for analysis.

Frozen Invariants:
- memory_type and outcome are orthogonal axes (NOT collapsed)
- 5 content types: architectural, api_change, bug_fix, test_update, config
- outcome: pass, fail, partial, unknown
- embedding_text = [Issue + Final Error + Final Diff] only, < 7500 tokens
"""

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

# Frozen type taxonomy (Requirement 5, Design §2)
VALID_MEMORY_TYPES = frozenset([
    "architectural",
    "api_change",
    "bug_fix",
    "test_update",
    "config"
])

# Outcome taxonomy (Requirement 3)
VALID_OUTCOMES = frozenset([
    "pass",
    "fail",
    "partial",
    "unknown"
])


@dataclass
class MemoryRecord:
    """
    Structured representation of task experience stored in memory.

    This dataclass captures all aspects of a task execution including:
    - Identity and provenance
    - Orthogonal type/outcome classification
    - Content for embedding and retrieval
    - Structural metadata
    - Usage tracking over time
    - Lifecycle management

    Requirements: 3, 5
    Design: §2 Components and Interfaces
    """

    # ========== Identity Fields ==========
    memory_id: str
    task_id: str
    repo: str
    sequence_index: int

    # ========== Type & Outcome (Orthogonal Axes) ==========
    # CRITICAL: These are independent dimensions
    # memory_type = content classification (what kind of change)
    # outcome = execution result (did it work)
    memory_type: str  # one of 5 content types
    outcome: str      # pass | fail | partial | unknown

    # ========== Content Fields (Preprocessed for Embedding) ==========
    issue_summary: str
    patch_summary: str
    failure_summary: str | None = None
    test_summary: str | None = None

    # ========== Structural Metadata ==========
    files_touched: list[str] = field(default_factory=list)
    functions_touched: list[str] = field(default_factory=list)
    commands_run: list[str] = field(default_factory=list)

    # ========== Retrieval Provenance ==========
    # Which memories were shown to the agent during this task
    retrieved_memory_ids_used: list[str] = field(default_factory=list)

    # ========== Embedding Fields ==========
    # embedding_text = [Issue + Final Error + Final Diff] only
    # MUST be < 7500 tokens (Requirement 4)
    embedding_text: str = ""
    embedding_vector_id: str = ""  # FAISS index pointer

    # ========== Size & Raw Trace ==========
    token_length: int = 0
    raw_trace_ref: str | None = None  # path to full trajectory JSON

    # ========== Usage Tracking (Updated Over Time) ==========
    use_count: int = 0  # = retrieval_count
    last_retrieved_at_step: int | None = None
    success_after_retrieval_count: int = 0  # ASSOCIATED, not causal
    failure_after_retrieval_count: int = 0  # ASSOCIATED, not causal

    # ========== Scoring / Lifecycle ==========
    importance_score: float = 0.0  # set by Type-Aware Decay
    is_consolidated: bool = False
    source_memory_ids: list[str] | None = None  # for consolidated summaries
    is_archived: bool = False
    archived_reason: str | None = None
    archived_at_step: int | None = None

    # ========== Timestamps ==========
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def __post_init__(self) -> None:
        """
        Validate orthogonal type/outcome axes after initialization.

        Validates:
        - memory_type is one of 5 valid content types
        - outcome is one of 4 valid outcomes
        - type and outcome are independent (orthogonal)

        Raises:
            ValueError: If validation fails
        """
        # Validate memory_type
        if self.memory_type not in VALID_MEMORY_TYPES:
            raise ValueError(
                f"Invalid memory_type '{self.memory_type}'. "
                f"Must be one of: {sorted(VALID_MEMORY_TYPES)}"
            )

        # Validate outcome
        if self.outcome not in VALID_OUTCOMES:
            raise ValueError(
                f"Invalid outcome '{self.outcome}'. "
                f"Must be one of: {sorted(VALID_OUTCOMES)}"
            )

        # Validate sequence_index is non-negative
        if self.sequence_index < 0:
            raise ValueError(
                f"sequence_index must be non-negative, got {self.sequence_index}"
            )

        # Validate usage tracking fields are non-negative
        if self.use_count < 0:
            raise ValueError(f"use_count must be non-negative, got {self.use_count}")
        if self.success_after_retrieval_count < 0:
            raise ValueError(
                f"success_after_retrieval_count must be non-negative, "
                f"got {self.success_after_retrieval_count}"
            )
        if self.failure_after_retrieval_count < 0:
            raise ValueError(
                f"failure_after_retrieval_count must be non-negative, "
                f"got {self.failure_after_retrieval_count}"
            )

        # Validate token_length is non-negative
        if self.token_length < 0:
            raise ValueError(
                f"token_length must be non-negative, got {self.token_length}"
            )

    @staticmethod
    def generate_id() -> str:
        """Generate a unique memory ID."""
        return f"MEM-{uuid.uuid4().hex[:8].upper()}"

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize MemoryRecord to dictionary.

        Returns:
            Dictionary representation with all fields
        """
        return asdict(self)

    def to_json(self) -> str:
        """
        Serialize MemoryRecord to JSON string.

        Returns:
            JSON string representation
        """
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryRecord":
        """
        Deserialize MemoryRecord from dictionary.

        Args:
            data: Dictionary containing MemoryRecord fields

        Returns:
            MemoryRecord instance

        Raises:
            ValueError: If required fields are missing or invalid
        """
        # Handle None values for optional list fields
        if data.get("source_memory_ids") is None:
            data["source_memory_ids"] = None

        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> "MemoryRecord":
        """
        Deserialize MemoryRecord from JSON string.

        Args:
            json_str: JSON string containing MemoryRecord data

        Returns:
            MemoryRecord instance

        Raises:
            ValueError: If JSON is invalid or required fields are missing
        """
        data = json.loads(json_str)
        return cls.from_dict(data)

    def update_usage(
        self,
        step: int,
        task_succeeded: bool | None = None
    ) -> None:
        """
        Update usage tracking when memory is retrieved.

        Args:
            step: Current sequence step where retrieval occurred
            task_succeeded: Whether the task succeeded after using this memory
                          (None if outcome not yet known)
        """
        self.use_count += 1
        self.last_retrieved_at_step = step
        self.updated_at = datetime.utcnow().isoformat()

        if task_succeeded is True:
            self.success_after_retrieval_count += 1
        elif task_succeeded is False:
            self.failure_after_retrieval_count += 1

    def archive(
        self,
        reason: str,
        step: int
    ) -> None:
        """
        Archive this memory record.

        Args:
            reason: Reason for archiving (e.g., "random_prune", "recency_prune")
            step: Sequence step where archiving occurred
        """
        self.is_archived = True
        self.archived_reason = reason
        self.archived_at_step = step
        self.updated_at = datetime.utcnow().isoformat()

    def set_importance_score(self, score: float) -> None:
        """
        Set importance score (used by Type-Aware Decay policy).

        Args:
            score: Computed importance score
        """
        self.importance_score = score
        self.updated_at = datetime.utcnow().isoformat()

    def mark_consolidated(
        self,
        source_ids: list[str]
    ) -> None:
        """
        Mark this record as a consolidated summary.

        Args:
            source_ids: List of memory_ids that were consolidated into this record
        """
        self.is_consolidated = True
        self.source_memory_ids = source_ids
        self.updated_at = datetime.utcnow().isoformat()

    def __repr__(self) -> str:
        """Concise string representation for debugging."""
        return (
            f"MemoryRecord(id={self.memory_id}, "
            f"task={self.task_id}, "
            f"type={self.memory_type}, "
            f"outcome={self.outcome}, "
            f"seq_idx={self.sequence_index}, "
            f"archived={self.is_archived})"
        )


def validate_orthogonal_axes(memory_type: str, outcome: str) -> None:
    """
    Validate that memory_type and outcome are valid and orthogonal.

    This is a standalone validation function that can be used before
    creating a MemoryRecord instance.

    Args:
        memory_type: Content type classification
        outcome: Execution outcome

    Raises:
        ValueError: If either axis is invalid

    Example:
        >>> validate_orthogonal_axes("bug_fix", "pass")  # OK
        >>> validate_orthogonal_axes("bug_fix", "fail")  # OK - orthogonal!
        >>> validate_orthogonal_axes("invalid", "pass")  # ValueError
    """
    if memory_type not in VALID_MEMORY_TYPES:
        raise ValueError(
            f"Invalid memory_type '{memory_type}'. "
            f"Must be one of: {sorted(VALID_MEMORY_TYPES)}"
        )

    if outcome not in VALID_OUTCOMES:
        raise ValueError(
            f"Invalid outcome '{outcome}'. "
            f"Must be one of: {sorted(VALID_OUTCOMES)}"
        )
