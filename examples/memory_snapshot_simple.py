"""Simple example of MemorySnapshotLogger without requiring OpenAI API.

This example demonstrates the core functionality of MemorySnapshotLogger
using mock memory records, without needing a full MemoryStore setup.

Requirements: THESIS_FINAL_v5.md §11.4, §25
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.logging.memory_snapshot_logger import MemorySnapshotLogger
from src.memory.record import MemoryRecord


def create_sample_records(num_records: int, base_step: int) -> list[MemoryRecord]:
    """Create sample memory records for demonstration."""
    records = []

    memory_types = ["architectural", "api_change", "bug_fix", "test_update", "config"]

    for i in range(num_records):
        # Ensure sequence_index is always non-negative
        sequence_index = max(0, base_step - (num_records - i - 1))

        record = MemoryRecord(
            memory_id=f"MEM-{base_step:03d}-{i:03d}",
            task_id=f"task-{base_step}",
            repo="django/django",
            sequence_index=sequence_index,  # Older records have lower index
            memory_type=memory_types[i % len(memory_types)],
            outcome="pass" if i % 3 != 0 else "fail",
            issue_summary=f"Issue {i}: Sample issue description",
            patch_summary=f"Patch {i}: Sample patch",
            failure_summary=None if i % 3 != 0 else f"Error {i}: Sample error",
            test_summary=f"Test {i}: Sample test results",
            files_touched=[f"file{i}.py", f"test_file{i}.py"],
            functions_touched=[f"function_{i}", f"helper_{i}"],
            commands_run=["pytest", "mypy"],
            retrieved_memory_ids_used=[],
            embedding_text=f"Issue: Sample issue {i}\nError: None\nDiff: Sample patch {i}",
            embedding_vector_id=str(i),
            token_length=100 + i * 10,
            raw_trace_ref=None,
            use_count=i % 5,
            last_retrieved_at_step=base_step - 1 if i % 2 == 0 else None,
            success_after_retrieval_count=i % 3,
            failure_after_retrieval_count=i % 4,
            importance_score=0.5 + (i * 0.05),  # Increasing scores
            is_consolidated=False,
            source_memory_ids=None,
            is_archived=False,
            archived_reason=None,
            archived_at_step=None
        )
        records.append(record)

    return records


def example_basic_snapshot_logging():
    """Basic example of snapshot logging."""
    print("\n=== Example 1: Basic Snapshot Logging ===\n")

    # Initialize snapshot logger
    run_id = "demo-run-001"
    policy_name = "type_aware_decay"
    snapshot_dir = Path("runs") / run_id / "memory" / "snapshots"

    logger = MemorySnapshotLogger(
        snapshot_dir=snapshot_dir,
        run_id=run_id,
        policy_name=policy_name
    )

    # Create sample records
    active_records = create_sample_records(num_records=5, base_step=10)

    # Log snapshot
    snapshot = logger.log_snapshot(
        step=10,
        boundary="before_task",
        active_records=active_records,
        current_step=10
    )

    print(f"✓ Created snapshot: before_task_10.json")
    print(f"  Active records: {len(snapshot['active_records'])}")
    print(f"  Timestamp: {snapshot['timestamp']}")
    print(f"  Policy: {snapshot['metadata']['policy_name']}")

    # Show first record details
    if snapshot['active_records']:
        first_record = snapshot['active_records'][0]
        print(f"\n  First record:")
        print(f"    memory_id: {first_record['memory_id']}")
        print(f"    memory_type: {first_record['memory_type']}")
        print(f"    importance_score: {first_record['importance_score']:.3f}")
        print(f"    age: {first_record['age']}")


def example_sequence_simulation():
    """Simulate a sequence with snapshots at every boundary."""
    print("\n=== Example 2: Sequence Simulation ===\n")

    run_id = "demo-run-002"
    policy_name = "type_aware_decay"
    snapshot_dir = Path("runs") / run_id / "memory" / "snapshots"

    logger = MemorySnapshotLogger(
        snapshot_dir=snapshot_dir,
        run_id=run_id,
        policy_name=policy_name
    )

    num_tasks = 3
    active_records = []

    for step in range(num_tasks):
        print(f"Task {step}:")

        # Before task
        logger.log_snapshot(
            step=step,
            boundary="before_task",
            active_records=active_records,
            current_step=step
        )
        print(f"  ✓ before_task_{step}.json ({len(active_records)} active)")

        # Add new memory after task
        new_record = create_sample_records(num_records=1, base_step=step)[0]
        active_records.append(new_record)

        # After task
        logger.log_snapshot(
            step=step,
            boundary="after_task",
            active_records=active_records,
            current_step=step
        )
        print(f"  ✓ after_task_{step}.json ({len(active_records)} active)")

        # Simulate pruning (remove oldest if > 5 records)
        archived = []
        if len(active_records) > 5:
            archived = [active_records.pop(0).memory_id]

        # After pruning
        logger.log_snapshot(
            step=step,
            boundary="after_prune",
            active_records=active_records,
            archived_this_step=archived,
            current_step=step
        )
        print(f"  ✓ after_prune_{step}.json ({len(active_records)} active, {len(archived)} archived)")

    # Verify coverage
    print("\nVerification:")
    is_complete, missing = logger.verify_complete_coverage(
        num_tasks=num_tasks,
        expected_boundaries=["before_task", "after_task", "after_prune"]
    )

    if is_complete:
        print("  ✓ All snapshots generated successfully")
    else:
        print(f"  ✗ Missing: {missing}")

    # List all snapshots
    snapshots = logger.list_snapshots()
    print(f"\n  Total snapshots: {len(snapshots)}")


def example_snapshot_analysis():
    """Analyze saved snapshots."""
    print("\n=== Example 3: Snapshot Analysis ===\n")

    run_id = "demo-run-002"
    snapshot_dir = Path("runs") / run_id / "memory" / "snapshots"

    if not snapshot_dir.exists():
        print("No snapshots found. Run example_sequence_simulation() first.")
        return

    logger = MemorySnapshotLogger(
        snapshot_dir=snapshot_dir,
        run_id=run_id,
        policy_name="type_aware_decay"
    )

    # Load and analyze snapshots
    snapshots = logger.list_snapshots()

    print("Memory evolution:")
    print("Step | Boundary     | Active | Archived")
    print("-----|--------------|--------|----------")

    for step, boundary in snapshots:
        try:
            snapshot = logger.load_snapshot(step=step, boundary=boundary)
            active_count = len(snapshot['active_records'])
            archived_count = len(snapshot.get('archived_this_step', []))

            print(f"{step:4d} | {boundary:12s} | {active_count:6d} | {archived_count:8d}")
        except FileNotFoundError:
            continue

    # Analyze memory composition at final step
    if snapshots:
        final_step, final_boundary = snapshots[-1]
        snapshot = logger.load_snapshot(step=final_step, boundary=final_boundary)

        if snapshot['active_records']:
            print("\nFinal memory composition:")
            type_counts = {}
            for record in snapshot['active_records']:
                mem_type = record['memory_type']
                type_counts[mem_type] = type_counts.get(mem_type, 0) + 1

            for mem_type, count in sorted(type_counts.items()):
                print(f"  {mem_type}: {count}")


def example_importance_score_tracking():
    """Track importance scores over time."""
    print("\n=== Example 4: Importance Score Tracking ===\n")

    run_id = "demo-run-003"
    policy_name = "type_aware_decay"
    snapshot_dir = Path("runs") / run_id / "memory" / "snapshots"

    logger = MemorySnapshotLogger(
        snapshot_dir=snapshot_dir,
        run_id=run_id,
        policy_name=policy_name
    )

    # Create records with varying importance scores
    num_tasks = 5
    for step in range(num_tasks):
        # Create records with scores that decay over time
        records = []
        for i in range(3):
            record = create_sample_records(num_records=1, base_step=step)[0]
            # Simulate Type-Aware Decay: older records have lower scores
            age = step - record.sequence_index
            record.importance_score = 1.0 / (1.0 + age * 0.2)
            records.append(record)

        logger.log_snapshot(
            step=step,
            boundary="before_task",
            active_records=records,
            current_step=step
        )

    # Analyze importance score distribution
    print("Importance score distribution over time:")
    print("Step | Min Score | Max Score | Mean Score")
    print("-----|-----------|-----------|------------")

    for step in range(num_tasks):
        snapshot = logger.load_snapshot(step=step, boundary="before_task")
        if snapshot['active_records']:
            scores = [r['importance_score'] for r in snapshot['active_records']]
            print(f"{step:4d} | {min(scores):9.3f} | {max(scores):9.3f} | {sum(scores)/len(scores):10.3f}")


if __name__ == "__main__":
    print("=" * 60)
    print("Memory Snapshot Logger - Simple Examples")
    print("=" * 60)

    # Run examples
    example_basic_snapshot_logging()
    example_sequence_simulation()
    example_snapshot_analysis()
    example_importance_score_tracking()

    print("\n" + "=" * 60)
    print("Examples completed!")
    print("Check runs/demo-run-*/memory/snapshots/ for output files")
    print("=" * 60)
