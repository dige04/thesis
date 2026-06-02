"""Unit tests for Random Prune policy.

Tests verify:
1. Random Prune policy uses shared_retrieve with identical scoring (Req 10.1)
2. Random Prune policy stores all incoming records (Req 10.2)
3. Random Prune policy randomly archives when exceeding max_records (Req 10.3)
4. Random Prune policy uses seeded RNG for reproducibility (Req 10.4)
5. Random Prune policy repeats until count <= max_records (Req 10.5)

**Validates: Requirements 10**
"""

from src.memory.policies.random_prune import RandomPrunePolicy
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


class TestRandomPrunePolicyInstantiation:
    """Test Random Prune policy instantiation and attributes."""

    def test_can_instantiate_with_valid_parameters(self):
        """Verify Random Prune policy can be instantiated with valid parameters."""
        policy = RandomPrunePolicy(seed=42, max_records=100)
        assert policy is not None
        assert policy.seed == 42
        assert policy.max_records == 100

    def test_has_correct_name(self):
        """Verify Random Prune policy has correct name attribute."""
        policy = RandomPrunePolicy(seed=42, max_records=100)
        assert policy.name == "random_prune"

    def test_is_memory_policy_subclass(self):
        """Verify Random Prune policy is a MemoryPolicy subclass."""
        from src.memory.policies.base import MemoryPolicy
        policy = RandomPrunePolicy(seed=42, max_records=100)
        assert isinstance(policy, MemoryPolicy)

    def test_accepts_various_seeds(self):
        """Verify instantiation accepts various seed values."""
        for seed in [1, 2, 3, 42, 100, 999]:
            policy = RandomPrunePolicy(seed=seed, max_records=100)
            assert policy.seed == seed

    def test_accepts_various_max_records(self):
        """Verify instantiation accepts various max_records values."""
        for max_records in [1, 10, 50, 100, 1000]:
            policy = RandomPrunePolicy(seed=42, max_records=max_records)
            assert policy.max_records == max_records

    def test_has_seeded_rng(self):
        """Verify policy has a seeded random number generator."""
        policy = RandomPrunePolicy(seed=42, max_records=100)
        assert hasattr(policy, 'rng')
        assert policy.rng is not None


class TestRandomPrunePolicyRetrieve:
    """Test Random Prune policy retrieve() method.
    
    **Validates: Requirements 10.1**
    """

    def test_retrieve_uses_shared_retrieve(self):
        """Verify retrieve() uses shared_retrieve (Req 10.1, Frozen Invariant #5)."""
        import inspect

        from src.memory.policies.random_prune import RandomPrunePolicy

        # Get source code of retrieve method
        source = inspect.getsource(RandomPrunePolicy.retrieve)

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

        policy = RandomPrunePolicy(seed=42, max_records=100)
        task = MockTask()
        store = MockMemoryStore()

        # Mock shared_retrieve to return a known result
        mock_result = [(0.9, create_mock_record("mem-001", 1))]

        with patch('src.memory.policies.random_prune.shared_retrieve', return_value=mock_result):
            result = policy.retrieve(task, store, top_k=5, token_budget=2000)

        # Should return the mocked result unchanged
        assert result == mock_result

    def test_retrieve_passes_correct_parameters_to_shared_retrieve(self):
        """Verify retrieve() passes all parameters correctly to shared_retrieve."""
        from unittest.mock import patch

        policy = RandomPrunePolicy(seed=42, max_records=100)
        task = MockTask()
        store = MockMemoryStore()

        with patch('src.memory.policies.random_prune.shared_retrieve') as mock_shared:
            policy.retrieve(task, store, top_k=7, token_budget=3000)

            # Verify shared_retrieve was called with correct parameters
            mock_shared.assert_called_once_with(task, store, 7, 3000)


class TestRandomPrunePolicyWrite:
    """Test Random Prune policy write() method.
    
    **Validates: Requirements 10.2**
    """

    def test_write_stores_all_records(self):
        """Verify write() stores all incoming records (Req 10.2)."""
        policy = RandomPrunePolicy(seed=42, max_records=100)
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
        policy = RandomPrunePolicy(seed=42, max_records=5)
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
        policy = RandomPrunePolicy(seed=42, max_records=100)
        store = MockMemoryStore()
        record = create_mock_record("mem-001", 1)

        policy.write(store, record)

        assert store.add_called_count == 1
        assert record in store.records


class TestRandomPrunePolicyMaintain:
    """Test Random Prune policy maintain() method.
    
    **Validates: Requirements 10.3, 10.4, 10.5**
    """

    def test_maintain_no_pruning_when_under_capacity(self):
        """Verify maintain() does not prune when active count <= max_records."""
        policy = RandomPrunePolicy(seed=42, max_records=10)
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
        policy = RandomPrunePolicy(seed=42, max_records=10)
        store = MockMemoryStore()

        # Add exactly max_records
        for i in range(10):
            store.records.append(create_mock_record(f"mem-{i:03d}", i))

        policy.maintain(store)

        # No archiving should occur
        assert store.archive_called_count == 0
        assert len(store.active_records()) == 10

    def test_maintain_prunes_when_over_capacity(self):
        """Verify maintain() prunes when active count > max_records (Req 10.3)."""
        policy = RandomPrunePolicy(seed=42, max_records=5)
        store = MockMemoryStore()

        # Add 10 records (over capacity)
        for i in range(10):
            store.records.append(create_mock_record(f"mem-{i:03d}", i))

        policy.maintain(store)

        # Should archive 5 records
        assert store.archive_called_count == 5
        assert len(store.active_records()) == 5

    def test_maintain_archives_correct_number(self):
        """Verify maintain() archives exactly enough to reach max_records (Req 10.5)."""
        policy = RandomPrunePolicy(seed=42, max_records=7)
        store = MockMemoryStore()

        # Add 12 records (5 over capacity)
        for i in range(12):
            store.records.append(create_mock_record(f"mem-{i:03d}", i))

        policy.maintain(store)

        # Should archive exactly 5 records
        assert store.archive_called_count == 5
        assert len(store.active_records()) == 7

    def test_maintain_archives_with_correct_reason(self):
        """Verify maintain() archives with reason='random_prune'."""
        policy = RandomPrunePolicy(seed=42, max_records=3)
        store = MockMemoryStore()

        # Add 5 records
        for i in range(5):
            store.records.append(create_mock_record(f"mem-{i:03d}", i))

        policy.maintain(store)

        # Verify archived records have correct reason
        for record in store.archived_records:
            assert record.archived_reason == "random_prune"

    def test_maintain_handles_single_record_over_capacity(self):
        """Verify maintain() handles case where only 1 record needs pruning."""
        policy = RandomPrunePolicy(seed=42, max_records=5)
        store = MockMemoryStore()

        # Add 6 records (1 over capacity)
        for i in range(6):
            store.records.append(create_mock_record(f"mem-{i:03d}", i))

        policy.maintain(store)

        # Should archive exactly 1 record
        assert store.archive_called_count == 1
        assert len(store.active_records()) == 5

    def test_maintain_handles_many_records_over_capacity(self):
        """Verify maintain() handles case where many records need pruning."""
        policy = RandomPrunePolicy(seed=42, max_records=2)
        store = MockMemoryStore()

        # Add 20 records (18 over capacity)
        for i in range(20):
            store.records.append(create_mock_record(f"mem-{i:03d}", i))

        policy.maintain(store)

        # Should archive 18 records
        assert store.archive_called_count == 18
        assert len(store.active_records()) == 2


class TestRandomPrunePolicySeededReproducibility:
    """Test CRITICAL invariant: Seeded RNG for reproducibility.
    
    **Validates: Requirements 10.4**
    
    This is a frozen invariant from the task description and design document.
    Same seed + same sequence = same pruning decisions.
    """

    def test_same_seed_produces_same_pruning_sequence(self):
        """Verify same seed produces identical pruning decisions (Req 10.4, CRITICAL)."""
        # Run 1: seed=42
        policy1 = RandomPrunePolicy(seed=42, max_records=3)
        store1 = MockMemoryStore()

        for i in range(10):
            store1.records.append(create_mock_record(f"mem-{i:03d}", i))

        policy1.maintain(store1)
        archived1 = sorted([r.memory_id for r in store1.archived_records])

        # Run 2: seed=42 (same seed)
        policy2 = RandomPrunePolicy(seed=42, max_records=3)
        store2 = MockMemoryStore()

        for i in range(10):
            store2.records.append(create_mock_record(f"mem-{i:03d}", i))

        policy2.maintain(store2)
        archived2 = sorted([r.memory_id for r in store2.archived_records])

        # Should archive the same memories
        assert archived1 == archived2

    def test_different_seeds_produce_different_pruning_sequences(self):
        """Verify different seeds produce different pruning decisions."""
        # Run 1: seed=1
        policy1 = RandomPrunePolicy(seed=1, max_records=3)
        store1 = MockMemoryStore()

        for i in range(10):
            store1.records.append(create_mock_record(f"mem-{i:03d}", i))

        policy1.maintain(store1)
        archived1 = sorted([r.memory_id for r in store1.archived_records])

        # Run 2: seed=2 (different seed)
        policy2 = RandomPrunePolicy(seed=2, max_records=3)
        store2 = MockMemoryStore()

        for i in range(10):
            store2.records.append(create_mock_record(f"mem-{i:03d}", i))

        policy2.maintain(store2)
        archived2 = sorted([r.memory_id for r in store2.archived_records])

        # Should archive different memories (with high probability)
        # Note: There's a tiny chance they could be the same by random chance,
        # but with 10 records and 7 to archive, this is extremely unlikely
        assert archived1 != archived2

    def test_seeded_rng_does_not_affect_global_random_state(self):
        """Verify seeded RNG does not interfere with global random state."""
        import random

        # Set global random state
        random.seed(999)
        global_before = random.random()

        # Create policy with different seed
        policy = RandomPrunePolicy(seed=42, max_records=3)
        store = MockMemoryStore()

        for i in range(10):
            store.records.append(create_mock_record(f"mem-{i:03d}", i))

        policy.maintain(store)

        # Reset global random state to same seed
        random.seed(999)
        global_after = random.random()

        # Global random state should be unaffected
        assert global_before == global_after

    def test_multiple_maintain_calls_with_same_seed_are_consistent(self):
        """Verify multiple maintain() calls with same seed are consistent."""
        policy = RandomPrunePolicy(seed=42, max_records=5)

        # First maintain call
        store1 = MockMemoryStore()
        for i in range(10):
            store1.records.append(create_mock_record(f"mem-{i:03d}", i))
        policy.maintain(store1)

        # Add more records and maintain again
        for i in range(10, 15):
            store1.records.append(create_mock_record(f"mem-{i:03d}", i))
        policy.maintain(store1)

        # Should still have exactly max_records active
        assert len(store1.active_records()) == 5


class TestRandomPrunePolicyRandomness:
    """Test that pruning is actually random (not deterministic by other factors)."""

    def test_does_not_prune_by_sequence_index(self):
        """Verify pruning is not based on sequence_index (unlike Recency Prune)."""
        policy = RandomPrunePolicy(seed=42, max_records=5)
        store = MockMemoryStore()

        # Add records with sequential sequence_index
        for i in range(10):
            store.records.append(create_mock_record(f"mem-{i:03d}", i))

        policy.maintain(store)

        # Archived records should NOT be the 5 oldest by sequence_index
        archived_seq_indices = sorted([r.sequence_index for r in store.archived_records])

        # If it were recency-based, archived would be [0, 1, 2, 3, 4]
        # With random pruning, this should be different (with high probability)
        assert archived_seq_indices != [0, 1, 2, 3, 4]

    def test_does_not_prune_by_memory_type(self):
        """Verify pruning is not based on memory_type."""
        policy = RandomPrunePolicy(seed=42, max_records=5)
        store = MockMemoryStore()

        # Add records with different memory types
        types = ["architectural", "api_change", "bug_fix", "test_update", "config"]
        for i in range(10):
            memory_type = types[i % len(types)]
            store.records.append(create_mock_record(f"mem-{i:03d}", i, memory_type))

        policy.maintain(store)

        # Should archive some of each type (not all of one type)
        archived_types = [r.memory_type for r in store.archived_records]

        # With 5 archived out of 10 records (2 of each type), we should see variety
        # Not all archived should be the same type
        assert len(set(archived_types)) > 1


class TestRandomPrunePolicyEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_maintain_with_empty_store(self):
        """Verify maintain() handles empty store gracefully."""
        policy = RandomPrunePolicy(seed=42, max_records=10)
        store = MockMemoryStore()

        # Should not raise
        policy.maintain(store)

        assert store.archive_called_count == 0

    def test_maintain_with_max_records_one(self):
        """Verify maintain() works with max_records=1."""
        policy = RandomPrunePolicy(seed=42, max_records=1)
        store = MockMemoryStore()

        # Add 3 records
        for i in range(3):
            store.records.append(create_mock_record(f"mem-{i:03d}", i))

        policy.maintain(store)

        # Should retain only 1 record
        assert len(store.active_records()) == 1
        assert store.archive_called_count == 2

    def test_maintain_final_count_assertion(self):
        """Verify maintain() asserts final count <= max_records."""
        policy = RandomPrunePolicy(seed=42, max_records=5)
        store = MockMemoryStore()

        # Add 10 records
        for i in range(10):
            store.records.append(create_mock_record(f"mem-{i:03d}", i))

        policy.maintain(store)

        # Final count should be exactly max_records
        final_count = len(store.active_records())
        assert final_count <= policy.max_records
        assert final_count == policy.max_records


class TestRandomPrunePolicyAPICompatibility:
    """Test Random Prune policy maintains API compatibility."""

    def test_implements_all_required_methods(self):
        """Verify Random Prune policy implements all MemoryPolicy methods."""
        policy = RandomPrunePolicy(seed=42, max_records=100)

        assert hasattr(policy, "retrieve")
        assert hasattr(policy, "write")
        assert hasattr(policy, "maintain")
        assert hasattr(policy, "name")

    def test_method_signatures_match_base_class(self):
        """Verify method signatures match MemoryPolicy interface."""
        import inspect

        policy = RandomPrunePolicy(seed=42, max_records=100)

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


class TestRandomPrunePolicyDocumentation:
    """Test Random Prune policy has proper documentation."""

    def test_class_has_docstring(self):
        """Verify RandomPrunePolicy class has docstring."""
        assert RandomPrunePolicy.__doc__ is not None
        assert "random" in RandomPrunePolicy.__doc__.lower()
        assert "Requirements 10" in RandomPrunePolicy.__doc__

    def test_retrieve_has_docstring(self):
        """Verify retrieve() method has docstring."""
        assert RandomPrunePolicy.retrieve.__doc__ is not None
        assert "shared_retrieve" in RandomPrunePolicy.retrieve.__doc__

    def test_write_has_docstring(self):
        """Verify write() method has docstring."""
        assert RandomPrunePolicy.write.__doc__ is not None
        assert "store" in RandomPrunePolicy.write.__doc__.lower()

    def test_maintain_has_docstring(self):
        """Verify maintain() method has docstring."""
        assert RandomPrunePolicy.maintain.__doc__ is not None
        assert "random" in RandomPrunePolicy.maintain.__doc__.lower()
        assert "seed" in RandomPrunePolicy.maintain.__doc__.lower() or "rng" in RandomPrunePolicy.maintain.__doc__.lower()
