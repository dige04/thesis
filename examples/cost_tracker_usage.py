"""Example usage of the CostTracker for tracking LLM and embedding costs.

This example demonstrates how to:
1. Initialize a cost tracker for a run
2. Track agent LLM calls
3. Track classifier calls
4. Track consolidation calls
5. Track embedding calls
6. Aggregate costs per task
7. Generate run-level cost summary
8. Generate daily cost reports
9. Check budget alerts

Requirements: 27
"""

from src.metrics.cost_tracker import (
    CostTracker,
    check_budget_alert,
    generate_daily_cost_report,
)


def example_basic_usage():
    """Basic usage example: tracking costs for a single run."""
    print("=" * 60)
    print("Example 1: Basic Cost Tracking")
    print("=" * 60)

    # Initialize cost tracker for a run
    tracker = CostTracker(
        run_id="example_run_001",
        run_dir="runs/example_run_001"
    )

    # Start tracking the run
    tracker.start_run(
        policy="type_aware_decay",
        sequence_name="django",
        seed=1
    )

    # Start tracking a task
    tracker.start_task("django__django-12345")

    # Track agent LLM calls
    print("\n1. Tracking agent LLM call...")
    agent_cost = tracker.track_llm_call(
        call_type="agent",
        model="gpt-4o-mini",
        prompt_tokens=1500,
        completion_tokens=800,
        task_id="django__django-12345",
        metadata={"temperature": 0, "max_tokens": 1000}
    )
    print(f"   Agent call cost: ${agent_cost.estimated_cost_usd:.6f}")

    # Track type classifier call
    print("\n2. Tracking classifier call...")
    classifier_cost = tracker.track_llm_call(
        call_type="classifier",
        model="gpt-4o-mini",
        prompt_tokens=300,
        completion_tokens=50,
        task_id="django__django-12345",
        metadata={"temperature": 0}
    )
    print(f"   Classifier call cost: ${classifier_cost.estimated_cost_usd:.6f}")

    # Track embedding call
    print("\n3. Tracking embedding call...")
    embedding_cost = tracker.track_embedding_call(
        model="text-embedding-3-small",
        tokens=600,
        task_id="django__django-12345",
        memory_id="mem_001"
    )
    print(f"   Embedding call cost: ${embedding_cost.estimated_cost_usd:.6f}")

    # Complete the task
    print("\n4. Completing task...")
    task_summary = tracker.complete_task("django__django-12345")
    print(f"   Task total cost: ${task_summary.total_cost:.6f}")
    print(f"   Agent LLM calls: {task_summary.agent_llm_calls}")
    print(f"   Classifier calls: {task_summary.classifier_calls}")
    print(f"   Embedding calls: {task_summary.embedding_calls}")

    # Complete the run
    print("\n5. Completing run...")
    run_summary = tracker.complete_run()
    print(f"   Run total cost: ${run_summary.total_cost:.4f}")
    print(f"   Tasks completed: {run_summary.tasks_completed}")
    print(f"   Total LLM calls: {run_summary.total_llm_calls}")
    print(f"   Total embedding calls: {run_summary.total_embedding_calls}")

    # Write cost summary to file
    print("\n6. Writing cost summary...")
    summary_file = tracker.write_cost_summary()
    print(f"   Cost summary written to: {summary_file}")

    print("\n" + "=" * 60)


def example_multiple_tasks():
    """Example with multiple tasks in a sequence."""
    print("=" * 60)
    print("Example 2: Multiple Tasks")
    print("=" * 60)

    tracker = CostTracker(
        run_id="example_run_002",
        run_dir="runs/example_run_002"
    )

    tracker.start_run(
        policy="full_memory",
        sequence_name="django",
        seed=2
    )

    # Track 3 tasks
    for i in range(3):
        task_id = f"django__django-1234{i}"
        print(f"\nTask {i+1}: {task_id}")

        tracker.start_task(task_id)

        # Agent calls (varying amounts)
        for _ in range(2 + i):
            tracker.track_llm_call(
                call_type="agent",
                model="gpt-4o-mini",
                prompt_tokens=1000 + i * 100,
                completion_tokens=500 + i * 50,
                task_id=task_id
            )

        # Classifier call
        tracker.track_llm_call(
            call_type="classifier",
            model="gpt-4o-mini",
            prompt_tokens=250,
            completion_tokens=40,
            task_id=task_id
        )

        # Embedding call
        tracker.track_embedding_call(
            model="text-embedding-3-small",
            tokens=500,
            task_id=task_id,
            memory_id=f"mem_{i:03d}"
        )

        task_summary = tracker.complete_task(task_id)
        print(f"  Task cost: ${task_summary.total_cost:.6f}")

    # Complete run
    run_summary = tracker.complete_run()
    tracker.write_cost_summary()

    print(f"\nRun Summary:")
    print(f"  Total cost: ${run_summary.total_cost:.4f}")
    print(f"  Tasks completed: {run_summary.tasks_completed}")
    print(f"  Agent LLM cost: ${run_summary.agent_llm_cost:.4f}")
    print(f"  Classifier cost: ${run_summary.classifier_cost:.4f}")
    print(f"  Embedding cost: ${run_summary.embedding_cost:.4f}")

    print("\n" + "=" * 60)


def example_consolidation_tracking():
    """Example tracking CLS consolidation costs."""
    print("=" * 60)
    print("Example 3: CLS Consolidation Tracking")
    print("=" * 60)

    tracker = CostTracker(
        run_id="example_run_003",
        run_dir="runs/example_run_003"
    )

    tracker.start_run(
        policy="cls_consolidation",
        sequence_name="django",
        seed=3
    )

    # Track a task with consolidation
    tracker.start_task("django__django-12345")

    # Agent call
    tracker.track_llm_call(
        call_type="agent",
        model="gpt-4o-mini",
        prompt_tokens=1200,
        completion_tokens=600,
        task_id="django__django-12345"
    )

    # Classifier call
    tracker.track_llm_call(
        call_type="classifier",
        model="gpt-4o-mini",
        prompt_tokens=300,
        completion_tokens=50,
        task_id="django__django-12345"
    )

    # Consolidation call (happens during policy maintenance)
    print("\nTracking consolidation call...")
    consolidation_cost = tracker.track_llm_call(
        call_type="consolidation",
        model="gpt-4o-mini",
        prompt_tokens=2000,  # Multiple memories being consolidated
        completion_tokens=350,  # Summary generation
        task_id="django__django-12345",
        metadata={"cluster_size": 5, "max_summary_tokens": 350}
    )
    print(f"  Consolidation cost: ${consolidation_cost.estimated_cost_usd:.6f}")

    # Embedding call for consolidated memory
    tracker.track_embedding_call(
        model="text-embedding-3-small",
        tokens=350,
        task_id="django__django-12345",
        memory_id="consolidated_mem_001"
    )

    task_summary = tracker.complete_task("django__django-12345")
    print(f"\nTask Summary:")
    print(f"  Agent cost: ${task_summary.agent_llm_cost:.6f}")
    print(f"  Classifier cost: ${task_summary.classifier_cost:.6f}")
    print(f"  Consolidation cost: ${task_summary.consolidation_cost:.6f}")
    print(f"  Embedding cost: ${task_summary.embedding_cost:.6f}")
    print(f"  Total cost: ${task_summary.total_cost:.6f}")

    tracker.complete_run()
    tracker.write_cost_summary()

    print("\n" + "=" * 60)


def example_daily_report():
    """Example generating daily cost report."""
    print("=" * 60)
    print("Example 4: Daily Cost Report")
    print("=" * 60)

    # Generate report across all runs
    print("\nGenerating daily cost report...")
    report = generate_daily_cost_report(runs_dir="runs")

    print(f"\nDaily Cost Report:")
    print(f"  Total runs: {report['total_runs']}")
    print(f"  Total cost: ${report['total_cost']:.2f}")

    print(f"\n  Cost by policy:")
    for policy, cost in report['cost_by_policy'].items():
        print(f"    {policy}: ${cost:.2f}")

    print(f"\n  Cost by date:")
    for date, cost in sorted(report['cost_by_date'].items()):
        print(f"    {date}: ${cost:.2f}")

    print(f"\n  Report written to: runs/daily_cost_report.json")

    print("\n" + "=" * 60)


def example_budget_alerts():
    """Example checking budget alerts."""
    print("=" * 60)
    print("Example 5: Budget Alerts")
    print("=" * 60)

    # Check budget with different thresholds
    print("\nChecking budget alerts...")

    alert = check_budget_alert(
        runs_dir="runs",
        daily_budget=50.0,
        total_budget=500.0
    )

    print(f"\nBudget Status:")
    print(f"  Daily cost: ${alert['daily_cost']:.2f} / ${alert['daily_budget']:.2f}")
    print(f"  Total cost: ${alert['total_cost']:.2f} / ${alert['total_budget']:.2f}")

    if alert['daily_alert']:
        print(f"\n  ⚠️  DAILY BUDGET ALERT!")
        print(f"     Exceeded by: ${alert['daily_cost'] - alert['daily_budget']:.2f}")
    else:
        print(f"\n  ✓ Daily budget OK")
        print(f"    Remaining: ${alert['daily_remaining']:.2f}")

    if alert['total_alert']:
        print(f"\n  ⚠️  TOTAL BUDGET ALERT!")
        print(f"     Exceeded by: ${alert['total_cost'] - alert['total_budget']:.2f}")
    else:
        print(f"\n  ✓ Total budget OK")
        print(f"    Remaining: ${alert['total_remaining']:.2f}")

    print("\n" + "=" * 60)


def example_integration_with_sequence_runner():
    """Example showing how to integrate with SequenceRunner."""
    print("=" * 60)
    print("Example 6: Integration with SequenceRunner")
    print("=" * 60)

    print("""
Integration pattern for SequenceRunner:

```python
class SequenceRunner:
    def __init__(self, run_id, policy, config):
        # ... existing initialization ...
        
        # Initialize cost tracker
        self.cost_tracker = CostTracker(
            run_id=run_id,
            run_dir=self.run_dir
        )
        
    def run_sequence(self, sequence, seed):
        # Start cost tracking
        self.cost_tracker.start_run(
            policy=self.policy.name,
            sequence_name=sequence.sequence_name,
            seed=seed
        )
        
        for task in sequence.tasks:
            # Start task tracking
            self.cost_tracker.start_task(task.task_id)
            
            # Execute task (agent, classifier, embeddings)
            task_result = self._execute_task(task, seed)
            
            # Complete task tracking
            task_cost = self.cost_tracker.complete_task(task.task_id)
            
            # Add cost to task result
            task_result.task_api_cost = task_cost.agent_llm_cost
            task_result.consolidation_llm_cost = task_cost.consolidation_cost
            
        # Complete run tracking
        run_summary = self.cost_tracker.complete_run()
        self.cost_tracker.write_cost_summary()
        
        return SequenceResult(
            # ... existing fields ...
            total_cost_usd=run_summary.total_cost
        )
```

Integration points:
1. CodingAgent: Track agent LLM calls in solve_task()
2. MemoryClassifier: Track classifier calls in classify()
3. MemoryStore: Track embedding calls in add()
4. CLSConsolidation: Track consolidation calls in consolidate_cluster()
5. SequenceRunner: Aggregate and write cost summary
""")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    # Run all examples
    example_basic_usage()
    print("\n")
    
    example_multiple_tasks()
    print("\n")
    
    example_consolidation_tracking()
    print("\n")
    
    example_daily_report()
    print("\n")
    
    example_budget_alerts()
    print("\n")
    
    example_integration_with_sequence_runner()
