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
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
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
        dataset_name: str = "princeton-nlp/SWE-bench_Verified",
        split: str = "test",
        namespace: str = "",
        model_name: str = "memory_pruning_agent",
        harness_timeout_seconds: int = 3600,
    ) -> None:
        """Initialize the evaluator.

        Args:
            docker_image: Legacy field (kept for back-compat). The real harness
                builds swebench instance images on demand; it is not used for the
                swebench invocation.
            timeout_seconds: Per-instance test timeout passed to the harness
                (``--timeout``).
            dataset_name: HF dataset the harness loads FAIL_TO_PASS/PASS_TO_PASS
                from, by instance_id (decision E: SWE-bench_Verified).
            split: dataset split (``test``).
            namespace: swebench image namespace. **Empty string builds arm64
                instance images LOCALLY** (deviation D5 / Apple Silicon); the
                default ``"swebench"`` would pull x86_64 images.
            model_name: ``model_name_or_path`` written into the predictions and
                used in the report filename.
            harness_timeout_seconds: wall-clock cap for the whole subprocess
                (image build can take minutes); distinct from the per-instance
                ``timeout_seconds``.
        """
        self.docker_image = docker_image
        self.timeout_seconds = timeout_seconds
        self.dataset_name = dataset_name
        self.split = split
        self.namespace = namespace
        self.model_name = model_name
        self.harness_timeout_seconds = harness_timeout_seconds
        logger.info(
            f"Initialized SWEBenchEvaluator: dataset={dataset_name}, "
            f"namespace={namespace!r} (empty=arm64 local build), "
            f"per-instance timeout={timeout_seconds}s, harness timeout={harness_timeout_seconds}s"
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
        """Evaluate ``patch`` via the public swebench harness (arm64, local build).

        Writes a one-line predictions JSONL
        (``{instance_id, model_name_or_path, model_patch}``), invokes
        ``python -m swebench.harness.run_evaluation`` scoped to this single
        instance against ``SWE-bench_Verified`` (the harness loads
        FAIL_TO_PASS/PASS_TO_PASS itself, decision E), and reads the run
        report's ``resolved`` verdict.

        ``--namespace ""`` makes the harness BUILD the arm64 instance image
        locally rather than pull the x86_64 image (deviation D5 / Apple Silicon).
        An empty patch is scored unresolved without invoking the harness.

        Args:
            task: The task being evaluated.
            patch: The agent's unified-diff patch (applied on base_commit).
            work_dir: Optional dir for the predictions/report files; a temp dir
                is created and removed when not provided.

        Returns:
            DockerEvalResult with 'success', 'passed', and 'error' keys.
        """
        task_id = task.task_id

        # An empty patch is a legitimate "unresolved" outcome (the harness would
        # mark it empty_patch and never run) — not an infrastructure failure.
        if not (patch and patch.strip()):
            logger.info(f"Empty patch for {task_id}: scoring unresolved (harness not invoked)")
            return DockerEvalResult(success=True, passed=False, error=None)

        model_name_safe = self.model_name.replace("/", "__")
        run_id = f"eval_{task_id}_{uuid.uuid4().hex[:8]}"

        owns_tmp = work_dir is None
        report_dir = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="sweeval_"))
        report_dir.mkdir(parents=True, exist_ok=True)
        preds_path = report_dir / "predictions.jsonl"

        try:
            preds_path.write_text(
                json.dumps({
                    "instance_id": task_id,
                    "model_name_or_path": self.model_name,
                    "model_patch": patch,
                }) + "\n",
                encoding="utf-8",
            )

            cmd = [
                sys.executable, "-m", "swebench.harness.run_evaluation",
                "--dataset_name", self.dataset_name,
                "--split", self.split,
                "--predictions_path", str(preds_path),
                "--instance_ids", task_id,
                "--run_id", run_id,
                "--max_workers", "1",
                "--timeout", str(self.timeout_seconds),
                "--cache_level", "env",
                "--namespace", self.namespace,  # "" => build arm64 image locally (D5)
            ]
            logger.info(f"Invoking swebench harness for {task_id} (run_id={run_id})")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.harness_timeout_seconds,
                cwd=report_dir,
                check=False,
            )

            # Primary path: the harness writes a report file.
            verdict = self._read_report(report_dir, model_name_safe, run_id, task_id)
            if verdict is not None:
                return DockerEvalResult(success=True, passed=verdict, error=None)

            # Fallback: some versions print the JSON report to stdout. Reuse the
            # stdout parser, which also distinguishes infra failure from
            # unparseable success (and never substring-matches).
            return self._parse_evaluation_output(result, task_id)

        except subprocess.TimeoutExpired:
            logger.error(f"swebench harness timeout for {task_id}")
            return DockerEvalResult(
                success=False,
                passed=False,
                error=f"Harness timeout after {self.harness_timeout_seconds}s",
            )
        except FileNotFoundError:
            logger.error(f"swebench/python not found for {task_id}")
            return DockerEvalResult(
                success=False,
                passed=False,
                error="python/swebench not found - is the swebench package installed?",
            )
        except Exception as e:
            logger.error(f"swebench harness error for {task_id}: {e}", exc_info=True)
            return DockerEvalResult(
                success=False,
                passed=False,
                error=f"Harness error: {type(e).__name__}: {e}",
            )
        finally:
            if owns_tmp:
                import shutil

                shutil.rmtree(report_dir, ignore_errors=True)

    def _read_report(
        self,
        report_dir: Path,
        model_name_safe: str,
        run_id: str,
        task_id: str,
    ) -> bool | None:
        """Read the ``resolved`` verdict from the swebench report files.

        Primary: ``{report_dir}/{model_name}.{run_id}.json`` (run summary with
        ``resolved_ids``). Fallback: the per-instance
        ``logs/run_evaluation/{run_id}/{model}/{instance_id}/report.json``.
        Returns the bool verdict, or None if no report covers this instance.
        """
        summary = report_dir / f"{model_name_safe}.{run_id}.json"
        per_instance = (
            report_dir / "logs" / "run_evaluation" / run_id
            / model_name_safe / task_id / "report.json"
        )
        for path in (summary, per_instance):
            if not path.exists():
                continue
            try:
                report = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            verdict = self._resolved_from_report(report, task_id)
            if verdict is not None:
                return verdict
        return None

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

            # The swebench harness builds arm64 instance images on demand
            # (namespace=""), so there is no single image to pre-check; verify
            # the daemon is reachable instead.
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode != 0:
                return False, "Docker daemon not reachable - is Docker running?"

            return True, None

        except subprocess.TimeoutExpired:
            return False, "Docker command timeout"
        except FileNotFoundError:
            return False, "Docker not found in PATH"
        except Exception as e:
            return False, f"Unexpected error: {type(e).__name__}: {e}"
