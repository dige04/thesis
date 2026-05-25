"""Memory management module for the research system.

This module provides the core memory storage and retrieval infrastructure
for the memory pruning research system. It implements a two-layer storage
architecture combining SQLite for metadata and FAISS for vector embeddings.
"""

from .record import (
    MemoryRecord,
    VALID_MEMORY_TYPES,
    VALID_OUTCOMES,
    validate_orthogonal_axes,
)
from .retriever import (
    shared_retrieve,
    format_memory_for_prompt,
)
from .classifier import (
    MemoryClassifier,
    ClassifierError,
    classify_memory_type,
)
from .reflection import (
    reflect_and_write_memory,
    ReflectionError,
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
