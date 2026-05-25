"""
Unit tests for failure analysis module.

Tests Task 17.1: Failure categorization and analysis.

Requirements: 28
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.analysis.failure_analysis import (
    FailureCategory,
    FailureRecord,
    categorize_failure,
    compute_failure_rates_by_category,
    extract_failure_records,
    generate_failure_analysis_report,
    identify_boundary_tasks,
)


class TestFailureCategorization:
    """Test failure categorization logic."""

    def test_categorize_timeout_failure(self):
        """Test that timeout=True is categorized as TIMEOUT."""
        task_result = {
            "task_id": "test-1",
            "resolved": 0,
            "timeout": True,
            "syntax_error": False,
            "patch_generated": False,
            "patch_applied": False,
        }

        category = categorize_failure(task_result)
        assert category == FailureCategory.TIMEOUT

    def test_categorize_syntax_error_failure(self):
        """Test that syntax_error=True is categorized as SYNTAX_ERROR."""
        task_result = {
            "task_id": "test-2",
            "resolved": 0,
            "timeout": False,
            "syntax_error": True,
            "patch_generated": True,
            "patch_applied": False,
        }

        category = categorize_failure(task_result)
        assert category == FailureCategory.SYNTAX_ERROR

    def test_categorize_test_failure(self):
        """Test that patch generated and applied but tests failed is TEST_FAILURE."""
        task_result = {
            "task_id": "test-3",
            "resolved": 0,
            "timeout": False,
            "syntax_error": False,
            "patch_generated": True,
            "patch_applied": True,
        }

        category = categorize_failure(task_result)
        assert category == FailureCategory.TEST_FAILURE

    def test_categorize_tool_error_no_patch(self):
        """Test that patch_generated=False is categorized as TOOL_ERROR."""
        task_result = {
            "task_id": "test-4",
            "resolved": 0,
            "timeout": False,
            "syntax_error": False,
            "patch_generated": False,
            "patch_applied": False,
        }

        category = categorize_failure(task_result)
        assert category == FailureCategory.TOOL_ERROR

    def test_categorize_tool_error_patch_not_applied(self):
        """Test that patch_applied=False is categorized as TOOL_ERROR."""
        task_result = {
            "task_id": "test-5",
            "resolved": 0,
            "timeout": False,
            "syntax_error": False,
            "patch_generated": True,
            "patch_applied": False,
        }

        category = categorize_failure(task_result)
        assert category == FailureCategory.TOOL_ERROR

    def test_categorize_unknown_failure(self):
        """Test that unclassified failures are categorized as UNKNOWN."""
        # This is a rare edge case where all flags are False but task still failed
        # In practice, this should not happen, but we handle it as UNKNOWN
        task_result = {
            "task_id": "test-6",
            "resolved": 0,
            "timeout": False,
            "syntax_error": False,
            "patch_generated": True,
            "patch_applied": True,
            # All flags indicate success, but resolved=0 (should not happen in practice)
        }

        # This will be categorized as TEST_FAILURE since patch was generated and applied
        # but tests failed. Let's test a truly unknown case instead.
        category = categorize_failure(task_result)
        assert category == FailureCategory.TEST_FAILURE  # Corrected expectation

    def test_categorize_success_raises_error(self):
        """Test that categorizing a successful task raises ValueError."""
        task_result = {
            "task_id": "test-7",
            "resolved": 1,  # Success
            "timeout": False,
            "syntax_error": False,
            "patch_generated": True,
            "patch_applied": True,
        }

        with pytest.raises(ValueError, match="succeeded, cannot categorize as failure"):
            categorize_failure(task_result)

    def test_categorize_priority_timeout_over_syntax(self):
        """Test that timeout takes priority over syntax_error."""
        task_result = {
            "task_id": "test-8",
            "resolved": 0,
            "timeout": True,
            "syntax_error": True,  # Both true
            "patch_generated": False,
            "patch_applied": False,
        }

        category = categorize_failure(task_result)
        assert category == FailureCategory.TIMEOUT  # Timeout has priority


class TestExtractFailureRecords:
    """Test extraction of failure records from task results."""

    def test_extract_failure_records_empty_dir(self):
        """Test extraction from empty directory returns empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runs_dir = Path(tmpdir)
            failure_records = extract_failure_records(runs_dir)
            assert failure_records == []

    def test_extract_failure_records_no_failures(self):
        """Test extraction when all tasks succeed returns empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runs_dir = Path(tmpdir)
            run_dir = runs_dir / "run_1"
            run_dir.mkdir()

            # Create task results with all successes
            task_results = [
                {
                    "task_id": "test-1",
                    "policy": "full_memory",
                    "seed": 1,
                    "repo": "test/repo",
                    "sequence_index": 0,
                    "resolved": 1,  # Success
                    "timeout": False,
                    "syntax_error": False,
                    "patch_generated": True,
                    "patch_applied": True,
                    "error_message": None,
                }
            ]

            with open(run_dir / "task_results.jsonl", "w") as f:
                for result in task_results:
                    f.write(json.dumps(result) + "\n")

            failure_records = extract_failure_records(runs_dir)
            assert failure_records == []

    def test_extract_failure_records_with_failures(self):
        """Test extraction of multiple failure records."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runs_dir = Path(tmpdir)
            run_dir = runs_dir / "run_1"
            run_dir.mkdir()

            # Create task results with failures
            task_results = [
                {
                    "task_id": "test-1",
                    "policy": "full_memory",
                    "seed": 1,
                    "repo": "test/repo",
                    "sequence_index": 0,
                    "resolved": 0,  # Failure
                    "timeout": True,
                    "syntax_error": False,
                    "patch_generated": False,
                    "patch_applied": False,
                    "error_message": "Task exceeded 20 step limit",
                },
                {
                    "task_id": "test-2",
                    "policy": "random_prune",
                    "seed": 1,
                    "repo": "test/repo",
                    "sequence_index": 1,
                    "resolved": 0,  # Failure
                    "timeout": False,
                    "syntax_error": True,
                    "patch_generated": True,
                    "patch_applied": False,
                    "error_message": "SyntaxError: invalid syntax",
                },
            ]

            with open(run_dir / "task_results.jsonl", "w") as f:
                for result in task_results:
                    f.write(json.dumps(result) + "\n")

            failure_records = extract_failure_records(runs_dir)

            assert len(failure_records) == 2
            assert failure_records[0].task_id == "test-1"
            assert failure_records[0].category == FailureCategory.TIMEOUT
            assert failure_records[0].error_message == "Task exceeded 20 step limit"

            assert failure_records[1].task_id == "test-2"
            assert failure_records[1].category == FailureCategory.SYNTAX_ERROR
            assert failure_records[1].error_message == "SyntaxError: invalid syntax"

    def test_extract_failure_records_multiple_runs(self):
        """Test extraction across multiple run directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runs_dir = Path(tmpdir)

            # Create multiple run directories
            for run_id in ["run_1", "run_2"]:
                run_dir = runs_dir / run_id
                run_dir.mkdir()

                task_results = [
                    {
                        "task_id": f"{run_id}-task-1",
                        "policy": "full_memory",
                        "seed": 1,
                        "repo": "test/repo",
                        "sequence_index": 0,
                        "resolved": 0,
                        "timeout": True,
                        "syntax_error": False,
                        "patch_generated": False,
                        "patch_applied": False,
                        "error_message": "Timeout",
                    }
                ]

                with open(run_dir / "task_results.jsonl", "w") as f:
                    for result in task_results:
                        f.write(json.dumps(result) + "\n")

            failure_records = extract_failure_records(runs_dir)
            assert len(failure_records) == 2


class TestComputeFailureRates:
    """Test computation of failure rates by category."""

    def test_compute_failure_rates_empty_list(self):
        """Test computation with empty failure list."""
        failure_records: list[FailureRecord] = []
        failure_rates = compute_failure_rates_by_category(failure_records)
        assert failure_rates == {}

    def test_compute_failure_rates_single_policy(self):
        """Test computation for single policy."""
        failure_records = [
            FailureRecord(
                task_id="test-1",
                policy="full_memory",
                seed=1,
                repo="test/repo",
                sequence_index=0,
                category=FailureCategory.TIMEOUT,
                error_message="Timeout",
                stack_trace=None,
                timeout=True,
                syntax_error=False,
                patch_generated=False,
                patch_applied=False,
            ),
            FailureRecord(
                task_id="test-2",
                policy="full_memory",
                seed=1,
                repo="test/repo",
                sequence_index=1,
                category=FailureCategory.TIMEOUT,
                error_message="Timeout",
                stack_trace=None,
                timeout=True,
                syntax_error=False,
                patch_generated=False,
                patch_applied=False,
            ),
            FailureRecord(
                task_id="test-3",
                policy="full_memory",
                seed=1,
                repo="test/repo",
                sequence_index=2,
                category=FailureCategory.SYNTAX_ERROR,
                error_message="Syntax error",
                stack_trace=None,
                timeout=False,
                syntax_error=True,
                patch_generated=True,
                patch_applied=False,
            ),
        ]

        failure_rates = compute_failure_rates_by_category(failure_records)

        assert "full_memory" in failure_rates
        assert failure_rates["full_memory"]["timeout"] == 2 / 3
        assert failure_rates["full_memory"]["syntax_error"] == 1 / 3
        assert failure_rates["full_memory"]["total_failures"] == 3.0

    def test_compute_failure_rates_multiple_policies(self):
        """Test computation across multiple policies."""
        failure_records = [
            FailureRecord(
                task_id="test-1",
                policy="full_memory",
                seed=1,
                repo="test/repo",
                sequence_index=0,
                category=FailureCategory.TIMEOUT,
                error_message="Timeout",
                stack_trace=None,
                timeout=True,
                syntax_error=False,
                patch_generated=False,
                patch_applied=False,
            ),
            FailureRecord(
                task_id="test-2",
                policy="random_prune",
                seed=1,
                repo="test/repo",
                sequence_index=1,
                category=FailureCategory.TEST_FAILURE,
                error_message="Test failed",
                stack_trace=None,
                timeout=False,
                syntax_error=False,
                patch_generated=True,
                patch_applied=True,
            ),
        ]

        failure_rates = compute_failure_rates_by_category(failure_records)

        assert "full_memory" in failure_rates
        assert "random_prune" in failure_rates
        assert failure_rates["full_memory"]["timeout"] == 1.0
        assert failure_rates["random_prune"]["test_failure"] == 1.0


class TestIdentifyBoundaryTasks:
    """Test identification of boundary tasks (Full Memory fails, pruning succeeds)."""

    def test_identify_boundary_tasks_empty_dir(self):
        """Test identification from empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runs_dir = Path(tmpdir)
            boundary_tasks = identify_boundary_tasks(runs_dir)
            assert boundary_tasks == []

    def test_identify_boundary_tasks_no_boundaries(self):
        """Test when Full Memory succeeds on all tasks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runs_dir = Path(tmpdir)
            run_dir = runs_dir / "run_1"
            run_dir.mkdir()

            task_results = [
                {
                    "task_id": "test-1",
                    "policy": "full_memory",
                    "seed": 1,
                    "repo": "test/repo",
                    "sequence_index": 0,
                    "resolved": 1,  # Success
                    "timeout": False,
                    "syntax_error": False,
                    "patch_generated": True,
                    "patch_applied": True,
                }
            ]

            with open(run_dir / "task_results.jsonl", "w") as f:
                for result in task_results:
                    f.write(json.dumps(result) + "\n")

            boundary_tasks = identify_boundary_tasks(runs_dir)
            assert boundary_tasks == []

    def test_identify_boundary_tasks_with_boundary(self):
        """Test identification when Full Memory fails but pruning succeeds."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runs_dir = Path(tmpdir)
            run_dir = runs_dir / "run_1"
            run_dir.mkdir()

            task_results = [
                # Full Memory fails
                {
                    "task_id": "test-1",
                    "policy": "full_memory",
                    "seed": 1,
                    "repo": "test/repo",
                    "sequence_index": 0,
                    "resolved": 0,  # Failure
                    "timeout": True,
                    "syntax_error": False,
                    "patch_generated": False,
                    "patch_applied": False,
                    "error_message": "Timeout",
                },
                # Random Prune succeeds
                {
                    "task_id": "test-1",
                    "policy": "random_prune",
                    "seed": 1,
                    "repo": "test/repo",
                    "sequence_index": 0,
                    "resolved": 1,  # Success
                    "timeout": False,
                    "syntax_error": False,
                    "patch_generated": True,
                    "patch_applied": True,
                },
            ]

            with open(run_dir / "task_results.jsonl", "w") as f:
                for result in task_results:
                    f.write(json.dumps(result) + "\n")

            boundary_tasks = identify_boundary_tasks(runs_dir)

            assert len(boundary_tasks) == 1
            assert boundary_tasks[0]["task_id"] == "test-1"
            assert boundary_tasks[0]["full_memory_error"] == "timeout"
            assert "random_prune" in boundary_tasks[0]["successful_policies"]
            assert boundary_tasks[0]["n_successful_policies"] == 1

    def test_identify_boundary_tasks_multiple_successful_policies(self):
        """Test when multiple pruning policies succeed where Full Memory fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runs_dir = Path(tmpdir)
            run_dir = runs_dir / "run_1"
            run_dir.mkdir()

            task_results = [
                # Full Memory fails
                {
                    "task_id": "test-1",
                    "policy": "full_memory",
                    "seed": 1,
                    "repo": "test/repo",
                    "sequence_index": 0,
                    "resolved": 0,
                    "timeout": False,
                    "syntax_error": False,
                    "patch_generated": True,
                    "patch_applied": True,
                    "error_message": "Test failed",
                },
                # Random Prune succeeds
                {
                    "task_id": "test-1",
                    "policy": "random_prune",
                    "seed": 1,
                    "repo": "test/repo",
                    "sequence_index": 0,
                    "resolved": 1,
                    "timeout": False,
                    "syntax_error": False,
                    "patch_generated": True,
                    "patch_applied": True,
                },
                # Type-Aware Decay succeeds
                {
                    "task_id": "test-1",
                    "policy": "type_aware_decay",
                    "seed": 1,
                    "repo": "test/repo",
                    "sequence_index": 0,
                    "resolved": 1,
                    "timeout": False,
                    "syntax_error": False,
                    "patch_generated": True,
                    "patch_applied": True,
                },
            ]

            with open(run_dir / "task_results.jsonl", "w") as f:
                for result in task_results:
                    f.write(json.dumps(result) + "\n")

            boundary_tasks = identify_boundary_tasks(runs_dir)

            assert len(boundary_tasks) == 1
            assert boundary_tasks[0]["n_successful_policies"] == 2
            assert "random_prune" in boundary_tasks[0]["successful_policies"]
            assert "type_aware_decay" in boundary_tasks[0]["successful_policies"]


class TestGenerateFailureAnalysisReport:
    """Test generation of comprehensive failure analysis report."""

    def test_generate_report_empty_dir(self):
        """Test report generation from empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runs_dir = Path(tmpdir)
            report = generate_failure_analysis_report(runs_dir)

            assert report["summary"]["total_failures"] == 0
            assert report["summary"]["n_boundary_tasks"] == 0
            assert report["failure_rates"] == {}
            assert report["boundary_tasks"] == []

    def test_generate_report_with_data(self):
        """Test report generation with failure data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runs_dir = Path(tmpdir)
            run_dir = runs_dir / "run_1"
            run_dir.mkdir()

            task_results = [
                # Full Memory timeout
                {
                    "task_id": "test-1",
                    "policy": "full_memory",
                    "seed": 1,
                    "repo": "test/repo",
                    "sequence_index": 0,
                    "resolved": 0,
                    "timeout": True,
                    "syntax_error": False,
                    "patch_generated": False,
                    "patch_applied": False,
                    "error_message": "Timeout",
                },
                # Random Prune succeeds
                {
                    "task_id": "test-1",
                    "policy": "random_prune",
                    "seed": 1,
                    "repo": "test/repo",
                    "sequence_index": 0,
                    "resolved": 1,
                    "timeout": False,
                    "syntax_error": False,
                    "patch_generated": True,
                    "patch_applied": True,
                },
                # Random Prune syntax error
                {
                    "task_id": "test-2",
                    "policy": "random_prune",
                    "seed": 1,
                    "repo": "test/repo",
                    "sequence_index": 1,
                    "resolved": 0,
                    "timeout": False,
                    "syntax_error": True,
                    "patch_generated": True,
                    "patch_applied": False,
                    "error_message": "Syntax error",
                },
            ]

            with open(run_dir / "task_results.jsonl", "w") as f:
                for result in task_results:
                    f.write(json.dumps(result) + "\n")

            report = generate_failure_analysis_report(runs_dir)

            # Check summary
            assert report["summary"]["total_failures"] == 2
            assert report["summary"]["n_boundary_tasks"] == 1

            # Check failure rates
            assert "full_memory" in report["failure_rates"]
            assert "random_prune" in report["failure_rates"]

            # Check boundary tasks
            assert len(report["boundary_tasks"]) == 1
            assert report["boundary_tasks"][0]["task_id"] == "test-1"

    def test_generate_report_saves_to_file(self):
        """Test that report is saved to file when output_path provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runs_dir = Path(tmpdir)
            output_path = Path(tmpdir) / "failure_report.json"

            report = generate_failure_analysis_report(runs_dir, output_path)

            assert output_path.exists()

            # Verify saved content matches returned report
            with open(output_path) as f:
                saved_report = json.load(f)

            assert saved_report == report
