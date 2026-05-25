"""Example usage of TaskResultLogger.

This example demonstrates how to use the TaskResultLogger to log task
execution results to task_results.jsonl.

Requirements: 18, 27
Schema: THESIS_FINAL_v5.md §11.1
"""

from pathlib import Path

from src.logging.task_logger import TaskResult, TaskResultLogger


def main():
    """Demonstrate TaskResultLogger usage."""
    # Create a logger for a specific run
    run_dir = Path("runs/example_run_001")
    logger = TaskResultLogger(run_dir)

    print(f"Logging to: {logger.log_file}")

    # Example 1: Log a successful task with retrieved memories
    result1 = TaskResult(
        run_id="gpt54_typeaware_seed1_seq1",
        policy="type_aware_decay",
        seed=1,
        repo="django/django",
        task_id="django__django-12345",
        sequence_index=5,
        # Task outcome
        resolved=1,  # Task passed eval_v3
        patch_generated=True,
        patch_applied=True,
        syntax_error=False,
        timeout=False,
        # Token usage & costs
        prompt_tokens=12345,
        completion_tokens=2048,
        total_tokens=14393,
        estimated_cost_usd=0.31,
        task_api_cost=0.31,
        consolidation_llm_cost=0.0,
        # Execution metrics
        wall_time_seconds=944.2,
        tool_calls=52,
        test_runs=3,
        files_read=18,
        files_modified=2,
        syntax_error_rate=0.038,
        # Retrieved memories (best item LAST)
        retrieved_memory_ids=["MEM-001", "MEM-007", "MEM-091", "MEM-188", "MEM-303"],
        retrieved_memory_scores=[0.61, 0.68, 0.72, 0.78, 0.84],
        retrieved_memory_types=[
            "test_update",
            "bug_fix",
            "api_change",
            "bug_fix",
            "architectural",
        ],
        retrieved_memory_ages=[12, 3, 7, 1, 2],
        # Memory state
        memory_count_before=89,
        memory_count_after=90,
        memory_tokens_before=26500,
        memory_tokens_after=26900,
        # Memory operations
        pruned_memory_ids=[],
        consolidated_memory_ids=[],
        # Task metadata
        task_difficulty="medium",
        error_message=None,
    )

    logger.log_task_result(result1)
    print(f"✓ Logged task {result1.task_id} (resolved={result1.resolved})")

    # Example 2: Log a failed task with timeout
    result2 = TaskResult(
        run_id="gpt54_typeaware_seed1_seq1",
        policy="type_aware_decay",
        seed=1,
        repo="django/django",
        task_id="django__django-12346",
        sequence_index=6,
        # Task outcome - FAILED
        resolved=0,
        patch_generated=True,
        patch_applied=False,
        syntax_error=False,
        timeout=True,  # Exceeded 20 step limit
        # Token usage & costs
        prompt_tokens=15000,
        completion_tokens=3000,
        total_tokens=18000,
        estimated_cost_usd=0.45,
        task_api_cost=0.45,
        consolidation_llm_cost=0.0,
        # Execution metrics
        wall_time_seconds=1200.0,  # Hit max wall time
        tool_calls=80,  # Hit max tool calls
        test_runs=5,  # Hit max test runs
        files_read=25,
        files_modified=5,
        syntax_error_rate=0.125,
        # Retrieved memories
        retrieved_memory_ids=["MEM-010", "MEM-020", "MEM-030"],
        retrieved_memory_scores=[0.55, 0.62, 0.71],
        retrieved_memory_types=["config", "test_update", "bug_fix"],
        retrieved_memory_ages=[5, 2, 1],
        # Memory state
        memory_count_before=90,
        memory_count_after=91,
        memory_tokens_before=26900,
        memory_tokens_after=27200,
        # Memory operations
        pruned_memory_ids=[],
        consolidated_memory_ids=[],
        # Task metadata
        task_difficulty="hard",
        error_message="Task exceeded 20 step limit (hard force-fail)",
    )

    logger.log_task_result(result2)
    print(f"✓ Logged task {result2.task_id} (resolved={result2.resolved}, timeout={result2.timeout})")

    # Example 3: Log a task with No Memory policy (no retrieved memories)
    result3 = TaskResult(
        run_id="gpt54_nomemory_seed1_seq1",
        policy="no_memory",
        seed=1,
        repo="django/django",
        task_id="django__django-12347",
        sequence_index=7,
        # Task outcome
        resolved=1,
        patch_generated=True,
        patch_applied=True,
        syntax_error=False,
        timeout=False,
        # Token usage & costs
        prompt_tokens=8000,
        completion_tokens=1500,
        total_tokens=9500,
        estimated_cost_usd=0.20,
        task_api_cost=0.20,
        consolidation_llm_cost=0.0,
        # Execution metrics
        wall_time_seconds=600.0,
        tool_calls=30,
        test_runs=2,
        files_read=10,
        files_modified=1,
        syntax_error_rate=0.0,
        # No retrieved memories (No Memory policy)
        retrieved_memory_ids=[],
        retrieved_memory_scores=[],
        retrieved_memory_types=[],
        retrieved_memory_ages=[],
        # Memory state (No Memory policy never stores)
        memory_count_before=0,
        memory_count_after=0,
        memory_tokens_before=0,
        memory_tokens_after=0,
        # Memory operations
        pruned_memory_ids=[],
        consolidated_memory_ids=[],
        # Task metadata
        task_difficulty="easy",
        error_message=None,
    )

    logger.log_task_result(result3)
    print(f"✓ Logged task {result3.task_id} (No Memory policy)")

    # Read back all results
    print(f"\n📊 Total tasks logged: {logger.get_task_count()}")

    # Validate run parameters
    try:
        logger.validate_run_parameters(
            "gpt54_typeaware_seed1_seq1", "type_aware_decay", 1
        )
        print("✓ Run parameters validated (first 2 tasks)")
    except ValueError as e:
        print(f"✗ Validation failed: {e}")

    # Display summary
    results = logger.read_results()
    print(f"\n📋 Summary:")
    for i, result in enumerate(results, 1):
        print(
            f"  {i}. {result['task_id']}: "
            f"resolved={result['resolved']}, "
            f"policy={result['policy']}, "
            f"cost=${result['estimated_cost_usd']:.2f}"
        )

    print(f"\n✅ All results logged to: {logger.log_file}")
    print(f"   File format: JSON Lines (one JSON object per line)")


if __name__ == "__main__":
    main()
