"""Memory management module for the research system.

This module provides the core memory storage and retrieval infrastructure
for the memory pruning research system. It implements a two-layer storage
architecture combining SQLite for metadata and FAISS for vector embeddings.
"""

from .classifier import (
    ClassifierError,
    MemoryClassifier,
    classify_memory_type,
)
from .record import (
    VALID_MEMORY_TYPES,
    VALID_OUTCOMES,
    MemoryRecord,
    validate_orthogonal_axes,
)
from .reflection import (
    ReflectionError,
    reflect_and_write_memory,
)
from .retriever import (
    format_memory_for_prompt,
    shared_retrieve,
)

__all__ = [
    "MemoryRecord",
    "VALID_MEMORY_TYPES",
    "VALID_OUTCOMES",
    "validate_orthogonal_axes",
    "shared_retrieve",
    "format_memory_for_prompt",
    "MemoryClassifier",
    "ClassifierError",
    "classify_memory_type",
    "reflect_and_write_memory",
    "ReflectionError",
]
