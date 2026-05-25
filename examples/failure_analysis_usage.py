"""
Example usage of failure analysis module.

This demonstrates how to use the failure analysis functions to:
1. Categorize task failures
2. Extract failure records from runs
3. Compute per-policy failure rates
4. Identify boundary tasks (Full Memory fails, pruning succeeds)
5. Generate comprehensive failure analysis reports

Requirements: 28
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analysis.failure_analysis import (
    FailureCategory,
    categorize_failure,
    extract_failure_records,
    generate_failure_analysis_report,
    identify_boundary_tasks,
    print_failure_analysis_summary,
)


def example_categorize_failure():
    """Example: Categorize a single task failure."""
    print("=" * 80)
    print("Example 1: Categorize Task Failure")
    print("=" * 80)
    print()

    # Example 1: Timeout failure
    task_result_timeout = {
        "task_id": "django__django-12345",
        "resolved": 0,
        "timeout": True,
        "syntax_error": False,
        "patch_generated": False,
        "patch_applied": False,
        "error_message": "Task exceeded 20 step limit (hard force-fail)",
    }

    category = categorize_failure(task_result_timeout)
    print(f"Task: {task_result_timeout['task_id']}")
    print(f"Category: {category}")
    print(f"Error: {task_result_timeout['error_message']}")
    print()

    # Example 2: Test failure
    task_result_test_fail = {
        "task_id": "flask__flask-5678",
        "resolved": 0,
        "timeout": False,
        "syntax_error": False,
        "patch_generated": True,
        "patch_applied": True,
        "error_message": "Test failed: expected 200, got 404",
    }

    category = categorize_failure(task_result_test_fail)
    print(f"Task: {task_result_test_fail['task_id']}")
    print(f"Category: {category}")
    print(f"Error: {task_result_test_fail['error_message']}")
    print()

    # Example 3: Syntax error
    task_result_syntax = {
        "task_id": "requests__requests-9012",
        "resolved": 0,
        "timeout": False,
        "syntax_error": True,
        "patch_generated": True,
        "patch_applied": False,
        "error_message": "SyntaxError: invalid syntax at line 42",
    }

    category = categorize_failure(task_result_syntax)
    print(f"Task: {task_result_syntax['task_id']}")
    print(f"Category: {category}")
    print(f"Error: {task_result_syntax['error_message']}")
    print()


def example_extract_failure_records():
    """Example: Extract all failure records from runs directory."""
    print("=" * 80)
    print("Example 2: Extract Failure Records")
    print("=" * 80)
    print()

    # Assuming runs directory exists
    runs_dir = Path("runs")

    if not runs_dir.exists():
        print(f"Runs directory not found: {runs_dir}")
        print("This example requires actual run data.")
        print()
        return

    failure_records = extract_failure_records(runs_dir)

    print(f"Total failures found: {len(failure_records)}")
    print()

    if failure_records:
        print("First 5 failures:")
        for record in failure_records[:5]:
            print(f"  {record.task_id} ({record.policy}, seed={record.seed})")
            print(f"    Category: {record.category}")
            print(f"    Error: {record.error_message}")
            print()


def example_identify_boundary_tasks():
    """Example: Identify boundary tasks where Full Memory fails but pruning succeeds."""
    print("=" * 80)
    print("Example 3: Identify Boundary Tasks")
    print("=" * 80)
    print()

    runs_dir = Path("runs")

    if not runs_dir.exists():
        print(f"Runs directory not found: {runs_dir}")
        print("This example requires actual run data.")
        print()
        return

    boundary_tasks = identify_boundary_tasks(runs_dir)

    print(f"Boundary tasks found: {len(boundary_tasks)}")
    print()
    print("These are tasks where Full Memory fails but at least one pruning policy succeeds.")
    print("This is critical for testing Hypothesis H5.")
    print()

    if boundary_tasks:
        print("First 3 boundary tasks:")
        for task in boundary_tasks[:3]:
            print(f"  {task['task_id']} (seed={task['seed']})")
            print(f"    Full Memory error: {task['full_memory_error']}")
            print(f"    Successful policies: {', '.join(task['successful_policies'])}")
            print()


def example_generate_full_report():
    """Example: Generate comprehensive failure analysis report."""
    print("=" * 80)
    print("Example 4: Generate Comprehensive Failure Analysis Report")
    print("=" * 80)
    print()

    runs_dir = Path("runs")

    if not runs_dir.exists():
        print(f"Runs directory not found: {runs_dir}")
        print("This example requires actual run data.")
        print()
        return

    # Generate report
    output_path = Path("results") / "failure_analysis_report.json"
    report = generate_failure_analysis_report(runs_dir, output_path)

    print(f"Report saved to: {output_path}")
    print()

    # Print human-readable summary
    print_failure_analysis_summary(report)


def example_all_failure_categories():
    """Example: Show all failure categories."""
    print("=" * 80)
    print("Example 5: All Failure Categories")
    print("=" * 80)
    print()

    print("Per Requirement 28, failures are categorized into 5 types:")
    print()

    for category in FailureCategory:
        print(f"  {category.value:20s}: {category.name}")

    print()
    print("Category descriptions:")
    print("  - TIMEOUT: Task exceeded step or time limits")
    print("  - TEST_FAILURE: Patch generated but failed eval_v3 tests")
    print("  - SYNTAX_ERROR: Code contained syntax errors")
    print("  - TOOL_ERROR: Tool execution or environment errors")
    print("  - UNKNOWN: Unclassified or unclear failure mode")
    print()


if __name__ == "__main__":
    # Run all examples
    example_all_failure_categories()
    example_categorize_failure()
    example_extract_failure_records()
    example_identify_boundary_tasks()
    example_generate_full_report()
