"""Example usage of the SequenceRunner for orchestrating task execution.

This example demonstrates how to:
1. Load a sequence from SWE-Bench-CL
2. Initialize a memory policy
3. Create a SequenceRunner
4. Execute the complete sequence
5. Access results

Requirements: Task 12.1 implementation
"""

from pathlib import Path

from src.benchmark.models import Sequence, Task
from src.benchmark.sequence_runner import SequenceRunner
from src.memory.policies.type_aware_decay import TypeAwareDecayPolicy


def main() -> None:
    """Run a simple sequence with Type-Aware Decay policy."""

    # Example: Create a small test sequence
    # In practice, this would come from swebenchcl_loader.py
    test_tasks = [
        Task(
            task_id="django__django-12345",
            repo="django/django",
            base_commit="abc123def456",
            issue_text="Fix bug in authentication middleware",
            test_patch="diff --git a/tests/auth/test_middleware.py ...",
            gold_patch="diff --git a/django/contrib/auth/middleware.py ...",
            created_at="2018-03-15T10:23:00Z",
            sequence_index=0,
            difficulty_label="medium",
        ),
        Task(
            task_id="django__django-12346",
            repo="django/django",
            base_commit="def456ghi789",
            issue_text="Add support for custom user models",
            test_patch="diff --git a/tests/auth/test_models.py ...",
            gold_patch="diff --git a/django/contrib/auth/models.py ...",
            created_at="2018-03-16T14:30:00Z",
            sequence_index=1,
            difficulty_label="hard",
        ),
        # Add more tasks to reach minimum 15...
        # (truncated for example)
    ]

    # Pad to minimum 15 tasks for validation
    while len(test_tasks) < 15:
        test_tasks.append(
            Task(
                task_id=f"django__django-{12347 + len(test_tasks) - 2}",
                repo="django/django",
                base_commit=f"commit{len(test_tasks)}",
                issue_text=f"Test task {len(test_tasks)}",
                test_patch="",
                gold_patch="",
                created_at="2018-03-17T10:00:00Z",
                sequence_index=len(test_tasks),
                difficulty_label="easy",
            )
        )

    sequence = Sequence(
        sequence_name="django",
        repo="django/django",
        tasks=test_tasks,
        task_count=len(test_tasks),
    )

    # Configuration
    config = {
        "agent": {
            "max_steps_per_task": 20,  # Frozen invariant #3
            "max_tool_calls_per_task": 80,
            "max_test_runs_per_task": 5,
            "max_wall_time_seconds": 1200,
            "temperature": 0,  # Frozen invariant (reproducibility)
        },
        "memory": {
            "top_k": 5,  # TBD until Week 4 calibration
            "max_context_tokens": 2000,  # TBD until Week 4 calibration
            "max_records": 100,
            "max_storage_tokens": 30000,
            "embedding_dim": 1536,
            "embedding_model": "text-embedding-3-small",
        },
        "evaluation": {
            "docker_image": "swebench/eval_v3:latest",
            "timeout_seconds": 300,
        },
        "reflection": {
            "model": "gpt-4o-mini",
            "temperature": 0.0,
        },
    }

    # Initialize policy
    policy = TypeAwareDecayPolicy(max_records=config["memory"]["max_records"])

    # Create unique run ID
    run_id = f"gpt54_typeaware_seed1_django"

    # Initialize sequence runner
    runner = SequenceRunner(
        run_id=run_id,
        policy=policy,
        config=config,
    )

    print(f"Starting sequence: {sequence.sequence_name}")
    print(f"Policy: {policy.name}")
    print(f"Tasks: {sequence.task_count}")
    print(f"Run ID: {run_id}")
    print("-" * 60)

    # Execute sequence
    try:
        result = runner.run_sequence(sequence=sequence, seed=1)

        # Print results
        print("\nSequence completed!")
        print(f"Completed tasks: {result.completed_tasks}/{result.total_tasks}")
        print(f"Resolved tasks: {result.resolved_tasks}")
        print(f"Failed tasks: {result.failed_tasks}")
        print(f"Timeout tasks: {result.timeout_tasks}")
        print(f"Total wall time: {result.total_wall_time:.1f}s")
        print(f"Total cost: ${result.total_cost_usd:.2f}")

        if result.error_message:
            print(f"\nError: {result.error_message}")

        # Access logged data
        run_dir = Path("runs") / run_id
        print(f"\nResults saved to: {run_dir}")
        print(f"  - Task results: {run_dir / 'task_results.jsonl'}")
        print(f"  - Memory events: {run_dir / 'memory_events.jsonl'}")
        print(f"  - Snapshots: {run_dir / 'memory' / 'snapshots'}")

    except Exception as e:
        print(f"\nSequence failed with error: {e}")
        raise


if __name__ == "__main__":
    main()
