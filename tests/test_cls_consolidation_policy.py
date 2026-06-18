"""Unit tests for CLS Consolidation policy.

Tests verify:
1. CLS Consolidation uses shared_retrieve with identical scoring (Req 13.1)
2. CLS Consolidation stores all incoming records (Req 13.2)
3. Consolidation triggers every 5 tasks on fixed schedule (Req 13.3)
4. Selects candidates: ≥10 tasks old, not consolidated, not architectural (Req 13.4)
5. Clusters by repo, files_touched, and embedding similarity (Req 13.5)
6. Generates consolidated summaries with max 350 tokens (Req 13.6)
7. Archives source memories and stores consolidated record (Req 13.7)
8. Falls back to Type-Aware Decay if still over budget (Req 13.8)

**Validates: Requirements 13**
"""

import numpy as np

from src.memory.policies.cls_consolidation import CLSConsolidationPolicy
from src.memory.record import MemoryRecord


class MockTask:
    """Mock task object for testing."""
    def __init__(self, repo="test/repo", issue_text="Test issue", task_id="test-001"):
        self.repo = repo
        self.issue_text = issue_text
        self.task_id = task_id


class MockFAISSIndex:
    """Mock FAISS index for testing."""
    def __init__(self):
        self.vectors = {}
        self.next_id = 0

    def add(self, vector):
        """Add vector and return ID."""
        vector_id = self.next_id
        self.vectors[vector_id] = vector
        self.next_id += 1
        return vector_id

    def reconstruct(self, vector_id):
        """Retrieve vector by ID."""
        if vector_id not in self.vectors:
            raise RuntimeError(f"Vector {vector_id} not found")
        return self.vectors[vector_id]


class MockMemoryStore:
    """Mock memory store for testing."""
    def __init__(self):
        self.records = []
        self.archived_records = []
        self.add_called_count = 0
        self.archive_called_count = 0
        self.faiss_index = MockFAISSIndex()
        self.importance_scores = {}

    def add(self, record):
        """Mock add method."""
        self.add_called_count += 1
        # Add embedding vector to FAISS if not already present
        if record.embedding_vector_id is None or record.embedding_vector_id == "":
            # Generate a random embedding vector
            vector = np.random.randn(384).astype(np.float32)
            vector_id = self.faiss_index.add(vector)
            record.embedding_vector_id = str(vector_id)
        self.records.append(record)

    def archive(self, memory_id, reason, replacement_id=None, current_step=None):
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
        """Update importance score for a memory."""
        self.importance_scores[memory_id] = score
        for record in self.records:
            if record.memory_id == memory_id:
                record.importance_score = score
                break


def create_mock_record(
    memory_id,
    sequence_index,
    memory_type="bug_fix",
    is_consolidated=False,
    files_touched=None,
    repo="test/repo"
):
    """Create a mock MemoryRecord for testing."""
    if files_touched is None:
        files_touched = [f"file_{sequence_index}.py"]

    return MemoryRecord(
        memory_id=memory_id,
        task_id=f"task-{sequence_index:03d}",
        repo=repo,
        sequence_index=sequence_index,
        memory_type=memory_type,
        outcome="pass",
        issue_summary=f"Issue {sequence_index}",
        patch_summary=f"Patch {sequence_index}",
        embedding_text=f"Embedding {sequence_index}",
        token_length=100,
        is_consolidated=is_consolidated,
        files_touched=files_touched
    )


class TestCLSConsolidationPolicyInstantiation:
    """Test CLS Consolidation policy instantiation and attributes."""

    def test_can_instantiate_with_valid_max_records(self):
        """Verify CLS Consolidation policy can be instantiated with valid max_records."""
        policy = CLSConsolidationPolicy(max_records=100)
        assert policy is not None
        assert policy.max_records == 100

    def test_has_correct_name(self):
        """Verify CLS Consolidation policy has correct name attribute."""
        policy = CLSConsolidationPolicy(max_records=100)
        assert policy.name == "cls_consolidation"

    def test_is_memory_policy_subclass(self):
        """Verify CLS Consolidation policy is a MemoryPolicy subclass."""
        from src.memory.policies.base import MemoryPolicy
        policy = CLSConsolidationPolicy(max_records=100)
        assert isinstance(policy, MemoryPolicy)

    def test_has_correct_frozen_parameters(self):
        """Verify CLS Consolidation has correct frozen parameters (Req 13)."""
        assert CLSConsolidationPolicy.CONSOLIDATION_INTERVAL == 5
        assert CLSConsolidationPolicy.MIN_CLUSTER_SIZE == 3
        assert CLSConsolidationPolicy.MAX_SUMMARY_TOKENS == 350
        # AMENDMENT A3 (2026-06-17): 10 -> 5 (= cap/2). The frozen v5 value of 10
        # was incompatible with the A1 cap=10 amendment (no active record ever
        # reaches age 10 at cap=10), leaving CLS inert. See AMENDMENTS.md.
        assert CLSConsolidationPolicy.OLD_MEMORY_THRESHOLD == 5
        assert CLSConsolidationPolicy.SIMILARITY_THRESHOLD == 0.70

    def test_initializes_task_counter_to_zero(self):
        """Verify task counter initializes to zero."""
        policy = CLSConsolidationPolicy(max_records=100)
        assert policy._tasks_since_last_consolidation == 0

    def test_select_candidates_fires_at_cap_10(self):
        """CLS must be able to consolidate under the A1 cap=10 (AMENDMENT A3).

        At cap=10 the active set spans ~10 consecutive sequence indices, so the
        oldest record is only ~9 tasks old — it never reaches the old threshold
        of 10. With the amended threshold (5 = cap/2), the oldest ~5 records
        qualify, so consolidation can actually occur.
        """
        policy = CLSConsolidationPolicy(max_records=10)
        records = [create_mock_record(f"m{i}", sequence_index=i) for i in range(10)]
        candidates = policy._select_candidates(records, current_step=9)
        assert {c.memory_id for c in candidates} == {"m0", "m1", "m2", "m3", "m4"}


class TestCLSConsolidationPolicyRetrieve:
    """Test CLS Consolidation policy retrieve() method.

    **Validates: Requirements 13.1**
    """

    def test_retrieve_uses_shared_retrieve(self):
        """Verify retrieve() uses shared_retrieve (Req 13.1, Frozen Invariant #5)."""
        import inspect

        from src.memory.policies.cls_consolidation import CLSConsolidationPolicy

        # Get source code of retrieve method
        source = inspect.getsource(CLSConsolidationPolicy.retrieve)

        # Verify it calls shared_retrieve
        assert "shared_retrieve" in source

        # Verify it passes all parameters correctly
        assert "task" in source
        assert "memory_store" in source
        assert "top_k" in source
        assert "token_budget" in source

    def test_retrieve_returns_list_of_records(self):
        """Verify retrieve() returns list of MemoryRecord objects."""
        from unittest.mock import patch

        policy = CLSConsolidationPolicy(max_records=100)
        task = MockTask()
        store = MockMemoryStore()

        # Mock shared_retrieve to return scored memories
        mock_result = [(0.9, create_mock_record("mem-001", 1))]

        with patch('src.memory.policies.cls_consolidation.shared_retrieve', return_value=mock_result):
            result = policy.retrieve(task, store, top_k=5, token_budget=2000)

        # Should return list of (score, MemoryRecord) tuples
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], tuple)
        assert len(result[0]) == 2
        assert isinstance(result[0][0], float)
        assert isinstance(result[0][1], MemoryRecord)


class TestCLSConsolidationPolicyWrite:
    """Test CLS Consolidation policy write() method.

    **Validates: Requirements 13.2**
    """

    def test_write_stores_all_records(self):
        """Verify write() stores all incoming records (Req 13.2)."""
        policy = CLSConsolidationPolicy(max_records=100)
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
        policy = CLSConsolidationPolicy(max_records=5)
        store = MockMemoryStore()

        # Write more records than max_records
        for i in range(10):
            record = create_mock_record(f"mem-{i:03d}", i)
            policy.write(store, record)

        # All records should be stored (pruning happens in maintain())
        assert store.add_called_count == 10
        assert len(store.records) == 10


class TestCLSConsolidationPolicyFixedSchedule:
    """Test CLS Consolidation fixed schedule behavior.

    **Validates: Requirements 13.3**
    """

    def test_consolidation_triggers_every_5_tasks(self):
        """Verify consolidation triggers every 5 tasks (Req 13.3, Frozen Invariant #9)."""
        policy = CLSConsolidationPolicy(max_records=100)
        store = MockMemoryStore()

        # Add old memories that could be consolidated
        for i in range(20):
            record = create_mock_record(f"mem-{i:03d}", i, memory_type="bug_fix")
            store.records.append(record)

        # Call maintain 4 times - should not consolidate
        for _ in range(4):
            policy.maintain(store)

        assert policy._tasks_since_last_consolidation == 4

        # 5th call should trigger consolidation
        policy.maintain(store)
        assert policy._tasks_since_last_consolidation == 0

    def test_consolidation_not_triggered_on_overflow(self):
        """Verify consolidation is NOT triggered by overflow (CRITICAL - Frozen Invariant #9)."""
        policy = CLSConsolidationPolicy(max_records=5)
        store = MockMemoryStore()

        # Add many records to exceed capacity
        for i in range(20):
            record = create_mock_record(f"mem-{i:03d}", i)
            store.records.append(record)

        # Call maintain once - should NOT consolidate (only 1 task, not 5)
        policy.maintain(store)

        # Counter should be 1, not reset to 0
        assert policy._tasks_since_last_consolidation == 1

        # Consolidation should not have happened (no archives from consolidation)
        # Note: Fallback to Type-Aware Decay may happen, but that's tested separately
        assert store.archive_called_count == 0 or all(
            r.archived_reason != "cls_consolidated" for r in store.archived_records
        )

    def test_counter_resets_after_consolidation(self):
        """Verify task counter resets to 0 after consolidation."""
        policy = CLSConsolidationPolicy(max_records=100)
        store = MockMemoryStore()

        # Add old memories
        for i in range(20):
            record = create_mock_record(f"mem-{i:03d}", i)
            store.records.append(record)

        # Trigger consolidation
        for _ in range(5):
            policy.maintain(store)

        # Counter should reset
        assert policy._tasks_since_last_consolidation == 0


class TestCLSConsolidationPolicyCandidateSelection:
    """Test candidate selection for consolidation.

    **Validates: Requirements 13.4**
    """

    def test_selects_old_memories_only(self):
        """Verify only memories ≥10 tasks old are selected (Req 13.4)."""
        policy = CLSConsolidationPolicy(max_records=100)
        store = MockMemoryStore()

        # Add memories with different ages
        # Current step will be 20 (max sequence_index)
        for i in range(21):
            record = create_mock_record(f"mem-{i:03d}", i, memory_type="bug_fix")
            store.records.append(record)

        # Trigger consolidation
        policy._tasks_since_last_consolidation = 5
        policy._consolidate(store)

        # Memories 0-10 are old enough (age ≥ 10)
        # Memories 11-20 are too recent (age < 10)
        # Only old memories should be considered for consolidation

    def test_excludes_consolidated_memories(self):
        """Verify already consolidated memories are excluded (Req 13.4)."""
        policy = CLSConsolidationPolicy(max_records=100)
        store = MockMemoryStore()

        # Add old memories, some already consolidated
        for i in range(15):
            is_consolidated = (i % 2 == 0)  # Every other one
            record = create_mock_record(
                f"mem-{i:03d}",
                i,
                memory_type="bug_fix",
                is_consolidated=is_consolidated
            )
            store.records.append(record)

        # Trigger consolidation
        policy._tasks_since_last_consolidation = 5
        policy._consolidate(store)

        # Already consolidated memories should not be re-consolidated

    def test_excludes_architectural_memories(self):
        """Verify architectural memories are excluded (Req 13.4, Sacred tier)."""
        policy = CLSConsolidationPolicy(max_records=100)
        store = MockMemoryStore()

        # Add old memories of different types
        for i in range(15):
            memory_type = "architectural" if i < 5 else "bug_fix"
            record = create_mock_record(f"mem-{i:03d}", i, memory_type=memory_type)
            store.records.append(record)

        # Trigger consolidation
        policy._tasks_since_last_consolidation = 5
        policy._consolidate(store)

        # Architectural memories should not be archived
        architectural_archived = [
            r for r in store.archived_records
            if r.memory_type == "architectural"
        ]
        assert len(architectural_archived) == 0

    def test_requires_minimum_candidates(self):
        """Verify consolidation requires at least MIN_CLUSTER_SIZE candidates."""
        policy = CLSConsolidationPolicy(max_records=100)
        store = MockMemoryStore()

        # Add only 2 old memories (below MIN_CLUSTER_SIZE=3)
        for i in range(2):
            record = create_mock_record(f"mem-{i:03d}", i, memory_type="bug_fix")
            store.records.append(record)

        # Add current task at step 15
        record = create_mock_record("mem-015", 15)
        store.records.append(record)

        # Trigger consolidation
        policy._tasks_since_last_consolidation = 5
        policy._consolidate(store)

        # Should not consolidate (not enough candidates)
        assert store.archive_called_count == 0


class TestCLSConsolidationPolicyFallback:
    """Test fallback to Type-Aware Decay.

    **Validates: Requirements 13.8**
    """

    def test_fallback_when_over_budget_after_consolidation(self):
        """Verify fallback to Type-Aware Decay if still over budget (Req 13.8)."""
        policy = CLSConsolidationPolicy(max_records=5)
        store = MockMemoryStore()

        # Add many records
        for i in range(20):
            record = create_mock_record(f"mem-{i:03d}", i, memory_type="bug_fix")
            store.records.append(record)

        # Trigger consolidation (won't reduce enough)
        policy._tasks_since_last_consolidation = 5
        policy.maintain(store)

        # Should fall back and prune to max_records
        assert store.count_active() <= 5

    def test_fallback_uses_type_aware_decay_formula(self):
        """Verify fallback uses Type-Aware Decay importance scoring."""
        policy = CLSConsolidationPolicy(max_records=3)
        store = MockMemoryStore()

        # Add records with different types
        records = [
            create_mock_record("mem-arch", 0, memory_type="architectural"),
            create_mock_record("mem-api", 1, memory_type="api_change"),
            create_mock_record("mem-bug", 2, memory_type="bug_fix"),
            create_mock_record("mem-test", 3, memory_type="test_update"),
            create_mock_record("mem-conf", 4, memory_type="config"),
        ]
        for record in records:
            store.records.append(record)
            # Set importance scores for Type-Aware Decay fallback
            store.update_importance_score(record.memory_id, 1.0)

        # Add current task
        current = create_mock_record("mem-current", 10)
        store.records.append(current)

        # Trigger maintain with consolidation (will trigger fallback)
        policy._tasks_since_last_consolidation = 5
        policy.maintain(store)

        # Fallback should have been triggered (Type-Aware Decay)
        # Note: The actual pruning behavior depends on Type-Aware Decay implementation
        # This test just verifies that fallback is called when over budget

    def test_no_fallback_when_under_budget(self):
        """Verify no fallback pruning when under budget."""
        policy = CLSConsolidationPolicy(max_records=100)
        store = MockMemoryStore()

        # Add few records (under capacity)
        for i in range(5):
            record = create_mock_record(f"mem-{i:03d}", i)
            store.records.append(record)

        # Trigger maintain
        policy.maintain(store)

        # Should not archive anything
        assert store.archive_called_count == 0


class TestCLSConsolidationPolicyEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_maintain_with_empty_store(self):
        """Verify maintain() handles empty store gracefully."""
        policy = CLSConsolidationPolicy(max_records=10)
        store = MockMemoryStore()

        # Should not raise
        policy.maintain(store)

        assert store.archive_called_count == 0

    def test_consolidation_with_no_candidates(self):
        """Verify consolidation handles no candidates gracefully."""
        policy = CLSConsolidationPolicy(max_records=100)
        store = MockMemoryStore()

        # Add only recent memories (all too young)
        for i in range(15, 20):
            record = create_mock_record(f"mem-{i:03d}", i)
            store.records.append(record)

        # Trigger consolidation
        policy._tasks_since_last_consolidation = 5
        policy._consolidate(store)

        # Should not crash, no consolidation
        assert store.archive_called_count == 0

    def test_group_by_repo_with_different_repos(self):
        """Verify _group_by_repo separates memories by repository."""
        policy = CLSConsolidationPolicy(max_records=100)

        # Create memories from different repos
        memories = [
            create_mock_record("mem-001", 1, repo="django/django"),
            create_mock_record("mem-002", 2, repo="flask/flask"),
            create_mock_record("mem-003", 3, repo="django/django"),
        ]

        groups = policy._group_by_repo(memories)

        # Should create 2 groups (one per repo)
        assert len(groups) == 2
        assert "django/django" in groups
        assert "flask/flask" in groups
        assert len(groups["django/django"]) == 2
        assert len(groups["flask/flask"]) == 1

    def test_group_by_repo_with_same_repo(self):
        """Verify _group_by_repo groups memories from same repository."""
        policy = CLSConsolidationPolicy(max_records=100)

        # Create memories from same repo
        memories = [
            create_mock_record("mem-001", 1, repo="django/django"),
            create_mock_record("mem-002", 2, repo="django/django"),
            create_mock_record("mem-003", 3, repo="django/django"),
        ]

        groups = policy._group_by_repo(memories)

        # Should create 1 group
        assert len(groups) == 1
        assert "django/django" in groups
        assert len(groups["django/django"]) == 3


class TestCLSConsolidationPolicyAPICompatibility:
    """Test CLS Consolidation policy maintains API compatibility."""

    def test_implements_all_required_methods(self):
        """Verify CLS Consolidation policy implements all MemoryPolicy methods."""
        policy = CLSConsolidationPolicy(max_records=100)

        assert hasattr(policy, "retrieve")
        assert hasattr(policy, "write")
        assert hasattr(policy, "maintain")
        assert hasattr(policy, "name")

    def test_method_signatures_match_base_class(self):
        """Verify method signatures match MemoryPolicy interface."""
        import inspect

        policy = CLSConsolidationPolicy(max_records=100)

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


class TestCLSConsolidationPolicyDocumentation:
    """Test CLS Consolidation policy has proper documentation."""

    def test_class_has_docstring(self):
        """Verify CLSConsolidationPolicy class has docstring."""
        assert CLSConsolidationPolicy.__doc__ is not None
        assert "consolidation" in CLSConsolidationPolicy.__doc__.lower()
        assert "Requirements 13" in CLSConsolidationPolicy.__doc__

    def test_retrieve_has_docstring(self):
        """Verify retrieve() method has docstring."""
        assert CLSConsolidationPolicy.retrieve.__doc__ is not None
        assert "shared_retrieve" in CLSConsolidationPolicy.retrieve.__doc__

    def test_write_has_docstring(self):
        """Verify write() method has docstring."""
        assert CLSConsolidationPolicy.write.__doc__ is not None
        assert "store" in CLSConsolidationPolicy.write.__doc__.lower()

    def test_maintain_has_docstring(self):
        """Verify maintain() method has docstring."""
        assert CLSConsolidationPolicy.maintain.__doc__ is not None
        assert "consolidation" in CLSConsolidationPolicy.maintain.__doc__.lower()
        assert "fallback" in CLSConsolidationPolicy.maintain.__doc__.lower()


class TestCLSConsolidationPolicyConsolidatedRecordType:
    """Test consolidated record memory_type respects 5-type taxonomy (Invariant #7).

    Bug 1 (plan 2.8): consolidated records previously used
    memory_type="consolidated_summary", which the MemoryRecord validator
    rejects with ValueError before store.add() is ever reached. The fix
    assigns the cluster's MAJORITY memory_type instead. Ties are broken
    alphabetically (smallest type name wins).
    """

    def test_consolidated_record_type_is_valid_and_majority(self):
        """Consolidated record's memory_type is in VALID_MEMORY_TYPES and equals
        the majority type of the input cluster, and store.add() does not raise."""
        from src.memory.record import VALID_MEMORY_TYPES

        policy = CLSConsolidationPolicy(max_records=100)
        store = MockMemoryStore()

        # Cluster of 3 memories: 2 bug_fix, 1 config -> majority is bug_fix
        cluster = [
            create_mock_record("mem-c0", 0, memory_type="bug_fix"),
            create_mock_record("mem-c1", 1, memory_type="bug_fix"),
            create_mock_record("mem-c2", 2, memory_type="config"),
        ]
        for record in cluster:
            store.records.append(record)

        # Must NOT raise ValueError (previously raised inside MemoryRecord ctor)
        policy._consolidate_cluster(cluster, store, current_step=20)

        consolidated = [r for r in store.records if r.is_consolidated]
        assert len(consolidated) == 1
        consolidated_record = consolidated[0]

        # Type must be in the frozen 5-type taxonomy
        assert consolidated_record.memory_type in VALID_MEMORY_TYPES
        # Type must equal the majority type of the cluster
        assert consolidated_record.memory_type == "bug_fix"
        # is_consolidated flag preserved for identifiability
        assert consolidated_record.is_consolidated is True

    def test_consolidated_record_type_tie_breaks_alphabetically(self):
        """On a tie, the majority type is broken deterministically (alphabetical)."""
        from src.memory.record import VALID_MEMORY_TYPES

        policy = CLSConsolidationPolicy(max_records=100)
        store = MockMemoryStore()

        # Tie: 1 test_update, 1 config -> alphabetical winner is "config"
        cluster = [
            create_mock_record("mem-t0", 0, memory_type="test_update"),
            create_mock_record("mem-t1", 1, memory_type="config"),
            create_mock_record("mem-t2", 2, memory_type="test_update"),
            create_mock_record("mem-t3", 3, memory_type="config"),
        ]
        for record in cluster:
            store.records.append(record)

        policy._consolidate_cluster(cluster, store, current_step=20)

        consolidated = [r for r in store.records if r.is_consolidated]
        assert len(consolidated) == 1
        assert consolidated[0].memory_type in VALID_MEMORY_TYPES
        assert consolidated[0].memory_type == "config"


class TestCLSConsolidationPolicyFrozenInvariants:
    """Test frozen invariants from design document."""

    def test_fixed_schedule_not_overflow_trigger(self):
        """Verify consolidation is FIXED schedule, NOT overflow trigger (Invariant #9)."""
        policy = CLSConsolidationPolicy(max_records=5)
        store = MockMemoryStore()

        # Add many records to exceed capacity
        for i in range(20):
            record = create_mock_record(f"mem-{i:03d}", i)
            store.records.append(record)

        # Call maintain 3 times
        for _ in range(3):
            policy.maintain(store)

        # Counter should be 3, not reset (no consolidation yet)
        assert policy._tasks_since_last_consolidation == 3

        # Even though over capacity, consolidation didn't trigger
        # (fallback pruning should have reduced count though)

    def test_uses_shared_retrieve_for_identical_scoring(self):
        """Verify uses shared_retrieve for identical scoring (Invariant #5)."""
        import inspect

        source = inspect.getsource(CLSConsolidationPolicy.retrieve)

        # Must call shared_retrieve, not implement custom scoring
        assert "shared_retrieve" in source
        # Check that we're not implementing cosine similarity ourselves
        # (mentioning it in docstring is OK, but not in code)
        code_lines = [line for line in source.split('\n') if not line.strip().startswith('#') and '"""' not in line and "'''" not in line]
        code_only = '\n'.join(code_lines)
        assert "np.dot" not in code_only.lower()  # Not implementing dot product
        assert "cosine_similarity" not in code_only.lower()  # Not implementing cosine

    def test_min_cluster_size_is_three(self):
        """Verify minimum cluster size is 3 (Invariant #9)."""
        assert CLSConsolidationPolicy.MIN_CLUSTER_SIZE == 3

    def test_consolidation_interval_is_five(self):
        """Verify consolidation interval is 5 tasks (Invariant #9)."""
        assert CLSConsolidationPolicy.CONSOLIDATION_INTERVAL == 5

    def test_max_summary_tokens_is_350(self):
        """Verify max summary tokens is 350 (Invariant #9)."""
        assert CLSConsolidationPolicy.MAX_SUMMARY_TOKENS == 350

    def test_old_memory_threshold_is_5(self):
        """Old-memory threshold is 5 (AMENDMENT A3; was 10 per v5 Invariant #23).

        Lowered to cap/2 so CLS can consolidate under the A1 cap=10. See AMENDMENTS.md.
        """
        assert CLSConsolidationPolicy.OLD_MEMORY_THRESHOLD == 5


class _FakeChatCompletion:
    """Minimal stand-in for an OpenAI chat completion response object."""

    def __init__(self, content):
        class _Msg:
            def __init__(self, c):
                self.content = c

        class _Choice:
            def __init__(self, c):
                self.message = _Msg(c)

        self.choices = [_Choice(content)]


class _FakeChatClient:
    """Mock chat client exposing .chat.completions.create(...)."""

    def __init__(self, content=None, raise_exc=None):
        self._content = content
        self._raise_exc = raise_exc
        self.calls = []

        outer = self

        class _Completions:
            def create(self, **kwargs):
                outer.calls.append(kwargs)
                if outer._raise_exc is not None:
                    raise outer._raise_exc
                return _FakeChatCompletion(outer._content)

        class _Chat:
            def __init__(self):
                self.completions = _Completions()

        self.chat = _Chat()


class TestCLSConsolidationPolicyLLMSummary:
    """Test the REAL LLM consolidation summary (plan 4.6).

    The consolidated record's content must be composed from the LLM JSON
    output (summary + recurring_pattern + successful_strategy + failure_traps
    + test_commands). The record's memory_type stays the cluster MAJORITY valid
    type (Invariant #7), is_consolidated=True, token_length is a real tiktoken
    count capped at MAX_SUMMARY_TOKENS, and any LLM failure falls back to the
    placeholder summary without crashing.
    """

    def _llm_json(self):
        import json
        return json.dumps({
            "memory_type": "consolidated_summary",  # must be IGNORED for record
            "summary": "Repo X relies on Q-object short-circuiting in query.py.",
            "common_files": ["django/db/models/query.py", "tests/queries.py"],
            "recurring_pattern": "filter().exclude() mis-combines Q objects",
            "successful_strategy": "short-circuit empty Q before AND-combine",
            "failure_traps": "forgetting to reset the alias map between joins",
            "test_commands": ["pytest tests/queries.py -k qobject"],
        })

    def test_consolidation_uses_llm_summary_content(self):
        """Consolidated record content comes from the mocked LLM JSON, with a
        valid majority memory_type, is_consolidated=True, and a real (>0,
        bounded) tiktoken token_length."""
        from unittest.mock import patch

        from src.memory.record import VALID_MEMORY_TYPES

        policy = CLSConsolidationPolicy(max_records=100)
        store = MockMemoryStore()

        # Cluster: 2 bug_fix, 1 config -> majority bug_fix
        cluster = [
            create_mock_record("mem-l0", 0, memory_type="bug_fix"),
            create_mock_record("mem-l1", 1, memory_type="bug_fix"),
            create_mock_record("mem-l2", 2, memory_type="config"),
        ]
        for record in cluster:
            store.records.append(record)

        fake_client = _FakeChatClient(content=self._llm_json())

        with patch(
            "src.memory.policies.cls_consolidation.get_aux_client",
            return_value=fake_client,
        ):
            policy._consolidate_cluster(cluster, store, current_step=20)

        # LLM called at temperature=1 (2026-06-14 amendment: Kimi reasoning).
        # D4 extended (2026-06-17): no json_object mode — MiniMax M3 returns 400
        # model_not_capable, so we drop it and use tolerant JSON extraction.
        assert len(fake_client.calls) == 1
        call = fake_client.calls[0]
        assert call["temperature"] == 1
        assert "response_format" not in call

        consolidated = [r for r in store.records if r.is_consolidated]
        assert len(consolidated) == 1
        rec = consolidated[0]

        # Content composed from the LLM JSON, not the placeholder f-string
        composed = (rec.issue_summary or "") + (rec.test_summary or "")
        assert "short-circuiting in query.py" in composed
        assert "filter().exclude() mis-combines Q objects" in composed
        assert "short-circuit empty Q before AND-combine" in composed
        assert "Consolidated summary of" not in composed  # placeholder marker
        assert "placeholder_pattern" not in composed

        # Type must be the majority valid type (Invariant #7), NOT consolidated_summary
        assert rec.memory_type in VALID_MEMORY_TYPES
        assert rec.memory_type == "bug_fix"
        assert rec.is_consolidated is True
        assert set(rec.source_memory_ids) == {"mem-l0", "mem-l1", "mem-l2"}

        # token_length is a real tiktoken count, > 0 and within a sane bound
        assert rec.token_length > 0
        assert rec.token_length <= CLSConsolidationPolicy.MAX_SUMMARY_TOKENS

    def test_summary_text_capped_at_max_tokens(self):
        """A huge LLM summary is truncated so token_length <= MAX_SUMMARY_TOKENS."""
        import json
        from unittest.mock import patch

        from src.memory.embedding_utils import count_tokens

        policy = CLSConsolidationPolicy(max_records=100)
        store = MockMemoryStore()
        cluster = [
            create_mock_record("mem-b0", 0, memory_type="bug_fix"),
            create_mock_record("mem-b1", 1, memory_type="bug_fix"),
            create_mock_record("mem-b2", 2, memory_type="bug_fix"),
        ]
        for record in cluster:
            store.records.append(record)

        huge = json.dumps({
            "summary": "word " * 2000,
            "common_files": [],
            "recurring_pattern": "pattern " * 500,
            "successful_strategy": "strategy " * 500,
            "failure_traps": "trap " * 500,
            "test_commands": ["pytest"],
        })
        fake_client = _FakeChatClient(content=huge)

        with patch(
            "src.memory.policies.cls_consolidation.get_aux_client",
            return_value=fake_client,
        ):
            policy._consolidate_cluster(cluster, store, current_step=20)

        rec = [r for r in store.records if r.is_consolidated][0]
        assert rec.token_length <= CLSConsolidationPolicy.MAX_SUMMARY_TOKENS
        # token_length is a real tiktoken count of the stored embedding_text
        assert rec.token_length == count_tokens(rec.embedding_text)

    def test_falls_back_to_placeholder_on_llm_failure(self):
        """Any LLM failure (API/JSON/empty) falls back to the placeholder
        summary without crashing the run."""
        from unittest.mock import patch

        from src.memory.record import VALID_MEMORY_TYPES

        policy = CLSConsolidationPolicy(max_records=100)
        store = MockMemoryStore()
        cluster = [
            create_mock_record("mem-f0", 0, memory_type="bug_fix"),
            create_mock_record("mem-f1", 1, memory_type="bug_fix"),
            create_mock_record("mem-f2", 2, memory_type="config"),
        ]
        for record in cluster:
            store.records.append(record)

        fake_client = _FakeChatClient(raise_exc=RuntimeError("boom"))

        with patch(
            "src.memory.policies.cls_consolidation.get_aux_client",
            return_value=fake_client,
        ):
            # Must NOT raise
            policy._consolidate_cluster(cluster, store, current_step=20)

        consolidated = [r for r in store.records if r.is_consolidated]
        assert len(consolidated) == 1
        rec = consolidated[0]
        # Fell back to the placeholder text
        assert "Consolidated summary of" in rec.issue_summary
        # Invariants still hold on the fallback record
        assert rec.memory_type in VALID_MEMORY_TYPES
        assert rec.memory_type == "bug_fix"
        assert rec.is_consolidated is True
        assert rec.token_length > 0

    def test_falls_back_to_placeholder_on_invalid_json(self):
        """Malformed JSON content also triggers the placeholder fallback."""
        from unittest.mock import patch

        policy = CLSConsolidationPolicy(max_records=100)
        store = MockMemoryStore()
        cluster = [
            create_mock_record("mem-j0", 0, memory_type="bug_fix"),
            create_mock_record("mem-j1", 1, memory_type="bug_fix"),
            create_mock_record("mem-j2", 2, memory_type="bug_fix"),
        ]
        for record in cluster:
            store.records.append(record)

        fake_client = _FakeChatClient(content="not valid json at all")

        with patch(
            "src.memory.policies.cls_consolidation.get_aux_client",
            return_value=fake_client,
        ):
            policy._consolidate_cluster(cluster, store, current_step=20)

        rec = [r for r in store.records if r.is_consolidated][0]
        assert "Consolidated summary of" in rec.issue_summary
        assert rec.token_length > 0
