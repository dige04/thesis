"""Evaluation harness wrapper for SWE-Bench eval_v3 Docker containers.

This module wraps the standard SWE-Bench eval_v3 Docker-based evaluation system,
providing a clean interface for evaluating generated patches against test suites.

The evaluator invokes Docker containers for each task-patch pair and returns
structured results with pass/fail status, execution time, and error information.

Requirements:
- Requirement 17: Evaluation Harness Integration
"""

import json
import logging
import subprocess
import time
from dataclasses import dataclass
from typing import Any, TypedDict

from src.benchmark.models import Task

logger = logging.getLogger(__name__)


class DockerEvalResult(TypedDict):
    """Result from Docker evaluation execution."""

    success: bool
    passed: bool
    error: str | None


@dataclass
class EvaluationResult:
    """Result of evaluating a patch using the eval_v3 harness.

    Attributes:
        success: Whether the evaluation completed without Docker/infrastructure errors
        passed: Whether the patch passed all tests (only valid if success=True)
        error: Error message if evaluation failed (None if success=True)
        execution_time: Time taken to run evaluation in seconds
        task_id: Task identifier for traceability
    """

    success: bool
    passed: bool
    error: str | None
    execution_time: float
    task_id: str


class SWEBenchEvaluator:
    """Wrapper for SWE-Bench eval_v3 Docker harness.

    This class provides a clean interface to the standard SWE-Bench evaluation
    system, handling Docker container lifecycle, error handling, and result parsing.

    The evaluator is designed to be used in the experimental pipeline where:
    1. Agent generates a patch for a task
    2. Evaluator runs the patch in a Docker container
    3. Binary pass/fail result is returned for analysis

    Attributes:
        docker_image: Name of the eval_v3 Docker image to use
        timeout_seconds: Maximum time to wait for evaluation (default: 300s)
    """

    def __init__(
        self,
        docker_image: str = "swebench/eval_v3:latest",
        timeout_seconds: int = 300,
    ) -> None:
        """Initialize the evaluator.

        Args:
            docker_image: Docker image name for eval_v3 harness
            timeout_seconds: Maximum evaluation time before timeout
        """
        self.docker_image = docker_image
        self.timeout_seconds = timeout_seconds
        logger.info(
            f"Initialized SWEBenchEvaluator with image={docker_image}, "
            f"timeout={timeout_seconds}s"
        )

    def evaluate_patch(
        self,
        task: Task,
        patch: str,
        work_dir: str | None = None,
    ) -> EvaluationResult:
        """Evaluate a generated patch using the eval_v3 Docker harness.

        This method:
        1. Invokes the eval_v3 Docker container with the task and patch
        2. Waits for evaluation to complete (up to timeout_seconds)
        3. Parses the result to determine pass/fail status
        4. Handles Docker failures gracefully

        Args:
            task: The task being evaluated
            patch: The generated patch to evaluate
            work_dir: Optional working directory for Docker execution

        Returns:
            EvaluationResult with success status, pass/fail result, and timing

        Requirements:
        - Requirement 17.1: Invoke eval_v3 Docker container for each patch
        - Requirement 17.2: Return binary pass/fail result
        - Requirement 17.3: Log execution time and errors
        - Requirement 17.4: Handle Docker failures gracefully
        """
        start_time = time.time()
        task_id = task.task_id

        logger.info(f"Starting evaluation for task {task_id}")

        try:
            # Invoke Docker container with eval_v3 harness
            result = self._run_docker_evaluation(task, patch, work_dir)
            execution_time = time.time() - start_time

            if result["success"]:
                logger.info(
                    f"Evaluation completed for {task_id}: "
                    f"passed={result['passed']}, time={execution_time:.2f}s"
                )
                return EvaluationResult(
                    success=True,
                    passed=result["passed"],
                    error=None,
                    execution_time=execution_time,
                    task_id=task_id,
                )
            else:
                logger.error(
                    f"Evaluation failed for {task_id}: {result['error']}, "
                    f"time={execution_time:.2f}s"
                )
                return EvaluationResult(
                    success=False,
                    passed=False,
                    error=result["error"],
                    execution_time=execution_time,
                    task_id=task_id,
                )

        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"Unexpected error during evaluation: {type(e).__name__}: {e}"
            logger.exception(f"Evaluation exception for {task_id}: {error_msg}")

            # Requirement 17.4: Handle Docker failures gracefully
            return EvaluationResult(
                success=False,
                passed=False,
                error=error_msg,
                execution_time=execution_time,
                task_id=task_id,
            )

    def _run_docker_evaluation(
        self,
        task: Task,
        patch: str,
        work_dir: str | None,
    ) -> DockerEvalResult:
        """Run the actual Docker evaluation command.

        This is the core integration point with the eval_v3 harness.
        It constructs and executes the Docker command, then parses the output.

        Args:
            task: The task being evaluated
            patch: The patch to evaluate
            work_dir: Optional working directory

        Returns:
            DockerEvalResult with 'success', 'passed', and 'error' keys

        Note:
            This is a placeholder implementation. The actual eval_v3 Docker
            command structure will be finalized during Spike Week when the
            Docker images are built and tested.

            Expected command format (to be confirmed):
            docker run --rm -v {work_dir}:/workspace {image} \
                --task-id {task_id} \
                --repo {repo} \
                --base-commit {base_commit} \
                --patch /workspace/patch.diff \
                --test-patch /workspace/test.patch
        """
        try:
            # TODO: Finalize Docker command structure during Spike Week
            # This is a placeholder that demonstrates the expected interface

            # Construct Docker command
            cmd = [
                "docker",
                "run",
                "--rm",
                "--network=none",  # Isolate container
                # NOTE: `docker run` has no --timeout flag; the wall-clock cap is
                # enforced by subprocess.run(timeout=...) below.
            ]

            # Add volume mount if work_dir provided
            if work_dir:
                cmd.extend(["-v", f"{work_dir}:/workspace"])

            # Add image and eval_v3 arguments
            cmd.extend(
                [
                    self.docker_image,
                    "--task-id",
                    task.task_id,
                    "--repo",
                    task.repo,
                    "--base-commit",
                    task.base_commit,
                ]
            )

            logger.debug(f"Docker command: {' '.join(cmd)}")

            # Execute Docker command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,  # Don't raise on non-zero exit
            )

            # Parse the JSON report emitted by the harness.
            return self._parse_evaluation_output(result, task.task_id)

        except subprocess.TimeoutExpired:
            # Handle Docker timeout using centralized error handling
            logger.error(f"Docker evaluation timeout for task {task.task_id}")
            return DockerEvalResult(
                success=False,
                passed=False,
                error=f"Evaluation timeout after {self.timeout_seconds}s",
            )
        except FileNotFoundError:
            # Handle Docker not found
            logger.error(f"Docker command not found for task {task.task_id}")
            return DockerEvalResult(
                success=False,
                passed=False,
                error="Docker command not found - is Docker installed?",
            )
        except Exception as e:
            # Handle any other Docker errors using centralized error handling
            logger.error(f"Docker execution error for task {task.task_id}: {e}", exc_info=True)
            return DockerEvalResult(
                success=False,
                passed=False,
                error=f"Docker execution error: {type(e).__name__}: {e}",
            )

    def _parse_evaluation_output(
        self,
        result: subprocess.CompletedProcess[str],
        task_id: str,
    ) -> DockerEvalResult:
        """Parse the JSON report emitted by the eval harness.

        The SWE-Bench / eval_v3 harness emits a JSON report. We accept the
        common shapes (see ``_resolved_from_report``) and read the boolean
        ``resolved`` for ``task_id``. Substring matching is NOT used — it is
        unreliable (an issue body containing "failed" would flip the verdict).

        Args:
            result: The completed subprocess result from Docker.
            task_id: The instance/task id to look up in the report.

        Returns:
            DockerEvalResult with 'success', 'passed', and 'error' keys.
        """
        stdout = (result.stdout or "").strip()

        report = self._extract_report_json(stdout)
        if report is not None:
            resolved = self._resolved_from_report(report, task_id)
            if resolved is not None:
                return DockerEvalResult(success=True, passed=resolved, error=None)

        # No parseable report → distinguish a Docker/infra failure from an
        # unparseable-but-successful exit.
        if result.returncode != 0:
            return DockerEvalResult(
                success=False,
                passed=False,
                error=f"Docker exit code {result.returncode}: {(result.stderr or '')[:500]}",
            )
        return DockerEvalResult(
            success=False,
            passed=False,
            error=f"Could not parse evaluation report for {task_id}: {stdout[:200]}",
        )

    @staticmethod
    def _extract_report_json(stdout: str) -> Any | None:
        """Best-effort extraction of a JSON report from harness stdout.

        Tries the whole stdout, then each line from the end (the report is
        typically the last JSON object printed). Returns the parsed object or
        None if no JSON is found.
        """
        candidates = [stdout, *reversed(stdout.splitlines())]
        for candidate in candidates:
            candidate = candidate.strip()
            if not candidate or candidate[0] not in "{[":
                continue
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
        return None

    @staticmethod
    def _resolved_from_report(report: Any, task_id: str) -> bool | None:
        """Read the boolean ``resolved`` verdict for ``task_id`` from a report.

        Accepts several shapes the harness may emit:
        - ``{"resolved": bool}`` / ``{"passed": bool}``  (single-instance)
        - ``{"<task_id>": {"resolved": bool}}``           (per-instance map)
        - ``{"resolved_ids": [...]}`` / ``{"resolved_instances": [...]}``  (SWE-Bench summary)
        Returns the boolean, or None if the report does not cover this task.
        """
        if not isinstance(report, dict):
            return None
        if isinstance(report.get("resolved"), bool):
            return report["resolved"]
        if isinstance(report.get("passed"), bool):
            return report["passed"]
        instance = report.get(task_id)
        if isinstance(instance, dict) and isinstance(instance.get("resolved"), bool):
            return instance["resolved"]
        for key in ("resolved_ids", "resolved_instances"):
            ids = report.get(key)
            if isinstance(ids, list):
                return task_id in ids
        return None

    def verify_docker_available(self) -> tuple[bool, str | None]:
        """Verify that Docker is available and the eval_v3 image exists.

        Returns:
            Tuple of (is_available, error_message)
            - (True, None) if Docker and image are available
            - (False, error_message) if there's a problem

        This method is used during smoke tests to validate the environment
        before running the full experiment.
        """
        try:
            # Check Docker is installed
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode != 0:
                return False, "Docker command failed - is Docker installed?"

            # Check eval_v3 image exists
            result = subprocess.run(
                ["docker", "images", "-q", self.docker_image],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode != 0:
                return False, f"Failed to check for image {self.docker_image}"

            if not result.stdout.strip():
                return (
                    False,
                    f"Docker image {self.docker_image} not found - run 'make setup' to build",
                )

            return True, None

        except subprocess.TimeoutExpired:
            return False, "Docker command timeout"
        except FileNotFoundError:
            return False, "Docker not found in PATH"
        except Exception as e:
            return False, f"Unexpected error: {type(e).__name__}: {e}"
