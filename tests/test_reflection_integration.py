"""
Integration tests for the reflection step.

Tests the complete reflection workflow including extraction, classification,
and memory record construction.

Requirements: 15
Design: §9 Memory Writing & Reflection Step
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

from src.memory.reflection import (
    reflect_and_write_memory,
    ReflectionError,
    _extract_reflection_data,
    _construct_memory_record,
    _construct_embedding_text,
)
from src.memory.classifier import ClassifierError
from src.memory.record import VALID_MEMORY_TYPES, VALID_OUTCOMES


class TestReflectionExtraction:
    """Test reflection data extraction."""

    def test_extract_reflection_data_basic(self):
        """Test basic reflection data extraction."""
        task = Mock()
        task.task_id = "test-task-1"
        task.repo = "test/repo"
        task.issue_text = "Fix bug in function foo()"

        trajectory = {
            "files_modified": ["src/foo.py"],
            "files_read": ["src/foo.py", "tests/test_foo.py"],
            "commands_run": ["pytest", "git diff"],
            "functions_touched": ["foo", "bar"]
        }

        patch = "+fixed line\n-broken line"

        evaluation_result = {
            "resolved": True,
            "error_message": None,
            "test_output": "5 passed in 2.3s"
        }

        data = _extract_reflection_data(
            task=task,
            trajectory=trajectory,
            patch=patch,
            evaluation_result=evaluation_result,
            model="gpt-4o-mini",
            temperature=0.0
        )

        # Verify extracted data
        assert "issue_summary" in data
        assert "patch_summary" in data
        assert "failure_summary" in data
        assert "test_summary" in data
        assert "files_touched" in data
        assert "functions_touched" in data
        assert "commands_run" in data
        assert "outcome" in data

        # Verify specific values
        assert data["outcome"] == "pass"
        assert "src/foo.py" in data["files_touched"]
        assert "tests/test_foo.py" in data["files_touched"]
        assert data["commands_run"] == ["pytest", "git diff"]

    def test_extract_reflection_data_failed_task(self):
        """Test reflection data extraction for failed task."""
        task = Mock()
        task.task_id = "test-task-2"
        task.repo = "test/repo"
        task.issue_text = "Fix bug"

        trajectory = {
            "files_modified": ["src/foo.py"],
            "files_read": [],
            "commands_run": ["pytest"],
            "functions_touched": []
        }

        patch = "+attempted fix"

        evaluation_result = {
            "resolved": False,
            "error_message": "AssertionError: Expected 2, got 3",
            "test_output": "3 passed, 2 failed"
        }

        data = _extract_reflection_data(
            task=task,
            trajectory=trajectory,
            patch=patch,
            evaluation_result=evaluation_result,
            model="gpt-4o-mini",
            temperature=0.0
        )

        # Verify failure fields
        assert data["outcome"] == "fail"
        assert data["failure_summary"] is not None
        assert "AssertionError" in data["failure_summary"]


class TestMemoryRecordConstruction:
    """Test memory record construction."""

    def test_construct_memory_record(self):
        """Test construction of complete memory record."""
        task = Mock()
        task.task_id = "test-task-1"
        task.repo = "test/repo"

        reflection_data = {
            "issue_summary": "Fix bug in foo()",
            "patch_summary": "Modified src/foo.py",
            "failure_summary": None,
            "test_summary": "5 passed",
            "files_touched": ["src/foo.py"],
            "functions_touched": ["foo"],
            "commands_run": ["pytest"],
            "outcome": "pass"
        }

        memory_type = "bug_fix"
        retrieved_memory_ids = ["MEM-001", "MEM-002"]
        sequence_index = 5

        record = _construct_memory_record(
            task=task,
            reflection_data=reflection_data,
            memory_type=memory_type,
            retrieved_memory_ids=retrieved_memory_ids,
            sequence_index=sequence_index
        )

        # Verify record fields
        assert record.task_id == "test-task-1"
        assert record.repo == "test/repo"
        assert record.sequence_index == 5
        assert record.memory_type == "bug_fix"
        assert record.outcome == "pass"
        assert record.issue_summary == "Fix bug in foo()"
        assert record.patch_summary == "Modified src/foo.py"
        assert record.failure_summary is None
        assert record.test_summary == "5 passed"
        assert record.files_touched == ["src/foo.py"]
        assert record.functions_touched == ["foo"]
        assert record.commands_run == ["pytest"]
        assert record.retrieved_memory_ids_used == ["MEM-001", "MEM-002"]
        assert record.memory_id.startswith("MEM-")
        # embedding_text is now built by MemoryStore.add() (Invariant #4
        # truncation), NOT pre-set by reflection — see plan 2.4 / repair Task 3
        # and test_construct_memory_record_leaves_embedding_to_store.
        assert record.embedding_text == ""
        assert record.token_length == 0


class TestEmbeddingTextConstruction:
    """Test embedding text construction."""

    def test_construct_embedding_text_with_failure(self):
        """Test embedding text construction with failure."""
        text = _construct_embedding_text(
            issue_summary="Fix bug in QuerySet",
            failure_summary="AssertionError: Expected 2",
            patch_summary="Modified query.py: +5 -2 lines"
        )

        assert "Issue: Fix bug in QuerySet" in text
        assert "Error: AssertionError: Expected 2" in text
        assert "Patch: Modified query.py: +5 -2 lines" in text

    def test_construct_embedding_text_without_failure(self):
        """Test embedding text construction without failure (passed task)."""
        text = _construct_embedding_text(
            issue_summary="Add feature X",
            failure_summary=None,
            patch_summary="Modified feature.py: +10 -0 lines"
        )

        assert "Issue: Add feature X" in text
        assert "Error:" not in text
        assert "Patch: Modified feature.py: +10 -0 lines" in text


class TestReflectAndWriteMemory:
    """Test the complete reflect_and_write_memory workflow."""

    @patch('src.memory.reflection.classify_memory_type')
    def test_reflect_and_write_successful_task(self, mock_classify):
        """Test complete reflection workflow for successful task."""
        # Setup mocks
        mock_classify.return_value = "bug_fix"

        task = Mock()
        task.task_id = "django__django-12345"
        task.repo = "django/django"
        task.issue_text = "Fix bug in QuerySet.exclude()"

        trajectory = {
            "files_modified": ["django/db/models/query.py"],
            "files_read": ["django/db/models/query.py", "tests/test_query.py"],
            "commands_run": ["pytest", "git diff"],
            "functions_touched": ["exclude", "_filter_or_exclude_inplace"]
        }

        patch = "+fixed line\n-broken line"

        evaluation_result = {
            "resolved": True,
            "error_message": None,
            "test_output": "5 passed in 2.3s"
        }

        memory_store = Mock()
        policy = Mock()
        policy.name = "full_memory"

        retrieved_memory_ids = ["MEM-001", "MEM-002"]
        sequence_index = 5

        # Execute reflection
        record = reflect_and_write_memory(
            task=task,
            trajectory=trajectory,
            patch=patch,
            evaluation_result=evaluation_result,
            memory_store=memory_store,
            policy=policy,
            retrieved_memory_ids=retrieved_memory_ids,
            sequence_index=sequence_index
        )

        # Verify record was created
        assert record is not None
        assert record.task_id == "django__django-12345"
        assert record.memory_type == "bug_fix"
        assert record.outcome == "pass"

        # Verify policy.write was called
        policy.write.assert_called_once()
        assert policy.write.call_args[0][0] == memory_store
        assert policy.write.call_args[0][1] == record

        # Verify classifier was called
        mock_classify.assert_called_once()

    @patch('src.memory.reflection.classify_memory_type')
    def test_reflect_fails_when_classifier_fails(self, mock_classify):
        """Test that reflection fails entirely when classifier fails."""
        # Setup classifier to fail
        mock_classify.side_effect = ClassifierError("Classifier unavailable")

        task = Mock()
        task.task_id = "test-task"
        task.repo = "test/repo"
        task.issue_text = "Test issue"

        trajectory = {
            "files_modified": [],
            "files_read": [],
            "commands_run": [],
            "functions_touched": []
        }

        evaluation_result = {
            "resolved": True,
            "error_message": None,
            "test_output": None
        }

        memory_store = Mock()
        policy = Mock()

        # Verify reflection fails
        with pytest.raises(ReflectionError) as exc_info:
            reflect_and_write_memory(
                task=task,
                trajectory=trajectory,
                patch=None,
                evaluation_result=evaluation_result,
                memory_store=memory_store,
                policy=policy,
                retrieved_memory_ids=[],
                sequence_index=0
            )

        assert "type classification unavailable" in str(exc_info.value).lower()

        # Verify policy.write was NOT called
        policy.write.assert_not_called()

    @patch('src.memory.reflection.classify_memory_type')
    def test_reflect_updates_retrieved_memory_usage(self, mock_classify):
        """Test that retrieved memory usage is updated."""
        mock_classify.return_value = "bug_fix"

        task = Mock()
        task.task_id = "test-task"
        task.repo = "test/repo"
        task.issue_text = "Test"

        trajectory = {
            "files_modified": [],
            "files_read": [],
            "commands_run": [],
            "functions_touched": []
        }

        evaluation_result = {
            "resolved": True,
            "error_message": None,
            "test_output": None
        }

        memory_store = Mock()
        policy = Mock()

        retrieved_memory_ids = ["MEM-001", "MEM-002", "MEM-003"]
        sequence_index = 10

        # Execute reflection
        reflect_and_write_memory(
            task=task,
            trajectory=trajectory,
            patch="+test",
            evaluation_result=evaluation_result,
            memory_store=memory_store,
            policy=policy,
            retrieved_memory_ids=retrieved_memory_ids,
            sequence_index=sequence_index
        )

        # Verify update_usage was called for each retrieved memory
        assert memory_store.update_usage.call_count == 3

        # Verify calls were made with correct parameters
        calls = memory_store.update_usage.call_args_list
        for i, memory_id in enumerate(retrieved_memory_ids):
            assert calls[i][1]["memory_id"] == memory_id
            assert calls[i][1]["step"] == sequence_index
            assert calls[i][1]["task_succeeded"] is True


class TestRequirement15Compliance:
    """Test compliance with Requirement 15 acceptance criteria."""

    @patch('src.memory.reflection.classify_memory_type')
    def test_requirement_15_1_generates_structured_record(self, mock_classify):
        """Requirement 15.1: Generate structured memory record from task."""
        mock_classify.return_value = "bug_fix"

        task = Mock()
        task.task_id = "test-task"
        task.repo = "test/repo"
        task.issue_text = "Test"

        trajectory = {"files_modified": [], "files_read": [], "commands_run": [], "functions_touched": []}
        evaluation_result = {"resolved": True, "error_message": None, "test_output": None}

        memory_store = Mock()
        policy = Mock()

        record = reflect_and_write_memory(
            task=task,
            trajectory=trajectory,
            patch="+test",
            evaluation_result=evaluation_result,
            memory_store=memory_store,
            policy=policy,
            retrieved_memory_ids=[],
            sequence_index=0
        )

        assert record is not None
        assert hasattr(record, 'issue_summary')
        assert hasattr(record, 'patch_summary')
        assert hasattr(record, 'failure_summary')
        assert hasattr(record, 'test_summary')

    def test_requirement_15_2_extracts_structural_metadata(self):
        """Requirement 15.2: Extract files_touched, functions_touched, commands_run."""
        task = Mock()
        task.task_id = "test-task"
        task.repo = "test/repo"
        task.issue_text = "Test"

        trajectory = {
            "files_modified": ["file1.py"],
            "files_read": ["file2.py"],
            "commands_run": ["pytest", "git diff"],
            "functions_touched": ["foo", "bar"]
        }

        evaluation_result = {"resolved": True, "error_message": None, "test_output": None}

        data = _extract_reflection_data(
            task=task,
            trajectory=trajectory,
            patch="+test",
            evaluation_result=evaluation_result,
            model="gpt-4o-mini",
            temperature=0.0
        )

        assert "file1.py" in data["files_touched"]
        assert "file2.py" in data["files_touched"]
        assert data["commands_run"] == ["pytest", "git diff"]
        assert data["functions_touched"] == ["foo", "bar"]

    @patch('src.memory.reflection.classify_memory_type')
    def test_requirement_15_3_records_retrieved_memory_ids(self, mock_classify):
        """Requirement 15.3: Record retrieved_memory_ids_used."""
        mock_classify.return_value = "bug_fix"

        task = Mock()
        task.task_id = "test-task"
        task.repo = "test/repo"
        task.issue_text = "Test"

        trajectory = {"files_modified": [], "files_read": [], "commands_run": [], "functions_touched": []}
        evaluation_result = {"resolved": True, "error_message": None, "test_output": None}

        memory_store = Mock()
        policy = Mock()

        retrieved_ids = ["MEM-001", "MEM-007", "MEM-042"]

        record = reflect_and_write_memory(
            task=task,
            trajectory=trajectory,
            patch="+test",
            evaluation_result=evaluation_result,
            memory_store=memory_store,
            policy=policy,
            retrieved_memory_ids=retrieved_ids,
            sequence_index=0
        )

        assert record.retrieved_memory_ids_used == retrieved_ids

    @patch('src.memory.reflection.classify_memory_type')
    def test_requirement_15_4_invokes_type_classifier(self, mock_classify):
        """Requirement 15.4: Invoke type classifier to assign memory_type."""
        mock_classify.return_value = "api_change"

        task = Mock()
        task.task_id = "test-task"
        task.repo = "test/repo"
        task.issue_text = "Test"

        trajectory = {"files_modified": [], "files_read": [], "commands_run": [], "functions_touched": []}
        evaluation_result = {"resolved": True, "error_message": None, "test_output": None}

        memory_store = Mock()
        policy = Mock()

        record = reflect_and_write_memory(
            task=task,
            trajectory=trajectory,
            patch="+test",
            evaluation_result=evaluation_result,
            memory_store=memory_store,
            policy=policy,
            retrieved_memory_ids=[],
            sequence_index=0
        )

        # Verify classifier was called
        mock_classify.assert_called_once()

        # Verify memory_type was assigned
        assert record.memory_type == "api_change"

    @patch('src.memory.reflection.classify_memory_type')
    def test_requirement_15_5_fails_if_classifier_unavailable(self, mock_classify):
        """Requirement 15.5: Fail entirely if classifier unavailable."""
        mock_classify.side_effect = ClassifierError("Classifier unavailable")

        task = Mock()
        task.task_id = "test-task"
        task.repo = "test/repo"
        task.issue_text = "Test"

        trajectory = {"files_modified": [], "files_read": [], "commands_run": [], "functions_touched": []}
        evaluation_result = {"resolved": True, "error_message": None, "test_output": None}

        memory_store = Mock()
        policy = Mock()

        with pytest.raises(ReflectionError):
            reflect_and_write_memory(
                task=task,
                trajectory=trajectory,
                patch="+test",
                evaluation_result=evaluation_result,
                memory_store=memory_store,
                policy=policy,
                retrieved_memory_ids=[],
                sequence_index=0
            )

    @patch('src.memory.reflection.classify_memory_type')
    def test_requirement_15_6_type_assigned_before_write(self, mock_classify):
        """Requirement 15.6: Type assignment completes before write."""
        mock_classify.return_value = "bug_fix"

        task = Mock()
        task.task_id = "test-task"
        task.repo = "test/repo"
        task.issue_text = "Test"

        trajectory = {"files_modified": [], "files_read": [], "commands_run": [], "functions_touched": []}
        evaluation_result = {"resolved": True, "error_message": None, "test_output": None}

        memory_store = Mock()
        policy = Mock()

        # Track call order
        call_order = []
        mock_classify.side_effect = lambda *args, **kwargs: (call_order.append("classify"), "bug_fix")[1]
        policy.write.side_effect = lambda *args, **kwargs: call_order.append("write")

        reflect_and_write_memory(
            task=task,
            trajectory=trajectory,
            patch="+test",
            evaluation_result=evaluation_result,
            memory_store=memory_store,
            policy=policy,
            retrieved_memory_ids=[],
            sequence_index=0
        )

        # Verify classify was called before write
        assert call_order == ["classify", "write"]


def test_construct_memory_record_leaves_embedding_to_store():
    """plan 2.4 / repair Task 3: reflection must NOT pre-set embedding_text;
    MemoryStore.add() owns canonical (truncating) construction (Invariant #4)."""
    task = Mock()
    task.task_id = "django__django-1"
    task.repo = "django/django"
    task.issue_text = "Fix query bug"

    reflection_data = {
        "issue_summary": "Fix query bug",
        "patch_summary": "diff --git a/q.py b/q.py",
        "failure_summary": None,
        "test_summary": None,
        "files_touched": ["q.py"],
        "functions_touched": [],
        "commands_run": ["pytest"],
        "outcome": "pass",
    }

    record = _construct_memory_record(
        task=task,
        reflection_data=reflection_data,
        memory_type="bug_fix",
        retrieved_memory_ids=[],
        sequence_index=0,
    )

    assert record.embedding_text == ""
    assert record.token_length == 0
    # Summaries stay populated so MemoryStore.add() can build the payload.
    assert record.issue_summary == "Fix query bug"
    assert record.patch_summary == "diff --git a/q.py b/q.py"
