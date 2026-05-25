"""MemoryStore: Two-layer persistent storage for memory records.

This module implements the core memory storage interface using:
- SQLite: Metadata storage (memory records, usage tracking, lifecycle)
- FAISS: Vector embeddings for semantic similarity search

The MemoryStore maintains separation between archived and active records,
tracks usage statistics, and enforces embedding size constraints to prevent
silent truncation by the 8K token embedding model limit.

Frozen Invariants (THESIS_FINAL_v5.md §0.1):
- Embedding payload < 7500 tokens (Invariant #4)
- Pure cosine similarity retrieval (Invariant #5)
- Same-repo retrieval in main experiment (Invariant #16)
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

import faiss
import numpy as np
from openai import OpenAI

from .embedding_utils import (
    construct_embedding_text,
    verify_embedding_size,
)
from .record import MemoryRecord
from src.errors import EmbeddingSizeError, MemoryBudgetError, handle_memory_budget_violation

logger = logging.getLogger(__name__)


class MemoryStore:
    """Two-layer storage backend for memory records.

    Architecture:
        - SQLite: Stores MemoryRecord metadata, supports filtering and updates
        - FAISS: Stores embedding vectors, supports cosine similarity search

    The store maintains:
        - Active records: Available for retrieval (is_archived=False)
        - Archived records: Excluded from retrieval (is_archived=True)
        - Usage tracking: use_count, last_retrieved_at_step, success/failure counts
        - Snapshots: Before/after memory state at task boundaries

    Attributes:
        run_id: Unique identifier for the experimental run
        policy_name: Name of the memory policy (one of 6)
        db_path: Path to SQLite database file
        conn: SQLite connection
        faiss_index: FAISS index for vector similarity search
        faiss_path: Path to FAISS index file
        embedding_dim: Dimension of embedding vectors
        snapshot_dir: Directory for memory snapshots
        tokenizer: Tokenizer for counting tokens
        openai_client: OpenAI client for generating embeddings
        embedding_model: Name of the embedding model
    """

    def __init__(
        self,
        run_id: str,
        policy_name: str,
        embedding_dim: int = 1536,  # text-embedding-3-small dimension
        embedding_model: str = "text-embedding-3-small"
    ):
        """Initialize SQLite + FAISS storage for a run.

        Args:
            run_id: Unique identifier for this experimental run
            policy_name: Name of the memory policy being used
            embedding_dim: Dimension of embedding vectors (default: 1536 for text-embedding-3-small)
            embedding_model: Name of the OpenAI embedding model to use

        Notes:
            - Creates SQLite database at runs/{run_id}/memory.db
            - Creates FAISS index at runs/{run_id}/memory.faiss
            - Initializes snapshot directory at runs/{run_id}/memory/snapshots/
        """
        self.run_id = run_id
        self.policy_name = policy_name
        self.embedding_dim = embedding_dim
        self.embedding_model = embedding_model

        # Setup directory structure
        self.run_dir = Path("runs") / run_id
        self.memory_dir = self.run_dir / "memory"
        self.snapshot_dir = self.memory_dir / "snapshots"

        # Create directories
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

        # Initialize SQLite database
        self.db_path = self.memory_dir / "memory.db"
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name

        # Initialize FAISS index
        self.faiss_path = self.memory_dir / "memory.faiss"
        self._init_faiss_index()

        # Initialize OpenAI client for embeddings
        self.openai_client = OpenAI()

        # Create schema
        self._create_schema()

        # Track vector ID to memory ID mapping
        self.vector_id_to_memory_id: dict[int, str] = {}
        self._load_vector_mapping()

    def _init_faiss_index(self) -> None:
        """Initialize or load FAISS index.

        Creates a new FAISS IndexFlatIP (Inner Product) index for cosine similarity.
        L2-normalized vectors in IndexFlatIP give cosine similarity scores.

        If index file exists, loads it. Otherwise creates a new empty index.
        """
        if self.faiss_path.exists():
            # Load existing index
            self.faiss_index = faiss.read_index(str(self.faiss_path))
        else:
            # Create new index with L2 normalization for cosine similarity
            # IndexFlatIP with L2-normalized vectors = cosine similarity
            self.faiss_index = faiss.IndexFlatIP(self.embedding_dim)

    def _save_faiss_index(self) -> None:
        """Save FAISS index to disk."""
        faiss.write_index(self.faiss_index, str(self.faiss_path))

    def _load_vector_mapping(self) -> None:
        """Load vector ID to memory ID mapping from SQLite."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT embedding_vector_id, memory_id
            FROM memory_records
            WHERE embedding_vector_id != ''
        """)

        for row in cursor.fetchall():
            try:
                vector_id = int(row[0])
                self.vector_id_to_memory_id[vector_id] = row[1]
            except (ValueError, TypeError):
                # Skip invalid vector IDs
                pass

    def _create_schema(self) -> None:
        """Create SQLite schema for memory records.

        Schema includes all fields from MemoryRecord with proper types and indexes.
        """
        cursor = self.conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory_records (
                -- Identity fields
                memory_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                repo TEXT NOT NULL,
                sequence_index INTEGER NOT NULL,

                -- Type & outcome (orthogonal axes)
                memory_type TEXT NOT NULL,
                outcome TEXT NOT NULL,

                -- Content fields
                issue_summary TEXT NOT NULL,
                patch_summary TEXT NOT NULL,
                failure_summary TEXT,
                test_summary TEXT,

                -- Structural metadata (stored as JSON)
                files_touched TEXT NOT NULL,
                functions_touched TEXT NOT NULL,
                commands_run TEXT NOT NULL,

                -- Retrieval provenance (stored as JSON)
                retrieved_memory_ids_used TEXT NOT NULL,

                -- Embedding fields
                embedding_text TEXT NOT NULL,
                embedding_vector_id TEXT NOT NULL,

                -- Size & raw trace
                token_length INTEGER NOT NULL,
                raw_trace_ref TEXT,

                -- Usage tracking (updated over time)
                use_count INTEGER NOT NULL DEFAULT 0,
                last_retrieved_at_step INTEGER,
                success_after_retrieval_count INTEGER NOT NULL DEFAULT 0,
                failure_after_retrieval_count INTEGER NOT NULL DEFAULT 0,

                -- Scoring / lifecycle
                importance_score REAL NOT NULL DEFAULT 0.0,
                is_consolidated INTEGER NOT NULL DEFAULT 0,
                source_memory_ids TEXT,
                is_archived INTEGER NOT NULL DEFAULT 0,
                archived_reason TEXT,
                archived_at_step INTEGER,

                -- Timestamps
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Create indexes for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_repo_archived
            ON memory_records(repo, is_archived)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_archived
            ON memory_records(is_archived)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sequence_index
            ON memory_records(sequence_index)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_type
            ON memory_records(memory_type)
        """)

        self.conn.commit()

    def _generate_embedding(self, text: str) -> np.ndarray:
        """Generate embedding vector for text using OpenAI API.

        Args:
            text: Text to embed

        Returns:
            L2-normalized embedding vector as numpy array

        Notes:
            - Uses OpenAI text-embedding-3-small model
            - Returns L2-normalized vectors for cosine similarity
        """
        response = self.openai_client.embeddings.create(
            model=self.embedding_model,
            input=text
        )

        # Extract embedding vector
        embedding = np.array(response.data[0].embedding, dtype=np.float32)

        # L2 normalize for cosine similarity
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return embedding

    def add(self, record: MemoryRecord) -> None:
        """Add a new memory record to the store.

        This method:
        1. Verifies embedding_text < 7500 tokens (Frozen Invariant #4)
        2. Generates embedding vector from embedding_text
        3. Stores vector in FAISS and gets vector_id
        4. Stores complete record in SQLite with vector_id reference

        Args:
            record: MemoryRecord instance to store

        Raises:
            AssertionError: If embedding_text exceeds 7500 tokens

        Notes:
            - Embedding payload = [Issue + Final Error + Final Diff] only
            - No metadata (type, outcome, files) included in embedding
            - Truncates patch_summary from end if needed to fit 7500 limit
            - If embedding_text is not set, constructs it automatically
        """
        # Construct embedding text if not already set
        if not record.embedding_text:
            embedding_text, token_count, was_truncated = construct_embedding_text(
                issue_summary=record.issue_summary,
                failure_summary=record.failure_summary,
                patch_summary=record.patch_summary
            )
            record.embedding_text = embedding_text
            record.token_length = token_count

            if was_truncated:
                logger.info(
                    f"Truncated embedding for {record.memory_id}: "
                    f"final_tokens={token_count}"
                )

        # Verify embedding size (Frozen Invariant #4)
        self._verify_embedding_size(record.embedding_text)

        # Generate embedding vector
        embedding_vector = self._generate_embedding(record.embedding_text)

        # Add vector to FAISS and get vector ID
        # Vector ID is the current index size (0-indexed)
        vector_id = self.faiss_index.ntotal
        self.faiss_index.add(embedding_vector.reshape(1, -1))

        # Update record with vector ID
        record.embedding_vector_id = str(vector_id)

        # Store mapping
        self.vector_id_to_memory_id[vector_id] = record.memory_id

        # Save FAISS index to disk
        self._save_faiss_index()

        # Insert record into SQLite
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO memory_records (
                memory_id, task_id, repo, sequence_index,
                memory_type, outcome,
                issue_summary, patch_summary, failure_summary, test_summary,
                files_touched, functions_touched, commands_run,
                retrieved_memory_ids_used,
                embedding_text, embedding_vector_id,
                token_length, raw_trace_ref,
                use_count, last_retrieved_at_step,
                success_after_retrieval_count, failure_after_retrieval_count,
                importance_score, is_consolidated, source_memory_ids,
                is_archived, archived_reason, archived_at_step,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record.memory_id, record.task_id, record.repo, record.sequence_index,
            record.memory_type, record.outcome,
            record.issue_summary, record.patch_summary, record.failure_summary, record.test_summary,
            json.dumps(record.files_touched), json.dumps(record.functions_touched), json.dumps(record.commands_run),
            json.dumps(record.retrieved_memory_ids_used),
            record.embedding_text, record.embedding_vector_id,
            record.token_length, record.raw_trace_ref,
            record.use_count, record.last_retrieved_at_step,
            record.success_after_retrieval_count, record.failure_after_retrieval_count,
            record.importance_score, int(record.is_consolidated),
            json.dumps(record.source_memory_ids) if record.source_memory_ids else None,
            int(record.is_archived), record.archived_reason, record.archived_at_step,
            record.created_at, record.updated_at
        ))

        self.conn.commit()

    def _row_to_record(self, row: sqlite3.Row) -> MemoryRecord:
        """Convert SQLite row to MemoryRecord instance.

        Args:
            row: SQLite row object

        Returns:
            MemoryRecord instance
        """
        return MemoryRecord(
            memory_id=row["memory_id"],
            task_id=row["task_id"],
            repo=row["repo"],
            sequence_index=row["sequence_index"],
            memory_type=row["memory_type"],
            outcome=row["outcome"],
            issue_summary=row["issue_summary"],
            patch_summary=row["patch_summary"],
            failure_summary=row["failure_summary"],
            test_summary=row["test_summary"],
            files_touched=json.loads(row["files_touched"]),
            functions_touched=json.loads(row["functions_touched"]),
            commands_run=json.loads(row["commands_run"]),
            retrieved_memory_ids_used=json.loads(row["retrieved_memory_ids_used"]),
            embedding_text=row["embedding_text"],
            embedding_vector_id=row["embedding_vector_id"],
            token_length=row["token_length"],
            raw_trace_ref=row["raw_trace_ref"],
            use_count=row["use_count"],
            last_retrieved_at_step=row["last_retrieved_at_step"],
            success_after_retrieval_count=row["success_after_retrieval_count"],
            failure_after_retrieval_count=row["failure_after_retrieval_count"],
            importance_score=row["importance_score"],
            is_consolidated=bool(row["is_consolidated"]),
            source_memory_ids=json.loads(row["source_memory_ids"]) if row["source_memory_ids"] else None,
            is_archived=bool(row["is_archived"]),
            archived_reason=row["archived_reason"],
            archived_at_step=row["archived_at_step"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )

    def filter(self, repo: str, is_archived: bool) -> list[MemoryRecord]:
        """Filter memories by repository and archived status.

        Args:
            repo: Repository name (e.g., "django/django")
            is_archived: Whether to include archived records

        Returns:
            List of MemoryRecord instances matching the filter criteria

        Notes:
            - Used by retrieval to get candidate memories
            - Active records have is_archived=False
            - Archived records are excluded from retrieval
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM memory_records
            WHERE repo = ? AND is_archived = ?
        """, (repo, int(is_archived)))

        return [self._row_to_record(row) for row in cursor.fetchall()]

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int,
        repo: str | None = None,
        same_repo_only: bool = True
    ) -> list[tuple[float, MemoryRecord]]:
        """Cosine similarity search in FAISS.

        This method implements pure cosine similarity scoring with NO bonuses
        or penalties based on memory_type, outcome, age, or retrieval_count.
        (Frozen Invariant #5)

        Args:
            query_vector: Embedding vector for the query (should be L2-normalized)
            top_k: Maximum number of results to return
            repo: Repository to filter by (if same_repo_only=True)
            same_repo_only: Whether to restrict to same repository

        Returns:
            List of (similarity_score, MemoryRecord) tuples, sorted by score descending

        Notes:
            - Filters candidates by repo and is_archived=False before scoring
            - Uses pure cosine similarity (no adjustments)
            - Returns top-k highest-scoring memories
            - Used by shared_retrieve function (identical across all 6 policies)
        """
        # Get candidate records from SQLite (filter by repo and archived status)
        if same_repo_only and repo:
            candidates = self.filter(repo=repo, is_archived=False)
        else:
            candidates = self.active_records()

        if not candidates:
            return []

        # Get vector IDs for candidates
        candidate_vector_ids = []
        candidate_records = []

        for record in candidates:
            try:
                vector_id = int(record.embedding_vector_id)
                candidate_vector_ids.append(vector_id)
                candidate_records.append(record)
            except (ValueError, TypeError):
                # Skip records with invalid vector IDs
                continue

        if not candidate_vector_ids:
            return []

        # Ensure query vector is L2-normalized
        query_norm = np.linalg.norm(query_vector)
        if query_norm > 0:
            query_vector = query_vector / query_norm

        # Perform FAISS search on all vectors (we'll filter results)
        # Search for more than top_k to account for filtering
        search_k = min(self.faiss_index.ntotal, max(top_k * 2, 100))
        similarities, indices = self.faiss_index.search(
            query_vector.reshape(1, -1).astype(np.float32),
            search_k
        )

        # Filter results to only include candidate vector IDs
        candidate_set = set(candidate_vector_ids)
        results = []

        for sim, idx in zip(similarities[0], indices[0], strict=False):
            if idx in candidate_set:
                # Find the corresponding record
                for record in candidate_records:
                    if int(record.embedding_vector_id) == idx:
                        results.append((float(sim), record))
                        break

                if len(results) >= top_k:
                    break

        # Sort by similarity descending (highest first)
        results.sort(key=lambda x: x[0], reverse=True)

        return results[:top_k]

    def archive(
        self,
        memory_id: str,
        reason: str,
        replacement_id: str | None = None,
        current_step: int | None = None
    ) -> None:
        """Archive a memory record.

        Archiving removes a memory from active retrieval while preserving
        it for post-hoc analysis. Archived records have is_archived=True
        and are excluded from filter() and search() results.

        Args:
            memory_id: UUID of the memory to archive
            reason: Reason for archiving (e.g., "random_prune", "type_aware_decay")
            replacement_id: Optional UUID of consolidated memory that replaces this one
            current_step: Current sequence step (for logging)

        Notes:
            - Updates SQLite: is_archived=True, archived_reason, archived_at_step
            - Logs memory event to memory_events.jsonl
            - Does NOT delete from FAISS (preserves for analysis)
            - Used by all pruning policies (Random, Recency, Type-Aware Decay)
            - Used by CLS Consolidation when source memories are consolidated
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE memory_records
            SET is_archived = 1,
                archived_reason = ?,
                archived_at_step = ?,
                updated_at = ?
            WHERE memory_id = ?
        """, (reason, current_step, datetime.utcnow().isoformat(), memory_id))

        self.conn.commit()

        # TODO: Log memory event to memory_events.jsonl
        # This will be implemented when the logging system is in place

    def active_records(self) -> list[MemoryRecord]:
        """Return all non-archived records.

        Returns:
            List of all MemoryRecord instances with is_archived=False

        Notes:
            - Used by policies during maintenance to get pruning candidates
            - Used by snapshot generation
            - Excludes archived records
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM memory_records
            WHERE is_archived = 0
        """)

        return [self._row_to_record(row) for row in cursor.fetchall()]

    def count_active(self) -> int:
        """Count non-archived records.

        Returns:
            Number of active (non-archived) memory records

        Notes:
            - Used by policies to check if pruning is needed
            - Compared against max_records threshold
            - Fast query (no need to load full records)
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM memory_records
            WHERE is_archived = 0
        """)

        return cursor.fetchone()[0]

    def snapshot(self, step: int, boundary: str) -> dict:
        """Generate memory snapshot for logging.

        Snapshots capture the complete memory state at task boundaries
        (before_task_n, after_task_n) for post-hoc analysis.

        Args:
            step: Current task sequence_index
            boundary: Boundary type ("before_task" or "after_task")

        Returns:
            Dictionary containing:
                - step: Task sequence_index
                - boundary: Boundary type
                - active_records: List of {memory_id, importance_score, memory_type}
                - archived_this_step: List of memory_ids archived at this step
                - metadata: policy_name, timestamp

        Notes:
            - Saved to runs/{run_id}/memory/snapshots/{boundary}_{step}.json
            - Enables post-hoc analysis without re-running experiments
            - Includes importance_score for Type-Aware Decay analysis
        """
        # Get all active records
        active = self.active_records()

        # Get records archived at this step
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT memory_id FROM memory_records
            WHERE is_archived = 1 AND archived_at_step = ?
        """, (step,))
        archived_this_step = [row[0] for row in cursor.fetchall()]

        # Build snapshot dictionary
        snapshot_data = {
            "step": step,
            "boundary": boundary,
            "active_records": [
                {
                    "memory_id": record.memory_id,
                    "importance_score": record.importance_score,
                    "memory_type": record.memory_type
                }
                for record in active
            ],
            "archived_this_step": archived_this_step,
            "metadata": {
                "policy_name": self.policy_name,
                "timestamp": datetime.utcnow().isoformat()
            }
        }

        # Write to snapshot file
        snapshot_file = self.snapshot_dir / f"{boundary}_{step}.json"
        with open(snapshot_file, "w") as f:
            json.dump(snapshot_data, f, indent=2)

        return snapshot_data

    def stats(self) -> dict:
        """Return memory store statistics.

        Returns:
            Dictionary containing:
                - active_count: Number of non-archived records
                - archived_count: Number of archived records
                - total_tokens: Sum of token_length for active records
                - total_records: Total number of records (active + archived)

        Notes:
            - Used for logging and monitoring
            - Logged in task_results.jsonl as memory_count_before/after
            - total_tokens compared against max_storage_tokens limit
        """
        cursor = self.conn.cursor()

        # Get active count
        cursor.execute("SELECT COUNT(*) FROM memory_records WHERE is_archived = 0")
        active_count = cursor.fetchone()[0]

        # Get archived count
        cursor.execute("SELECT COUNT(*) FROM memory_records WHERE is_archived = 1")
        archived_count = cursor.fetchone()[0]

        # Get total tokens for active records
        cursor.execute("SELECT SUM(token_length) FROM memory_records WHERE is_archived = 0")
        total_tokens = cursor.fetchone()[0] or 0

        return {
            "active_count": active_count,
            "archived_count": archived_count,
            "total_tokens": total_tokens,
            "total_records": active_count + archived_count
        }

    def update_usage(
        self,
        memory_id: str,
        step: int,
        task_succeeded: bool | None = None
    ) -> None:
        """Update usage tracking when memory is retrieved.

        Args:
            memory_id: UUID of the memory that was retrieved
            step: Current sequence step where retrieval occurred
            task_succeeded: Whether the task succeeded after using this memory
                          (None if outcome not yet known)

        Notes:
            - Increments use_count
            - Updates last_retrieved_at_step
            - Updates success_after_retrieval_count or failure_after_retrieval_count
            - These counts are ASSOCIATED with outcomes, not causal
        """
        cursor = self.conn.cursor()

        # Build update query based on task outcome
        if task_succeeded is True:
            cursor.execute("""
                UPDATE memory_records
                SET use_count = use_count + 1,
                    last_retrieved_at_step = ?,
                    success_after_retrieval_count = success_after_retrieval_count + 1,
                    updated_at = ?
                WHERE memory_id = ?
            """, (step, datetime.utcnow().isoformat(), memory_id))
        elif task_succeeded is False:
            cursor.execute("""
                UPDATE memory_records
                SET use_count = use_count + 1,
                    last_retrieved_at_step = ?,
                    failure_after_retrieval_count = failure_after_retrieval_count + 1,
                    updated_at = ?
                WHERE memory_id = ?
            """, (step, datetime.utcnow().isoformat(), memory_id))
        else:
            # Outcome not yet known, just update use_count and last_retrieved_at_step
            cursor.execute("""
                UPDATE memory_records
                SET use_count = use_count + 1,
                    last_retrieved_at_step = ?,
                    updated_at = ?
                WHERE memory_id = ?
            """, (step, datetime.utcnow().isoformat(), memory_id))

        self.conn.commit()

    def update_importance_score(self, memory_id: str, score: float) -> None:
        """Update importance score for a memory record.

        Args:
            memory_id: UUID of the memory to update
            score: New importance score

        Notes:
            - Used by Type-Aware Decay policy to set computed scores
            - Score is used for pruning decisions
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE memory_records
            SET importance_score = ?,
                updated_at = ?
            WHERE memory_id = ?
        """, (score, datetime.utcnow().isoformat(), memory_id))

        self.conn.commit()

    def _verify_embedding_size(self, text: str) -> None:
        """Verify embedding text is under 7500 token limit.

        This enforces Frozen Invariant #4: embedding payload < 7500 tokens
        to prevent silent truncation by the 8K token embedding model.

        Args:
            text: Embedding text to verify

        Raises:
            AssertionError: If text exceeds 7500 tokens

        Notes:
            - Called by add() before generating embeddings
            - Caller should use construct_embedding_text() to ensure compliance
            - 7500 token limit provides 500 token safety margin below 8K model cap
        """
        verify_embedding_size(text)

    def close(self) -> None:
        """Close database connections and save FAISS index."""
        self.conn.close()
        self._save_faiss_index()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
