"""Unit tests for Recency Prune policy.

Tests verify:
1. Recency Prune policy uses shared_retrieve with identical scoring (Req 11.1)
2. Recency Prune policy stores all incoming records (Req 11.2)
3. Recency Prune policy archives oldest by sequence_index when exceeding max_records (Req 11.3)
4. Recency Prune policy retains max_records most recent memories (Req 11.4)

**Validates: Requirements 11**
"""

import pytest
from src.memory.policies.recency_prune import RecencyPrunePolicy
from src.memory.record import MemoryRecord


class MockTask:
    """Mock task object for testing."""
    def __init__(self, repo="test/repo", issue_text="Test issue", task_id="test-001"):
        self.repo = repo
        self.issue_text = issue_text
        self.task_id = task_id


class MockMemoryStore:
    """Mock memory store for testing."""
    def __init__(self):
        self.records = []
        self.archived_records = []
        self.add_called_count = 0
        self.archive_called_count = 0
    
    def add(self, record):
        """Mock add method."""
        self.add_called_count += 1
        self.records.append(record)
    
    def archive(self, memory_id, reason, current_step=None):
        """Mock archive method."""
        self.archive_called_count += 1
        # Find and move record to archived
        for i, record in enumerate(self.records):
            if record.memory_id == memory_id:
                archived = self.records.pop(i)
                archived.is_archived = True
                archived.archived_reason = reason
                archived.archived_at_step = current_step
                self.archived_records.append(archived)
                break
    
    def active_records(self):
        """Return non-archived records."""
        return [r for r in self.records if not r.is_archived]
    
    def count_active(self):
        """Count non-archived records."""
        return len(self.active_records())


def create_mock_record(memory_id, sequence_index, memory_type="bug_fix"):
    """Create a mock MemoryRecord for testing."""
    return MemoryRecord(
        memory_id=memory_id,
        task_id=f"task-{sequence_index:03d}",
        repo="test/repo",
        sequence_index=sequence_index,
        memory_type=memory_type,
        outcome="pass",
        issue_summary=f"Issue {sequence_index}",
        patch_summary=f"Patch {sequence_index}",
        embedding_text=f"Embedding {sequence_index}",
        token_length=100
    )


class TestRecencyPrunePolicyInstantiation:
    """Test Recency Prune policy instantiation and attributes."""
    
    def test_can_instantiate_with_valid_parameters(self):
        """Verify Recency Prune policy can be instantiated with valid parameters."""
        policy = RecencyPrunePolicy(max_records=100)
        assert policy is not None
        assert policy.max_records == 100
    
    def test_has_correct_name(self):
        """Verify Recency Prune policy has correct name attribute."""
        policy = RecencyPrunePolicy(max_records=100)
        assert policy.name == "recency_prune"
    
    def test_is_memory_policy_subclass(self):
        """Verify Recency Prune policy is a MemoryPolicy subclass."""
        from src.memory.policies.base import MemoryPolicy
        policy = RecencyPrunePolicy(max_records=100)
        assert isinstance(policy, MemoryPolicy)
    
    def test_accepts_various_max_records(self):
        """Verify instantiation accepts various max_records values."""
        for max_records in [1, 10, 50, 100, 1000]:
            policy = RecencyPrunePolicy(max_records=max_records)
            assert policy.max_records == max_records


class TestRecencyPrunePolicyRetrieve:
    """Test Recency Prune policy retrieve() method.
    
    **Validates: Requirements 11.1**
    """
    
    def test_retrieve_uses_shared_retrieve(self):
        """Verify retrieve() uses shared_retrieve (Req 11.1, Frozen Invariant #5)."""
        import inspect
        from src.memory.policies.recency_prune import RecencyPrunePolicy
        
        # Get source code of retrieve method
        source = inspect.getsource(RecencyPrunePolicy.retrieve)
        
        # Verify it calls shared_retrieve
        assert "shared_retrieve" in source
        
        # Verify it passes all parameters correctly
        assert "task" in source
        assert "memory_store" in source
        assert "top_k" in source
        assert "token_budget" in source
    
    def test_retrieve_returns_shared_retrieve_result(self):
        """Verify retrieve() returns result from shared_retrieve unchanged."""
        from unittest.mock import patch
        
        policy = RecencyPrunePolicy(max_records=100)
        task = MockTask()
        store = MockMemoryStore()
        
        # Mock shared_retrieve to return a known result
        mock_result = [(0.9, create_mock_record("mem-001", 1))]
        
        with patch('src.memory.policies.recency_prune.shared_retrieve', return_value=mock_result):
            result = policy.retrieve(task, store, top_k=5, token_budget=2000)
        
        # Should return the mocked result unchanged
        assert result == mock_result
    
    def test_retrieve_passes_correct_parameters_to_shared_retrieve(self):
        """Verify retrieve() passes all parameters correctly to shared_retrieve."""
        from unittest.mock import patch
        
        policy = RecencyPrunePolicy(max_records=100)
        task = MockTask()
        store = MockMemoryStore()
        
        with patch('src.memory.policies.recency_prune.shared_retrieve') as mock_shared:
            policy.retrieve(task, store, top_k=7, token_budget=3000)
            
            # Verify shared_retrieve was called with correct parameters
            mock_shared.assert_called_once_with(task, store, 7, 3000)


class TestRecencyPrunePolicyWrite:
    """Test Recency Prune policy write() method.
    
    **Validates: Requirements 11.2**
    """
    
    def test_write_stores_all_records(self):
        """Verify write() stores all incoming records (Req 11.2)."""
        policy = RecencyPrunePolicy(max_records=100)
        store = MockMemoryStore()
        
        # Write multiple records
        for i in range(10):
            record = create_mock_record(f"mem-{i:03d}", i)
            policy.write(store, record)
        
        # Verify all records were stored
        assert store.add_called_count == 10
        assert len(store.records) == 10
    
    def test_write_does_not_check_capacity(self):
        """Verify write() stores records without checking capacity."""
        policy = RecencyPrunePolicy(max_records=5)
        store = MockMemoryStore()
        
        # Write more records than max_records
        for i in range(10):
            record = create_mock_record(f"mem-{i:03d}", i)
            policy.write(store, record)
        
        # All records should be stored (pruning happens in maintain())
        assert store.add_called_count == 10
        assert len(store.records) == 10
    
    def test_write_calls_store_add(self):
        """Verify write() calls memory_store.add()."""
        policy = RecencyPrunePolicy(max_records=100)
        store = MockMemoryStore()
        record = create_mock_record("mem-001", 1)
        
        policy.write(store, record)
        
        assert store.add_called_count == 1
        assert record in store.records


class TestRecencyPrunePolicyMaintain:
    """Test Recency Prune policy maintain() method.
    
    **Validates: Requirements 11.3, 11.4**
    """
    
    def test_maintain_no_pruning_when_under_capacity(self):
        """Verify maintain() does not prune when active count <= max_records."""
        policy = RecencyPrunePolicy(max_records=10)
        store = MockMemoryStore()
        
        # Add 5 records (under capacity)
        for i in range(5):
            store.records.append(create_mock_record(f"mem-{i:03d}", i))
        
        policy.maintain(store)
        
        # No archiving should occur
        assert store.archive_called_count == 0
        assert len(store.active_records()) == 5
    
    def test_maintain_no_pruning_when_at_capacity(self):
        """Verify maintain() does not prune when active count == max_records."""
        policy = RecencyPrunePolicy(max_records=10)
        store = MockMemoryStore()
        
        # Add exactly max_records
        for i in range(10):
            store.records.append(create_mock_record(f"mem-{i:03d}", i))
        
        policy.maintain(store)
        
        # No archiving should occur
        assert store.archive_called_count == 0
        assert len(store.active_records()) == 10
    
    def test_maintain_prunes_when_over_capacity(self):
        """Verify maintain() prunes when active count > max_records (Req 11.3)."""
        policy = RecencyPrunePolicy(max_records=5)
        store = MockMemoryStore()
        
        # Add 10 records (over capacity)
        for i in range(10):
            store.records.append(create_mock_record(f"mem-{i:03d}", i))
        
        policy.maintain(store)
        
        # Should archive 5 records
        assert store.archive_called_count == 5
        assert len(store.active_records()) == 5
    
    def test_maintain_archives_oldest_by_sequence_index(self):
        """Verify maintain() archives oldest memories by sequence_index (Req 11.3, CRITICAL)."""
        policy = RecencyPrunePolicy(max_records=5)
        store = MockMemoryStore()
        
        # Add 10 records with sequential sequence_index
        for i in range(10):
            store.records.append(create_mock_record(f"mem-{i:03d}", i))
        
        policy.maintain(store)
        
        # Should archive the 5 oldest (sequence_index 0-4)
        archived_seq_indices = sorted([r.sequence_index for r in store.archived_records])
        assert archived_seq_indices == [0, 1, 2, 3, 4]
        
        # Should retain the 5 newest (sequence_index 5-9)
        active_seq_indices = sorted([r.sequence_index for r in store.active_records()])
        assert active_seq_indices == [5, 6, 7, 8, 9]
    
    def test_maintain_retains_most_recent_memories(self):
        """Verify maintain() retains max_records most recent memories (Req 11.4)."""
        policy = RecencyPrunePolicy(max_records=3)
        store = MockMemoryStore()
        
        # Add 8 records
        for i in range(8):
            store.records.append(create_mock_record(f"mem-{i:03d}", i))
        
        policy.maintain(store)
        
        # Should retain the 3 most recent (sequence_index 5, 6, 7)
        active_seq_indices = sorted([r.sequence_index for r in store.active_records()])
        assert active_seq_indices == [5, 6, 7]
        
        # Should archive the 5 oldest (sequence_index 0, 1, 2, 3, 4)
        archived_seq_indices = sorted([r.sequence_index for r in store.archived_records])
        assert archived_seq_indices == [0, 1, 2, 3, 4]
    
    def test_maintain_archives_correct_number(self):
        """Verify maintain() archives exactly enough to reach max_records."""
        policy = RecencyPrunePolicy(max_records=7)
        store = MockMemoryStore()
        
        # Add 12 records (5 over capacity)
        for i in range(12):
            store.records.append(create_mock_record(f"mem-{i:03d}", i))
        
        policy.maintain(store)
        
        # Should archive exactly 5 records
        assert store.archive_called_count == 5
        assert len(store.active_records()) == 7
    
    def test_maintain_archives_with_correct_reason(self):
        """Verify maintain() archives with reason='recency_prune'."""
        policy = RecencyPrunePolicy(max_records=3)
        store = MockMemoryStore()
        
        # Add 5 records
        for i in range(5):
            store.records.append(create_mock_record(f"mem-{i:03d}", i))
        
        policy.maintain(store)
        
        # Verify archived records have correct reason
        for record in store.archived_records:
            assert record.archived_reason == "recency_prune"
    
    def test_maintain_handles_single_record_over_capacity(self):
        """Verify maintain() handles case where only 1 record needs pruning."""
        policy = RecencyPrunePolicy(max_records=5)
        store = MockMemoryStore()
        
        # Add 6 records (1 over capacity)
        for i in range(6):
            store.records.append(create_mock_record(f"mem-{i:03d}", i))
        
        policy.maintain(store)
        
        # Should archive exactly 1 record (the oldest)
        assert store.archive_called_count == 1
        assert len(store.active_records()) == 5
        assert store.archived_records[0].sequence_index == 0
    
    def test_maintain_handles_many_records_over_capacity(self):
        """Verify maintain() handles case where many records need pruning."""
        policy = RecencyPrunePolicy(max_records=2)
        store = MockMemoryStore()
        
        # Add 20 records (18 over capacity)
        for i in range(20):
            store.records.append(create_mock_record(f"mem-{i:03d}", i))
        
        policy.maintain(store)
        
        # Should archive 18 records (the oldest)
        assert store.archive_called_count == 18
        assert len(store.active_records()) == 2
        
        # Should retain only the 2 most recent
        active_seq_indices = sorted([r.sequence_index for r in store.active_records()])
        assert active_seq_indices == [18, 19]


class TestRecencyPrunePolicyDeterminism:
    """Test CRITICAL invariant: Deterministic pruning by sequence_index.
    
    **Validates: Requirements 11.3**
    
    This is a key difference from Random Prune: Recency Prune is deterministic.
    Same memory state always produces same pruning decisions.
    """
    
    def test_pruning_is_deterministic(self):
        """Verify pruning decisions are deterministic (Req 11.3, CRITICAL)."""
        # Run 1
        policy1 = RecencyPrunePolicy(max_records=3)
        store1 = MockMemoryStore()
        
        for i in range(10):
            store1.records.append(create_mock_record(f"mem-{i:03d}", i))
        
        policy1.maintain(store1)
        archived1 = sorted([r.memory_id for r in store1.archived_records])
        
        # Run 2 (same setup)
        policy2 = RecencyPrunePolicy(max_records=3)
        store2 = MockMemoryStore()
        
        for i in range(10):
            store2.records.append(create_mock_record(f"mem-{i:03d}", i))
        
        policy2.maintain(store2)
        archived2 = sorted([r.memory_id for r in store2.archived_records])
        
        # Should archive the same memories (deterministic)
        assert archived1 == archived2
    
    def test_pruning_based_only_on_sequence_index(self):
        """Verify pruning is based ONLY on sequence_index, not other attributes."""
        policy = RecencyPrunePolicy(max_records=5)
        store = MockMemoryStore()
        
        # Add records with different memory types but sequential sequence_index
        types = ["architectural", "api_change", "bug_fix", "test_update", "config"]
        for i in range(10):
            memory_type = types[i % len(types)]
            store.records.append(create_mock_record(f"mem-{i:03d}", i, memory_type))
        
        policy.maintain(store)
        
        # Should archive based on sequence_index only (0-4), regardless of type
        archived_seq_indices = sorted([r.sequence_index for r in store.archived_records])
        assert archived_seq_indices == [0, 1, 2, 3, 4]
    
    def test_pruning_with_non_sequential_sequence_indices(self):
        """Verify pruning works correctly with non-sequential sequence_indices."""
        policy = RecencyPrunePolicy(max_records=3)
        store = MockMemoryStore()
        
        # Add records with non-sequential sequence_index
        sequence_indices = [5, 2, 8, 1, 9, 3, 7]
        for i, seq_idx in enumerate(sequence_indices):
            store.records.append(create_mock_record(f"mem-{i:03d}", seq_idx))
        
        policy.maintain(store)
        
        # Should archive the 4 oldest by sequence_index (1, 2, 3, 5)
        archived_seq_indices = sorted([r.sequence_index for r in store.archived_records])
        assert archived_seq_indices == [1, 2, 3, 5]
        
        # Should retain the 3 newest by sequence_index (7, 8, 9)
        active_seq_indices = sorted([r.sequence_index for r in store.active_records()])
        assert active_seq_indices == [7, 8, 9]


class TestRecencyPrunePolicyEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_maintain_with_empty_store(self):
        """Verify maintain() handles empty store gracefully."""
        policy = RecencyPrunePolicy(max_records=10)
        store = MockMemoryStore()
        
        # Should not raise
        policy.maintain(store)
        
        assert store.archive_called_count == 0
    
    def test_maintain_with_max_records_one(self):
        """Verify maintain() works with max_records=1."""
        policy = RecencyPrunePolicy(max_records=1)
        store = MockMemoryStore()
        
        # Add 3 records
        for i in range(3):
            store.records.append(create_mock_record(f"mem-{i:03d}", i))
        
        policy.maintain(store)
        
        # Should retain only the most recent record (sequence_index=2)
        assert len(store.active_records()) == 1
        assert store.active_records()[0].sequence_index == 2
        assert store.archive_called_count == 2
    
    def test_maintain_final_count_assertion(self):
        """Verify maintain() asserts final count <= max_records."""
        policy = RecencyPrunePolicy(max_records=5)
        store = MockMemoryStore()
        
        # Add 10 records
        for i in range(10):
            store.records.append(create_mock_record(f"mem-{i:03d}", i))
        
        policy.maintain(store)
        
        # Final count should be exactly max_records
        final_count = len(store.active_records())
        assert final_count <= policy.max_records
        assert final_count == policy.max_records
    
    def test_maintain_with_duplicate_sequence_indices(self):
        """Verify maintain() handles duplicate sequence_indices gracefully."""
        policy = RecencyPrunePolicy(max_records=3)
        store = MockMemoryStore()
        
        # Add records with some duplicate sequence_indices
        sequence_indices = [1, 2, 2, 3, 4, 4, 5]
        for i, seq_idx in enumerate(sequence_indices):
            store.records.append(create_mock_record(f"mem-{i:03d}", seq_idx))
        
        policy.maintain(store)
        
        # Should archive 4 records to reach max_records=3
        assert store.archive_called_count == 4
        assert len(store.active_records()) == 3


class TestRecencyPrunePolicyAPICompatibility:
    """Test Recency Prune policy maintains API compatibility."""
    
    def test_implements_all_required_methods(self):
        """Verify Recency Prune policy implements all MemoryPolicy methods."""
        policy = RecencyPrunePolicy(max_records=100)
        
        assert hasattr(policy, "retrieve")
        assert hasattr(policy, "write")
        assert hasattr(policy, "maintain")
        assert hasattr(policy, "name")
    
    def test_method_signatures_match_base_class(self):
        """Verify method signatures match MemoryPolicy interface."""
        import inspect
        
        policy = RecencyPrunePolicy(max_records=100)
        
        # Get method signatures
        retrieve_sig = inspect.signature(policy.retrieve)
        write_sig = inspect.signature(policy.write)
        maintain_sig = inspect.signature(policy.maintain)
        
        # Verify retrieve parameters
        retrieve_params = list(retrieve_sig.parameters.keys())
        assert 'task' in retrieve_params
        assert 'memory_store' in retrieve_params
        assert 'top_k' in retrieve_params
        assert 'token_budget' in retrieve_params
        
        # Verify write parameters
        write_params = list(write_sig.parameters.keys())
        assert 'memory_store' in write_params
        assert 'record' in write_params
        
        # Verify maintain parameters
        maintain_params = list(maintain_sig.parameters.keys())
        assert 'memory_store' in maintain_params


class TestRecencyPrunePolicyDocumentation:
    """Test Recency Prune policy has proper documentation."""
    
    def test_class_has_docstring(self):
        """Verify RecencyPrunePolicy class has docstring."""
        assert RecencyPrunePolicy.__doc__ is not None
        assert "recency" in RecencyPrunePolicy.__doc__.lower()
        assert "Requirements 11" in RecencyPrunePolicy.__doc__
    
    def test_retrieve_has_docstring(self):
        """Verify retrieve() method has docstring."""
        assert RecencyPrunePolicy.retrieve.__doc__ is not None
        assert "shared_retrieve" in RecencyPrunePolicy.retrieve.__doc__
    
    def test_write_has_docstring(self):
        """Verify write() method has docstring."""
        assert RecencyPrunePolicy.write.__doc__ is not None
        assert "store" in RecencyPrunePolicy.write.__doc__.lower()
    
    def test_maintain_has_docstring(self):
        """Verify maintain() method has docstring."""
        assert RecencyPrunePolicy.maintain.__doc__ is not None
        assert "recency" in RecencyPrunePolicy.maintain.__doc__.lower() or "oldest" in RecencyPrunePolicy.maintain.__doc__.lower()
        assert "sequence_index" in RecencyPrunePolicy.maintain.__doc__


class TestRecencyPrunePolicyVsRandomPrune:
    """Test that Recency Prune behaves differently from Random Prune."""
    
    def test_recency_prune_is_deterministic_unlike_random_prune(self):
        """Verify Recency Prune is deterministic (unlike Random Prune)."""
        # Recency Prune should always produce the same result
        policy = RecencyPrunePolicy(max_records=5)
        
        # Run 1
        store1 = MockMemoryStore()
        for i in range(10):
            store1.records.append(create_mock_record(f"mem-{i:03d}", i))
        policy.maintain(store1)
        archived1 = sorted([r.sequence_index for r in store1.archived_records])
        
        # Run 2
        store2 = MockMemoryStore()
        for i in range(10):
            store2.records.append(create_mock_record(f"mem-{i:03d}", i))
        policy.maintain(store2)
        archived2 = sorted([r.sequence_index for r in store2.archived_records])
        
        # Should be identical (deterministic)
        assert archived1 == archived2
        assert archived1 == [0, 1, 2, 3, 4]
    
    def test_recency_prune_archives_oldest_not_random(self):
        """Verify Recency Prune archives oldest, not random selection."""
        policy = RecencyPrunePolicy(max_records=5)
        store = MockMemoryStore()
        
        # Add 10 records
        for i in range(10):
            store.records.append(create_mock_record(f"mem-{i:03d}", i))
        
        policy.maintain(store)
        
        # Should archive the 5 oldest (0-4), not a random selection
        archived_seq_indices = sorted([r.sequence_index for r in store.archived_records])
        assert archived_seq_indices == [0, 1, 2, 3, 4]
        
        # Active should be the 5 newest (5-9)
        active_seq_indices = sorted([r.sequence_index for r in store.active_records()])
        assert active_seq_indices == [5, 6, 7, 8, 9]
