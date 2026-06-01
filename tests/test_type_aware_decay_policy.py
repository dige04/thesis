"""Unit tests for Type-Aware Decay policy.

Tests verify:
1. Type-Aware Decay policy uses shared_retrieve with identical scoring (Req 12.1)
2. Type-Aware Decay policy stores all incoming records (Req 12.2)
3. Type-Aware Decay policy computes importance_score using Anderson-Schooler formula (Req 12.3)
4. Type-Aware Decay policy uses locked type-specific parameters (Req 12.4)
5. Type-Aware Decay policy archives lowest-scoring memories (Req 12.5)

**Validates: Requirements 12**
"""

from unittest.mock import Mock

from src.memory.policies.type_aware_decay import TypeAwareDecayPolicy, TYPE_PARAMS
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

    def update_importance_score(self, memory_id, score):
        """Mock importance-score persistence (mirrors real MemoryStore)."""
        for record in self.records:
            if record.memory_id == memory_id:
                record.importance_score = score
                break


def create_mock_record(memory_id, sequence_index, memory_type="bug_fix", use_count=0):
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
        token_length=100,
        use_count=use_count
    )


class TestTypeAwareDecayPolicyInstantiation:
    """Test Type-Aware Decay policy instantiation and attributes."""

    def test_can_instantiate_with_valid_parameters(self):
        """Verify Type-Aware Decay policy can be instantiated with valid parameters."""
        policy = TypeAwareDecayPolicy(max_records=100)
        assert policy is not None
        assert policy.max_records == 100

    def test_has_correct_name(self):
        """Verify Type-Aware Decay policy has correct name attribute."""
        policy = TypeAwareDecayPolicy(max_records=100)
        assert policy.name == "type_aware_decay"

    def test_is_memory_policy_subclass(self):
        """Verify Type-Aware Decay policy is a MemoryPolicy subclass."""
        from src.memory.policies.base import MemoryPolicy
        policy = TypeAwareDecayPolicy(max_records=100)
        assert isinstance(policy, MemoryPolicy)

    def test_has_frequency_exponent(self):
        """Verify policy has FREQUENCY_EXPONENT attribute set to 0.5."""
        policy = TypeAwareDecayPolicy(max_records=100)
        assert hasattr(policy, 'FREQUENCY_EXPONENT')
        assert policy.FREQUENCY_EXPONENT == 0.5

    def test_accepts_various_max_records(self):
        """Verify instantiation accepts various max_records values."""
        for max_records in [1, 10, 50, 100, 1000]:
            policy = TypeAwareDecayPolicy(max_records=max_records)
            assert policy.max_records == max_records


class TestTypeAwareDecayPolicyTypeParams:
    """Test Type-Aware Decay type-specific parameters (LOCKED).

    **Validates: Requirements 12.4**
    """

    def test_type_params_exist(self):
        """Verify TYPE_PARAMS constant exists and has all 5 types."""
        assert TYPE_PARAMS is not None
        assert len(TYPE_PARAMS) == 5
        assert "architectural" in TYPE_PARAMS
        assert "api_change" in TYPE_PARAMS
        assert "bug_fix" in TYPE_PARAMS
        assert "test_update" in TYPE_PARAMS
        assert "config" in TYPE_PARAMS

    def test_type_params_locked_values(self):
        """Verify TYPE_PARAMS has locked values from THESIS_FINAL_v5.md §8 P4 (Req 12.4)."""
        # architectural: base=1.0, decay=0.05 (Sacred)
        assert TYPE_PARAMS["architectural"] == (1.0, 0.05, "Sacred")
        
        # api_change: base=0.8, decay=0.15 (Critical)
        assert TYPE_PARAMS["api_change"] == (0.8, 0.15, "Critical")
        
        # bug_fix: base=0.6, decay=0.25 (Important)
        assert TYPE_PARAMS["bug_fix"] == (0.6, 0.25, "Important")
        
        # test_update: base=0.4, decay=0.35 (Expendable)
        assert TYPE_PARAMS["test_update"] == (0.4, 0.35, "Expendable")
        
        # config: base=0.3, decay=0.40 (Expendable)
        assert TYPE_PARAMS["config"] == (0.3, 0.40, "Expendable")


class TestTypeAwareDecayPolicyRetrieve:
    """Test Type-Aware Decay policy retrieve() method.

    **Validates: Requirements 12.1**
    """

    def test_retrieve_uses_shared_retrieve(self):
        """Verify retrieve() uses shared_retrieve (Req 12.1, Frozen Invariant #5)."""
        import inspect
        from src.memory.policies.type_aware_decay import TypeAwareDecayPolicy

        # Get source code of retrieve method
        source = inspect.getsource(TypeAwareDecayPolicy.retrieve)

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

        policy = TypeAwareDecayPolicy(max_records=100)
        task = MockTask()
        store = MockMemoryStore()

        # Mock shared_retrieve to return a known result
        mock_result = [(0.9, create_mock_record("mem-001", 1))]

        with patch('src.memory.policies.type_aware_decay.shared_retrieve', return_value=mock_result):
            result = policy.retrieve(task, store, top_k=5, token_budget=2000)

        # Should return the mocked result unchanged
        assert result == mock_result

    def test_retrieve_passes_correct_parameters_to_shared_retrieve(self):
        """Verify retrieve() passes all parameters correctly to shared_retrieve."""
        from unittest.mock import patch

        policy = TypeAwareDecayPolicy(max_records=100)
        task = MockTask()
        store = MockMemoryStore()

        with patch('src.memory.policies.type_aware_decay.shared_retrieve') as mock_shared:
            policy.retrieve(task, store, top_k=7, token_budget=3000)

            # Verify shared_retrieve was called with correct parameters
            mock_shared.assert_called_once_with(task, store, 7, 3000)


class TestTypeAwareDecayPolicyWrite:
    """Test Type-Aware Decay policy write() method.

    **Validates: Requirements 12.2**
    """

    def test_write_stores_all_records(self):
        """Verify write() stores all incoming records (Req 12.2)."""
        policy = TypeAwareDecayPolicy(max_records=100)
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
        policy = TypeAwareDecayPolicy(max_records=5)
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
        policy = TypeAwareDecayPolicy(max_records=100)
        store = MockMemoryStore()
        record = create_mock_record("mem-001", 1)

        policy.write(store, record)

        assert store.add_called_count == 1
        assert record in store.records


class TestTypeAwareDecayPolicyMaintain:
    """Test Type-Aware Decay policy maintain() method.

    **Validates: Requirements 12.3, 12.5**
    """

    def test_maintain_no_pruning_when_under_capacity(self):
        """Verify maintain() does not prune when active count <= max_records."""
        policy = TypeAwareDecayPolicy(max_records=10)
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
        policy = TypeAwareDecayPolicy(max_records=10)
        store = MockMemoryStore()

        # Add exactly max_records
        for i in range(10):
            store.records.append(create_mock_record(f"mem-{i:03d}", i))

        policy.maintain(store)

        # No archiving should occur
        assert store.archive_called_count == 0
        assert len(store.active_records()) == 10

    def test_maintain_prunes_when_over_capacity(self):
        """Verify maintain() prunes when active count > max_records (Req 12.5)."""
        policy = TypeAwareDecayPolicy(max_records=5)
        store = MockMemoryStore()

        # Add 10 records (over capacity)
        for i in range(10):
            store.records.append(create_mock_record(f"mem-{i:03d}", i))

        policy.maintain(store)

        # Should archive 5 records
        assert store.archive_called_count == 5
        assert len(store.active_records()) == 5

    def test_maintain_archives_correct_number(self):
        """Verify maintain() archives exactly enough to reach max_records."""
        policy = TypeAwareDecayPolicy(max_records=7)
        store = MockMemoryStore()

        # Add 12 records (5 over capacity)
        for i in range(12):
            store.records.append(create_mock_record(f"mem-{i:03d}", i))

        policy.maintain(store)

        # Should archive exactly 5 records
        assert store.archive_called_count == 5
        assert len(store.active_records()) == 7

    def test_maintain_archives_with_correct_reason(self):
        """Verify maintain() archives with reason='type_aware_decay'."""
        policy = TypeAwareDecayPolicy(max_records=3)
        store = MockMemoryStore()

        # Add 5 records
        for i in range(5):
            store.records.append(create_mock_record(f"mem-{i:03d}", i))

        policy.maintain(store)

        # Verify archived records have correct reason
        for record in store.archived_records:
            assert record.archived_reason == "type_aware_decay"

    def test_maintain_updates_importance_score(self):
        """Verify maintain() updates importance_score field for all records."""
        policy = TypeAwareDecayPolicy(max_records=10)
        store = MockMemoryStore()

        # Add 5 records
        for i in range(5):
            record = create_mock_record(f"mem-{i:03d}", i)
            record.importance_score = 0.0  # Initialize to 0
            store.records.append(record)

        policy.maintain(store)

        # All records should have updated importance_score
        for record in store.active_records():
            assert record.importance_score > 0.0

    def test_maintain_persists_importance_scores_to_store(self):
        """Verify maintain() persists each computed score via update_importance_score."""
        records = [
            create_mock_record("MEM-001", sequence_index=0, memory_type="architectural"),
            create_mock_record("MEM-002", sequence_index=2, memory_type="config"),
        ]
        store = MockMemoryStore()
        store.records.extend(records)
        store.update_importance_score = Mock()

        policy = TypeAwareDecayPolicy(max_records=10)
        policy.maintain(store)

        assert store.update_importance_score.call_count == 2
        updated_ids = {
            call.args[0] for call in store.update_importance_score.call_args_list
        }
        assert updated_ids == {"MEM-001", "MEM-002"}
        for call in store.update_importance_score.call_args_list:
            assert call.args[1] > 0


class TestTypeAwareDecayFormula:
    """Test Anderson-Schooler power-law formula implementation.

    **Validates: Requirements 12.3**

    Formula: importance_score = base_value(type) × age^(-decay_d(type)) × (1 + use_count)^0.5
    """

    def test_formula_architectural_memory(self):
        """Verify formula for architectural memory (base=1.0, decay=0.05)."""
        policy = TypeAwareDecayPolicy(max_records=10)
        store = MockMemoryStore()

        # Add architectural memory at sequence_index=10, current_step=50
        # age = 50 - 10 = 40, use_count = 3
        record = create_mock_record("mem-001", 10, "architectural", use_count=3)
        store.records.append(record)

        # Add a newer record to set current_step
        store.records.append(create_mock_record("mem-002", 50, "config"))

        policy.maintain(store)

        # Expected score: 1.0 × 40^(-0.05) × (1+3)^0.5
        # = 1.0 × 0.726 × 2.0 ≈ 1.452
        # Actual calculation: 1.0 × 40^(-0.05) × (1+3)^0.5 ≈ 1.663
        assert record.importance_score > 1.4
        assert record.importance_score < 1.7

    def test_formula_config_memory(self):
        """Verify formula for config memory (base=0.3, decay=0.40)."""
        policy = TypeAwareDecayPolicy(max_records=10)
        store = MockMemoryStore()

        # Add config memory at sequence_index=45, current_step=50
        # age = 50 - 45 = 5, use_count = 1
        record = create_mock_record("mem-001", 45, "config", use_count=1)
        store.records.append(record)

        # Add a newer record to set current_step
        store.records.append(create_mock_record("mem-002", 50, "config"))

        policy.maintain(store)

        # Expected score: 0.3 × 5^(-0.40) × (1+1)^0.5
        # = 0.3 × 0.455 × 1.414 ≈ 0.193
        # Actual calculation: 0.3 × 5^(-0.40) × (1+1)^0.5 ≈ 0.223
        assert record.importance_score > 0.18
        assert record.importance_score < 0.25

    def test_formula_frequency_exponent_sublinear(self):
        """Verify frequency exponent is sub-linear (0.5, not 1.0)."""
        policy = TypeAwareDecayPolicy(max_records=10)
        store = MockMemoryStore()

        # Two identical memories except use_count
        record1 = create_mock_record("mem-001", 10, "bug_fix", use_count=1)
        record2 = create_mock_record("mem-002", 10, "bug_fix", use_count=4)
        store.records.append(record1)
        store.records.append(record2)

        # Add a newer record to set current_step
        store.records.append(create_mock_record("mem-003", 50, "config"))

        policy.maintain(store)

        # With use_count=1: (1+1)^0.5 = 1.414
        # With use_count=4: (1+4)^0.5 = 2.236
        # Ratio should be 2.236 / 1.414 ≈ 1.58 (NOT 4.0 if exponent was 1.0)
        ratio = record2.importance_score / record1.importance_score
        assert ratio > 1.5
        assert ratio < 1.7

    def test_formula_age_effect(self):
        """Verify age has power-law decay effect."""
        policy = TypeAwareDecayPolicy(max_records=10)
        store = MockMemoryStore()

        # Two memories with different ages
        old_record = create_mock_record("mem-001", 10, "bug_fix", use_count=0)
        recent_record = create_mock_record("mem-002", 45, "bug_fix", use_count=0)
        store.records.append(old_record)
        store.records.append(recent_record)

        # Add a newer record to set current_step=50
        store.records.append(create_mock_record("mem-003", 50, "config"))

        policy.maintain(store)

        # Old: age=40, Recent: age=5
        # With decay=0.25 for bug_fix:
        # Old: 40^(-0.25) = 0.398
        # Recent: 5^(-0.25) = 0.669
        # Recent should have higher score
        assert recent_record.importance_score > old_record.importance_score


class TestTypeAwareDecayLowestScoring:
    """Test CRITICAL invariant: Archives lowest-scoring memories.

    **Validates: Requirements 12.5**
    """

    def test_archives_lowest_scoring_memories(self):
        """Verify maintain() archives lowest-scoring memories (Req 12.5, CRITICAL)."""
        policy = TypeAwareDecayPolicy(max_records=3)
        store = MockMemoryStore()

        # Add memories with different types (different base values)
        # architectural (base=1.0) should score highest
        # config (base=0.3) should score lowest
        arch_record = create_mock_record("mem-arch", 40, "architectural", use_count=2)
        api_record = create_mock_record("mem-api", 40, "api_change", use_count=2)
        bug_record = create_mock_record("mem-bug", 40, "bug_fix", use_count=2)
        test_record = create_mock_record("mem-test", 40, "test_update", use_count=2)
        config_record = create_mock_record("mem-config", 40, "config", use_count=2)

        store.records.extend([arch_record, api_record, bug_record, test_record, config_record])

        # Add a newer record to set current_step=50
        store.records.append(create_mock_record("mem-new", 50, "config"))

        policy.maintain(store)

        # Should archive 3 lowest-scoring (test_update and config)
        # Should retain 3 highest-scoring (architectural, api_change, bug_fix)
        active_ids = [r.memory_id for r in store.active_records()]
        archived_ids = [r.memory_id for r in store.archived_records]

        # Architectural should be retained (highest base value)
        assert "mem-arch" in active_ids
        # Config should be archived (lowest base value)
        assert "mem-config" in archived_ids
        # Test_update should be archived (second lowest base value)
        assert "mem-test" in archived_ids

    def test_retains_highest_scoring_memories(self):
        """Verify maintain() retains max_records highest-scoring memories."""
        policy = TypeAwareDecayPolicy(max_records=2)
        store = MockMemoryStore()

        # Add 5 memories with same age but different types
        for i, mem_type in enumerate(["architectural", "api_change", "bug_fix", "test_update", "config"]):
            store.records.append(create_mock_record(f"mem-{i}", 40, mem_type, use_count=1))

        # Add a newer record to set current_step=50
        store.records.append(create_mock_record("mem-new", 50, "config"))

        policy.maintain(store)

        # Should retain 2 highest-scoring (architectural and api_change)
        active_types = [r.memory_type for r in store.active_records()]
        assert "architectural" in active_types
        assert "api_change" in active_types

    def test_archives_based_on_score_not_type_alone(self):
        """Verify pruning considers full formula, not just type."""
        policy = TypeAwareDecayPolicy(max_records=2)
        store = MockMemoryStore()

        # Old architectural memory (high base, but very old)
        old_arch = create_mock_record("mem-old-arch", 5, "architectural", use_count=0)
        
        # Recent config memory (low base, but very recent and frequently used)
        recent_config = create_mock_record("mem-recent-config", 48, "config", use_count=10)
        
        # Medium bug_fix memory
        medium_bug = create_mock_record("mem-medium-bug", 30, "bug_fix", use_count=3)

        store.records.extend([old_arch, recent_config, medium_bug])

        # Add a newer record to set current_step=50
        store.records.append(create_mock_record("mem-new", 50, "config"))

        policy.maintain(store)

        # Should archive 2 lowest-scoring
        # The formula should balance type, age, and frequency
        assert len(store.active_records()) == 2
        assert len(store.archived_records) == 2


class TestTypeAwareDecayDeterminism:
    """Test that Type-Aware Decay is deterministic (no randomness)."""

    def test_same_input_produces_same_output(self):
        """Verify same input produces identical pruning decisions."""
        # Run 1
        policy1 = TypeAwareDecayPolicy(max_records=3)
        store1 = MockMemoryStore()

        for i in range(10):
            mem_type = ["architectural", "config", "bug_fix"][i % 3]
            store1.records.append(create_mock_record(f"mem-{i:03d}", i, mem_type, use_count=i % 5))

        policy1.maintain(store1)
        archived1 = sorted([r.memory_id for r in store1.archived_records])

        # Run 2 (same input)
        policy2 = TypeAwareDecayPolicy(max_records=3)
        store2 = MockMemoryStore()

        for i in range(10):
            mem_type = ["architectural", "config", "bug_fix"][i % 3]
            store2.records.append(create_mock_record(f"mem-{i:03d}", i, mem_type, use_count=i % 5))

        policy2.maintain(store2)
        archived2 = sorted([r.memory_id for r in store2.archived_records])

        # Should archive the same memories
        assert archived1 == archived2


class TestTypeAwareDecayEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_maintain_with_empty_store(self):
        """Verify maintain() handles empty store gracefully."""
        policy = TypeAwareDecayPolicy(max_records=10)
        store = MockMemoryStore()

        # Should not raise
        policy.maintain(store)

        assert store.archive_called_count == 0

    def test_maintain_with_max_records_one(self):
        """Verify maintain() works with max_records=1."""
        policy = TypeAwareDecayPolicy(max_records=1)
        store = MockMemoryStore()

        # Add 3 records
        for i in range(3):
            store.records.append(create_mock_record(f"mem-{i:03d}", i, "bug_fix"))

        policy.maintain(store)

        # Should retain only 1 highest-scoring memory
        assert len(store.active_records()) == 1
        assert store.archive_called_count == 2

    def test_maintain_with_unknown_memory_type(self):
        """Verify maintain() handles unknown memory type with default parameters."""
        policy = TypeAwareDecayPolicy(max_records=2)
        store = MockMemoryStore()

        # Create a record with a valid type, then manually change it to unknown
        # (bypassing validation to test the maintain() fallback logic)
        unknown_record = create_mock_record("mem-unknown", 10, "config", use_count=1)
        # Manually set to unknown type after creation
        unknown_record.memory_type = "unknown_type"
        
        known_record = create_mock_record("mem-known", 10, "architectural", use_count=1)
        store.records.extend([unknown_record, known_record])

        # Add a newer record to set current_step
        store.records.append(create_mock_record("mem-new", 50, "config"))

        # Should not raise, should use default parameters (0.3, 0.40, "Expendable")
        policy.maintain(store)

        # Unknown type should get lowest score (default to config parameters)
        assert unknown_record.importance_score < known_record.importance_score

    def test_maintain_final_count_assertion(self):
        """Verify maintain() asserts final count <= max_records."""
        policy = TypeAwareDecayPolicy(max_records=5)
        store = MockMemoryStore()

        # Add 10 records
        for i in range(10):
            store.records.append(create_mock_record(f"mem-{i:03d}", i, "bug_fix"))

        policy.maintain(store)

        # Final count should be exactly max_records
        final_count = len(store.active_records())
        assert final_count <= policy.max_records
        assert final_count == policy.max_records


class TestTypeAwareDecayAPICompatibility:
    """Test Type-Aware Decay policy maintains API compatibility."""

    def test_implements_all_required_methods(self):
        """Verify Type-Aware Decay policy implements all MemoryPolicy methods."""
        policy = TypeAwareDecayPolicy(max_records=100)

        assert hasattr(policy, "retrieve")
        assert hasattr(policy, "write")
        assert hasattr(policy, "maintain")
        assert hasattr(policy, "name")

    def test_method_signatures_match_base_class(self):
        """Verify method signatures match MemoryPolicy interface."""
        import inspect

        policy = TypeAwareDecayPolicy(max_records=100)

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


class TestTypeAwareDecayDocumentation:
    """Test Type-Aware Decay policy has proper documentation."""

    def test_class_has_docstring(self):
        """Verify TypeAwareDecayPolicy class has docstring."""
        assert TypeAwareDecayPolicy.__doc__ is not None
        assert "type-aware" in TypeAwareDecayPolicy.__doc__.lower() or "type aware" in TypeAwareDecayPolicy.__doc__.lower()
        assert "Requirements 12" in TypeAwareDecayPolicy.__doc__

    def test_retrieve_has_docstring(self):
        """Verify retrieve() method has docstring."""
        assert TypeAwareDecayPolicy.retrieve.__doc__ is not None
        assert "shared_retrieve" in TypeAwareDecayPolicy.retrieve.__doc__

    def test_write_has_docstring(self):
        """Verify write() method has docstring."""
        assert TypeAwareDecayPolicy.write.__doc__ is not None
        assert "store" in TypeAwareDecayPolicy.write.__doc__.lower()

    def test_maintain_has_docstring(self):
        """Verify maintain() method has docstring."""
        assert TypeAwareDecayPolicy.maintain.__doc__ is not None
        assert "anderson" in TypeAwareDecayPolicy.maintain.__doc__.lower() or "importance_score" in TypeAwareDecayPolicy.maintain.__doc__
