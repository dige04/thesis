"""
Example usage of MemoryEventLogger.

This demonstrates how the memory event logger will be integrated with
memory policies to track all memory operations.

Requirements: 18
Design: §11.2 Memory Events Schema
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.logging.memory_event_logger import MemoryEventLogger


def example_basic_usage():
    """Basic usage example: logging write, archive, and consolidate events."""
    print("=== Basic Usage Example ===\n")

    # Initialize logger for a run
    log_path = Path("runs/example_run_001/memory_events.jsonl")
    logger = MemoryEventLogger(log_path, policy_name="type_aware_decay")

    # Log a write event (after task completion)
    event_id = logger.log_write(
        memory_id="MEM-001",
        step=5,
        task_id="django__django-12345",
        repo="django/django",
        metadata={
            "memory_type": "bug_fix",
            "token_length": 1234,
            "outcome": "pass",
        },
    )
    print(f"Logged write event: {event_id}")

    # Log an archive event (when pruning)
    event_id = logger.log_archive(
        memory_id="MEM-002",
        step=10,
        task_id="django__django-12346",
        repo="django/django",
        reason="type_aware_decay",
        metadata={
            "importance_score": 0.23,
            "age": 5,
            "use_count": 2,
        },
    )
    print(f"Logged archive event: {event_id}")

    # Log a consolidate event (CLS consolidation)
    event_id = logger.log_consolidate(
        memory_id="MEM-003",
        replacement_id="MEM-CONS-001",
        step=15,
        task_id="django__django-12347",
        repo="django/django",
        metadata={
            "source_count": 4,
            "summary_tokens": 312,
            "cluster_id": "cluster_001",
        },
    )
    print(f"Logged consolidate event: {event_id}")

    print(f"\nTotal events logged: {logger.get_event_count()}")
    print(f"Log file: {log_path}\n")


def example_policy_integration():
    """Example: How policies will integrate with the logger."""
    print("=== Policy Integration Example ===\n")

    log_path = Path("runs/example_run_002/memory_events.jsonl")
    logger = MemoryEventLogger(log_path, policy_name="random_prune")

    # Simulate a sequence of tasks
    for step in range(1, 6):
        task_id = f"task-{step:03d}"
        repo = "repo/example"

        # Write memory after each task
        logger.log_write(
            memory_id=f"MEM-{step:03d}",
            step=step,
            task_id=task_id,
            repo=repo,
            metadata={"memory_type": "bug_fix", "token_length": 1000 + step * 100},
        )
        print(f"Step {step}: Wrote memory MEM-{step:03d}")

        # Prune if needed (e.g., at step 3 and 5)
        if step in [3, 5]:
            victim_id = f"MEM-{step-2:03d}"
            logger.log_archive(
                memory_id=victim_id,
                step=step,
                task_id=task_id,
                repo=repo,
                reason="random_prune",
                metadata={"age": 2, "use_count": 0},
            )
            print(f"Step {step}: Archived memory {victim_id} (random prune)")

    print(f"\nTotal events: {logger.get_event_count()}")

    # Read and analyze events
    write_events = logger.read_events(event_type="write")
    archive_events = logger.read_events(event_type="archive")

    print(f"Write events: {len(write_events)}")
    print(f"Archive events: {len(archive_events)}\n")


def example_reading_events():
    """Example: Reading and filtering events for analysis."""
    print("=== Reading Events Example ===\n")

    log_path = Path("runs/example_run_003/memory_events.jsonl")
    logger = MemoryEventLogger(log_path, policy_name="cls_consolidation")

    # Log various events
    logger.log_write("MEM-001", 1, "task-001", "repo/a")
    logger.log_write("MEM-002", 2, "task-002", "repo/a")
    logger.log_archive("MEM-001", 3, "task-003", "repo/a", "recency_prune")
    logger.log_consolidate("MEM-002", "MEM-CONS-001", 5, "task-005", "repo/a")

    # Read all events
    all_events = logger.read_events()
    print(f"All events: {len(all_events)}")

    # Filter by event type
    archive_events = logger.read_events(event_type="archive")
    print(f"Archive events: {len(archive_events)}")
    for event in archive_events:
        print(f"  - {event['memory_id']} archived at step {event['step']}")

    # Filter by memory ID
    mem_002_events = logger.read_events(memory_id="MEM-002")
    print(f"\nEvents for MEM-002: {len(mem_002_events)}")
    for event in mem_002_events:
        print(f"  - {event['event_type']} at step {event['step']}")

    print()


def example_cls_consolidation_workflow():
    """Example: CLS consolidation workflow with multiple source memories."""
    print("=== CLS Consolidation Workflow Example ===\n")

    log_path = Path("runs/example_run_004/memory_events.jsonl")
    logger = MemoryEventLogger(log_path, policy_name="cls_consolidation")

    # Write several memories
    source_ids = []
    for i in range(1, 5):
        memory_id = f"MEM-{i:03d}"
        source_ids.append(memory_id)
        logger.log_write(
            memory_id=memory_id,
            step=i,
            task_id=f"task-{i:03d}",
            repo="django/django",
            metadata={"memory_type": "bug_fix", "files_touched": ["models.py"]},
        )
        print(f"Wrote {memory_id}")

    # Consolidate them at step 5
    consolidated_id = "MEM-CONS-001"
    print(f"\nConsolidating {len(source_ids)} memories into {consolidated_id}")

    for source_id in source_ids:
        logger.log_consolidate(
            memory_id=source_id,
            replacement_id=consolidated_id,
            step=5,
            task_id="task-005",
            repo="django/django",
            metadata={
                "source_count": len(source_ids),
                "summary_tokens": 312,
                "cluster_id": "cluster_001",
            },
        )
        print(f"  - Consolidated {source_id} -> {consolidated_id}")

    # Write the consolidated memory
    logger.log_write(
        memory_id=consolidated_id,
        step=5,
        task_id="task-005",
        repo="django/django",
        metadata={
            "memory_type": "bug_fix",
            "is_consolidated": True,
            "source_memory_ids": source_ids,
        },
    )
    print(f"\nWrote consolidated memory {consolidated_id}")

    print(f"\nTotal events: {logger.get_event_count()}")

    # Analyze consolidation events
    consolidate_events = logger.read_events(event_type="consolidate")
    print(f"Consolidation events: {len(consolidate_events)}")
    print()


if __name__ == "__main__":
    # Run all examples
    example_basic_usage()
    example_policy_integration()
    example_reading_events()
    example_cls_consolidation_workflow()

    print("=== Examples Complete ===")
    print("\nThe memory event logger is ready for integration with memory policies.")
    print("Each policy will call logger.log_write(), logger.log_archive(), or")
    print("logger.log_consolidate() at appropriate points in their lifecycle.")
