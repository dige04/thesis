"""Unit tests for MemorySnapshotLogger.

Tests verify that memory snapshots are correctly generated at task boundaries
with all required fields and proper JSON formatting.

Requirements: THESIS_FINAL_v5.md §11.4, §25
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.logging.memory_snapshot_logger import MemorySnapshotLogger
from src.memory.record import MemoryRecord


@pytest.fixture
def temp_snapshot_dir():
    """Create temporary directory for snapshot tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_records():
    """Create sample memory records for testing."""
    return [
        MemoryRecord(
            memory_id="MEM-001",
            task_id="task-1",
            repo="django/django",
            sequence_index=5,
            memory_type="architectural",
            outcome="pass",
            issue_summary="Add user authentication",
            patch_summary="Implemented JWT auth",
            failure_summary=None,
            test_summary="All tests passed",
            files_touched=["auth.py", "models.py"],
            functions_touched=["authenticate", "create_token"],
            commands_run=["pytest"],
            retrieved_memory_ids_used=[],
            embedding_text="Issue: Add user authentication\nFinal Error: (none)\nFinal Diff: Implemented JWT auth",
            embedding_vector_id="0",
            token_length=100,
            raw_trace_ref=None,
            use_count=3,
            last_retrieved_at_step=10,
            success_after_retrieval_count=2,
            failure_after_retrieval_count=1,
            importance_score=0.85,
            is_consolidated=False,
            source_memory_ids=None,
            is_archived=False,
            archived_reason=None,
            archived_at_step=None
        ),
        MemoryRecord(
            memory_id="MEM-002",
            task_id="task-2",
            repo="django/django",
            sequence_index=8,
            memory_type="bug_fix",
            outcome="pass",
            issue_summary="Fix login redirect",
            patch_summary="Fixed redirect URL",
            failure_summary=None,
            test_summary="Tests passed",
            files_touched=["views.py"],
            functions_touched=["login_view"],
            commands_run=["pytest"],
            retrieved_memory_ids_used=["MEM-001"],
            embedding_text="Issue: Fix login redirect\nFinal Error: (none)\nFinal Diff: Fixed redirect URL",
            embedding_vector_id="1",
            token_length=80,
            raw_trace_ref=None,
            use_count=1,
            last_retrieved_at_step=12,
            success_after_retrieval_count=1,
            failure_after_retrieval_count=0,
            importance_score=0.62,
            is_consolidated=False,
            source_memory_ids=None,
            is_archived=False,
            archived_reason=None,
            archived_at_step=None
        )
    ]


def test_snapshot_logger_initialization(temp_snapshot_dir):
    """Test MemorySnapshotLogger initialization."""
    logger = MemorySnapshotLogger(
        snapshot_dir=temp_snapshot_dir,
        run_id="test-run-001",
        policy_name="type_aware_decay"
    )

    assert logger.snapshot_dir == temp_snapshot_dir
    assert logger.run_id == "test-run-001"
    assert logger.policy_name == "type_aware_decay"
    assert temp_snapshot_dir.exists()


def test_log_snapshot_creates_file(temp_snapshot_dir, sample_records):
    """Test that log_snapshot creates a JSON file with correct name."""
    logger = MemorySnapshotLogger(
        snapshot_dir=temp_snapshot_dir,
        run_id="test-run-001",
        policy_name="type_aware_decay"
    )

    snapshot = logger.log_snapshot(
        step=10,
        boundary="before_task",
        active_records=sample_records,
        current_step=12
    )

    # Check file was created
    snapshot_file = temp_snapshot_dir / "before_task_10.json"
    assert snapshot_file.exists()

    # Check file is valid JSON
    with open(snapshot_file) as f:
        data = json.load(f)

    assert data == snapshot


def test_snapshot_contains_required_fields(temp_snapshot_dir, sample_records):
    """Test that snapshot contains all required fields from §11.4."""
    logger = MemorySnapshotLogger(
        snapshot_dir=temp_snapshot_dir,
        run_id="test-run-001",
        policy_name="type_aware_decay"
    )

    snapshot = logger.log_snapshot(
        step=10,
        boundary="after_task",
        active_records=sample_records,
        archived_this_step=["MEM-003", "MEM-004"],
        current_step=12
    )

    # Required fields from §11.4
    assert "step" in snapshot
    assert "boundary" in snapshot
    assert "active_records" in snapshot
    assert "timestamp" in snapshot

    # Check step and boundary values
    assert snapshot["step"] == 10
    assert snapshot["boundary"] == "after_task"

    # Check active_records structure
    assert len(snapshot["active_records"]) == 2

    for record in snapshot["active_records"]:
        assert "memory_id" in record
        assert "importance_score" in record
        assert "memory_type" in record
        assert "age" in record

    # Check archived records
    assert "archived_this_step" in snapshot
    assert snapshot["archived_this_step"] == ["MEM-003", "MEM-004"]


def test_snapshot_age_calculation(temp_snapshot_dir, sample_records):
    """Test that age is correctly calculated as current_step - sequence_index."""
    logger = MemorySnapshotLogger(
        snapshot_dir=temp_snapshot_dir,
        run_id="test-run-001",
        policy_name="type_aware_decay"
    )

    current_step = 15
    snapshot = logger.log_snapshot(
        step=15,
        boundary="before_task",
        active_records=sample_records,
        current_step=current_step
    )

    # MEM-001: sequence_index=5, current_step=15 -> age=10
    # MEM-002: sequence_index=8, current_step=15 -> age=7
    assert snapshot["active_records"][0]["age"] == 10
    assert snapshot["active_records"][1]["age"] == 7


def test_snapshot_preserves_importance_scores(temp_snapshot_dir, sample_records):
    """Test that importance scores are preserved in snapshot."""
    logger = MemorySnapshotLogger(
        snapshot_dir=temp_snapshot_dir,
        run_id="test-run-001",
        policy_name="type_aware_decay"
    )

    snapshot = logger.log_snapshot(
        step=10,
        boundary="before_task",
        active_records=sample_records,
        current_step=12
    )

    # Check importance scores match
    assert snapshot["active_records"][0]["importance_score"] == 0.85
    assert snapshot["active_records"][1]["importance_score"] == 0.62


def test_snapshot_preserves_memory_types(temp_snapshot_dir, sample_records):
    """Test that memory types are preserved in snapshot."""
    logger = MemorySnapshotLogger(
        snapshot_dir=temp_snapshot_dir,
        run_id="test-run-001",
        policy_name="type_aware_decay"
    )

    snapshot = logger.log_snapshot(
        step=10,
        boundary="before_task",
        active_records=sample_records,
        current_step=12
    )

    # Check memory types match
    assert snapshot["active_records"][0]["memory_type"] == "architectural"
    assert snapshot["active_records"][1]["memory_type"] == "bug_fix"


def test_snapshot_json_formatting(temp_snapshot_dir, sample_records):
    """Test that snapshot JSON is pretty-printed with indent=2."""
    logger = MemorySnapshotLogger(
        snapshot_dir=temp_snapshot_dir,
        run_id="test-run-001",
        policy_name="type_aware_decay"
    )

    logger.log_snapshot(
        step=10,
        boundary="before_task",
        active_records=sample_records,
        current_step=12
    )

    snapshot_file = temp_snapshot_dir / "before_task_10.json"

    # Read raw file content
    with open(snapshot_file) as f:
        content = f.read()

    # Check for indentation (pretty-printed)
    assert "  " in content  # Should have 2-space indentation
    assert "\n" in content  # Should have newlines


def test_load_snapshot(temp_snapshot_dir, sample_records):
    """Test loading a previously saved snapshot."""
    logger = MemorySnapshotLogger(
        snapshot_dir=temp_snapshot_dir,
        run_id="test-run-001",
        policy_name="type_aware_decay"
    )

    # Save snapshot
    original = logger.log_snapshot(
        step=10,
        boundary="before_task",
        active_records=sample_records,
        current_step=12
    )

    # Load snapshot
    loaded = logger.load_snapshot(step=10, boundary="before_task")

    # Should match original
    assert loaded == original


def test_load_snapshot_missing_file(temp_snapshot_dir):
    """Test that loading non-existent snapshot raises FileNotFoundError."""
    logger = MemorySnapshotLogger(
        snapshot_dir=temp_snapshot_dir,
        run_id="test-run-001",
        policy_name="type_aware_decay"
    )

    with pytest.raises(FileNotFoundError):
        logger.load_snapshot(step=999, boundary="before_task")


def test_list_snapshots(temp_snapshot_dir, sample_records):
    """Test listing all available snapshots."""
    logger = MemorySnapshotLogger(
        snapshot_dir=temp_snapshot_dir,
        run_id="test-run-001",
        policy_name="type_aware_decay"
    )

    # Create multiple snapshots
    logger.log_snapshot(step=5, boundary="before_task", active_records=sample_records, current_step=5)
    logger.log_snapshot(step=5, boundary="after_task", active_records=sample_records, current_step=5)
    logger.log_snapshot(step=10, boundary="before_task", active_records=sample_records, current_step=10)
    logger.log_snapshot(step=10, boundary="after_task", active_records=sample_records, current_step=10)

    # List snapshots
    snapshots = logger.list_snapshots()

    # Should be sorted by step, then boundary
    assert len(snapshots) == 4
    assert (5, "after_task") in snapshots
    assert (5, "before_task") in snapshots
    assert (10, "after_task") in snapshots
    assert (10, "before_task") in snapshots


def test_verify_complete_coverage_success(temp_snapshot_dir, sample_records):
    """Test verify_complete_coverage with all snapshots present."""
    logger = MemorySnapshotLogger(
        snapshot_dir=temp_snapshot_dir,
        run_id="test-run-001",
        policy_name="type_aware_decay"
    )

    # Create snapshots for 3 tasks
    for step in range(3):
        logger.log_snapshot(step=step, boundary="before_task", active_records=sample_records, current_step=step)
        logger.log_snapshot(step=step, boundary="after_task", active_records=sample_records, current_step=step)

    # Verify coverage
    is_complete, missing = logger.verify_complete_coverage(num_tasks=3)

    assert is_complete is True
    assert len(missing) == 0


def test_verify_complete_coverage_missing(temp_snapshot_dir, sample_records):
    """Test verify_complete_coverage with missing snapshots."""
    logger = MemorySnapshotLogger(
        snapshot_dir=temp_snapshot_dir,
        run_id="test-run-001",
        policy_name="type_aware_decay"
    )

    # Create only some snapshots
    logger.log_snapshot(step=0, boundary="before_task", active_records=sample_records, current_step=0)
    logger.log_snapshot(step=1, boundary="after_task", active_records=sample_records, current_step=1)

    # Verify coverage for 3 tasks
    is_complete, missing = logger.verify_complete_coverage(num_tasks=3)

    assert is_complete is False
    assert len(missing) > 0
    assert "after_task_0" in missing
    assert "before_task_1" in missing


def test_snapshot_with_empty_active_records(temp_snapshot_dir):
    """Test snapshot with no active records (edge case)."""
    logger = MemorySnapshotLogger(
        snapshot_dir=temp_snapshot_dir,
        run_id="test-run-001",
        policy_name="no_memory"
    )

    snapshot = logger.log_snapshot(
        step=0,
        boundary="before_task",
        active_records=[],
        current_step=0
    )

    assert snapshot["active_records"] == []
    assert snapshot["metadata"]["active_count"] == 0


def test_snapshots_at_every_task_boundary(temp_snapshot_dir, sample_records):
    """Test that snapshots are generated at EVERY task boundary (Requirement 25)."""
    logger = MemorySnapshotLogger(
        snapshot_dir=temp_snapshot_dir,
        run_id="test-run-001",
        policy_name="type_aware_decay"
    )

    num_tasks = 5

    # Simulate sequence execution with snapshots at every boundary
    for step in range(num_tasks):
        # Before task
        logger.log_snapshot(
            step=step,
            boundary="before_task",
            active_records=sample_records,
            current_step=step
        )

        # After task
        logger.log_snapshot(
            step=step,
            boundary="after_task",
            active_records=sample_records,
            current_step=step
        )

    # Verify all snapshots exist
    is_complete, missing = logger.verify_complete_coverage(num_tasks=num_tasks)

    assert is_complete is True
    assert len(missing) == 0

    # Verify total count
    snapshots = logger.list_snapshots()
    assert len(snapshots) == num_tasks * 2  # before + after for each task
