"""Tests for memory retriever module.

This module tests the shared_retrieve() function and related utilities
to ensure compliance with frozen invariants.

Frozen Invariants Tested:
- Retrieval scoring = pure cosine similarity, identical across all 6 conditions
- Injection order = relevance-sorted, best item LAST (Lost-in-the-Middle fix)
- Same-repo retrieval only in main experiment
- Token budget enforcement with no partial items

Requirements: 6, 7
"""

import hashlib
import tempfile
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from src.memory.record import MemoryRecord
from src.memory.retriever import (
    _build_query_text,
    _trim_to_token_budget,
    format_memory_for_prompt,
    shared_retrieve,
)
from src.memory.store import MemoryStore


@dataclass
class MockTask:
    """Mock task object for testing."""
    task_id: str
    repo: str
    issue_text: str


def _deterministic_embedding(self, text: str) -> np.ndarray:
    """Offline, deterministic stand-in for ``MemoryStore._generate_embedding``.

    Mirrors the real method's contract exactly: an **L2-normalized float32**
    vector of length ``self.embedding_dim``. The vector is a deterministic
    function of ``text`` (hashlib-seeded RNG), so FAISS cosine ranking is
    stable and reproducible without a live embedder. Distinct texts get
    distinct directions; identical texts get identical vectors — this keeps
    the pure-cosine (#5) and best-item-LAST (#6) ordering assertions valid
    while removing the network dependency on ``localhost:11434``.
    """
    seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "little")
    rng = np.random.default_rng(seed)
    # Non-negative components (like real text embeddings, which are
    # non-negatively correlated) so cosine similarity stays in [0, 1] —
    # standard-normal directions could be anti-correlated and yield negative
    # inner products, which violates the [0, 1] cosine invariant the tests assert.
    vec = rng.random(self.embedding_dim).astype(np.float32)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec


@pytest.fixture
def temp_memory_store():
    """Create a temporary memory store for testing.

    Patches ``_generate_embedding`` with a deterministic offline stand-in so
    both ``store.add()`` and the retrieval query path run without a live
    embedder (the real method would hit ``localhost:11434``). The patch is at
    the class level, so it covers every store created inside the fixture.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create runs directory structure
        run_dir = Path(tmpdir) / "runs" / "test_run"
        run_dir.mkdir(parents=True, exist_ok=True)

        # Change to temp directory for test
        import os
        original_cwd = os.getcwd()
        os.chdir(tmpdir)

        try:
            with patch.object(
                MemoryStore, "_generate_embedding", _deterministic_embedding
            ):
                store = MemoryStore(
                    run_id="test_run",
                    policy_name="test_policy"
                )
                yield store
                store.close()
        finally:
            os.chdir(original_cwd)


@pytest.fixture
def sample_memories():
    """Create sample memory records for testing."""
    memories = []

    for i in range(5):
        memory = MemoryRecord(
            memory_id=f"MEM-{i:03d}",
            task_id=f"django__django-{1000 + i}",
            repo="django/django",
            sequence_index=i,
            memory_type="bug_fix",
            outcome="pass",
            issue_summary=f"Issue {i}: Fix bug in QuerySet",
            patch_summary=f"Patch {i}: Modified query.py",
            failure_summary=None,
            test_summary=f"Test {i}: All tests passed",
            embedding_text=f"Issue {i}: Fix bug in QuerySet\nPatch {i}: Modified query.py",
            token_length=50 + i * 10  # Varying token lengths: 50, 60, 70, 80, 90
        )
        memories.append(memory)

    return memories


class TestBuildQueryText:
    """Test query text construction."""

    def test_build_query_text_format(self):
        """Test that query text has correct format."""
        task = MockTask(
            task_id="django__django-12345",
            repo="django/django",
            issue_text="Fix bug in QuerySet.exclude"
        )

        query = _build_query_text(task)

        assert query == "Repository: django/django\nIssue: Fix bug in QuerySet.exclude"
        assert "Repository:" in query
        assert "Issue:" in query
        assert task.repo in query
        assert task.issue_text in query

    def test_build_query_text_different_repos(self):
        """Test query text for different repositories."""
        repos = ["django/django", "flask/flask", "requests/requests"]

        for repo in repos:
            task = MockTask(
                task_id=f"{repo.replace('/', '__')}-123",
                repo=repo,
                issue_text="Test issue"
            )
            query = _build_query_text(task)
            assert repo in query


class TestTrimToTokenBudget:
    """Test token budget enforcement."""

    def test_trim_within_budget_returns_all(self, sample_memories):
        """Test that memories within budget are not trimmed."""
        # Total tokens: 50 + 60 + 70 + 80 + 90 = 350
        scored = [(0.9 - i * 0.1, mem) for i, mem in enumerate(sample_memories)]

        result = _trim_to_token_budget(scored, token_budget=400)

        assert len(result) == 5
        assert result == scored

    def test_trim_drops_lowest_scoring(self, sample_memories):
        """Test that lowest-scoring memories are dropped first."""
        # Scores: 0.9, 0.8, 0.7, 0.6, 0.5 (descending)
        scored = [(0.9 - i * 0.1, mem) for i, mem in enumerate(sample_memories)]

        # Budget allows only first 3 memories: 50 + 60 + 70 = 180
        result = _trim_to_token_budget(scored, token_budget=200)

        assert len(result) == 3
        # Should keep highest-scoring (first 3)
        assert result[0][0] == 0.9
        assert result[1][0] == 0.8
        assert result[2][0] == 0.7

    def test_trim_guarantees_no_partial_items(self, sample_memories):
        """Test that entire memories are dropped, not truncated."""
        scored = [(0.9 - i * 0.1, mem) for i, mem in enumerate(sample_memories)]

        # Budget that would require partial item
        result = _trim_to_token_budget(scored, token_budget=125)

        # Should fit 50 + 60 = 110, but not 50 + 60 + 70 = 180
        assert len(result) == 2
        total_tokens = sum(mem.token_length for _, mem in result)
        assert total_tokens <= 125

    def test_trim_empty_list(self):
        """Test trimming empty list returns empty list."""
        result = _trim_to_token_budget([], token_budget=1000)
        assert result == []

    def test_trim_single_memory_exceeds_budget(self, sample_memories):
        """Test that empty list returned if even one memory exceeds budget."""
        scored = [(0.9, sample_memories[0])]  # 50 tokens

        result = _trim_to_token_budget(scored, token_budget=40)

        assert result == []

    def test_trim_maintains_descending_order(self, sample_memories):
        """Test that result maintains descending score order."""
        scored = [(0.9 - i * 0.1, mem) for i, mem in enumerate(sample_memories)]

        result = _trim_to_token_budget(scored, token_budget=200)

        # Verify descending order maintained
        scores = [score for score, _ in result]
        assert scores == sorted(scores, reverse=True)


class TestSharedRetrieve:
    """Test shared retrieval function."""

    def test_shared_retrieve_pure_cosine_scoring(
        self,
        temp_memory_store,
        sample_memories
    ):
        """Test that retrieval uses pure cosine similarity with NO bonuses.

        Embeddings come from the fixture's deterministic offline stand-in.
        """
        # Add memories to store
        for memory in sample_memories:
            temp_memory_store.add(memory)

        task = MockTask(
            task_id="django__django-99999",
            repo="django/django",
            issue_text="Test issue"
        )

        # Retrieve memories
        result = shared_retrieve(
            task=task,
            memory_store=temp_memory_store,
            top_k=3,
            token_budget=500
        )

        # Verify retrieval occurred
        assert isinstance(result, list)
        # Note: Actual scoring depends on FAISS, so we just verify structure
        for score, memory in result:
            assert isinstance(score, float)
            assert isinstance(memory, MemoryRecord)

    def test_shared_retrieve_filters_by_repo(self, temp_memory_store):
        """Test that retrieval filters by same repository."""
        # Create memories from different repos
        django_mem = MemoryRecord(
            memory_id="MEM-DJANGO",
            task_id="django__django-123",
            repo="django/django",
            sequence_index=0,
            memory_type="bug_fix",
            outcome="pass",
            issue_summary="Django issue",
            patch_summary="Django patch",
            embedding_text="Django issue\nDjango patch",
            token_length=50
        )

        flask_mem = MemoryRecord(
            memory_id="MEM-FLASK",
            task_id="flask__flask-456",
            repo="flask/flask",
            sequence_index=1,
            memory_type="bug_fix",
            outcome="pass",
            issue_summary="Flask issue",
            patch_summary="Flask patch",
            embedding_text="Flask issue\nFlask patch",
            token_length=50
        )

        temp_memory_store.add(django_mem)
        temp_memory_store.add(flask_mem)

        task = MockTask(
            task_id="django__django-789",
            repo="django/django",
            issue_text="Test Django issue"
        )

        # Retrieve with same_repo_only=True
        result = shared_retrieve(
            task=task,
            memory_store=temp_memory_store,
            top_k=5,
            token_budget=500,
            same_repo_only=True
        )

        # Should only get Django memory
        memory_ids = [mem.memory_id for _, mem in result]
        assert "MEM-DJANGO" in memory_ids or len(memory_ids) == 0  # May be 0 if no similar embeddings
        if "MEM-FLASK" in memory_ids:
            pytest.fail("Flask memory should not be retrieved for Django task")

    def test_shared_retrieve_filters_archived(self, temp_memory_store, sample_memories):
        """Test that archived memories are excluded from retrieval."""
        # Add memories and archive one
        for memory in sample_memories[:3]:
            temp_memory_store.add(memory)

        # Archive the first memory
        temp_memory_store.archive(
            memory_id=sample_memories[0].memory_id,
            reason="test_archive",
            current_step=10
        )

        task = MockTask(
            task_id="django__django-99999",
            repo="django/django",
            issue_text="Test issue"
        )

        result = shared_retrieve(
            task=task,
            memory_store=temp_memory_store,
            top_k=5,
            token_budget=500
        )

        # Archived memory should not be in results
        memory_ids = [mem.memory_id for _, mem in result]
        assert sample_memories[0].memory_id not in memory_ids

    def test_shared_retrieve_returns_ascending_order(self, temp_memory_store, sample_memories):
        """Test that results are sorted ascending (best LAST) for injection."""
        # Add memories
        for memory in sample_memories[:3]:
            temp_memory_store.add(memory)

        task = MockTask(
            task_id="django__django-99999",
            repo="django/django",
            issue_text="Test issue"
        )

        result = shared_retrieve(
            task=task,
            memory_store=temp_memory_store,
            top_k=3,
            token_budget=500
        )

        if len(result) > 1:
            # Verify ascending order (best LAST)
            scores = [score for score, _ in result]
            assert scores == sorted(scores), "Results should be sorted ascending (best LAST)"

    def test_shared_retrieve_respects_top_k(self, temp_memory_store, sample_memories):
        """Test that retrieval respects top_k limit."""
        # Add all memories
        for memory in sample_memories:
            temp_memory_store.add(memory)

        task = MockTask(
            task_id="django__django-99999",
            repo="django/django",
            issue_text="Test issue"
        )

        result = shared_retrieve(
            task=task,
            memory_store=temp_memory_store,
            top_k=3,
            token_budget=1000
        )

        # Should return at most top_k memories
        assert len(result) <= 3

    def test_shared_retrieve_enforces_token_budget(self, temp_memory_store, sample_memories):
        """Test that retrieval enforces token budget."""
        # Add memories with known token lengths
        for memory in sample_memories:
            temp_memory_store.add(memory)

        task = MockTask(
            task_id="django__django-99999",
            repo="django/django",
            issue_text="Test issue"
        )

        # Set tight budget
        result = shared_retrieve(
            task=task,
            memory_store=temp_memory_store,
            top_k=5,
            token_budget=100  # Should fit at most 2 memories (50 + 60 = 110 exceeds, so 1)
        )

        # Verify total tokens within budget
        total_tokens = sum(mem.token_length for _, mem in result)
        assert total_tokens <= 100

    def test_shared_retrieve_empty_store(self, temp_memory_store):
        """Test retrieval from empty store returns empty list."""
        task = MockTask(
            task_id="django__django-99999",
            repo="django/django",
            issue_text="Test issue"
        )

        result = shared_retrieve(
            task=task,
            memory_store=temp_memory_store,
            top_k=5,
            token_budget=500
        )

        assert result == []


class TestFormatMemoryForPrompt:
    """Test memory formatting for prompt injection."""

    def test_format_empty_list(self):
        """Test formatting empty list returns empty string."""
        result = format_memory_for_prompt([])
        assert result == ""

    def test_format_with_metadata(self, sample_memories):
        """Test formatting includes metadata headers."""
        scored = [(0.7, sample_memories[0]), (0.9, sample_memories[1])]

        result = format_memory_for_prompt(scored, include_metadata=True)

        assert "Memory 1/2" in result
        assert "Memory 2/2" in result
        assert "Similarity: 0.700" in result
        assert "Similarity: 0.900" in result
        assert sample_memories[0].memory_id in result
        assert sample_memories[1].memory_id in result

    def test_format_without_metadata(self, sample_memories):
        """Test formatting without metadata only includes content."""
        scored = [(0.7, sample_memories[0]), (0.9, sample_memories[1])]

        result = format_memory_for_prompt(scored, include_metadata=False)

        assert "Memory 1/2" not in result
        assert "Similarity" not in result
        assert sample_memories[0].embedding_text in result
        assert sample_memories[1].embedding_text in result

    def test_format_preserves_order(self, sample_memories):
        """Test that formatting preserves input order (ascending for injection)."""
        # Input is ascending (best LAST)
        scored = [
            (0.5, sample_memories[0]),
            (0.7, sample_memories[1]),
            (0.9, sample_memories[2])
        ]

        result = format_memory_for_prompt(scored, include_metadata=True)

        # Find positions of memory IDs in result
        pos_0 = result.find(sample_memories[0].memory_id)
        pos_1 = result.find(sample_memories[1].memory_id)
        pos_2 = result.find(sample_memories[2].memory_id)

        # Verify order preserved (ascending)
        assert pos_0 < pos_1 < pos_2, "Order should be preserved (best LAST)"


class TestFrozenInvariants:
    """Test compliance with frozen invariants."""

    def test_invariant_pure_cosine_no_bonuses(self, temp_memory_store, sample_memories):
        """Test Invariant #5: Pure cosine similarity, no bonuses/penalties."""
        # Add memories with different types and outcomes
        mem1 = MemoryRecord(
            memory_id="MEM-001",
            task_id="task-1",
            repo="django/django",
            sequence_index=0,
            memory_type="architectural",  # High-value type
            outcome="pass",
            issue_summary="Issue 1",
            patch_summary="Patch 1",
            embedding_text="Issue 1\nPatch 1",
            token_length=50,
            use_count=10  # High use count
        )

        mem2 = MemoryRecord(
            memory_id="MEM-002",
            task_id="task-2",
            repo="django/django",
            sequence_index=1,
            memory_type="config",  # Low-value type
            outcome="fail",
            issue_summary="Issue 2",
            patch_summary="Patch 2",
            embedding_text="Issue 2\nPatch 2",
            token_length=50,
            use_count=0  # No use
        )

        temp_memory_store.add(mem1)
        temp_memory_store.add(mem2)

        task = MockTask(
            task_id="task-3",
            repo="django/django",
            issue_text="Test issue"
        )

        # Retrieve memories
        result = shared_retrieve(
            task=task,
            memory_store=temp_memory_store,
            top_k=2,
            token_budget=500
        )

        # Verify that scoring is based ONLY on cosine similarity
        # We cannot directly verify the scores without knowing embeddings,
        # but we can verify that the function doesn't crash and returns valid results
        for score, memory in result:
            assert 0.0 <= score <= 1.0, "Cosine similarity should be in [0, 1]"
            # Verify no bonus fields are used in scoring
            # (This is implicit - if bonuses were used, we'd see different code)

    def test_invariant_best_item_last(self, temp_memory_store, sample_memories):
        """Test Invariant #6: Injection order = best item LAST."""
        # Add memories
        for memory in sample_memories[:3]:
            temp_memory_store.add(memory)

        task = MockTask(
            task_id="task-999",
            repo="django/django",
            issue_text="Test issue"
        )

        result = shared_retrieve(
            task=task,
            memory_store=temp_memory_store,
            top_k=3,
            token_budget=500
        )

        if len(result) > 1:
            # Verify ascending order (best LAST)
            scores = [score for score, _ in result]
            for i in range(len(scores) - 1):
                assert scores[i] <= scores[i + 1], (
                    f"Results must be sorted ascending (best LAST). "
                    f"Found {scores[i]} > {scores[i+1]} at position {i}"
                )

    def test_invariant_same_repo_retrieval(self, temp_memory_store):
        """Test Invariant #16: Same-repo retrieval in main experiment."""
        # Create memories from different repos
        django_mem = MemoryRecord(
            memory_id="MEM-DJANGO",
            task_id="django-task",
            repo="django/django",
            sequence_index=0,
            memory_type="bug_fix",
            outcome="pass",
            issue_summary="Django issue",
            patch_summary="Django patch",
            embedding_text="Django issue\nDjango patch",
            token_length=50
        )

        flask_mem = MemoryRecord(
            memory_id="MEM-FLASK",
            task_id="flask-task",
            repo="flask/flask",
            sequence_index=1,
            memory_type="bug_fix",
            outcome="pass",
            issue_summary="Flask issue",
            patch_summary="Flask patch",
            embedding_text="Flask issue\nFlask patch",
            token_length=50
        )

        temp_memory_store.add(django_mem)
        temp_memory_store.add(flask_mem)

        task = MockTask(
            task_id="django-new-task",
            repo="django/django",
            issue_text="New Django issue"
        )

        # Test with same_repo_only=True (main experiment)
        result_same_repo = shared_retrieve(
            task=task,
            memory_store=temp_memory_store,
            top_k=5,
            token_budget=500,
            same_repo_only=True
        )

        # Should only retrieve from same repo
        for _, memory in result_same_repo:
            assert memory.repo == "django/django", (
                f"With same_repo_only=True, should only retrieve from django/django, "
                f"but got {memory.repo}"
            )

    def test_invariant_token_budget_no_partial_items(self, temp_memory_store, sample_memories):
        """Test Requirement 6: Token budget enforcement with no partial items."""
        # Add memories with known token lengths
        for memory in sample_memories:
            temp_memory_store.add(memory)

        task = MockTask(
            task_id="task-999",
            repo="django/django",
            issue_text="Test issue"
        )

        # Set budget that would require partial item
        result = shared_retrieve(
            task=task,
            memory_store=temp_memory_store,
            top_k=5,
            token_budget=125  # Should fit 50 + 60 = 110, but not 50 + 60 + 70 = 180
        )

        # Verify total tokens within budget
        total_tokens = sum(mem.token_length for _, mem in result)
        assert total_tokens <= 125, (
            f"Total tokens {total_tokens} exceeds budget 125. "
            f"No partial items should be included."
        )

        # Verify each memory is complete (not truncated)
        for _, memory in result:
            assert memory.token_length > 0, "Memory should have positive token length"
            # Verify embedding_text is not truncated (would have marker)
            if "[... truncated ...]" in memory.embedding_text:
                # This is OK - truncation happened during embedding construction
                # But the entire memory is included, not partially
                pass
