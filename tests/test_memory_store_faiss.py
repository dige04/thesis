"""
Unit tests for MemoryStore FAISS vector index implementation.

Tests cover:
- FAISS index initialization
- Embedding generation and storage
- Cosine similarity search
- Vector ID mapping to memory records
- Index persistence and rebuilding
"""

import os
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
        # Set up runs directory structure
        run_id = "test_run_001"
        run_dir = Path(tmpdir) / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # Change to temp directory for tests
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        
        yield run_id
        
        # Restore original directory
        os.chdir(original_cwd)


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for embedding generation."""
    with patch('src.memory.store.OpenAI') as mock_openai:
        # Create mock client
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        # Mock embedding response
        def create_embedding(model, input):
            # Return a deterministic embedding based on input length
            # This simulates different embeddings for different texts
            embedding_dim = 1536
            seed = hash(input) % 1000
            np.random.seed(seed)
            embedding = np.random.randn(embedding_dim).astype(np.float32)
            # L2 normalize
            embedding = embedding / np.linalg.norm(embedding)
            
            mock_response = MagicMock()
            mock_response.data = [MagicMock(embedding=embedding.tolist())]
            return mock_response
        
        mock_client.embeddings.create = create_embedding
        
        yield mock_client


def create_test_record(
    memory_id: str = "MEM-TEST001",
    task_id: str = "task-001",
    repo: str = "test/repo",
    sequence_index: int = 0,
    memory_type: str = "bug_fix",
    outcome: str = "pass",
    embedding_text: str = "Test issue summary. Test patch summary."
) -> MemoryRecord:
    """Create a test MemoryRecord instance."""
    return MemoryRecord(
        memory_id=memory_id,
        task_id=task_id,
        repo=repo,
        sequence_index=sequence_index,
        memory_type=memory_type,
        outcome=outcome,
        issue_summary="Test issue summary",
        patch_summary="Test patch summary",
        failure_summary=None,
        test_summary=None,
        files_touched=["test.py"],
        functions_touched=["test_func"],
        commands_run=["pytest"],
        retrieved_memory_ids_used=[],
        embedding_text=embedding_text,
        embedding_vector_id="",
        token_length=10,
        raw_trace_ref=None
    )


class TestFAISSIndexInitialization:
    """Test FAISS index initialization and persistence."""
    
    def test_init_creates_faiss_index(self, temp_run_dir, mock_openai_client):
        """Test that MemoryStore initializes FAISS index."""
        store = MemoryStore(run_id=temp_run_dir, policy_name="test_policy")
        
        assert store.faiss_index is not None
        assert store.faiss_index.ntotal == 0  # Empty index initially
        assert store.embedding_dim == 1536
        
        store.close()
    
    def test_faiss_index_persists_to_disk(self, temp_run_dir, mock_openai_client):
        """Test that FAISS index is saved to disk."""
        store = MemoryStore(run_id=temp_run_dir, policy_name="test_policy")
        
        # Add a record to populate the index
        record = create_test_record()
        store.add(record)
        
        # Close to save
        store.close()
        
        # Check that index file exists
        faiss_path = Path("runs") / temp_run_dir / "memory" / "memory.faiss"
        assert faiss_path.exists()
    
    def test_faiss_index_loads_from_disk(self, temp_run_dir, mock_openai_client):
        """Test that FAISS index is loaded from disk on subsequent initialization."""
        # Create store and add a record
        store1 = MemoryStore(run_id=temp_run_dir, policy_name="test_policy")
        record = create_test_record()
        store1.add(record)
        store1.close()
        
        # Create new store instance - should load existing index
        store2 = MemoryStore(run_id=temp_run_dir, policy_name="test_policy")
        assert store2.faiss_index.ntotal == 1  # Should have the record from before
        
        store2.close()


class TestEmbeddingGeneration:
    """Test embedding generation and storage."""
    
    def test_add_generates_embedding(self, temp_run_dir, mock_openai_client):
        """Test that add() generates embedding and stores in FAISS."""
        store = MemoryStore(run_id=temp_run_dir, policy_name="test_policy")
        
        record = create_test_record()
        store.add(record)
        
        # Check that embedding was generated and stored
        assert record.embedding_vector_id != ""
        assert record.embedding_vector_id == "0"  # First vector has ID 0
        assert store.faiss_index.ntotal == 1
        
        store.close()
    
    def test_add_multiple_records(self, temp_run_dir, mock_openai_client):
        """Test adding multiple records with different embeddings."""
        store = MemoryStore(run_id=temp_run_dir, policy_name="test_policy")
        
        # Add three records
        record1 = create_test_record(memory_id="MEM-001", embedding_text="First record")
        record2 = create_test_record(memory_id="MEM-002", embedding_text="Second record")
        record3 = create_test_record(memory_id="MEM-003", embedding_text="Third record")
        
        store.add(record1)
        store.add(record2)
        store.add(record3)
        
        # Check vector IDs are sequential
        assert record1.embedding_vector_id == "0"
        assert record2.embedding_vector_id == "1"
        assert record3.embedding_vector_id == "2"
        assert store.faiss_index.ntotal == 3
        
        store.close()
    
    def test_embedding_size_verification(self, temp_run_dir, mock_openai_client):
        """Test that embedding size is verified before adding."""
        store = MemoryStore(run_id=temp_run_dir, policy_name="test_policy")
        
        # Create a record with very long embedding text (> 7500 tokens)
        long_text = "word " * 8000  # Approximately 8000 tokens
        record = create_test_record(embedding_text=long_text)
        
        # Should raise AssertionError
        with pytest.raises(AssertionError, match="exceeds 7500 token limit"):
            store.add(record)
        
        store.close()


class TestCosineSimilaritySearch:
    """Test FAISS cosine similarity search."""
    
    def test_search_returns_similar_records(self, temp_run_dir, mock_openai_client):
        """Test that search returns records sorted by similarity."""
        store = MemoryStore(run_id=temp_run_dir, policy_name="test_policy")
        
        # Add records with different content
        record1 = create_test_record(
            memory_id="MEM-001",
            embedding_text="Django authentication bug fix"
        )
        record2 = create_test_record(
            memory_id="MEM-002",
            embedding_text="React component styling update"
        )
        record3 = create_test_record(
            memory_id="MEM-003",
            embedding_text="Django login authentication issue"
        )
        
        store.add(record1)
        store.add(record2)
        store.add(record3)
        
        # Search with query similar to record1 and record3
        query_text = "Django authentication problem"
        query_vector = store._generate_embedding(query_text)
        
        results = store.search(query_vector, top_k=2, same_repo_only=False)
        
        # Should return 2 results
        assert len(results) == 2
        
        # Results should be tuples of (similarity_score, MemoryRecord)
        assert all(isinstance(r[0], float) for r in results)
        assert all(isinstance(r[1], MemoryRecord) for r in results)
        
        # Scores should be in descending order
        assert results[0][0] >= results[1][0]
        
        store.close()
    
    def test_search_filters_by_repo(self, temp_run_dir, mock_openai_client):
        """Test that search filters by repository when same_repo_only=True."""
        store = MemoryStore(run_id=temp_run_dir, policy_name="test_policy")
        
        # Add records from different repos
        record1 = create_test_record(
            memory_id="MEM-001",
            repo="django/django",
            embedding_text="Django bug fix"
        )
        record2 = create_test_record(
            memory_id="MEM-002",
            repo="react/react",
            embedding_text="React bug fix"
        )
        record3 = create_test_record(
            memory_id="MEM-003",
            repo="django/django",
            embedding_text="Django feature"
        )
        
        store.add(record1)
        store.add(record2)
        store.add(record3)
        
        # Search with same_repo_only=True for django/django
        query_vector = store._generate_embedding("Django issue")
        results = store.search(
            query_vector,
            top_k=10,
            repo="django/django",
            same_repo_only=True
        )
        
        # Should only return django/django records
        assert len(results) == 2
        assert all(r[1].repo == "django/django" for r in results)
        
        store.close()
    
    def test_search_excludes_archived_records(self, temp_run_dir, mock_openai_client):
        """Test that search excludes archived records."""
        store = MemoryStore(run_id=temp_run_dir, policy_name="test_policy")
        
        # Add records
        record1 = create_test_record(memory_id="MEM-001", embedding_text="Active record")
        record2 = create_test_record(memory_id="MEM-002", embedding_text="Archived record")
        
        store.add(record1)
        store.add(record2)
        
        # Archive record2
        store.archive(memory_id="MEM-002", reason="test_archive", current_step=1)
        
        # Search should only return active records
        query_vector = store._generate_embedding("record")
        results = store.search(query_vector, top_k=10, same_repo_only=False)
        
        assert len(results) == 1
        assert results[0][1].memory_id == "MEM-001"
        
        store.close()
    
    def test_search_returns_empty_for_no_candidates(self, temp_run_dir, mock_openai_client):
        """Test that search returns empty list when no candidates match."""
        store = MemoryStore(run_id=temp_run_dir, policy_name="test_policy")
        
        # Add record from one repo
        record = create_test_record(repo="django/django")
        store.add(record)
        
        # Search for different repo
        query_vector = store._generate_embedding("test")
        results = store.search(
            query_vector,
            top_k=10,
            repo="react/react",
            same_repo_only=True
        )
        
        assert len(results) == 0
        
        store.close()


class TestVectorIDMapping:
    """Test vector ID to memory ID mapping."""
    
    def test_vector_id_mapping_maintained(self, temp_run_dir, mock_openai_client):
        """Test that vector ID to memory ID mapping is maintained."""
        store = MemoryStore(run_id=temp_run_dir, policy_name="test_policy")
        
        # Add records
        record1 = create_test_record(memory_id="MEM-001")
        record2 = create_test_record(memory_id="MEM-002")
        
        store.add(record1)
        store.add(record2)
        
        # Check mapping
        assert store.vector_id_to_memory_id[0] == "MEM-001"
        assert store.vector_id_to_memory_id[1] == "MEM-002"
        
        store.close()
    
    def test_vector_id_mapping_persists(self, temp_run_dir, mock_openai_client):
        """Test that vector ID mapping is loaded from SQLite on initialization."""
        # Create store and add records
        store1 = MemoryStore(run_id=temp_run_dir, policy_name="test_policy")
        record1 = create_test_record(memory_id="MEM-001")
        record2 = create_test_record(memory_id="MEM-002")
        store1.add(record1)
        store1.add(record2)
        store1.close()
        
        # Create new store instance - should load mapping
        store2 = MemoryStore(run_id=temp_run_dir, policy_name="test_policy")
        assert store2.vector_id_to_memory_id[0] == "MEM-001"
        assert store2.vector_id_to_memory_id[1] == "MEM-002"
        
        store2.close()


class TestIndexRebuilding:
    """Test index rebuilding on archive operations."""
    
    def test_archive_does_not_delete_from_faiss(self, temp_run_dir, mock_openai_client):
        """Test that archiving does not delete vectors from FAISS (preserves for analysis)."""
        store = MemoryStore(run_id=temp_run_dir, policy_name="test_policy")
        
        # Add records
        record1 = create_test_record(memory_id="MEM-001")
        record2 = create_test_record(memory_id="MEM-002")
        
        store.add(record1)
        store.add(record2)
        
        initial_count = store.faiss_index.ntotal
        
        # Archive one record
        store.archive(memory_id="MEM-001", reason="test_archive", current_step=1)
        
        # FAISS index should still have both vectors (not deleted)
        assert store.faiss_index.ntotal == initial_count
        
        # But search should exclude archived record
        query_vector = store._generate_embedding("test")
        results = store.search(query_vector, top_k=10, same_repo_only=False)
        assert len(results) == 1
        assert results[0][1].memory_id == "MEM-002"
        
        store.close()


class TestPureCosineSimilarity:
    """Test that retrieval uses pure cosine similarity (Frozen Invariant #5)."""
    
    def test_no_bonuses_or_penalties(self, temp_run_dir, mock_openai_client):
        """Test that search does not apply bonuses based on type, outcome, age, or use_count."""
        store = MemoryStore(run_id=temp_run_dir, policy_name="test_policy")
        
        # Add records with different metadata but similar content
        record1 = create_test_record(
            memory_id="MEM-001",
            memory_type="architectural",
            outcome="pass",
            sequence_index=0,
            embedding_text="Test content"
        )
        record2 = create_test_record(
            memory_id="MEM-002",
            memory_type="bug_fix",
            outcome="fail",
            sequence_index=10,
            embedding_text="Test content"
        )
        
        # Set different use counts
        record1.use_count = 10
        record2.use_count = 0
        
        store.add(record1)
        store.add(record2)
        
        # Search with identical query
        query_vector = store._generate_embedding("Test content")
        results = store.search(query_vector, top_k=2, same_repo_only=False)
        
        # Both should have very similar scores (pure cosine, no adjustments)
        # The scores should be nearly identical since content is the same
        assert len(results) == 2
        score1, score2 = results[0][0], results[1][0]
        
        # Scores should be very close (within 0.01 tolerance for floating point)
        assert abs(score1 - score2) < 0.01, (
            f"Scores differ too much: {score1} vs {score2}. "
            "This suggests bonuses/penalties are being applied."
        )
        
        store.close()
