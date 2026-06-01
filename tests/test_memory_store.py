"""
Unit tests for MemoryStore SQLite metadata storage.

Tests cover:
- Schema creation and initialization
- Adding memory records with usage tracking
- Filtering by repository and archived status
- Archiving memories
- Snapshot generation
- Usage tracking updates
- Statistics computation

Frozen Invariants Tested:
- Embedding payload < 7500 tokens (Invariant #4)
- Same-repo filtering (Invariant #16)
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.memory.record import MemoryRecord
from src.memory.store import MemoryStore


@pytest.fixture
def temp_run_dir():
    """Create a temporary directory for test runs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Change to temp directory for test
        original_cwd = Path.cwd()
        temp_path = Path(tmpdir)
        
        # Create runs directory in temp location
        runs_dir = temp_path / "runs"
        runs_dir.mkdir(exist_ok=True)
        
        yield temp_path
        
        # Cleanup is automatic with TemporaryDirectory


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for embedding generation."""
    with patch('src.memory.store.OpenAI') as mock_openai:
        # Create mock response
        mock_response = MagicMock()
        mock_response.data = [MagicMock()]
        mock_response.data[0].embedding = np.random.rand(1536).tolist()
        
        # Setup mock client
        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        yield mock_client


@pytest.fixture
def memory_store(temp_run_dir, mock_openai_client, monkeypatch):
    """Create a MemoryStore instance for testing."""
    # Change working directory to temp directory
    monkeypatch.chdir(temp_run_dir)
    
    store = MemoryStore(
        run_id="test_run_001",
        policy_name="test_policy"
    )
    
    yield store
    
    # Cleanup
    store.close()


@pytest.fixture
def sample_record():
    """Create a sample MemoryRecord for testing."""
    return MemoryRecord(
        memory_id=MemoryRecord.generate_id(),
        task_id="test_task_001",
        repo="test/repo",
        sequence_index=0,
        memory_type="bug_fix",
        outcome="pass",
        issue_summary="Fix null pointer exception in user service",
        patch_summary="Added null check before accessing user object",
        failure_summary=None,
        test_summary="All tests pass",
        files_touched=["src/user_service.py"],
        functions_touched=["get_user", "validate_user"],
        commands_run=["pytest tests/test_user_service.py"],
        retrieved_memory_ids_used=[],
        embedding_text="Issue: Fix null pointer exception\nPatch: Added null check",
        token_length=50
    )


class TestMemoryStoreInitialization:
    """Test MemoryStore initialization and schema creation."""
    
    def test_creates_directory_structure(self, temp_run_dir, mock_openai_client, monkeypatch):
        """Test that MemoryStore creates required directories."""
        monkeypatch.chdir(temp_run_dir)
        
        store = MemoryStore(run_id="test_run_001", policy_name="test_policy")
        
        assert (temp_run_dir / "runs" / "test_run_001" / "memory").exists()
        assert (temp_run_dir / "runs" / "test_run_001" / "memory" / "snapshots").exists()
        
        store.close()
    
    def test_creates_sqlite_database(self, temp_run_dir, mock_openai_client, monkeypatch):
        """Test that SQLite database is created."""
        monkeypatch.chdir(temp_run_dir)
        
        store = MemoryStore(run_id="test_run_001", policy_name="test_policy")
        
        db_path = temp_run_dir / "runs" / "test_run_001" / "memory" / "memory.db"
        assert db_path.exists()
        
        store.close()
    
    def test_creates_faiss_index(self, temp_run_dir, mock_openai_client, monkeypatch):
        """Test that FAISS index is initialized."""
        monkeypatch.chdir(temp_run_dir)
        
        store = MemoryStore(run_id="test_run_001", policy_name="test_policy")
        
        assert store.faiss_index is not None
        assert store.faiss_index.d == 1536  # Embedding dimension
        
        store.close()
    
    def test_schema_has_all_required_fields(self, memory_store):
        """Test that SQLite schema includes all MemoryRecord fields."""
        cursor = memory_store.conn.cursor()
        cursor.execute("PRAGMA table_info(memory_records)")
        columns = {row[1] for row in cursor.fetchall()}
        
        required_fields = {
            "memory_id", "task_id", "repo", "sequence_index",
            "memory_type", "outcome",
            "issue_summary", "patch_summary", "failure_summary", "test_summary",
            "files_touched", "functions_touched", "commands_run",
            "retrieved_memory_ids_used",
            "embedding_text", "embedding_vector_id",
            "token_length", "raw_trace_ref",
            "use_count", "last_retrieved_at_step",
            "success_after_retrieval_count", "failure_after_retrieval_count",
            "importance_score", "is_consolidated", "source_memory_ids",
            "is_archived", "archived_reason", "archived_at_step",
            "created_at", "updated_at"
        }
        
        assert required_fields.issubset(columns)
    
    def test_creates_required_indexes(self, memory_store):
        """Test that required indexes are created."""
        cursor = memory_store.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = {row[0] for row in cursor.fetchall()}
        
        required_indexes = {
            "idx_repo_archived",
            "idx_archived",
            "idx_sequence_index",
            "idx_memory_type"
        }
        
        assert required_indexes.issubset(indexes)


class TestMemoryStoreAdd:
    """Test adding memory records to the store."""
    
    def test_add_record_success(self, memory_store, sample_record):
        """Test successfully adding a memory record."""
        memory_store.add(sample_record)
        
        # Verify record was added
        cursor = memory_store.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM memory_records WHERE memory_id = ?", 
                      (sample_record.memory_id,))
        count = cursor.fetchone()[0]
        
        assert count == 1
    
    def test_add_record_stores_all_fields(self, memory_store, sample_record):
        """Test that all fields are stored correctly."""
        memory_store.add(sample_record)
        
        # Retrieve and verify
        cursor = memory_store.conn.cursor()
        cursor.execute("SELECT * FROM memory_records WHERE memory_id = ?", 
                      (sample_record.memory_id,))
        row = cursor.fetchone()
        
        assert row["task_id"] == sample_record.task_id
        assert row["repo"] == sample_record.repo
        assert row["sequence_index"] == sample_record.sequence_index
        assert row["memory_type"] == sample_record.memory_type
        assert row["outcome"] == sample_record.outcome
        assert row["issue_summary"] == sample_record.issue_summary
        assert row["patch_summary"] == sample_record.patch_summary
    
    def test_add_record_stores_json_fields(self, memory_store, sample_record):
        """Test that list fields are stored as JSON."""
        memory_store.add(sample_record)
        
        cursor = memory_store.conn.cursor()
        cursor.execute("SELECT files_touched, functions_touched, commands_run FROM memory_records WHERE memory_id = ?", 
                      (sample_record.memory_id,))
        row = cursor.fetchone()
        
        assert json.loads(row["files_touched"]) == sample_record.files_touched
        assert json.loads(row["functions_touched"]) == sample_record.functions_touched
        assert json.loads(row["commands_run"]) == sample_record.commands_run
    
    def test_add_record_generates_embedding_vector_id(self, memory_store, sample_record):
        """Test that embedding vector ID is generated."""
        memory_store.add(sample_record)
        
        assert sample_record.embedding_vector_id != ""
        assert sample_record.embedding_vector_id.isdigit()
    
    def test_add_record_verifies_embedding_size(self, memory_store):
        """Test that embedding size is verified (Frozen Invariant #4)."""
        # Create record with very long embedding text (> 7500 tokens)
        long_text = "word " * 8000  # Approximately 8000 tokens
        
        record = MemoryRecord(
            memory_id=MemoryRecord.generate_id(),
            task_id="test_task_002",
            repo="test/repo",
            sequence_index=1,
            memory_type="bug_fix",
            outcome="pass",
            issue_summary="Test",
            patch_summary="Test",
            embedding_text=long_text,
            token_length=8000
        )
        
        with pytest.raises(AssertionError, match="exceeds 7500 token limit"):
            memory_store.add(record)
    
    def test_add_multiple_records(self, memory_store):
        """Test adding multiple records."""
        records = []
        for i in range(5):
            record = MemoryRecord(
                memory_id=MemoryRecord.generate_id(),
                task_id=f"test_task_{i:03d}",
                repo="test/repo",
                sequence_index=i,
                memory_type="bug_fix",
                outcome="pass",
                issue_summary=f"Issue {i}",
                patch_summary=f"Patch {i}",
                embedding_text=f"Issue {i} Patch {i}",
                token_length=10
            )
            records.append(record)
            memory_store.add(record)
        
        # Verify all records were added
        assert memory_store.count_active() == 5


class TestMemoryStoreFilter:
    """Test filtering memory records."""
    
    def test_filter_by_repo(self, memory_store):
        """Test filtering by repository."""
        # Add records from different repos
        for i, repo in enumerate(["repo1/test", "repo2/test", "repo1/test"]):
            record = MemoryRecord(
                memory_id=MemoryRecord.generate_id(),
                task_id=f"task_{i}",
                repo=repo,
                sequence_index=i,
                memory_type="bug_fix",
                outcome="pass",
                issue_summary=f"Issue {i}",
                patch_summary=f"Patch {i}",
                embedding_text=f"Issue {i}",
                token_length=10
            )
            memory_store.add(record)
        
        # Filter by repo1
        results = memory_store.filter(repo="repo1/test", is_archived=False)
        
        assert len(results) == 2
        assert all(r.repo == "repo1/test" for r in results)
    
    def test_filter_excludes_archived(self, memory_store):
        """Test that archived records are excluded."""
        # Add records
        records = []
        for i in range(3):
            record = MemoryRecord(
                memory_id=MemoryRecord.generate_id(),
                task_id=f"task_{i}",
                repo="test/repo",
                sequence_index=i,
                memory_type="bug_fix",
                outcome="pass",
                issue_summary=f"Issue {i}",
                patch_summary=f"Patch {i}",
                embedding_text=f"Issue {i}",
                token_length=10
            )
            records.append(record)
            memory_store.add(record)
        
        # Archive one record
        memory_store.archive(records[1].memory_id, reason="test_archive", current_step=1)
        
        # Filter for active records
        active = memory_store.filter(repo="test/repo", is_archived=False)
        
        assert len(active) == 2
        assert all(not r.is_archived for r in active)
        assert records[1].memory_id not in [r.memory_id for r in active]
    
    def test_filter_returns_memory_records(self, memory_store, sample_record):
        """Test that filter returns MemoryRecord instances."""
        memory_store.add(sample_record)
        
        results = memory_store.filter(repo=sample_record.repo, is_archived=False)
        
        assert len(results) == 1
        assert isinstance(results[0], MemoryRecord)
        assert results[0].memory_id == sample_record.memory_id


class TestMemoryStoreArchive:
    """Test archiving memory records."""
    
    def test_archive_sets_archived_flag(self, memory_store, sample_record):
        """Test that archiving sets is_archived=True."""
        memory_store.add(sample_record)
        memory_store.archive(sample_record.memory_id, reason="test_prune", current_step=5)
        
        cursor = memory_store.conn.cursor()
        cursor.execute("SELECT is_archived FROM memory_records WHERE memory_id = ?", 
                      (sample_record.memory_id,))
        is_archived = cursor.fetchone()[0]
        
        assert is_archived == 1
    
    def test_archive_stores_reason(self, memory_store, sample_record):
        """Test that archive reason is stored."""
        memory_store.add(sample_record)
        memory_store.archive(sample_record.memory_id, reason="random_prune", current_step=5)
        
        cursor = memory_store.conn.cursor()
        cursor.execute("SELECT archived_reason FROM memory_records WHERE memory_id = ?", 
                      (sample_record.memory_id,))
        reason = cursor.fetchone()[0]
        
        assert reason == "random_prune"
    
    def test_archive_stores_step(self, memory_store, sample_record):
        """Test that archive step is stored."""
        memory_store.add(sample_record)
        memory_store.archive(sample_record.memory_id, reason="test", current_step=10)
        
        cursor = memory_store.conn.cursor()
        cursor.execute("SELECT archived_at_step FROM memory_records WHERE memory_id = ?", 
                      (sample_record.memory_id,))
        step = cursor.fetchone()[0]
        
        assert step == 10
    
    def test_archive_removes_from_active(self, memory_store, sample_record):
        """Test that archived records are excluded from active_records()."""
        memory_store.add(sample_record)
        
        # Verify it's active
        assert memory_store.count_active() == 1
        
        # Archive it
        memory_store.archive(sample_record.memory_id, reason="test", current_step=1)
        
        # Verify it's no longer active
        assert memory_store.count_active() == 0
        active = memory_store.active_records()
        assert len(active) == 0


class TestMemoryStoreUsageTracking:
    """Test usage tracking updates."""
    
    def test_update_usage_increments_use_count(self, memory_store, sample_record):
        """Test that update_usage increments use_count."""
        memory_store.add(sample_record)
        
        # Update usage
        memory_store.update_usage(sample_record.memory_id, step=5)
        
        cursor = memory_store.conn.cursor()
        cursor.execute("SELECT use_count FROM memory_records WHERE memory_id = ?", 
                      (sample_record.memory_id,))
        use_count = cursor.fetchone()[0]
        
        assert use_count == 1
    
    def test_update_usage_sets_last_retrieved_step(self, memory_store, sample_record):
        """Test that update_usage sets last_retrieved_at_step."""
        memory_store.add(sample_record)
        
        memory_store.update_usage(sample_record.memory_id, step=7)
        
        cursor = memory_store.conn.cursor()
        cursor.execute("SELECT last_retrieved_at_step FROM memory_records WHERE memory_id = ?", 
                      (sample_record.memory_id,))
        last_step = cursor.fetchone()[0]
        
        assert last_step == 7
    
    def test_update_usage_tracks_success(self, memory_store, sample_record):
        """Test that update_usage tracks successful outcomes."""
        memory_store.add(sample_record)
        
        memory_store.update_usage(sample_record.memory_id, step=5, task_succeeded=True)
        
        cursor = memory_store.conn.cursor()
        cursor.execute("SELECT success_after_retrieval_count FROM memory_records WHERE memory_id = ?", 
                      (sample_record.memory_id,))
        success_count = cursor.fetchone()[0]
        
        assert success_count == 1
    
    def test_update_usage_tracks_failure(self, memory_store, sample_record):
        """Test that update_usage tracks failed outcomes."""
        memory_store.add(sample_record)
        
        memory_store.update_usage(sample_record.memory_id, step=5, task_succeeded=False)
        
        cursor = memory_store.conn.cursor()
        cursor.execute("SELECT failure_after_retrieval_count FROM memory_records WHERE memory_id = ?", 
                      (sample_record.memory_id,))
        failure_count = cursor.fetchone()[0]
        
        assert failure_count == 1
    
    def test_update_usage_multiple_times(self, memory_store, sample_record):
        """Test multiple usage updates."""
        memory_store.add(sample_record)
        
        # Update multiple times
        memory_store.update_usage(sample_record.memory_id, step=1, task_succeeded=True)
        memory_store.update_usage(sample_record.memory_id, step=3, task_succeeded=False)
        memory_store.update_usage(sample_record.memory_id, step=5, task_succeeded=True)
        
        cursor = memory_store.conn.cursor()
        cursor.execute("""
            SELECT use_count, success_after_retrieval_count, failure_after_retrieval_count, last_retrieved_at_step
            FROM memory_records WHERE memory_id = ?
        """, (sample_record.memory_id,))
        row = cursor.fetchone()
        
        assert row[0] == 3  # use_count
        assert row[1] == 2  # success_count
        assert row[2] == 1  # failure_count
        assert row[3] == 5  # last_step


class TestMemoryStoreSnapshot:
    """Test snapshot generation."""
    
    def test_snapshot_creates_file(self, memory_store, sample_record):
        """Test that snapshot creates a JSON file."""
        memory_store.add(sample_record)
        
        snapshot = memory_store.snapshot(step=0, boundary="before_task")
        
        snapshot_file = memory_store.snapshot_dir / "before_task_0.json"
        assert snapshot_file.exists()
    
    def test_snapshot_contains_required_fields(self, memory_store, sample_record):
        """Test that snapshot contains all required fields."""
        memory_store.add(sample_record)
        
        snapshot = memory_store.snapshot(step=0, boundary="after_task")
        
        assert "step" in snapshot
        assert "boundary" in snapshot
        assert "active_records" in snapshot
        assert "archived_this_step" in snapshot
        assert "metadata" in snapshot
        
        assert snapshot["step"] == 0
        assert snapshot["boundary"] == "after_task"
        assert snapshot["metadata"]["policy_name"] == "test_policy"
    
    def test_snapshot_includes_active_records(self, memory_store):
        """Test that snapshot includes all active records."""
        # Add multiple records
        for i in range(3):
            record = MemoryRecord(
                memory_id=MemoryRecord.generate_id(),
                task_id=f"task_{i}",
                repo="test/repo",
                sequence_index=i,
                memory_type="bug_fix",
                outcome="pass",
                issue_summary=f"Issue {i}",
                patch_summary=f"Patch {i}",
                embedding_text=f"Issue {i}",
                token_length=10
            )
            memory_store.add(record)
        
        snapshot = memory_store.snapshot(step=2, boundary="after_task")
        
        assert len(snapshot["active_records"]) == 3
        assert all("memory_id" in r for r in snapshot["active_records"])
        assert all("importance_score" in r for r in snapshot["active_records"])
        assert all("memory_type" in r for r in snapshot["active_records"])
    
    def test_snapshot_tracks_archived_this_step(self, memory_store):
        """Test that snapshot tracks records archived at current step."""
        # Add records
        records = []
        for i in range(3):
            record = MemoryRecord(
                memory_id=MemoryRecord.generate_id(),
                task_id=f"task_{i}",
                repo="test/repo",
                sequence_index=i,
                memory_type="bug_fix",
                outcome="pass",
                issue_summary=f"Issue {i}",
                patch_summary=f"Patch {i}",
                embedding_text=f"Issue {i}",
                token_length=10
            )
            records.append(record)
            memory_store.add(record)
        
        # Archive one at step 5
        memory_store.archive(records[1].memory_id, reason="test", current_step=5)
        
        # Take snapshot at step 5
        snapshot = memory_store.snapshot(step=5, boundary="after_task")
        
        assert records[1].memory_id in snapshot["archived_this_step"]
        assert len(snapshot["archived_this_step"]) == 1


class TestMemoryStoreStats:
    """Test statistics computation."""
    
    def test_stats_counts_active_records(self, memory_store):
        """Test that stats correctly counts active records."""
        # Add records
        for i in range(5):
            record = MemoryRecord(
                memory_id=MemoryRecord.generate_id(),
                task_id=f"task_{i}",
                repo="test/repo",
                sequence_index=i,
                memory_type="bug_fix",
                outcome="pass",
                issue_summary=f"Issue {i}",
                patch_summary=f"Patch {i}",
                embedding_text=f"Issue {i}",
                token_length=100
            )
            memory_store.add(record)
        
        stats = memory_store.stats()
        
        assert stats["active_count"] == 5
        assert stats["archived_count"] == 0
        assert stats["total_records"] == 5
    
    def test_stats_counts_archived_records(self, memory_store):
        """Test that stats correctly counts archived records."""
        # Add records
        records = []
        for i in range(5):
            record = MemoryRecord(
                memory_id=MemoryRecord.generate_id(),
                task_id=f"task_{i}",
                repo="test/repo",
                sequence_index=i,
                memory_type="bug_fix",
                outcome="pass",
                issue_summary=f"Issue {i}",
                patch_summary=f"Patch {i}",
                embedding_text=f"Issue {i}",
                token_length=100
            )
            records.append(record)
            memory_store.add(record)
        
        # Archive 2 records
        memory_store.archive(records[0].memory_id, reason="test", current_step=1)
        memory_store.archive(records[1].memory_id, reason="test", current_step=1)
        
        stats = memory_store.stats()
        
        assert stats["active_count"] == 3
        assert stats["archived_count"] == 2
        assert stats["total_records"] == 5
    
    def test_stats_sums_token_length(self, memory_store):
        """Test that stats correctly sums token lengths."""
        # Add records with known token lengths
        for i in range(3):
            record = MemoryRecord(
                memory_id=MemoryRecord.generate_id(),
                task_id=f"task_{i}",
                repo="test/repo",
                sequence_index=i,
                memory_type="bug_fix",
                outcome="pass",
                issue_summary=f"Issue {i}",
                patch_summary=f"Patch {i}",
                embedding_text=f"Issue {i}",
                token_length=100 * (i + 1)  # 100, 200, 300
            )
            memory_store.add(record)
        
        stats = memory_store.stats()
        
        assert stats["total_tokens"] == 600  # 100 + 200 + 300


class TestMemoryStoreActiveRecords:
    """Test active_records() method."""
    
    def test_active_records_returns_all_non_archived(self, memory_store):
        """Test that active_records returns all non-archived records."""
        # Add records
        for i in range(5):
            record = MemoryRecord(
                memory_id=MemoryRecord.generate_id(),
                task_id=f"task_{i}",
                repo="test/repo",
                sequence_index=i,
                memory_type="bug_fix",
                outcome="pass",
                issue_summary=f"Issue {i}",
                patch_summary=f"Patch {i}",
                embedding_text=f"Issue {i}",
                token_length=10
            )
            memory_store.add(record)
        
        active = memory_store.active_records()
        
        assert len(active) == 5
        assert all(isinstance(r, MemoryRecord) for r in active)
        assert all(not r.is_archived for r in active)
    
    def test_active_records_excludes_archived(self, memory_store):
        """Test that active_records excludes archived records."""
        # Add records
        records = []
        for i in range(5):
            record = MemoryRecord(
                memory_id=MemoryRecord.generate_id(),
                task_id=f"task_{i}",
                repo="test/repo",
                sequence_index=i,
                memory_type="bug_fix",
                outcome="pass",
                issue_summary=f"Issue {i}",
                patch_summary=f"Patch {i}",
                embedding_text=f"Issue {i}",
                token_length=10
            )
            records.append(record)
            memory_store.add(record)
        
        # Archive some records
        memory_store.archive(records[1].memory_id, reason="test", current_step=1)
        memory_store.archive(records[3].memory_id, reason="test", current_step=1)
        
        active = memory_store.active_records()
        
        assert len(active) == 3
        archived_ids = {records[1].memory_id, records[3].memory_id}
        assert all(r.memory_id not in archived_ids for r in active)


class TestMemoryStoreCountActive:
    """Test count_active() method."""
    
    def test_count_active_returns_correct_count(self, memory_store):
        """Test that count_active returns correct count."""
        # Initially empty
        assert memory_store.count_active() == 0
        
        # Add records
        for i in range(7):
            record = MemoryRecord(
                memory_id=MemoryRecord.generate_id(),
                task_id=f"task_{i}",
                repo="test/repo",
                sequence_index=i,
                memory_type="bug_fix",
                outcome="pass",
                issue_summary=f"Issue {i}",
                patch_summary=f"Patch {i}",
                embedding_text=f"Issue {i}",
                token_length=10
            )
            memory_store.add(record)
        
        assert memory_store.count_active() == 7
    
    def test_count_active_excludes_archived(self, memory_store):
        """Test that count_active excludes archived records."""
        # Add records
        records = []
        for i in range(5):
            record = MemoryRecord(
                memory_id=MemoryRecord.generate_id(),
                task_id=f"task_{i}",
                repo="test/repo",
                sequence_index=i,
                memory_type="bug_fix",
                outcome="pass",
                issue_summary=f"Issue {i}",
                patch_summary=f"Patch {i}",
                embedding_text=f"Issue {i}",
                token_length=10
            )
            records.append(record)
            memory_store.add(record)
        
        # Archive 2 records
        memory_store.archive(records[0].memory_id, reason="test", current_step=1)
        memory_store.archive(records[2].memory_id, reason="test", current_step=1)
        
        assert memory_store.count_active() == 3


# ─────────────────────────────────────────────────────────────────────────────
# Repair-plan Task 2 (plan 2.3): same-repo search must score ALL same-repo
# candidates exactly, not rely on a global FAISS top-k that can be entirely
# cross-repo (Frozen Invariant #16). And Task 5 (plan 2.6): archived-at-step.
# ─────────────────────────────────────────────────────────────────────────────

def _insert_raw_record(store, memory_id, repo, vector_id):
    """Insert a minimal record directly into SQLite (bypasses embedding call)."""
    cur = store.conn.cursor()
    cur.execute(
        """
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
        """,
        (
            memory_id, "task-x", repo, 0,
            "bug_fix", "pass",
            "issue", "patch", None, None,
            "[]", "[]", "[]",
            "[]",
            "Issue: i\n\nPatch: p", str(vector_id),
            8, None,
            0, None,
            0, 0,
            0.0, 0, None,
            0, None, None,
            "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z",
        ),
    )
    store.conn.commit()


def test_same_repo_search_scores_all_candidates_even_when_global_hits_are_cross_repo(memory_store):
    import faiss

    memory_store.embedding_dim = 3
    memory_store.faiss_index = faiss.IndexFlatIP(3)
    memory_store.vector_id_to_memory_id = {}

    def add(memory_id, repo, vector):
        vec = np.array(vector, dtype=np.float32)
        vec = vec / np.linalg.norm(vec)
        vid = memory_store.faiss_index.ntotal
        memory_store.faiss_index.add(vec.reshape(1, -1))
        memory_store.vector_id_to_memory_id[vid] = memory_id
        _insert_raw_record(memory_store, memory_id, repo, vid)

    # 120 cross-repo vectors identical to the query (cosine 1.0) drown out the
    # single same-repo candidate in any global top-k search.
    for i in range(120):
        add(f"MEM-X-{i}", "flask/flask", [1.0, 0.0, 0.0])
    add("MEM-DJANGO", "django/django", [0.5, 0.5, 0.0])

    query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    results = memory_store.search(
        query_vector=query, top_k=1, repo="django/django", same_repo_only=True
    )
    assert [rec.memory_id for _, rec in results] == ["MEM-DJANGO"]


def test_archived_memory_ids_at_step_returns_only_step_matches(memory_store, sample_record):
    memory_store.add(sample_record)
    memory_store.archive(
        memory_id=sample_record.memory_id, reason="type_aware_decay", current_step=4
    )

    assert memory_store.archived_memory_ids_at_step(4) == [sample_record.memory_id]
    assert memory_store.archived_memory_ids_at_step(3) == []
