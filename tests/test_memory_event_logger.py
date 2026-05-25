"""
Unit tests for MemoryEventLogger.

Tests the memory event logging system for write, archive, and consolidate operations.

Requirements: 18
Design: §11.2 Memory Events Schema
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.logging.memory_event_logger import MemoryEventLogger


class TestMemoryEventLoggerInitialization:
    """Test MemoryEventLogger initialization."""

    def test_init_creates_directory(self):
        """Test that initialization creates parent directory if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "runs" / "run_001" / "memory_events.jsonl"
            logger = MemoryEventLogger(log_path, "type_aware_decay")

            assert log_path.parent.exists()
            assert log_path.exists()
            assert logger.policy_name == "type_aware_decay"
            assert logger.event_counter == 0

    def test_init_with_existing_file(self):
        """Test initialization with existing log file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "memory_events.jsonl"
            log_path.touch()

            logger = MemoryEventLogger(log_path, "full_memory")

            assert log_path.exists()
            assert logger.policy_name == "full_memory"

    def test_init_empty_policy_name_raises(self):
        """Test that empty policy name raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "memory_events.jsonl"

            with pytest.raises(ValueError, match="policy_name cannot be empty"):
                MemoryEventLogger(log_path, "")


class TestMemoryEventLoggerWriteEvents:
    """Test logging write events."""

    def test_log_write_event(self):
        """Test logging a write event with all required fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "memory_events.jsonl"
            logger = MemoryEventLogger(log_path, "type_aware_decay")

            event_id = logger.log_write(
                memory_id="MEM-001",
                step=5,
                task_id="django__django-12345",
                repo="django/django",
                metadata={"memory_type": "bug_fix", "token_length": 1234},
            )

            # Verify event ID format
            assert event_id == "evt_00001"

            # Read and verify event
            with open(log_path, "r") as f:
                event = json.loads(f.readline())

            assert event["event_id"] == "evt_00001"
            assert event["step"] == 5
            assert event["policy"] == "type_aware_decay"
            assert event["event_type"] == "write"
            assert event["memory_id"] == "MEM-001"
            assert event["replacement_id"] is None
            assert event["task_id"] == "django__django-12345"
            assert event["repo"] == "django/django"
            assert event["reason"] == "task_completed"
            assert event["metadata"]["memory_type"] == "bug_fix"
            assert event["metadata"]["token_length"] == 1234
            assert "timestamp" in event
            assert event["timestamp"].endswith("Z")

    def test_log_write_without_metadata(self):
        """Test logging write event without metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "memory_events.jsonl"
            logger = MemoryEventLogger(log_path, "full_memory")

            event_id = logger.log_write(
                memory_id="MEM-002",
                step=10,
                task_id="django__django-12346",
                repo="django/django",
            )

            assert event_id == "evt_00001"

            # Read and verify event
            with open(log_path, "r") as f:
                event = json.loads(f.readline())

            assert event["metadata"] == {}

    def test_log_multiple_write_events(self):
        """Test logging multiple write events increments counter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "memory_events.jsonl"
            logger = MemoryEventLogger(log_path, "random_prune")

            event_id_1 = logger.log_write(
                memory_id="MEM-001",
                step=1,
                task_id="task-001",
                repo="repo/a",
            )
            event_id_2 = logger.log_write(
                memory_id="MEM-002",
                step=2,
                task_id="task-002",
                repo="repo/a",
            )
            event_id_3 = logger.log_write(
                memory_id="MEM-003",
                step=3,
                task_id="task-003",
                repo="repo/a",
            )

            assert event_id_1 == "evt_00001"
            assert event_id_2 == "evt_00002"
            assert event_id_3 == "evt_00003"

            # Verify all events written
            with open(log_path, "r") as f:
                lines = f.readlines()

            assert len(lines) == 3


class TestMemoryEventLoggerArchiveEvents:
    """Test logging archive events."""

    def test_log_archive_event(self):
        """Test logging an archive event with all required fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "memory_events.jsonl"
            logger = MemoryEventLogger(log_path, "random_prune")

            event_id = logger.log_archive(
                memory_id="MEM-001",
                step=10,
                task_id="django__django-12346",
                repo="django/django",
                reason="random_prune",
                metadata={"age": 5, "use_count": 2},
            )

            assert event_id == "evt_00001"

            # Read and verify event
            with open(log_path, "r") as f:
                event = json.loads(f.readline())

            assert event["event_id"] == "evt_00001"
            assert event["step"] == 10
            assert event["policy"] == "random_prune"
            assert event["event_type"] == "archive"
            assert event["memory_id"] == "MEM-001"
            assert event["replacement_id"] is None
            assert event["task_id"] == "django__django-12346"
            assert event["repo"] == "django/django"
            assert event["reason"] == "random_prune"
            assert event["metadata"]["age"] == 5
            assert event["metadata"]["use_count"] == 2

    def test_log_archive_different_reasons(self):
        """Test logging archive events with different reasons."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "memory_events.jsonl"
            logger = MemoryEventLogger(log_path, "type_aware_decay")

            reasons = [
                "random_prune",
                "recency_prune",
                "type_aware_decay",
                "budget_exceeded",
            ]

            for i, reason in enumerate(reasons, start=1):
                logger.log_archive(
                    memory_id=f"MEM-{i:03d}",
                    step=i * 5,
                    task_id=f"task-{i:03d}",
                    repo="repo/a",
                    reason=reason,
                )

            # Verify all events
            with open(log_path, "r") as f:
                events = [json.loads(line) for line in f]

            assert len(events) == 4
            for i, event in enumerate(events):
                assert event["reason"] == reasons[i]


class TestMemoryEventLoggerConsolidateEvents:
    """Test logging consolidate events."""

    def test_log_consolidate_event(self):
        """Test logging a consolidate event with all required fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "memory_events.jsonl"
            logger = MemoryEventLogger(log_path, "cls_consolidation")

            event_id = logger.log_consolidate(
                memory_id="MEM-001",
                replacement_id="MEM-CONS-001",
                step=15,
                task_id="django__django-12347",
                repo="django/django",
                metadata={"source_count": 4, "summary_tokens": 312},
            )

            assert event_id == "evt_00001"

            # Read and verify event
            with open(log_path, "r") as f:
                event = json.loads(f.readline())

            assert event["event_id"] == "evt_00001"
            assert event["step"] == 15
            assert event["policy"] == "cls_consolidation"
            assert event["event_type"] == "consolidate"
            assert event["memory_id"] == "MEM-001"
            assert event["replacement_id"] == "MEM-CONS-001"
            assert event["task_id"] == "django__django-12347"
            assert event["repo"] == "django/django"
            assert event["reason"] == "cls_consolidated"
            assert event["metadata"]["source_count"] == 4
            assert event["metadata"]["summary_tokens"] == 312

    def test_log_consolidate_requires_replacement_id(self):
        """Test that consolidate event requires replacement_id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "memory_events.jsonl"
            logger = MemoryEventLogger(log_path, "cls_consolidation")

            with pytest.raises(
                ValueError, match="replacement_id is required for consolidate events"
            ):
                logger.log_event(
                    event_type="consolidate",
                    memory_id="MEM-001",
                    step=15,
                    task_id="task-001",
                    repo="repo/a",
                    reason="cls_consolidated",
                    replacement_id=None,  # Missing!
                )


class TestMemoryEventLoggerValidation:
    """Test validation of event fields."""

    def test_invalid_event_type_raises(self):
        """Test that invalid event type raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "memory_events.jsonl"
            logger = MemoryEventLogger(log_path, "full_memory")

            with pytest.raises(ValueError, match="Invalid event_type"):
                logger.log_event(
                    event_type="invalid",  # type: ignore
                    memory_id="MEM-001",
                    step=1,
                    task_id="task-001",
                    repo="repo/a",
                    reason="test",
                )

    def test_empty_memory_id_raises(self):
        """Test that empty memory_id raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "memory_events.jsonl"
            logger = MemoryEventLogger(log_path, "full_memory")

            with pytest.raises(ValueError, match="memory_id cannot be empty"):
                logger.log_event(
                    event_type="write",
                    memory_id="",
                    step=1,
                    task_id="task-001",
                    repo="repo/a",
                    reason="test",
                )

    def test_negative_step_raises(self):
        """Test that negative step raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "memory_events.jsonl"
            logger = MemoryEventLogger(log_path, "full_memory")

            with pytest.raises(ValueError, match="step must be non-negative"):
                logger.log_event(
                    event_type="write",
                    memory_id="MEM-001",
                    step=-1,
                    task_id="task-001",
                    repo="repo/a",
                    reason="test",
                )

    def test_empty_task_id_raises(self):
        """Test that empty task_id raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "memory_events.jsonl"
            logger = MemoryEventLogger(log_path, "full_memory")

            with pytest.raises(ValueError, match="task_id cannot be empty"):
                logger.log_event(
                    event_type="write",
                    memory_id="MEM-001",
                    step=1,
                    task_id="",
                    repo="repo/a",
                    reason="test",
                )

    def test_empty_repo_raises(self):
        """Test that empty repo raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "memory_events.jsonl"
            logger = MemoryEventLogger(log_path, "full_memory")

            with pytest.raises(ValueError, match="repo cannot be empty"):
                logger.log_event(
                    event_type="write",
                    memory_id="MEM-001",
                    step=1,
                    task_id="task-001",
                    repo="",
                    reason="test",
                )

    def test_empty_reason_raises(self):
        """Test that empty reason raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "memory_events.jsonl"
            logger = MemoryEventLogger(log_path, "full_memory")

            with pytest.raises(ValueError, match="reason cannot be empty"):
                logger.log_event(
                    event_type="write",
                    memory_id="MEM-001",
                    step=1,
                    task_id="task-001",
                    repo="repo/a",
                    reason="",
                )


class TestMemoryEventLoggerJSONLFormat:
    """Test JSON Lines format compliance."""

    def test_atomic_append_format(self):
        """Test that events are written in JSON Lines format (one per line)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "memory_events.jsonl"
            logger = MemoryEventLogger(log_path, "type_aware_decay")

            # Log multiple events
            for i in range(5):
                logger.log_write(
                    memory_id=f"MEM-{i:03d}",
                    step=i,
                    task_id=f"task-{i:03d}",
                    repo="repo/a",
                )

            # Verify format
            with open(log_path, "r") as f:
                lines = f.readlines()

            assert len(lines) == 5

            # Each line should be valid JSON
            for i, line in enumerate(lines):
                event = json.loads(line)
                assert event["event_id"] == f"evt_{i+1:05d}"
                assert event["memory_id"] == f"MEM-{i:03d}"

    def test_no_pretty_printing(self):
        """Test that events are written as single lines (no pretty printing)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "memory_events.jsonl"
            logger = MemoryEventLogger(log_path, "full_memory")

            logger.log_write(
                memory_id="MEM-001",
                step=1,
                task_id="task-001",
                repo="repo/a",
            )

            # Read raw content
            with open(log_path, "r") as f:
                content = f.read()

            # Should be exactly one line (plus newline)
            lines = content.split("\n")
            assert len(lines) == 2  # One event line + trailing newline
            assert lines[1] == ""  # Trailing newline creates empty second element


class TestMemoryEventLoggerReadOperations:
    """Test reading and filtering events."""

    def test_get_event_count(self):
        """Test getting total event count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "memory_events.jsonl"
            logger = MemoryEventLogger(log_path, "random_prune")

            assert logger.get_event_count() == 0

            logger.log_write("MEM-001", 1, "task-001", "repo/a")
            assert logger.get_event_count() == 1

            logger.log_write("MEM-002", 2, "task-002", "repo/a")
            logger.log_archive("MEM-001", 3, "task-003", "repo/a", "random_prune")
            assert logger.get_event_count() == 3

    def test_read_all_events(self):
        """Test reading all events without filters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "memory_events.jsonl"
            logger = MemoryEventLogger(log_path, "type_aware_decay")

            logger.log_write("MEM-001", 1, "task-001", "repo/a")
            logger.log_archive("MEM-002", 2, "task-002", "repo/a", "type_aware_decay")
            logger.log_consolidate(
                "MEM-003", "MEM-CONS-001", 3, "task-003", "repo/a"
            )

            events = logger.read_events()

            assert len(events) == 3
            assert events[0]["event_type"] == "write"
            assert events[1]["event_type"] == "archive"
            assert events[2]["event_type"] == "consolidate"

    def test_read_events_filter_by_type(self):
        """Test reading events filtered by event type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "memory_events.jsonl"
            logger = MemoryEventLogger(log_path, "random_prune")

            logger.log_write("MEM-001", 1, "task-001", "repo/a")
            logger.log_write("MEM-002", 2, "task-002", "repo/a")
            logger.log_archive("MEM-001", 3, "task-003", "repo/a", "random_prune")
            logger.log_archive("MEM-002", 4, "task-004", "repo/a", "random_prune")

            write_events = logger.read_events(event_type="write")
            archive_events = logger.read_events(event_type="archive")

            assert len(write_events) == 2
            assert len(archive_events) == 2
            assert all(e["event_type"] == "write" for e in write_events)
            assert all(e["event_type"] == "archive" for e in archive_events)

    def test_read_events_filter_by_memory_id(self):
        """Test reading events filtered by memory ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "memory_events.jsonl"
            logger = MemoryEventLogger(log_path, "recency_prune")

            logger.log_write("MEM-001", 1, "task-001", "repo/a")
            logger.log_write("MEM-002", 2, "task-002", "repo/a")
            logger.log_archive("MEM-001", 3, "task-003", "repo/a", "recency_prune")

            mem_001_events = logger.read_events(memory_id="MEM-001")
            mem_002_events = logger.read_events(memory_id="MEM-002")

            assert len(mem_001_events) == 2  # write + archive
            assert len(mem_002_events) == 1  # write only
            assert all(e["memory_id"] == "MEM-001" for e in mem_001_events)
            assert all(e["memory_id"] == "MEM-002" for e in mem_002_events)

    def test_read_events_combined_filters(self):
        """Test reading events with multiple filters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "memory_events.jsonl"
            logger = MemoryEventLogger(log_path, "type_aware_decay")

            logger.log_write("MEM-001", 1, "task-001", "repo/a")
            logger.log_archive("MEM-001", 2, "task-002", "repo/a", "type_aware_decay")
            logger.log_archive("MEM-002", 3, "task-003", "repo/a", "type_aware_decay")

            events = logger.read_events(event_type="archive", memory_id="MEM-001")

            assert len(events) == 1
            assert events[0]["event_type"] == "archive"
            assert events[0]["memory_id"] == "MEM-001"

    def test_read_events_empty_file(self):
        """Test reading from empty log file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "memory_events.jsonl"
            logger = MemoryEventLogger(log_path, "full_memory")

            events = logger.read_events()

            assert events == []


class TestMemoryEventLoggerSchemaCompliance:
    """Test compliance with THESIS_FINAL_v5.md §11.2 schema."""

    def test_memory_events_schema_complete(self):
        """Test that all required schema fields are present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "memory_events.jsonl"
            logger = MemoryEventLogger(log_path, "cls_consolidation")

            # Test write event
            logger.log_write(
                memory_id="MEM-001",
                step=5,
                task_id="django__django-12345",
                repo="django/django",
                metadata={"token_length": 1234},
            )

            # Test archive event
            logger.log_archive(
                memory_id="MEM-002",
                step=10,
                task_id="django__django-12346",
                repo="django/django",
                reason="random_prune",
                metadata={"age": 5},
            )

            # Test consolidate event
            logger.log_consolidate(
                memory_id="MEM-003",
                replacement_id="MEM-CONS-001",
                step=15,
                task_id="django__django-12347",
                repo="django/django",
                metadata={"source_count": 4, "summary_tokens": 312},
            )

            # Read all events
            events = logger.read_events()

            # Required fields from §11.2
            required_fields = [
                "event_id",
                "step",
                "policy",
                "event_type",
                "memory_id",
                "replacement_id",
                "task_id",
                "repo",
                "reason",
                "metadata",
                "timestamp",
            ]

            for event in events:
                for field in required_fields:
                    assert field in event, f"Missing required field: {field}"

                # Validate field types
                assert isinstance(event["event_id"], str)
                assert isinstance(event["step"], int)
                assert isinstance(event["policy"], str)
                assert isinstance(event["event_type"], str)
                assert isinstance(event["memory_id"], str)
                assert event["replacement_id"] is None or isinstance(
                    event["replacement_id"], str
                )
                assert isinstance(event["task_id"], str)
                assert isinstance(event["repo"], str)
                assert isinstance(event["reason"], str)
                assert isinstance(event["metadata"], dict)
                assert isinstance(event["timestamp"], str)

                # Validate event_type values
                assert event["event_type"] in ("write", "archive", "consolidate")

                # Validate timestamp format (ISO 8601 with Z suffix)
                assert event["timestamp"].endswith("Z")


class TestMemoryEventLoggerRepr:
    """Test string representation."""

    def test_repr(self):
        """Test __repr__ method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "memory_events.jsonl"
            logger = MemoryEventLogger(log_path, "type_aware_decay")

            logger.log_write("MEM-001", 1, "task-001", "repo/a")
            logger.log_write("MEM-002", 2, "task-002", "repo/a")

            repr_str = repr(logger)

            assert "MemoryEventLogger" in repr_str
            assert "type_aware_decay" in repr_str
            assert "events=2" in repr_str
