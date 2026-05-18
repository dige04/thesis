"""
Unit tests for MemoryRecord dataclass.

Tests cover:
- Frozen invariant validation (orthogonal type/outcome axes)
- Field validation (non-negative values, required fields)
- Serialization/deserialization (to_dict, from_dict, to_json, from_json)
- Usage tracking updates
- Lifecycle management (archive, consolidation)
- Edge cases and error conditions

Requirements: 3, 5
Design: §2 Components and Interfaces
"""

import json
from datetime import datetime

import pytest

from src.memory.record import (
    VALID_MEMORY_TYPES,
    VALID_OUTCOMES,
    MemoryRecord,
    validate_orthogonal_axes,
)


class TestMemoryRecordValidation:
    """Test validation of orthogonal type/outcome axes."""

    def test_valid_memory_types(self):
        """Test that all 5 valid memory types are accepted."""
        for memory_type in VALID_MEMORY_TYPES:
            record = MemoryRecord(
                memory_id="MEM-TEST001",
                task_id="test__test-123",
                repo="test/repo",
                sequence_index=0,
                memory_type=memory_type,
                outcome="pass",
                issue_summary="Test issue",
                patch_summary="Test patch",
            )
            assert record.memory_type == memory_type

    def test_valid_outcomes(self):
        """Test that all 4 valid outcomes are accepted."""
        for outcome in VALID_OUTCOMES:
            record = MemoryRecord(
                memory_id="MEM-TEST001",
                task_id="test__test-123",
                repo="test/repo",
                sequence_index=0,
                memory_type="bug_fix",
                outcome=outcome,
                issue_summary="Test issue",
                patch_summary="Test patch",
            )
            assert record.outcome == outcome

    def test_invalid_memory_type_raises_error(self):
        """Test that invalid memory_type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid memory_type"):
            MemoryRecord(
                memory_id="MEM-TEST001",
                task_id="test__test-123",
                repo="test/repo",
                sequence_index=0,
                memory_type="invalid_type",
                outcome="pass",
                issue_summary="Test issue",
                patch_summary="Test patch",
            )

    def test_invalid_outcome_raises_error(self):
        """Test that invalid outcome raises ValueError."""
        with pytest.raises(ValueError, match="Invalid outcome"):
            MemoryRecord(
                memory_id="MEM-TEST001",
                task_id="test__test-123",
                repo="test/repo",
                sequence_index=0,
                memory_type="bug_fix",
                outcome="invalid_outcome",
                issue_summary="Test issue",
                patch_summary="Test patch",
            )

    def test_orthogonal_axes_bug_fix_pass(self):
        """Test orthogonal axes: bug_fix can have outcome=pass."""
        record = MemoryRecord(
            memory_id="MEM-TEST001",
            task_id="test__test-123",
            repo="test/repo",
            sequence_index=0,
            memory_type="bug_fix",
            outcome="pass",
            issue_summary="Test issue",
            patch_summary="Test patch",
        )
        assert record.memory_type == "bug_fix"
        assert record.outcome == "pass"

    def test_orthogonal_axes_bug_fix_fail(self):
        """Test orthogonal axes: bug_fix can have outcome=fail."""
        record = MemoryRecord(
            memory_id="MEM-TEST001",
            task_id="test__test-123",
            repo="test/repo",
            sequence_index=0,
            memory_type="bug_fix",
            outcome="fail",
            issue_summary="Test issue",
            patch_summary="Test patch",
        )
        assert record.memory_type == "bug_fix"
        assert record.outcome == "fail"

    def test_orthogonal_axes_architectural_fail(self):
        """Test orthogonal axes: architectural can have outcome=fail."""
        record = MemoryRecord(
            memory_id="MEM-TEST001",
            task_id="test__test-123",
            repo="test/repo",
            sequence_index=0,
            memory_type="architectural",
            outcome="fail",
            issue_summary="Test issue",
            patch_summary="Test patch",
        )
        assert record.memory_type == "architectural"
        assert record.outcome == "fail"

    def test_negative_sequence_index_raises_error(self):
        """Test that negative sequence_index raises ValueError."""
        with pytest.raises(ValueError, match="sequence_index must be non-negative"):
            MemoryRecord(
                memory_id="MEM-TEST001",
                task_id="test__test-123",
                repo="test/repo",
                sequence_index=-1,
                memory_type="bug_fix",
                outcome="pass",
                issue_summary="Test issue",
                patch_summary="Test patch",
            )

    def test_negative_use_count_raises_error(self):
        """Test that negative use_count raises ValueError."""
        with pytest.raises(ValueError, match="use_count must be non-negative"):
            MemoryRecord(
                memory_id="MEM-TEST001",
                task_id="test__test-123",
                repo="test/repo",
                sequence_index=0,
                memory_type="bug_fix",
                outcome="pass",
                issue_summary="Test issue",
                patch_summary="Test patch",
                use_count=-1,
            )

    def test_negative_token_length_raises_error(self):
        """Test that negative token_length raises ValueError."""
        with pytest.raises(ValueError, match="token_length must be non-negative"):
            MemoryRecord(
                memory_id="MEM-TEST001",
                task_id="test__test-123",
                repo="test/repo",
                sequence_index=0,
                memory_type="bug_fix",
                outcome="pass",
                issue_summary="Test issue",
                patch_summary="Test patch",
                token_length=-1,
            )


class TestMemoryRecordFields:
    """Test that all required fields are present and correctly typed."""

    def test_identity_fields(self):
        """Test identity fields: memory_id, task_id, repo, sequence_index."""
        record = MemoryRecord(
            memory_id="MEM-TEST001",
            task_id="django__django-12345",
            repo="django/django",
            sequence_index=17,
            memory_type="bug_fix",
            outcome="pass",
            issue_summary="Test issue",
            patch_summary="Test patch",
        )
        assert record.memory_id == "MEM-TEST001"
        assert record.task_id == "django__django-12345"
        assert record.repo == "django/django"
        assert record.sequence_index == 17

    def test_type_outcome_fields(self):
        """Test type/outcome fields are orthogonal."""
        record = MemoryRecord(
            memory_id="MEM-TEST001",
            task_id="test__test-123",
            repo="test/repo",
            sequence_index=0,
            memory_type="api_change",
            outcome="partial",
            issue_summary="Test issue",
            patch_summary="Test patch",
        )
        assert record.memory_type == "api_change"
        assert record.outcome == "partial"

    def test_content_fields(self):
        """Test content fields: issue_summary, patch_summary, failure_summary, test_summary."""
        record = MemoryRecord(
            memory_id="MEM-TEST001",
            task_id="test__test-123",
            repo="test/repo",
            sequence_index=0,
            memory_type="bug_fix",
            outcome="fail",
            issue_summary="Fix null pointer exception",
            patch_summary="Added null check in handler",
            failure_summary="Tests still failing on edge case",
            test_summary="3 tests pass, 1 fails",
        )
        assert record.issue_summary == "Fix null pointer exception"
        assert record.patch_summary == "Added null check in handler"
        assert record.failure_summary == "Tests still failing on edge case"
        assert record.test_summary == "3 tests pass, 1 fails"

    def test_structural_metadata_fields(self):
        """Test structural metadata: files_touched, functions_touched, commands_run."""
        record = MemoryRecord(
            memory_id="MEM-TEST001",
            task_id="test__test-123",
            repo="test/repo",
            sequence_index=0,
            memory_type="bug_fix",
            outcome="pass",
            issue_summary="Test issue",
            patch_summary="Test patch",
            files_touched=["src/main.py", "tests/test_main.py"],
            functions_touched=["handle_request", "validate_input"],
            commands_run=["pytest", "mypy"],
        )
        assert record.files_touched == ["src/main.py", "tests/test_main.py"]
        assert record.functions_touched == ["handle_request", "validate_input"]
        assert record.commands_run == ["pytest", "mypy"]

    def test_retrieval_provenance_fields(self):
        """Test retrieval provenance: retrieved_memory_ids_used."""
        record = MemoryRecord(
            memory_id="MEM-TEST001",
            task_id="test__test-123",
            repo="test/repo",
            sequence_index=0,
            memory_type="bug_fix",
            outcome="pass",
            issue_summary="Test issue",
            patch_summary="Test patch",
            retrieved_memory_ids_used=["MEM-001", "MEM-007", "MEM-091"],
        )
        assert record.retrieved_memory_ids_used == ["MEM-001", "MEM-007", "MEM-091"]

    def test_embedding_fields(self):
        """Test embedding fields: embedding_text, embedding_vector_id."""
        record = MemoryRecord(
            memory_id="MEM-TEST001",
            task_id="test__test-123",
            repo="test/repo",
            sequence_index=0,
            memory_type="bug_fix",
            outcome="pass",
            issue_summary="Test issue",
            patch_summary="Test patch",
            embedding_text="Issue: Test issue\nError: None\nDiff: Test patch",
            embedding_vector_id="FAISS-12345",
        )
        assert "Issue: Test issue" in record.embedding_text
        assert record.embedding_vector_id == "FAISS-12345"

    def test_usage_tracking_fields(self):
        """Test usage tracking: use_count, last_retrieved_at_step, success/failure counts."""
        record = MemoryRecord(
            memory_id="MEM-TEST001",
            task_id="test__test-123",
            repo="test/repo",
            sequence_index=0,
            memory_type="bug_fix",
            outcome="pass",
            issue_summary="Test issue",
            patch_summary="Test patch",
            use_count=5,
            last_retrieved_at_step=17,
            success_after_retrieval_count=3,
            failure_after_retrieval_count=2,
        )
        assert record.use_count == 5
        assert record.last_retrieved_at_step == 17
        assert record.success_after_retrieval_count == 3
        assert record.failure_after_retrieval_count == 2

    def test_lifecycle_fields(self):
        """Test lifecycle fields: importance_score, is_consolidated, source_memory_ids, is_archived."""
        record = MemoryRecord(
            memory_id="MEM-TEST001",
            task_id="test__test-123",
            repo="test/repo",
            sequence_index=0,
            memory_type="bug_fix",
            outcome="pass",
            issue_summary="Test issue",
            patch_summary="Test patch",
            importance_score=0.74,
            is_consolidated=True,
            source_memory_ids=["MEM-001", "MEM-002"],
            is_archived=True,
            archived_reason="recency_prune",
            archived_at_step=25,
        )
        assert record.importance_score == 0.74
        assert record.is_consolidated is True
        assert record.source_memory_ids == ["MEM-001", "MEM-002"]
        assert record.is_archived is True
        assert record.archived_reason == "recency_prune"
        assert record.archived_at_step == 25


class TestMemoryRecordSerialization:
    """Test serialization and deserialization methods."""

    def test_to_dict(self):
        """Test to_dict() returns all fields."""
        record = MemoryRecord(
            memory_id="MEM-TEST001",
            task_id="test__test-123",
            repo="test/repo",
            sequence_index=0,
            memory_type="bug_fix",
            outcome="pass",
            issue_summary="Test issue",
            patch_summary="Test patch",
        )
        data = record.to_dict()

        assert isinstance(data, dict)
        assert data["memory_id"] == "MEM-TEST001"
        assert data["task_id"] == "test__test-123"
        assert data["memory_type"] == "bug_fix"
        assert data["outcome"] == "pass"

    def test_from_dict(self):
        """Test from_dict() reconstructs MemoryRecord."""
        data = {
            "memory_id": "MEM-TEST001",
            "task_id": "test__test-123",
            "repo": "test/repo",
            "sequence_index": 0,
            "memory_type": "bug_fix",
            "outcome": "pass",
            "issue_summary": "Test issue",
            "patch_summary": "Test patch",
            "failure_summary": None,
            "test_summary": None,
            "files_touched": [],
            "functions_touched": [],
            "commands_run": [],
            "retrieved_memory_ids_used": [],
            "embedding_text": "",
            "embedding_vector_id": "",
            "token_length": 0,
            "raw_trace_ref": None,
            "use_count": 0,
            "last_retrieved_at_step": None,
            "success_after_retrieval_count": 0,
            "failure_after_retrieval_count": 0,
            "importance_score": 0.0,
            "is_consolidated": False,
            "source_memory_ids": None,
            "is_archived": False,
            "archived_reason": None,
            "archived_at_step": None,
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }

        record = MemoryRecord.from_dict(data)
        assert record.memory_id == "MEM-TEST001"
        assert record.task_id == "test__test-123"
        assert record.memory_type == "bug_fix"
        assert record.outcome == "pass"

    def test_to_json(self):
        """Test to_json() returns valid JSON string."""
        record = MemoryRecord(
            memory_id="MEM-TEST001",
            task_id="test__test-123",
            repo="test/repo",
            sequence_index=0,
            memory_type="bug_fix",
            outcome="pass",
            issue_summary="Test issue",
            patch_summary="Test patch",
        )
        json_str = record.to_json()

        assert isinstance(json_str, str)
        data = json.loads(json_str)
        assert data["memory_id"] == "MEM-TEST001"

    def test_from_json(self):
        """Test from_json() reconstructs MemoryRecord from JSON string."""
        json_str = """
        {
            "memory_id": "MEM-TEST001",
            "task_id": "test__test-123",
            "repo": "test/repo",
            "sequence_index": 0,
            "memory_type": "bug_fix",
            "outcome": "pass",
            "issue_summary": "Test issue",
            "patch_summary": "Test patch",
            "failure_summary": null,
            "test_summary": null,
            "files_touched": [],
            "functions_touched": [],
            "commands_run": [],
            "retrieved_memory_ids_used": [],
            "embedding_text": "",
            "embedding_vector_id": "",
            "token_length": 0,
            "raw_trace_ref": null,
            "use_count": 0,
            "last_retrieved_at_step": null,
            "success_after_retrieval_count": 0,
            "failure_after_retrieval_count": 0,
            "importance_score": 0.0,
            "is_consolidated": false,
            "source_memory_ids": null,
            "is_archived": false,
            "archived_reason": null,
            "archived_at_step": null,
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00"
        }
        """

        record = MemoryRecord.from_json(json_str)
        assert record.memory_id == "MEM-TEST001"
        assert record.task_id == "test__test-123"
        assert record.memory_type == "bug_fix"
        assert record.outcome == "pass"

    def test_roundtrip_dict(self):
        """Test roundtrip: record -> dict -> record."""
        original = MemoryRecord(
            memory_id="MEM-TEST001",
            task_id="test__test-123",
            repo="test/repo",
            sequence_index=5,
            memory_type="api_change",
            outcome="partial",
            issue_summary="Test issue",
            patch_summary="Test patch",
            files_touched=["src/api.py"],
            use_count=3,
        )

        data = original.to_dict()
        reconstructed = MemoryRecord.from_dict(data)

        assert reconstructed.memory_id == original.memory_id
        assert reconstructed.task_id == original.task_id
        assert reconstructed.memory_type == original.memory_type
        assert reconstructed.outcome == original.outcome
        assert reconstructed.sequence_index == original.sequence_index
        assert reconstructed.files_touched == original.files_touched
        assert reconstructed.use_count == original.use_count

    def test_roundtrip_json(self):
        """Test roundtrip: record -> json -> record."""
        original = MemoryRecord(
            memory_id="MEM-TEST001",
            task_id="test__test-123",
            repo="test/repo",
            sequence_index=5,
            memory_type="config",
            outcome="unknown",
            issue_summary="Test issue",
            patch_summary="Test patch",
        )

        json_str = original.to_json()
        reconstructed = MemoryRecord.from_json(json_str)

        assert reconstructed.memory_id == original.memory_id
        assert reconstructed.memory_type == original.memory_type
        assert reconstructed.outcome == original.outcome


class TestMemoryRecordUsageTracking:
    """Test usage tracking update methods."""

    def test_update_usage_increments_use_count(self):
        """Test update_usage() increments use_count."""
        record = MemoryRecord(
            memory_id="MEM-TEST001",
            task_id="test__test-123",
            repo="test/repo",
            sequence_index=0,
            memory_type="bug_fix",
            outcome="pass",
            issue_summary="Test issue",
            patch_summary="Test patch",
        )

        assert record.use_count == 0
        record.update_usage(step=5)
        assert record.use_count == 1
        record.update_usage(step=10)
        assert record.use_count == 2

    def test_update_usage_sets_last_retrieved_step(self):
        """Test update_usage() sets last_retrieved_at_step."""
        record = MemoryRecord(
            memory_id="MEM-TEST001",
            task_id="test__test-123",
            repo="test/repo",
            sequence_index=0,
            memory_type="bug_fix",
            outcome="pass",
            issue_summary="Test issue",
            patch_summary="Test patch",
        )

        record.update_usage(step=17)
        assert record.last_retrieved_at_step == 17

        record.update_usage(step=25)
        assert record.last_retrieved_at_step == 25

    def test_update_usage_tracks_success(self):
        """Test update_usage() tracks success_after_retrieval_count."""
        record = MemoryRecord(
            memory_id="MEM-TEST001",
            task_id="test__test-123",
            repo="test/repo",
            sequence_index=0,
            memory_type="bug_fix",
            outcome="pass",
            issue_summary="Test issue",
            patch_summary="Test patch",
        )

        assert record.success_after_retrieval_count == 0
        record.update_usage(step=5, task_succeeded=True)
        assert record.success_after_retrieval_count == 1
        record.update_usage(step=10, task_succeeded=True)
        assert record.success_after_retrieval_count == 2

    def test_update_usage_tracks_failure(self):
        """Test update_usage() tracks failure_after_retrieval_count."""
        record = MemoryRecord(
            memory_id="MEM-TEST001",
            task_id="test__test-123",
            repo="test/repo",
            sequence_index=0,
            memory_type="bug_fix",
            outcome="pass",
            issue_summary="Test issue",
            patch_summary="Test patch",
        )

        assert record.failure_after_retrieval_count == 0
        record.update_usage(step=5, task_succeeded=False)
        assert record.failure_after_retrieval_count == 1
        record.update_usage(step=10, task_succeeded=False)
        assert record.failure_after_retrieval_count == 2

    def test_update_usage_without_outcome(self):
        """Test update_usage() with task_succeeded=None doesn't update success/failure counts."""
        record = MemoryRecord(
            memory_id="MEM-TEST001",
            task_id="test__test-123",
            repo="test/repo",
            sequence_index=0,
            memory_type="bug_fix",
            outcome="pass",
            issue_summary="Test issue",
            patch_summary="Test patch",
        )

        record.update_usage(step=5, task_succeeded=None)
        assert record.use_count == 1
        assert record.success_after_retrieval_count == 0
        assert record.failure_after_retrieval_count == 0


class TestMemoryRecordLifecycle:
    """Test lifecycle management methods."""

    def test_archive(self):
        """Test archive() marks record as archived."""
        record = MemoryRecord(
            memory_id="MEM-TEST001",
            task_id="test__test-123",
            repo="test/repo",
            sequence_index=0,
            memory_type="bug_fix",
            outcome="pass",
            issue_summary="Test issue",
            patch_summary="Test patch",
        )

        assert record.is_archived is False
        record.archive(reason="recency_prune", step=25)

        assert record.is_archived is True
        assert record.archived_reason == "recency_prune"
        assert record.archived_at_step == 25

    def test_set_importance_score(self):
        """Test set_importance_score() updates importance_score."""
        record = MemoryRecord(
            memory_id="MEM-TEST001",
            task_id="test__test-123",
            repo="test/repo",
            sequence_index=0,
            memory_type="bug_fix",
            outcome="pass",
            issue_summary="Test issue",
            patch_summary="Test patch",
        )

        assert record.importance_score == 0.0
        record.set_importance_score(0.74)
        assert record.importance_score == 0.74

    def test_mark_consolidated(self):
        """Test mark_consolidated() marks record as consolidated."""
        record = MemoryRecord(
            memory_id="MEM-CONS-001",
            task_id="test__test-123",
            repo="test/repo",
            sequence_index=0,
            memory_type="bug_fix",
            outcome="pass",
            issue_summary="Consolidated summary",
            patch_summary="Multiple patches consolidated",
        )

        assert record.is_consolidated is False
        assert record.source_memory_ids is None

        record.mark_consolidated(source_ids=["MEM-001", "MEM-002", "MEM-003"])

        assert record.is_consolidated is True
        assert record.source_memory_ids == ["MEM-001", "MEM-002", "MEM-003"]


class TestMemoryRecordHelpers:
    """Test helper functions and methods."""

    def test_generate_id_format(self):
        """Test generate_id() returns correctly formatted ID."""
        memory_id = MemoryRecord.generate_id()
        assert memory_id.startswith("MEM-")
        assert len(memory_id) == 12  # "MEM-" + 8 hex chars

    def test_generate_id_unique(self):
        """Test generate_id() generates unique IDs."""
        ids = [MemoryRecord.generate_id() for _ in range(100)]
        assert len(ids) == len(set(ids))  # all unique

    def test_validate_orthogonal_axes_valid(self):
        """Test validate_orthogonal_axes() accepts valid combinations."""
        # Should not raise
        validate_orthogonal_axes("bug_fix", "pass")
        validate_orthogonal_axes("bug_fix", "fail")
        validate_orthogonal_axes("architectural", "unknown")
        validate_orthogonal_axes("config", "partial")

    def test_validate_orthogonal_axes_invalid_type(self):
        """Test validate_orthogonal_axes() rejects invalid memory_type."""
        with pytest.raises(ValueError, match="Invalid memory_type"):
            validate_orthogonal_axes("invalid_type", "pass")

    def test_validate_orthogonal_axes_invalid_outcome(self):
        """Test validate_orthogonal_axes() rejects invalid outcome."""
        with pytest.raises(ValueError, match="Invalid outcome"):
            validate_orthogonal_axes("bug_fix", "invalid_outcome")

    def test_repr(self):
        """Test __repr__() returns concise string representation."""
        record = MemoryRecord(
            memory_id="MEM-TEST001",
            task_id="test__test-123",
            repo="test/repo",
            sequence_index=5,
            memory_type="bug_fix",
            outcome="pass",
            issue_summary="Test issue",
            patch_summary="Test patch",
        )

        repr_str = repr(record)
        assert "MEM-TEST001" in repr_str
        assert "test__test-123" in repr_str
        assert "bug_fix" in repr_str
        assert "pass" in repr_str
        assert "seq_idx=5" in repr_str


class TestMemoryRecordEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_lists_default(self):
        """Test that list fields default to empty lists."""
        record = MemoryRecord(
            memory_id="MEM-TEST001",
            task_id="test__test-123",
            repo="test/repo",
            sequence_index=0,
            memory_type="bug_fix",
            outcome="pass",
            issue_summary="Test issue",
            patch_summary="Test patch",
        )

        assert record.files_touched == []
        assert record.functions_touched == []
        assert record.commands_run == []
        assert record.retrieved_memory_ids_used == []

    def test_optional_fields_none(self):
        """Test that optional fields can be None."""
        record = MemoryRecord(
            memory_id="MEM-TEST001",
            task_id="test__test-123",
            repo="test/repo",
            sequence_index=0,
            memory_type="bug_fix",
            outcome="pass",
            issue_summary="Test issue",
            patch_summary="Test patch",
            failure_summary=None,
            test_summary=None,
            raw_trace_ref=None,
            last_retrieved_at_step=None,
            source_memory_ids=None,
            archived_reason=None,
            archived_at_step=None,
        )

        assert record.failure_summary is None
        assert record.test_summary is None
        assert record.raw_trace_ref is None
        assert record.last_retrieved_at_step is None
        assert record.source_memory_ids is None
        assert record.archived_reason is None
        assert record.archived_at_step is None

    def test_zero_sequence_index(self):
        """Test that sequence_index=0 is valid."""
        record = MemoryRecord(
            memory_id="MEM-TEST001",
            task_id="test__test-123",
            repo="test/repo",
            sequence_index=0,
            memory_type="bug_fix",
            outcome="pass",
            issue_summary="Test issue",
            patch_summary="Test patch",
        )
        assert record.sequence_index == 0

    def test_large_sequence_index(self):
        """Test that large sequence_index values are valid."""
        record = MemoryRecord(
            memory_id="MEM-TEST001",
            task_id="test__test-123",
            repo="test/repo",
            sequence_index=999,
            memory_type="bug_fix",
            outcome="pass",
            issue_summary="Test issue",
            patch_summary="Test patch",
        )
        assert record.sequence_index == 999

    def test_timestamps_auto_generated(self):
        """Test that created_at and updated_at are auto-generated."""
        record = MemoryRecord(
            memory_id="MEM-TEST001",
            task_id="test__test-123",
            repo="test/repo",
            sequence_index=0,
            memory_type="bug_fix",
            outcome="pass",
            issue_summary="Test issue",
            patch_summary="Test patch",
        )

        assert record.created_at is not None
        assert record.updated_at is not None
        # Should be valid ISO format
        datetime.fromisoformat(record.created_at)
        datetime.fromisoformat(record.updated_at)
