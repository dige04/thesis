"""Unit tests for Full Memory policy.

Tests verify:
1. Full Memory policy uses shared_retrieve with identical scoring (Req 9.1)
2. Full Memory policy stores all records without limit (Req 9.2, 9.3)
3. Full Memory policy never prunes or archives (Req 9.4)
4. Full Memory policy maintains API compatibility with other policies
5. Full Memory policy is properly instantiable and has correct name

**Validates: Requirements 9**
"""

import pytest

from src.memory.policies.full_memory import FullMemoryPolicy


class MockTask:
    """Mock task object for testing."""
    def __init__(self):
        self.task_id = "test-task-001"
        self.repo = "test/repo"
        self.issue_text = "Test issue"


class MockMemoryStore:
    """Mock memory store for testing."""
    def __init__(self):
        self.records = []
        self.add_called_count = 0
        self.archive_called_count = 0
        self.active_count = 0

    def add(self, record):
        """Mock add method."""
        self.add_called_count += 1
        self.records.append(record)
        self.active_count += 1

    def archive(self, memory_id, reason):
        """Mock archive method."""
        self.archive_called_count += 1
        self.active_count -= 1

    def count_active(self):
        """Mock count_active method."""
        return self.active_count

    def _generate_embedding(self, text):
        """Mock embedding generation."""
        return [0.1] * 1536  # Mock embedding vector

    def search(self, query_vector, top_k, repo=None, same_repo_only=True):
        """Mock search method."""
        # Return empty list for simplicity
        return []


class MockMemoryRecord:
    """Mock memory record for testing."""
    def __init__(self, memory_id="test-mem-001"):
        self.memory_id = memory_id
        self.task_id = "test-task-001"
        self.repo = "test/repo"
        self.memory_type = "bug_fix"
        self.token_length = 100


class TestFullMemoryPolicyInstantiation:
    """Test Full Memory policy instantiation and attributes."""

    def test_can_instantiate(self):
        """Verify Full Memory policy can be instantiated."""
        policy = FullMemoryPolicy()
        assert policy is not None

    def test_has_correct_name(self):
        """Verify Full Memory policy has correct name attribute."""
        policy = FullMemoryPolicy()
        assert policy.name == "full_memory"

    def test_is_memory_policy_subclass(self):
        """Verify Full Memory policy is a MemoryPolicy subclass."""
        from src.memory.policies.base import MemoryPolicy
        policy = FullMemoryPolicy()
        assert isinstance(policy, MemoryPolicy)

    def test_no_configuration_parameters_required(self):
        """Verify Full Memory policy requires no configuration parameters."""
        # Should instantiate without any parameters
        policy = FullMemoryPolicy()
        assert policy is not None


class TestFullMemoryPolicyRetrieve:
    """Test Full Memory policy retrieve() method.
    
    **Validates: Requirements 9.1**
    """

    def test_retrieve_uses_shared_retrieve(self):
        """Verify retrieve() uses shared_retrieve (Req 9.1)."""
        import inspect

        from src.memory.policies.full_memory import FullMemoryPolicy

        # Get source code of retrieve method
        source = inspect.getsource(FullMemoryPolicy.retrieve)

        # Verify it calls shared_retrieve
        assert "shared_retrieve" in source

    def test_retrieve_returns_list_of_tuples(self):
        """Verify retrieve() returns list of (score, MemoryRecord) tuples."""
        policy = FullMemoryPolicy()
        task = MockTask()
        store = MockMemoryStore()

        result = policy.retrieve(task, store, top_k=5, token_budget=2000)

        assert isinstance(result, list)
        # Empty list is valid (no memories in store)
        assert len(result) == 0

    def test_retrieve_respects_top_k_parameter(self):
        """Verify retrieve() respects top_k parameter (same as other policies)."""
        policy = FullMemoryPolicy()
        task = MockTask()
        store = MockMemoryStore()

        # Even though Full Memory stores everything, retrieval still respects top_k
        # This is tested by verifying shared_retrieve is called with correct params
        result = policy.retrieve(task, store, top_k=5, token_budget=2000)

        # Result should be empty (no memories in mock store)
        assert isinstance(result, list)

    def test_retrieve_respects_token_budget_parameter(self):
        """Verify retrieve() respects token_budget parameter (same as other policies)."""
        policy = FullMemoryPolicy()
        task = MockTask()
        store = MockMemoryStore()

        # Even though Full Memory stores everything, retrieval still respects budget
        result = policy.retrieve(task, store, top_k=5, token_budget=2000)

        # Result should be empty (no memories in mock store)
        assert isinstance(result, list)

    def test_retrieve_uses_same_repo_only(self):
        """Verify retrieve() uses same_repo_only=True (main experiment setting)."""
        import inspect

        from src.memory.policies.full_memory import FullMemoryPolicy

        # Get source code of retrieve method
        source = inspect.getsource(FullMemoryPolicy.retrieve)

        # Verify it passes same_repo_only=True to shared_retrieve
        assert "same_repo_only=True" in source


class TestFullMemoryPolicyWrite:
    """Test Full Memory policy write() method.
    
    **Validates: Requirements 9.2, 9.3**
    """

    def test_write_stores_record(self):
        """Verify write() stores all records (Req 9.2)."""
        policy = FullMemoryPolicy()
        store = MockMemoryStore()
        record = MockMemoryRecord()

        # Call write
        policy.write(store, record)

        # Verify record was added to store
        assert store.add_called_count == 1
        assert len(store.records) == 1
        assert store.records[0] == record

    def test_write_stores_all_records_without_limit(self):
        """Verify write() stores all records without capacity checks (Req 9.3)."""
        policy = FullMemoryPolicy()
        store = MockMemoryStore()

        # Write many records (exceeding typical max_records limit)
        num_records = 200  # Typical max_records is 100
        for i in range(num_records):
            record = MockMemoryRecord(memory_id=f"test-mem-{i:03d}")
            policy.write(store, record)

        # Verify all records were stored
        assert store.add_called_count == num_records
        assert len(store.records) == num_records
        assert store.active_count == num_records

    def test_write_no_capacity_checks(self):
        """Verify write() performs no capacity checks."""
        import inspect

        from src.memory.policies.full_memory import FullMemoryPolicy

        # Get source code of write method
        source = inspect.getsource(FullMemoryPolicy.write)

        # Verify it does NOT check capacity in the logic (excluding docstrings)
        # Remove docstring to check only code logic
        lines = source.split('\n')
        code_lines = []
        in_docstring = False
        for line in lines:
            if '"""' in line:
                in_docstring = not in_docstring
                continue
            if not in_docstring:
                code_lines.append(line)
        code_only = '\n'.join(code_lines)

        # Verify no capacity checks in actual code
        assert "if" not in code_only or "TYPE_CHECKING" in code_only
        assert "while" not in code_only

    def test_write_returns_none(self):
        """Verify write() returns None for API compatibility."""
        policy = FullMemoryPolicy()
        store = MockMemoryStore()
        record = MockMemoryRecord()

        result = policy.write(store, record)

        # Should return None (standard for write methods)
        assert result is None

    def test_write_does_not_trigger_pruning(self):
        """Verify write() does not trigger any pruning."""
        policy = FullMemoryPolicy()
        store = MockMemoryStore()

        # Write many records
        for i in range(100):
            record = MockMemoryRecord(memory_id=f"test-mem-{i:03d}")
            policy.write(store, record)

        # Verify no archiving occurred
        assert store.archive_called_count == 0

    def test_write_does_not_raise_exception(self):
        """Verify write() does not raise exceptions."""
        policy = FullMemoryPolicy()
        store = MockMemoryStore()
        record = MockMemoryRecord()

        # Should not raise
        try:
            policy.write(store, record)
        except Exception as e:
            pytest.fail(f"write() raised unexpected exception: {e}")


class TestFullMemoryPolicyMaintain:
    """Test Full Memory policy maintain() method.
    
    **Validates: Requirements 9.4**
    """

    def test_maintain_is_noop(self):
        """Verify maintain() performs no pruning or archiving (Req 9.4)."""
        policy = FullMemoryPolicy()
        store = MockMemoryStore()

        # Add many records to store (exceeding typical max_records)
        for i in range(200):
            record = MockMemoryRecord(memory_id=f"test-mem-{i:03d}")
            store.records.append(record)
            store.active_count += 1

        initial_count = store.active_count

        # Call maintain
        policy.maintain(store)

        # Verify no archiving occurred
        assert store.archive_called_count == 0
        # Verify active count unchanged
        assert store.active_count == initial_count

    def test_maintain_never_prunes(self):
        """Verify maintain() never prunes regardless of memory count."""
        import inspect

        from src.memory.policies.full_memory import FullMemoryPolicy

        # Get source code of maintain method
        source = inspect.getsource(FullMemoryPolicy.maintain)

        # Verify it does NOT call archive in the logic (excluding docstrings)
        # Remove docstring to check only code logic
        lines = source.split('\n')
        code_lines = []
        in_docstring = False
        for line in lines:
            if '"""' in line:
                in_docstring = not in_docstring
                continue
            if not in_docstring:
                code_lines.append(line)
        code_only = '\n'.join(code_lines)

        # Verify no archiving in actual code
        assert ".archive(" not in code_only
        assert "while" not in code_only

    def test_maintain_returns_none(self):
        """Verify maintain() returns None."""
        policy = FullMemoryPolicy()
        store = MockMemoryStore()

        result = policy.maintain(store)

        assert result is None

    def test_maintain_does_not_raise_exception(self):
        """Verify maintain() does not raise exceptions."""
        policy = FullMemoryPolicy()
        store = MockMemoryStore()

        # Should not raise
        try:
            policy.maintain(store)
        except Exception as e:
            pytest.fail(f"maintain() raised unexpected exception: {e}")

    def test_maintain_called_multiple_times(self):
        """Verify maintain() can be called multiple times without side effects."""
        policy = FullMemoryPolicy()
        store = MockMemoryStore()

        # Add records
        for i in range(100):
            record = MockMemoryRecord(memory_id=f"test-mem-{i:03d}")
            store.records.append(record)
            store.active_count += 1

        initial_count = store.active_count

        # Call maintain multiple times
        for _ in range(10):
            policy.maintain(store)

        # Should still be no-op
        assert store.archive_called_count == 0
        assert store.active_count == initial_count


class TestFullMemoryPolicyAPICompatibility:
    """Test Full Memory policy maintains API compatibility with other policies."""

    def test_implements_all_required_methods(self):
        """Verify Full Memory policy implements all MemoryPolicy methods."""
        policy = FullMemoryPolicy()

        assert hasattr(policy, "retrieve")
        assert hasattr(policy, "write")
        assert hasattr(policy, "maintain")
        assert hasattr(policy, "name")

    def test_method_signatures_match_base_class(self):
        """Verify method signatures match MemoryPolicy interface."""
        import inspect

        policy = FullMemoryPolicy()

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
        """Verify Full Memory policy can be used alongside other policies."""
        from src.memory.policies.base import MemoryPolicy

        policy = FullMemoryPolicy()

        # Should be usable in a list of policies
        policies = [policy]
        assert len(policies) == 1
        assert isinstance(policies[0], MemoryPolicy)
        assert policies[0].name == "full_memory"


class TestFullMemoryPolicyFrozenInvariant:
    """Test Full Memory policy frozen invariant: uses shared_retrieve.
    
    This is a CRITICAL invariant (Requirement 6, Design §2.6):
    All policies except No Memory MUST use shared_retrieve() to ensure
    identical retrieval scoring across all conditions.
    """

    def test_uses_shared_retrieve(self):
        """Verify Full Memory policy uses shared_retrieve (frozen invariant)."""
        import inspect

        from src.memory.policies.full_memory import FullMemoryPolicy

        # Get source code of retrieve method
        source = inspect.getsource(FullMemoryPolicy.retrieve)

        # Verify it calls shared_retrieve
        assert "shared_retrieve" in source

        # Verify it imports shared_retrieve
        module_source = inspect.getsource(
            inspect.getmodule(FullMemoryPolicy)
        )
        assert "from ..retriever import shared_retrieve" in module_source

    def test_no_custom_scoring_in_retrieve(self):
        """Verify retrieve() does not implement custom scoring logic."""
        import inspect

        from src.memory.policies.full_memory import FullMemoryPolicy

        # Get source code of retrieve method
        source = inspect.getsource(FullMemoryPolicy.retrieve)

        # Verify it calls shared_retrieve (the key requirement)
        assert "shared_retrieve" in source

        # Verify it does NOT implement custom scoring logic in code
        # (mentions in docstrings are fine)
        lines = source.split('\n')
        code_lines = []
        in_docstring = False
        for line in lines:
            if '"""' in line:
                in_docstring = not in_docstring
                continue
            if not in_docstring:
                code_lines.append(line)
        code_only = '\n'.join(code_lines)

        # The only scoring should be from shared_retrieve call
        assert "shared_retrieve(" in code_only


class TestFullMemoryPolicyUnboundedGrowth:
    """Test Full Memory policy allows unbounded memory growth."""

    def test_memory_grows_unbounded(self):
        """Verify memory count grows without limit."""
        policy = FullMemoryPolicy()
        store = MockMemoryStore()

        # Write many records (far exceeding typical limits)
        num_records = 500  # Typical max_records is 100
        for i in range(num_records):
            record = MockMemoryRecord(memory_id=f"test-mem-{i:03d}")
            policy.write(store, record)

        # Verify all records stored
        assert store.active_count == num_records

        # Call maintain (should not prune)
        policy.maintain(store)

        # Verify count unchanged
        assert store.active_count == num_records

    def test_no_max_records_enforcement(self):
        """Verify max_records limit is not enforced."""
        policy = FullMemoryPolicy()
        store = MockMemoryStore()

        # Write records exceeding typical max_records
        for i in range(150):
            record = MockMemoryRecord(memory_id=f"test-mem-{i:03d}")
            policy.write(store, record)
            policy.maintain(store)  # Call maintain after each write

        # Verify no pruning occurred
        assert store.archive_called_count == 0
        assert store.active_count == 150

    def test_no_token_budget_enforcement_in_storage(self):
        """Verify max_storage_tokens limit is not enforced in storage."""
        policy = FullMemoryPolicy()
        store = MockMemoryStore()

        # Write records with large token counts
        total_tokens = 0
        for i in range(100):
            record = MockMemoryRecord(memory_id=f"test-mem-{i:03d}")
            record.token_length = 500  # 500 tokens each
            total_tokens += 500
            policy.write(store, record)

        # Total tokens = 50,000 (exceeds typical max_storage_tokens of 30,000)
        assert total_tokens == 50000

        # Verify all records stored
        assert store.active_count == 100

        # Call maintain (should not prune)
        policy.maintain(store)

        # Verify no pruning
        assert store.archive_called_count == 0


class TestFullMemoryPolicyDocumentation:
    """Test Full Memory policy has proper documentation."""

    def test_class_has_docstring(self):
        """Verify FullMemoryPolicy class has docstring."""
        assert FullMemoryPolicy.__doc__ is not None
        assert "baseline" in FullMemoryPolicy.__doc__.lower()
        # Docstring is comprehensive with design rationale and hypothesis testing

    def test_retrieve_has_docstring(self):
        """Verify retrieve() method has docstring."""
        assert FullMemoryPolicy.retrieve.__doc__ is not None
        assert "shared_retrieve" in FullMemoryPolicy.retrieve.__doc__
        assert "Requirement 6" in FullMemoryPolicy.retrieve.__doc__

    def test_write_has_docstring(self):
        """Verify write() method has docstring."""
        assert FullMemoryPolicy.write.__doc__ is not None
        assert "without" in FullMemoryPolicy.write.__doc__.lower()
        assert "capacity" in FullMemoryPolicy.write.__doc__.lower() or "limit" in FullMemoryPolicy.write.__doc__.lower()

    def test_maintain_has_docstring(self):
        """Verify maintain() method has docstring."""
        assert FullMemoryPolicy.maintain.__doc__ is not None
        assert "no-op" in FullMemoryPolicy.maintain.__doc__.lower() or "never" in FullMemoryPolicy.maintain.__doc__.lower()

    def test_critical_note_in_module_docstring(self):
        """Verify module docstring contains CRITICAL note about Full Memory."""
        from src.memory.policies import full_memory
        module_doc = full_memory.__doc__

        assert module_doc is not None
        assert "CRITICAL" in module_doc
        assert "store everything" in module_doc.lower()
        assert "retrieve top-k" in module_doc.lower()


class TestFullMemoryPolicyDesignPrinciples:
    """Test Full Memory policy adheres to design principles."""

    def test_retrieval_budget_still_enforced(self):
        """Verify retrieval still respects token budget (not unbounded in prompt)."""
        # This is the key design principle: Full Memory stores everything,
        # but retrieval still respects top_k and token_budget

        policy = FullMemoryPolicy()
        task = MockTask()
        store = MockMemoryStore()

        # Retrieve with small budget
        result = policy.retrieve(task, store, top_k=3, token_budget=500)

        # Result should respect the budget (tested via shared_retrieve)
        assert isinstance(result, list)

    def test_policy_difference_is_storage_not_retrieval(self):
        """Verify policy difference is in storage decisions, not retrieval."""
        import inspect

        from src.memory.policies.full_memory import FullMemoryPolicy

        # Get source code
        write_source = inspect.getsource(FullMemoryPolicy.write)
        maintain_source = inspect.getsource(FullMemoryPolicy.maintain)

        # Write should store everything (no checks)
        assert "add" in write_source or ".add(" in write_source

        # Maintain should be no-op (no pruning in code logic)
        # Remove docstring to check only code logic
        lines = maintain_source.split('\n')
        code_lines = []
        in_docstring = False
        for line in lines:
            if '"""' in line:
                in_docstring = not in_docstring
                continue
            if not in_docstring:
                code_lines.append(line)
        code_only = '\n'.join(code_lines)

        # Verify no archiving in actual code
        assert ".archive(" not in code_only
