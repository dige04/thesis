"""Unit tests for No Memory policy.

Tests verify:
1. No Memory policy returns empty list for all retrieval requests (Req 8.1)
2. No Memory policy discards all write requests (Req 8.2)
3. No Memory policy performs no maintenance operations (Req 8.3)
4. No Memory policy maintains API compatibility with other policies
5. No Memory policy is properly instantiable and has correct name

**Validates: Requirements 8**
"""

import pytest

from src.memory.policies.no_memory import NoMemoryPolicy


class MockTask:
    """Mock task object for testing."""
    def __init__(self):
        self.repo = "test/repo"
        self.issue_text = "Test issue"


class MockMemoryStore:
    """Mock memory store for testing."""
    def __init__(self):
        self.records = []
        self.add_called = False
        self.archive_called = False

    def add(self, record):
        """Mock add method."""
        self.add_called = True
        self.records.append(record)

    def archive(self, memory_id, reason):
        """Mock archive method."""
        self.archive_called = True


class MockMemoryRecord:
    """Mock memory record for testing."""
    def __init__(self):
        self.memory_id = "test-mem-001"
        self.task_id = "test-task-001"
        self.repo = "test/repo"


class TestNoMemoryPolicyInstantiation:
    """Test No Memory policy instantiation and attributes."""

    def test_can_instantiate(self):
        """Verify No Memory policy can be instantiated."""
        policy = NoMemoryPolicy()
        assert policy is not None

    def test_has_correct_name(self):
        """Verify No Memory policy has correct name attribute."""
        policy = NoMemoryPolicy()
        assert policy.name == "no_memory"

    def test_is_memory_policy_subclass(self):
        """Verify No Memory policy is a MemoryPolicy subclass."""
        from src.memory.policies.base import MemoryPolicy
        policy = NoMemoryPolicy()
        assert isinstance(policy, MemoryPolicy)


class TestNoMemoryPolicyRetrieve:
    """Test No Memory policy retrieve() method.

    **Validates: Requirements 8.1**
    """

    def test_retrieve_returns_empty_list(self):
        """Verify retrieve() returns empty list (Req 8.1)."""
        policy = NoMemoryPolicy()
        task = MockTask()
        store = MockMemoryStore()

        result = policy.retrieve(task, store, top_k=5, token_budget=2000)

        assert result == []
        assert isinstance(result, list)
        assert len(result) == 0

    def test_retrieve_ignores_top_k_parameter(self):
        """Verify retrieve() returns empty list regardless of top_k."""
        policy = NoMemoryPolicy()
        task = MockTask()
        store = MockMemoryStore()

        # Test with different top_k values
        for top_k in [1, 5, 10, 100]:
            result = policy.retrieve(task, store, top_k=top_k, token_budget=2000)
            assert result == []

    def test_retrieve_ignores_token_budget_parameter(self):
        """Verify retrieve() returns empty list regardless of token_budget."""
        policy = NoMemoryPolicy()
        task = MockTask()
        store = MockMemoryStore()

        # Test with different token budgets
        for budget in [100, 1000, 5000, 10000]:
            result = policy.retrieve(task, store, top_k=5, token_budget=budget)
            assert result == []

    def test_retrieve_does_not_access_memory_store(self):
        """Verify retrieve() does not interact with memory store."""
        policy = NoMemoryPolicy()
        task = MockTask()
        store = MockMemoryStore()

        # Add some records to store
        store.records = [MockMemoryRecord() for _ in range(10)]

        result = policy.retrieve(task, store, top_k=5, token_budget=2000)

        # Should still return empty list, ignoring store contents
        assert result == []

    def test_retrieve_with_none_task(self):
        """Verify retrieve() handles None task gracefully."""
        policy = NoMemoryPolicy()
        store = MockMemoryStore()

        # Should not raise, just return empty list
        result = policy.retrieve(None, store, top_k=5, token_budget=2000)
        assert result == []

    def test_retrieve_with_none_store(self):
        """Verify retrieve() handles None store gracefully."""
        policy = NoMemoryPolicy()
        task = MockTask()

        # Should not raise, just return empty list
        result = policy.retrieve(task, None, top_k=5, token_budget=2000)
        assert result == []


class TestNoMemoryPolicyWrite:
    """Test No Memory policy write() method.

    **Validates: Requirements 8.2**
    """

    def test_write_discards_record(self):
        """Verify write() discards all records (Req 8.2)."""
        policy = NoMemoryPolicy()
        store = MockMemoryStore()
        record = MockMemoryRecord()

        # Call write
        policy.write(store, record)

        # Verify record was NOT added to store
        assert not store.add_called
        assert len(store.records) == 0

    def test_write_returns_none(self):
        """Verify write() returns None for API compatibility (Req 8.2)."""
        policy = NoMemoryPolicy()
        store = MockMemoryStore()
        record = MockMemoryRecord()

        result = policy.write(store, record)

        # Should return None (success acknowledgment)
        assert result is None

    def test_write_multiple_records_all_discarded(self):
        """Verify write() discards all records when called multiple times."""
        policy = NoMemoryPolicy()
        store = MockMemoryStore()

        # Write multiple records
        for i in range(10):
            record = MockMemoryRecord()
            record.memory_id = f"test-mem-{i:03d}"
            policy.write(store, record)

        # Verify all records were discarded
        assert not store.add_called
        assert len(store.records) == 0

    def test_write_does_not_raise_exception(self):
        """Verify write() does not raise exceptions."""
        policy = NoMemoryPolicy()
        store = MockMemoryStore()
        record = MockMemoryRecord()

        # Should not raise
        try:
            policy.write(store, record)
        except Exception as e:
            pytest.fail(f"write() raised unexpected exception: {e}")

    def test_write_with_none_record(self):
        """Verify write() handles None record gracefully."""
        policy = NoMemoryPolicy()
        store = MockMemoryStore()

        # Should not raise, just discard silently
        result = policy.write(store, None)
        assert result is None
        assert not store.add_called

    def test_write_with_none_store(self):
        """Verify write() handles None store gracefully."""
        policy = NoMemoryPolicy()
        record = MockMemoryRecord()

        # Should not raise, just discard silently
        result = policy.write(None, record)
        assert result is None


class TestNoMemoryPolicyMaintain:
    """Test No Memory policy maintain() method.

    **Validates: Requirements 8.3**
    """

    def test_maintain_is_noop(self):
        """Verify maintain() performs no operations (Req 8.3)."""
        policy = NoMemoryPolicy()
        store = MockMemoryStore()

        # Add some records to store
        store.records = [MockMemoryRecord() for _ in range(10)]

        # Call maintain
        policy.maintain(store)

        # Verify no archiving occurred
        assert not store.archive_called
        # Verify records unchanged
        assert len(store.records) == 10

    def test_maintain_returns_none(self):
        """Verify maintain() returns None."""
        policy = NoMemoryPolicy()
        store = MockMemoryStore()

        result = policy.maintain(store)

        assert result is None

    def test_maintain_does_not_raise_exception(self):
        """Verify maintain() does not raise exceptions."""
        policy = NoMemoryPolicy()
        store = MockMemoryStore()

        # Should not raise
        try:
            policy.maintain(store)
        except Exception as e:
            pytest.fail(f"maintain() raised unexpected exception: {e}")

    def test_maintain_with_none_store(self):
        """Verify maintain() handles None store gracefully."""
        policy = NoMemoryPolicy()

        # Should not raise, just no-op
        result = policy.maintain(None)
        assert result is None

    def test_maintain_called_multiple_times(self):
        """Verify maintain() can be called multiple times without side effects."""
        policy = NoMemoryPolicy()
        store = MockMemoryStore()

        # Call maintain multiple times
        for _ in range(10):
            policy.maintain(store)

        # Should still be no-op
        assert not store.archive_called


class TestNoMemoryPolicyAPICompatibility:
    """Test No Memory policy maintains API compatibility with other policies."""

    def test_implements_all_required_methods(self):
        """Verify No Memory policy implements all MemoryPolicy methods."""
        policy = NoMemoryPolicy()

        assert hasattr(policy, "retrieve")
        assert hasattr(policy, "write")
        assert hasattr(policy, "maintain")
        assert hasattr(policy, "name")

    def test_method_signatures_match_base_class(self):
        """Verify method signatures match MemoryPolicy interface."""
        import inspect

        policy = NoMemoryPolicy()

        # Get method signatures from implementation
        impl_retrieve = inspect.signature(policy.retrieve)
        impl_write = inspect.signature(policy.write)
        impl_maintain = inspect.signature(policy.maintain)

        # Verify retrieve has correct parameters (excluding 'self')
        retrieve_params = list(impl_retrieve.parameters.keys())
        assert 'task' in retrieve_params
        assert 'memory_store' in retrieve_params
        assert 'top_k' in retrieve_params
        assert 'token_budget' in retrieve_params

        # Verify write has correct parameters (excluding 'self')
        write_params = list(impl_write.parameters.keys())
        assert 'memory_store' in write_params
        assert 'record' in write_params

        # Verify maintain has correct parameters (excluding 'self')
        maintain_params = list(impl_maintain.parameters.keys())
        assert 'memory_store' in maintain_params

    def test_can_be_used_in_policy_list(self):
        """Verify No Memory policy can be used alongside other policies."""
        from src.memory.policies.base import MemoryPolicy

        policy = NoMemoryPolicy()

        # Should be usable in a list of policies
        policies = [policy]
        assert len(policies) == 1
        assert isinstance(policies[0], MemoryPolicy)
        assert policies[0].name == "no_memory"


class TestNoMemoryPolicyFrozenInvariant:
    """Test No Memory policy frozen invariant: does NOT use shared_retrieve.

    This is the ONLY policy that does not use shared_retrieve(), because
    it has no memories to retrieve from. This is explicitly documented in
    the design (Requirement 6, Design §2.6).
    """

    def test_does_not_use_shared_retrieve(self):
        """Verify No Memory policy does NOT use shared_retrieve (by design)."""
        import inspect

        from src.memory.policies.no_memory import NoMemoryPolicy

        # Get source code of retrieve method
        source = inspect.getsource(NoMemoryPolicy.retrieve)

        # Verify it does NOT call shared_retrieve
        assert "shared_retrieve" not in source

        # Verify it returns empty list directly
        assert "return []" in source

    def test_retrieve_is_constant_time(self):
        """Verify retrieve() is O(1) - no memory access."""
        import time

        policy = NoMemoryPolicy()
        task = MockTask()
        store = MockMemoryStore()

        # Add many records to store
        store.records = [MockMemoryRecord() for _ in range(10000)]

        # Time retrieval
        start = time.time()
        result = policy.retrieve(task, store, top_k=5, token_budget=2000)
        elapsed = time.time() - start

        # Should be instant (< 1ms) regardless of store size
        assert elapsed < 0.001
        assert result == []


class TestNoMemoryPolicyDocumentation:
    """Test No Memory policy has proper documentation."""

    def test_class_has_docstring(self):
        """Verify NoMemoryPolicy class has docstring."""
        assert NoMemoryPolicy.__doc__ is not None
        assert "baseline" in NoMemoryPolicy.__doc__.lower()
        assert "Requirements 8" in NoMemoryPolicy.__doc__

    def test_retrieve_has_docstring(self):
        """Verify retrieve() method has docstring."""
        assert NoMemoryPolicy.retrieve.__doc__ is not None
        assert "empty list" in NoMemoryPolicy.retrieve.__doc__.lower()
        assert "Requirements 8.1" in NoMemoryPolicy.retrieve.__doc__

    def test_write_has_docstring(self):
        """Verify write() method has docstring."""
        assert NoMemoryPolicy.write.__doc__ is not None
        assert "discard" in NoMemoryPolicy.write.__doc__.lower()
        assert "Requirements 8.2" in NoMemoryPolicy.write.__doc__

    def test_maintain_has_docstring(self):
        """Verify maintain() method has docstring."""
        assert NoMemoryPolicy.maintain.__doc__ is not None
        assert "no-op" in NoMemoryPolicy.maintain.__doc__.lower() or "no maintenance" in NoMemoryPolicy.maintain.__doc__.lower()
        assert "Requirements 8.3" in NoMemoryPolicy.maintain.__doc__
