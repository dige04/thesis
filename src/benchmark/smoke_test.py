"""Smoke test for validating core system functionality.

This module implements the smoke test (Task 19.2) which validates:
1. Load 3 tasks from one sequence
2. Execute with No Memory policy
3. Verify eval_v3 Docker invocation
4. Verify logging schemas
5. Gate: >15% pass rate = GO for full experiment

Requirements: 30
Design: THESIS_FINAL_v5.md §21 (Spike Week)
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any

from src.benchmark.models import Sequence, Task
from src.benchmark.sequence_runner import SequenceRunner
from src.benchmark.swebenchcl_loader import SWEBenchCLLoader
from src.config.loader import load_config
from src.memory.policies.no_memory import NoMemoryPolicy

logger = logging.getLogger(__name__)


class SmokeTestResult:
    """Result of smoke test execution.

    Attributes:
        total_tasks: Total number of tasks executed (should be 3)
        completed_tasks: Number of tasks that completed execution
        resolved_tasks: Number of tasks that passed evaluation
        pass_rate: Percentage of tasks that passed (resolved/total)
        docker_invoked: Whether eval_v3 Docker was successfully invoked
        logging_valid: Whether all logging schemas are valid
        errors: List of error messages encountered
        success: Whether smoke test passed all gates
    """

    def __init__(self):
        self.total_tasks = 0
        self.completed_tasks = 0
        self.resolved_tasks = 0
        self.pass_rate = 0.0
        self.docker_invoked = False
        self.logging_valid = False
        self.errors: list[str] = []
        self.success = False

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for JSON serialization."""
        return {
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "resolved_tasks": self.resolved_tasks,
            "pass_rate": self.pass_rate,
            "docker_invoked": self.docker_invoked,
            "logging_valid": self.logging_valid,
            "errors": self.errors,
            "success": self.success,
        }


def create_smoke_test_sequence(
    full_sequence: Sequence, num_tasks: int = 3
) -> list[Task]:
    """Create a smoke test task list with first N tasks.

    Note: Returns a list of tasks instead of a Sequence object because
    Sequence validation requires at least 15 tasks (frozen decision #1).
    The smoke test only needs 3 tasks for quick validation.

    Args:
        full_sequence: Full sequence to extract tasks from
        num_tasks: Number of tasks to include (default: 3)

    Returns:
        List of first num_tasks tasks

    Raises:
        ValueError: If sequence has fewer than num_tasks tasks
    """
    if len(full_sequence.tasks) < num_tasks:
        raise ValueError(
            f"Sequence {full_sequence.sequence_name} has only "
            f"{len(full_sequence.tasks)} tasks, need at least {num_tasks}"
        )

    # Take first num_tasks tasks
    smoke_tasks = full_sequence.tasks[:num_tasks]

    return smoke_tasks


def verify_logging_schemas(run_dir: Path) -> tuple[bool, list[str]]:
    """Verify that all required logging files exist and have valid schemas.

    Checks for:
    - task_results.jsonl with required fields
    - memory_events.jsonl (may be empty for No Memory policy)
    - memory/snapshots/ directory with before/after snapshots

    Args:
        run_dir: Directory containing run outputs

    Returns:
        Tuple of (valid, errors) where valid is True if all schemas are valid
        and errors is a list of validation error messages
    """
    errors = []
    valid = True

    # Check task_results.jsonl
    task_results_path = run_dir / "task_results.jsonl"
    if not task_results_path.exists():
        errors.append("task_results.jsonl not found")
        valid = False
    else:
        # Validate task results schema
        try:
            with open(task_results_path, encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    if not line.strip():
                        continue
                    result = json.loads(line)

                    # Check required fields
                    required_fields = [
                        "run_id",
                        "policy",
                        "seed",
                        "repo",
                        "task_id",
                        "sequence_index",
                        "resolved",
                        "patch_generated",
                        "patch_applied",
                        "syntax_error",
                        "timeout",
                        "prompt_tokens",
                        "completion_tokens",
                        "total_tokens",
                        "estimated_cost_usd",
                        "wall_time_seconds",
                        "tool_calls",
                        "test_runs",
                        "files_read",
                        "files_modified",
                        "syntax_error_rate",
                        "retrieved_memory_ids",
                        "retrieved_memory_scores",
                        "retrieved_memory_types",
                        "retrieved_memory_ages",
                        "memory_count_before",
                        "memory_count_after",
                        "memory_tokens_before",
                        "memory_tokens_after",
                        "task_difficulty",
                    ]

                    missing_fields = [
                        field for field in required_fields if field not in result
                    ]
                    if missing_fields:
                        errors.append(
                            f"task_results.jsonl line {line_num} missing fields: "
                            f"{', '.join(missing_fields)}"
                        )
                        valid = False

        except json.JSONDecodeError as e:
            errors.append(f"task_results.jsonl has invalid JSON: {e}")
            valid = False
        except Exception as e:
            errors.append(f"Error reading task_results.jsonl: {e}")
            valid = False

    # Check memory_events.jsonl (may be empty for No Memory policy)
    memory_events_path = run_dir / "memory_events.jsonl"
    if not memory_events_path.exists():
        errors.append("memory_events.jsonl not found")
        valid = False

    # Check memory snapshots directory
    snapshots_dir = run_dir / "memory" / "snapshots"
    if not snapshots_dir.exists():
        errors.append("memory/snapshots/ directory not found")
        valid = False
    else:
        # Check for before/after snapshots
        snapshot_files = list(snapshots_dir.glob("*.json"))
        if len(snapshot_files) == 0:
            errors.append("No snapshot files found in memory/snapshots/")
            valid = False
        else:
            # Verify snapshot schema
            for snapshot_file in snapshot_files:
                try:
                    with open(snapshot_file, encoding="utf-8") as f:
                        snapshot = json.load(f)

                        # Check required fields
                        required_fields = [
                            "step",
                            "boundary",
                            "active_records",
                            "run_id",
                            "policy_name",
                            "timestamp",
                        ]

                        missing_fields = [
                            field
                            for field in required_fields
                            if field not in snapshot
                        ]
                        if missing_fields:
                            errors.append(
                                f"{snapshot_file.name} missing fields: "
                                f"{', '.join(missing_fields)}"
                            )
                            valid = False

                except json.JSONDecodeError as e:
                    errors.append(f"{snapshot_file.name} has invalid JSON: {e}")
                    valid = False
                except Exception as e:
                    errors.append(f"Error reading {snapshot_file.name}: {e}")
                    valid = False

    return valid, errors


def verify_docker_invocation(run_dir: Path) -> tuple[bool, list[str]]:
    """Verify that eval_v3 Docker was successfully invoked.

    Checks task_results.jsonl for evidence of Docker evaluation:
    - At least one task has patch_generated=true
    - Evaluation results are present (resolved field)

    Args:
        run_dir: Directory containing run outputs

    Returns:
        Tuple of (invoked, errors) where invoked is True if Docker was invoked
        and errors is a list of error messages
    """
    errors = []
    invoked = False

    task_results_path = run_dir / "task_results.jsonl"
    if not task_results_path.exists():
        errors.append("task_results.jsonl not found, cannot verify Docker invocation")
        return False, errors

    try:
        with open(task_results_path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                result = json.loads(line)

                # Check if patch was generated and evaluated
                if result.get("patch_generated", False):
                    # Check if resolved field is present (indicates evaluation occurred)
                    if "resolved" in result:
                        invoked = True
                        break

        if not invoked:
            errors.append(
                "No evidence of Docker evaluation found in task_results.jsonl. "
                "Either no patches were generated or evaluation did not run."
            )

    except Exception as e:
        errors.append(f"Error checking Docker invocation: {e}")
        return False, errors

    return invoked, errors


def run_smoke_test(
    sequence: Sequence,
    config: dict[str, Any],
    seed: int = 42,
    num_tasks: int = 3,
) -> SmokeTestResult:
    """Run smoke test with No Memory policy.

    Args:
        sequence: Full sequence to extract tasks from
        config: Configuration dictionary
        seed: Random seed for reproducibility (default: 42)
        num_tasks: Number of tasks to test (default: 3)

    Returns:
        SmokeTestResult with test outcomes and validation results
    """
    result = SmokeTestResult()

    try:
        # Create smoke test task list (first 3 tasks)
        logger.info(
            f"Creating smoke test from {sequence.sequence_name} "
            f"with {num_tasks} tasks"
        )
        smoke_tasks = create_smoke_test_sequence(sequence, num_tasks)
        result.total_tasks = num_tasks

        # Initialize No Memory policy
        logger.info("Initializing No Memory policy for smoke test")
        policy = NoMemoryPolicy()

        # Create sequence runner
        run_id = f"smoke_test_{sequence.sequence_name}_{seed}"
        logger.info(f"Creating sequence runner with run_id={run_id}")
        runner = SequenceRunner(
            run_id=run_id,
            policy=policy,
            config=config,
        )

        # Execute each task individually (since we can't create a Sequence with < 15 tasks)
        logger.info(f"Executing smoke test tasks ({num_tasks} tasks)...")
        completed_tasks = 0
        resolved_tasks = 0

        for task in smoke_tasks:
            try:
                # Execute single task using the runner's internal method
                task_result = runner._execute_task(task, seed)

                completed_tasks += 1
                if task_result.resolved == 1:
                    resolved_tasks += 1

                logger.info(
                    f"Completed task {task.task_id}: "
                    f"resolved={task_result.resolved}"
                )

            except Exception as e:
                logger.error(f"Task {task.task_id} failed: {e}", exc_info=True)
                result.errors.append(f"Task {task.task_id} failed: {e}")

        # Update results
        result.completed_tasks = completed_tasks
        result.resolved_tasks = resolved_tasks

        # Calculate pass rate
        if result.total_tasks > 0:
            result.pass_rate = (result.resolved_tasks / result.total_tasks) * 100.0

        logger.info(
            f"Smoke test execution completed: "
            f"{result.resolved_tasks}/{result.total_tasks} tasks passed "
            f"({result.pass_rate:.1f}%)"
        )

        # Verify Docker invocation
        logger.info("Verifying eval_v3 Docker invocation...")
        docker_invoked, docker_errors = verify_docker_invocation(runner.run_dir)
        result.docker_invoked = docker_invoked
        result.errors.extend(docker_errors)

        if docker_invoked:
            logger.info("✓ Docker invocation verified")
        else:
            logger.error("✗ Docker invocation failed")

        # Verify logging schemas
        logger.info("Verifying logging schemas...")
        logging_valid, logging_errors = verify_logging_schemas(runner.run_dir)
        result.logging_valid = logging_valid
        result.errors.extend(logging_errors)

        if logging_valid:
            logger.info("✓ Logging schemas valid")
        else:
            logger.error("✗ Logging schema validation failed")

        # Check gate: >15% pass rate
        PASS_RATE_GATE = 15.0
        if result.pass_rate > PASS_RATE_GATE:
            logger.info(
                f"✓ Pass rate gate met: {result.pass_rate:.1f}% > {PASS_RATE_GATE}%"
            )
            gate_passed = True
        else:
            logger.error(
                f"✗ Pass rate gate NOT met: {result.pass_rate:.1f}% <= {PASS_RATE_GATE}%"
            )
            result.errors.append(
                f"Pass rate {result.pass_rate:.1f}% does not meet "
                f"{PASS_RATE_GATE}% threshold"
            )
            gate_passed = False

        # Overall success: all checks passed
        result.success = docker_invoked and logging_valid and gate_passed

        if result.success:
            logger.info("✓ Smoke test PASSED - GO for full experiment")
        else:
            logger.error("✗ Smoke test FAILED - DO NOT proceed to full experiment")

    except Exception as e:
        logger.error(f"Smoke test failed with exception: {e}", exc_info=True)
        result.errors.append(f"Smoke test exception: {e}")
        result.success = False

    return result


def main():
    """Main entry point for smoke test CLI."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info("=" * 80)
    logger.info("SMOKE TEST - Task 19.2")
    logger.info("=" * 80)

    try:
        # Load configuration
        logger.info("Loading configuration...")
        config = load_config()

        # Load the REAL curriculum and run the pilot repo's easy tasks.
        # Decision I pins the pilot pair to django + pytest; django's sequence
        # is 100% easy, so its first `num_tasks` are guaranteed easy and satisfy
        # Sequence validation (>=15 tasks, contiguous indices). NoMemory is the
        # policy (hard-wired inside run_smoke_test) — the plumbing-first lane.
        curriculum_path = config.get("experiment", {}).get(
            "curriculum_path", "data/SWE-Bench-CL-Curriculum.json"
        )
        logger.info(f"Loading curriculum from {curriculum_path}")
        loader = SWEBenchCLLoader(curriculum_path)
        sequence = loader.get_sequence_by_name("django_django_sequence")
        if sequence is None:
            raise RuntimeError(
                f"django_django_sequence not found in curriculum ({curriculum_path}). "
                "Run scripts/build_curriculum.py."
            )

        # Run smoke test (first num_tasks easy tasks of django, NoMemory)
        result = run_smoke_test(
            sequence=sequence,
            config=config,
            seed=42,
            num_tasks=3,
        )

        # Print results
        logger.info("=" * 80)
        logger.info("SMOKE TEST RESULTS")
        logger.info("=" * 80)
        logger.info(f"Total tasks: {result.total_tasks}")
        logger.info(f"Completed tasks: {result.completed_tasks}")
        logger.info(f"Resolved tasks: {result.resolved_tasks}")
        logger.info(f"Pass rate: {result.pass_rate:.1f}%")
        logger.info(f"Docker invoked: {result.docker_invoked}")
        logger.info(f"Logging valid: {result.logging_valid}")

        if result.errors:
            logger.info("\nErrors:")
            for error in result.errors:
                logger.error(f"  - {error}")

        logger.info(f"\nOverall: {'PASSED' if result.success else 'FAILED'}")
        logger.info("=" * 80)

        # Write results to file
        results_file = Path("runs") / "smoke_test_results.json"
        results_file.parent.mkdir(parents=True, exist_ok=True)
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2)
        logger.info(f"Results written to: {results_file}")

        # Exit with appropriate code
        sys.exit(0 if result.success else 1)

    except Exception as e:
        logger.error(f"Smoke test failed with exception: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
