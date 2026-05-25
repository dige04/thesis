"""Example usage of MemorySnapshotLogger for task boundary logging.

This example demonstrates how to integrate MemorySnapshotLogger into the
sequence runner to capture memory state at every task boundary.

Requirements: THESIS_FINAL_v5.md §11.4, §25
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.logging.memory_snapshot_logger import MemorySnapshotLogger
from src.memory.record import MemoryRecord
from src.memory.store import MemoryStore


def example_sequence_runner_with_snapshots():
    """Example of sequence runner with memory snapshot logging.

    This demonstrates the integration pattern from THESIS_FINAL_v5.md §25.3:

    ```python
    for task in sequence:
        memory_store.snapshot("before_task")
        result = solve_task(task, memory_store, policy, config)
        memory_store.snapshot("after_task_before_prune")
        # write + maintain happen inside solve_task
        memory_store.snapshot("after_prune")
    ```
    """
    # Initialize memory store
    run_id = "example-run-001"
    policy_name = "type_aware_decay"

    memory_store = MemoryStore(
        run_id=run_id,
        policy_name=policy_name
    )

    # Initialize snapshot logger
    snapshot_dir = Path("runs") / run_id / "memory" / "snapshots"
    snapshot_logger = MemorySnapshotLogger(
        snapshot_dir=snapshot_dir,
        run_id=run_id,
        policy_name=policy_name
    )

    # Simulate sequence execution
    num_tasks = 5

    for step in range(num_tasks):
        print(f"\n=== Task {step} ===")

        # 1. Snapshot BEFORE task
        active_records = memory_store.active_records()
        snapshot_logger.log_snapshot(
            step=step,
            boundary="before_task",
            active_records=active_records,
            current_step=step
        )
        print(f"✓ Saved before_task_{step}.json ({len(active_records)} active records)")

        # 2. Solve task (simulated)
        # result = solve_task(task, memory_store, policy, config)
        print(f"  Solving task {step}...")

        # 3. Snapshot AFTER task (before pruning)
        active_records = memory_store.active_records()
        snapshot_logger.log_snapshot(
            step=step,
            boundary="after_task_before_prune",
            active_records=active_records,
            current_step=step
        )
        print(f"✓ Saved after_task_before_prune_{step}.json ({len(active_records)} active records)")

        # 4. Policy maintenance (pruning/consolidation)
        # policy.maintain(memory_store)
        print(f"  Running policy maintenance...")

        # 5. Snapshot AFTER pruning
        active_records = memory_store.active_records()
        archived_this_step = []  # Would come from policy.maintain()
        snapshot_logger.log_snapshot(
            step=step,
            boundary="after_prune",
            active_records=active_records,
            archived_this_step=archived_this_step,
            current_step=step
        )
        print(f"✓ Saved after_prune_{step}.json ({len(active_records)} active records)")

    # Verify complete coverage
    print("\n=== Verification ===")
    is_complete, missing = snapshot_logger.verify_complete_coverage(
        num_tasks=num_tasks,
        expected_boundaries=["before_task", "after_task_before_prune", "after_prune"]
    )

    if is_complete:
        print("✓ All snapshots generated successfully")
    else:
        print(f"✗ Missing snapshots: {missing}")

    # List all snapshots
    snapshots = snapshot_logger.list_snapshots()
    print(f"\nTotal snapshots: {len(snapshots)}")
    for step, boundary in snapshots[:5]:  # Show first 5
        print(f"  - {boundary}_{step}.json")

    # Clean up
    memory_store.close()


def example_snapshot_analysis():
    """Example of loading and analyzing snapshots for post-hoc analysis.

    This demonstrates how to use saved snapshots to analyze memory evolution
    without re-running the experiment.
    """
    run_id = "example-run-001"
    snapshot_dir = Path("runs") / run_id / "memory" / "snapshots"

    snapshot_logger = MemorySnapshotLogger(
        snapshot_dir=snapshot_dir,
        run_id=run_id,
        policy_name="type_aware_decay"
    )

    print("\n=== Snapshot Analysis ===")

    # Load snapshot at specific boundary
    try:
        snapshot = snapshot_logger.load_snapshot(step=0, boundary="before_task")

        print(f"\nSnapshot: before_task_0")
        print(f"  Active records: {len(snapshot['active_records'])}")
        print(f"  Timestamp: {snapshot['timestamp']}")

        # Analyze memory composition
        if snapshot['active_records']:
            print("\n  Memory composition:")
            type_counts = {}
            for record in snapshot['active_records']:
                mem_type = record['memory_type']
                type_counts[mem_type] = type_counts.get(mem_type, 0) + 1

            for mem_type, count in sorted(type_counts.items()):
                print(f"    {mem_type}: {count}")

            # Show importance score distribution
            scores = [r['importance_score'] for r in snapshot['active_records']]
            print(f"\n  Importance scores:")
            print(f"    Min: {min(scores):.3f}")
            print(f"    Max: {max(scores):.3f}")
            print(f"    Mean: {sum(scores)/len(scores):.3f}")

    except FileNotFoundError:
        print("No snapshots found. Run example_sequence_runner_with_snapshots() first.")


def example_memory_evolution_tracking():
    """Example of tracking memory evolution across task boundaries.

    This demonstrates how to use snapshots to analyze how memory changes
    over time, which is useful for understanding policy behavior.
    """
    run_id = "example-run-001"
    snapshot_dir = Path("runs") / run_id / "memory" / "snapshots"

    snapshot_logger = MemorySnapshotLogger(
        snapshot_dir=snapshot_dir,
        run_id=run_id,
        policy_name="type_aware_decay"
    )

    print("\n=== Memory Evolution Tracking ===")

    # Track active count over time
    snapshots = snapshot_logger.list_snapshots()

    if not snapshots:
        print("No snapshots found. Run example_sequence_runner_with_snapshots() first.")
        return

    print("\nActive memory count over time:")
    print("Step | Boundary              | Active | Archived")
    print("-----|----------------------|--------|----------")

    for step, boundary in sorted(snapshots):
        try:
            snapshot = snapshot_logger.load_snapshot(step=step, boundary=boundary)
            active_count = len(snapshot['active_records'])
            archived_count = len(snapshot.get('archived_this_step', []))

            print(f"{step:4d} | {boundary:20s} | {active_count:6d} | {archived_count:8d}")
        except FileNotFoundError:
            continue


if __name__ == "__main__":
    # Run examples
    print("=" * 60)
    print("Memory Snapshot Logger - Example Usage")
    print("=" * 60)

    # Example 1: Sequence runner with snapshots
    example_sequence_runner_with_snapshots()

    # Example 2: Snapshot analysis
    example_snapshot_analysis()

    # Example 3: Memory evolution tracking
    example_memory_evolution_tracking()

    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)
