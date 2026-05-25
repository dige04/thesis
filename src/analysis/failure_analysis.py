"""
Failure analysis for task execution results.

This module implements Task 17.1: Failure categorization and analysis.

Per Requirement 28:
- Categorize task failures: timeout, test_failure, syntax_error, tool_error, unknown
- Log both error message and stack trace when available
- Compute per-policy failure rates by category
- Identify tasks where Full_Memory_Policy fails but pruning policy succeeds
  (boundary condition for H5)

Requirements: 28
"""

import json
from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class FailureCategory(StrEnum):
    """
    Failure categories for task execution.

    Per Requirement 28, failures are categorized into 5 types:
    - TIMEOUT: Task exceeded step or time limits
    - TEST_FAILURE: Patch generated but failed eval_v3 tests
    - SYNTAX_ERROR: Code contained syntax errors
    - TOOL_ERROR: Tool execution or environment errors
    - UNKNOWN: Unclassified or unclear failure mode
    """

    TIMEOUT = "timeout"
    TEST_FAILURE = "test_failure"
    SYNTAX_ERROR = "syntax_error"
    TOOL_ERROR = "tool_error"
    UNKNOWN = "unknown"


@dataclass
class FailureRecord:
    """
    Structured representation of a task failure.

    Attributes:
        task_id: Unique task identifier
        policy: Memory policy name
        seed: Random seed
        repo: Repository name
        sequence_index: Position in sequence
        category: Failure category (one of 5 types)
        error_message: Final error message (if available)
        stack_trace: Stack trace (if available)
        timeout: Whether task timed out
        syntax_error: Whether syntax errors occurred
        patch_generated: Whether a patch was generated
        patch_applied: Whether patch was applied
    """

    task_id: str
    policy: str
    seed: int
    repo: str
    sequence_index: int
    category: FailureCategory
    error_message: str | None
    stack_trace: str | None
    timeout: bool
    syntax_error: bool
    patch_generated: bool
    patch_applied: bool


def categorize_failure(task_result: dict[str, Any]) -> FailureCategory:
    """
    Categorize a task failure based on task result fields.

    Per Requirement 28, failures are categorized as:
    1. TIMEOUT: timeout=True
    2. SYNTAX_ERROR: syntax_error=True
    3. TEST_FAILURE: patch_generated=True, patch_applied=True, but resolved=0
    4. TOOL_ERROR: patch_generated=False or patch_applied=False
    5. UNKNOWN: All other failure modes

    Args:
        task_result: Task result dictionary from task_results.jsonl

    Returns:
        FailureCategory enum value
    """
    # Check if task succeeded (not a failure)
    if task_result.get("resolved", 0) == 1:
        raise ValueError(
            f"Task {task_result.get('task_id')} succeeded, cannot categorize as failure"
        )

    # Priority order for categorization (most specific first)
    if task_result.get("timeout", False):
        return FailureCategory.TIMEOUT

    if task_result.get("syntax_error", False):
        return FailureCategory.SYNTAX_ERROR

    # Test failure: patch was generated and applied, but tests failed
    if (
        task_result.get("patch_generated", False)
        and task_result.get("patch_applied", False)
    ):
        return FailureCategory.TEST_FAILURE

    # Tool error: patch generation or application failed
    if not task_result.get("patch_generated", False) or not task_result.get(
        "patch_applied", False
    ):
        return FailureCategory.TOOL_ERROR

    # Default to unknown for unclassified failures
    return FailureCategory.UNKNOWN


def extract_failure_records(runs_dir: Path) -> list[FailureRecord]:
    """
    Extract all failure records from task results.

    Per Requirement 28, this function:
    - Identifies all failed tasks (resolved=0)
    - Categorizes each failure
    - Extracts error message and stack trace when available

    Args:
        runs_dir: Path to runs/ directory containing all run folders

    Returns:
        List of FailureRecord objects for all failed tasks
    """
    failure_records: list[FailureRecord] = []

    for run_dir in runs_dir.iterdir():
        if not run_dir.is_dir():
            continue

        task_results_path = run_dir / "task_results.jsonl"
        if not task_results_path.exists():
            continue

        # Load all task results for this run
        with open(task_results_path) as f:
            for line in f:
                if not line.strip():
                    continue

                task_result = json.loads(line)

                # Skip successful tasks
                if task_result.get("resolved", 0) == 1:
                    continue

                # Categorize failure
                category = categorize_failure(task_result)

                # Extract error information
                error_message = task_result.get("error_message")
                stack_trace = task_result.get("stack_trace")  # May not exist yet

                # Create failure record
                failure_record = FailureRecord(
                    task_id=task_result["task_id"],
                    policy=task_result["policy"],
                    seed=task_result["seed"],
                    repo=task_result["repo"],
                    sequence_index=task_result["sequence_index"],
                    category=category,
                    error_message=error_message,
                    stack_trace=stack_trace,
                    timeout=task_result.get("timeout", False),
                    syntax_error=task_result.get("syntax_error", False),
                    patch_generated=task_result.get("patch_generated", False),
                    patch_applied=task_result.get("patch_applied", False),
                )

                failure_records.append(failure_record)

    return failure_records


def compute_failure_rates_by_category(
    failure_records: list[FailureRecord],
) -> dict[str, dict[str, float]]:
    """
    Compute per-policy failure rates by category.

    Per Requirement 28, this function computes:
    - Total failure rate per policy
    - Failure rate per category per policy
    - Percentage of each category within policy failures

    Args:
        failure_records: List of FailureRecord objects

    Returns:
        Nested dict: {policy: {category: rate}}
        where rate is the proportion of failures in that category
    """
    # Count failures by policy and category
    policy_category_counts: dict[str, dict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    policy_total_counts: dict[str, int] = defaultdict(int)

    for record in failure_records:
        policy_category_counts[record.policy][record.category.value] += 1
        policy_total_counts[record.policy] += 1

    # Compute rates
    failure_rates: dict[str, dict[str, float]] = {}

    for policy, category_counts in policy_category_counts.items():
        total = policy_total_counts[policy]
        if total == 0:
            continue

        failure_rates[policy] = {}
        for category, count in category_counts.items():
            failure_rates[policy][category] = count / total

        # Add total failure count for reference
        failure_rates[policy]["total_failures"] = float(total)

    return failure_rates


def identify_boundary_tasks(
    runs_dir: Path,
) -> list[dict[str, Any]]:
    """
    Identify tasks where Full Memory fails but a pruning policy succeeds.

    Per Requirement 28 and Hypothesis H5:
    - These are "boundary conditions" where pruning helps performance
    - Indicates that Full Memory's unbounded accumulation can harm performance
    - Critical for testing H5: "Pruning can harm performance when it removes
      rare but critical repository-specific memories"

    This function identifies the OPPOSITE case: where Full Memory harms
    performance and pruning helps.

    Args:
        runs_dir: Path to runs/ directory

    Returns:
        List of dicts containing:
        - task_id: Task identifier
        - repo: Repository name
        - sequence_index: Position in sequence
        - full_memory_error: Error category for Full Memory
        - successful_policies: List of policies that succeeded
        - seed: Random seed (for reproducibility)
    """
    # Load all task results grouped by (task_id, seed)
    task_results: dict[tuple[str, int], dict[str, dict[str, Any]]] = defaultdict(dict)

    for run_dir in runs_dir.iterdir():
        if not run_dir.is_dir():
            continue

        task_results_path = run_dir / "task_results.jsonl"
        if not task_results_path.exists():
            continue

        with open(task_results_path) as f:
            for line in f:
                if not line.strip():
                    continue

                task_result = json.loads(line)
                task_id = task_result["task_id"]
                seed = task_result["seed"]
                policy = task_result["policy"]

                task_results[(task_id, seed)][policy] = task_result

    # Identify boundary tasks
    boundary_tasks: list[dict[str, Any]] = []

    for (task_id, seed), policy_results in task_results.items():
        # Check if Full Memory failed
        full_memory_result = policy_results.get("full_memory")
        if not full_memory_result or full_memory_result.get("resolved", 0) == 1:
            continue  # Full Memory succeeded or not present

        # Check if any pruning policy succeeded
        pruning_policies = [
            "random_prune",
            "recency_prune",
            "type_aware_decay",
            "cls_consolidation",
        ]

        successful_policies = []
        for policy in pruning_policies:
            policy_result = policy_results.get(policy)
            if policy_result and policy_result.get("resolved", 0) == 1:
                successful_policies.append(policy)

        # If at least one pruning policy succeeded, this is a boundary task
        if successful_policies:
            # Categorize Full Memory failure
            full_memory_category = categorize_failure(full_memory_result)

            boundary_task = {
                "task_id": task_id,
                "repo": full_memory_result["repo"],
                "sequence_index": full_memory_result["sequence_index"],
                "seed": seed,
                "full_memory_error": full_memory_category.value,
                "full_memory_error_message": full_memory_result.get("error_message"),
                "successful_policies": successful_policies,
                "n_successful_policies": len(successful_policies),
            }

            boundary_tasks.append(boundary_task)

    return boundary_tasks


def generate_failure_analysis_report(
    runs_dir: Path,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """
    Generate comprehensive failure analysis report.

    Per Requirement 28, this function:
    1. Extracts all failure records
    2. Computes per-policy failure rates by category
    3. Identifies boundary tasks (Full Memory fails, pruning succeeds)
    4. Generates summary statistics

    Args:
        runs_dir: Path to runs/ directory
        output_path: Optional path to save report JSON

    Returns:
        Dict containing:
        - failure_rates: Per-policy failure rates by category
        - boundary_tasks: Tasks where Full Memory fails but pruning succeeds
        - summary: Overall statistics
    """
    # Extract failure records
    failure_records = extract_failure_records(runs_dir)

    # Compute failure rates by category
    failure_rates = compute_failure_rates_by_category(failure_records)

    # Identify boundary tasks
    boundary_tasks = identify_boundary_tasks(runs_dir)

    # Generate summary statistics
    total_failures = len(failure_records)
    category_counts = defaultdict(int)
    for record in failure_records:
        category_counts[record.category.value] += 1

    summary = {
        "total_failures": total_failures,
        "failures_by_category": dict(category_counts),
        "n_boundary_tasks": len(boundary_tasks),
        "policies_analyzed": list(failure_rates.keys()),
    }

    # Compile report
    report = {
        "failure_rates": failure_rates,
        "boundary_tasks": boundary_tasks,
        "summary": summary,
    }

    # Save if output path provided
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)

    return report


def print_failure_analysis_summary(report: dict[str, Any]) -> None:
    """
    Print human-readable summary of failure analysis.

    Args:
        report: Failure analysis report from generate_failure_analysis_report
    """
    print("=" * 80)
    print("FAILURE ANALYSIS REPORT")
    print("=" * 80)
    print()

    # Summary statistics
    summary = report["summary"]
    print(f"Total failures: {summary['total_failures']}")
    print(f"Boundary tasks (Full Memory fails, pruning succeeds): {summary['n_boundary_tasks']}")
    print()

    # Failures by category (overall)
    print("Failures by category (overall):")
    for category, count in summary["failures_by_category"].items():
        percentage = (count / summary["total_failures"] * 100) if summary["total_failures"] > 0 else 0
        print(f"  {category:20s}: {count:4d} ({percentage:5.1f}%)")
    print()

    # Per-policy failure rates
    print("Per-policy failure rates by category:")
    print()
    failure_rates = report["failure_rates"]

    for policy in sorted(failure_rates.keys()):
        rates = failure_rates[policy]
        total = rates.get("total_failures", 0)
        print(f"{policy}:")
        print(f"  Total failures: {int(total)}")

        for category in FailureCategory:
            rate = rates.get(category.value, 0.0)
            percentage = rate * 100
            print(f"    {category.value:20s}: {percentage:5.1f}%")
        print()

    # Boundary tasks
    boundary_tasks = report["boundary_tasks"]
    if boundary_tasks:
        print(f"Boundary tasks ({len(boundary_tasks)} total):")
        print()
        for task in boundary_tasks[:10]:  # Show first 10
            print(f"  {task['task_id']} (seed={task['seed']})")
            print(f"    Full Memory error: {task['full_memory_error']}")
            print(f"    Successful policies: {', '.join(task['successful_policies'])}")
            print()

        if len(boundary_tasks) > 10:
            print(f"  ... and {len(boundary_tasks) - 10} more")
            print()

    print("=" * 80)
