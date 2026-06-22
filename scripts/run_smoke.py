"""Smoke harness for Task 4a/4b: verify large-file read/edit behavior on real tasks.

Reads ``results/preflight/smoke_tasks.json`` (3 large-file tasks selected by
``scripts/preflight_retrieval_aware.py``), runs the FULL agent loop on each at
``AGENT_TOOL_MODE=fixed``, and checks that the agent exercised ranged reads,
avoided identical-repeat read loops, made at least one successful edit, and
recorded a termination_reason.

Usage (Task 4b — network run):
    AGENT_TOOL_MODE=fixed python -m scripts.run_smoke [--runs-root /path/to/runs]

Architecture
------------
The check logic is factored into ``evaluate_smoke_trajectory(...)`` — a pure
function that operates on an already-collected trajectory + result dict. This
allows ``tests/test_smoke_harness.py`` to test the check logic offline against
fixture trajectories without any network calls.

``run_smoke()`` is the only function that actually invokes the agent (and
therefore requires network/LLM access). Every test that calls ``run_smoke()``
directly must be marked ``@pytest.mark.skip(reason="network; run in Task 4b")``.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Path to the smoke tasks manifest (relative to repo root)
_SMOKE_TASKS_JSON = Path("results/preflight/smoke_tasks.json")

# Sentinel file written when all checks pass
_RUN_COMPLETED = "RUN_COMPLETED.json"


# ---------------------------------------------------------------------------
# Check logic (pure — no network, importable offline)
# ---------------------------------------------------------------------------


def evaluate_smoke_trajectory(
    trajectory: list[dict[str, Any]],
    result: dict[str, Any],
    task_meta: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate a smoke-run trajectory against the 4 check criteria.

    Parameters
    ----------
    trajectory:
        List of step dicts from the agent, each with keys: ``action``,
        ``action_input``, ``observation_summary``.
    result:
        The agent result dict (keys: ``termination_reason``, ...).
    task_meta:
        The smoke task metadata dict (keys: ``task_id``,
        ``approx_hunk_start_line``).

    Returns
    -------
    dict with:
        passed: bool — True iff ALL 4 checks pass
        checks: dict[str, bool] — per-check pass/fail
        failures: list[str] — human-readable failure descriptions
    """
    target_line: int = task_meta.get("approx_hunk_start_line", 0)

    checks = {
        "ranged_read_reaching_target": False,
        "no_identical_repeat_read_loop": True,
        "at_least_one_successful_edit": False,
        "termination_reason_recorded": False,
    }
    failures: list[str] = []

    # ── check 1: ranged read_file that reaches the target region ─────────────
    # A read "reaches" the target only when the read WINDOW actually covers it.
    # In fixed mode the backend caps reads at MAX_READ_LINES=400 lines, so a call
    # like read_file(path, 1, 9999) only delivers lines 1-400 with a continuation
    # hint — the agent never sees line 6700. To avoid a false-pass on that pattern
    # we require that start_line itself is within MAX_READ_LINES of the target:
    #   start_line > target_line - MAX_READ_LINES
    # (i.e. the window started close enough that the cap doesn't skip the target).
    _MAX_READ_LINES = 400  # must match AgentTools.MAX_READ_LINES
    for step in trajectory:
        if step.get("action") == "read_file":
            args = step.get("action_input", {})
            start = args.get("start_line")
            if start is not None and target_line > 0:
                # start must be within one window-worth of the target
                if start > target_line - _MAX_READ_LINES:
                    checks["ranged_read_reaching_target"] = True
                    break

    if not checks["ranged_read_reaching_target"]:
        failures.append(
            f"No ranged read_file reached target region (approx_hunk_start_line="
            f"{target_line}). A valid read must have start_line > "
            f"{target_line - _MAX_READ_LINES} so the {_MAX_READ_LINES}-line window "
            f"actually covers the target — indicative of a head-only read pattern."
        )

    # ── check 2: no identical-repeat read_file loop ───────────────────────────
    # An identical-repeat loop = two consecutive read_file calls with the same
    # action_input (same path + same start_line + same end_line).
    prev_read: dict[str, Any] | None = None
    for step in trajectory:
        if step.get("action") == "read_file":
            args = step.get("action_input", {})
            key = (
                args.get("path", ""),
                args.get("start_line"),
                args.get("end_line"),
            )
            if prev_read == key:
                checks["no_identical_repeat_read_loop"] = False
                failures.append(
                    f"Identical-repeat read_file loop detected: same call "
                    f"(path={key[0]!r}, start_line={key[1]}, end_line={key[2]}) "
                    f"issued consecutively — agent is stuck reading the same range."
                )
                break
            prev_read = key
        else:
            # Reset on any non-read step (loop requires CONSECUTIVE identical reads)
            prev_read = None

    # ── check 3: at least one successful edit ────────────────────────────────
    for step in trajectory:
        if step.get("action") == "edit_file":
            obs = step.get("observation_summary", "")
            if isinstance(obs, str) and (
                obs.startswith("Edited ") or obs.lower().startswith("edited ")
            ):
                checks["at_least_one_successful_edit"] = True
                break
        if step.get("action") == "write_file":
            obs = step.get("observation_summary", "")
            if isinstance(obs, str) and (
                obs.startswith("Wrote ") or obs.lower().startswith("wrote ")
            ):
                # write_file also counts as a successful file modification
                checks["at_least_one_successful_edit"] = True
                break

    if not checks["at_least_one_successful_edit"]:
        failures.append(
            "No successful edit_file or write_file observed in trajectory. "
            "The agent must make at least one file modification to be meaningful."
        )

    # ── check 4: termination_reason recorded ──────────────────────────────────
    tr = result.get("termination_reason")
    if tr is not None and tr != "":
        checks["termination_reason_recorded"] = True
    else:
        failures.append(
            f"termination_reason not recorded in result (got: {tr!r}). "
            "Every run must record why the loop ended (finished_tool, "
            "step_limit, wall_time, ...)."
        )

    passed = all(checks.values())
    return {
        "passed": passed,
        "checks": checks,
        "failures": failures,
        "task_id": task_meta.get("task_id"),
    }


# ---------------------------------------------------------------------------
# Smoke runner (network — only called in Task 4b)
# ---------------------------------------------------------------------------


def run_smoke(
    task_ids: list[str] | None = None,
    runs_root: str | Path | None = None,
    smoke_tasks_json: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Run the full agent loop on the 3 smoke tasks and verify behavior.

    This function is the ONLY part that invokes the real LLM. All check
    logic is in ``evaluate_smoke_trajectory`` (pure, testable offline).

    Parameters
    ----------
    task_ids:
        Optional subset of task IDs to run (default: all 3 from smoke_tasks.json).
    runs_root:
        Where to write run artifacts (default: ``RUNS_ROOT`` env var or ``runs``).
    smoke_tasks_json:
        Path to ``smoke_tasks.json`` (default: ``results/preflight/smoke_tasks.json``).

    Returns
    -------
    dict mapping task_id → per-task result dict:
        ``passed``, ``checks``, ``failures``, ``run_dir``, ``task_result``
    """
    import time
    import uuid

    # ── locate smoke_tasks.json ───────────────────────────────────────────────
    manifest_path = Path(smoke_tasks_json) if smoke_tasks_json else _SMOKE_TASKS_JSON
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"smoke_tasks.json not found at {manifest_path}. "
            "Run scripts/preflight_retrieval_aware.py first to generate it."
        )
    manifest = json.loads(manifest_path.read_text())
    smoke_tasks: list[dict[str, Any]] = manifest["smoke_tasks"]

    # Filter to requested task_ids
    if task_ids:
        smoke_tasks = [t for t in smoke_tasks if t["task_id"] in task_ids]
    if not smoke_tasks:
        raise ValueError("No matching smoke tasks found.")

    # ── set AGENT_TOOL_MODE=fixed ─────────────────────────────────────────────
    os.environ["AGENT_TOOL_MODE"] = "fixed"

    # ── runs_root ─────────────────────────────────────────────────────────────
    _root = Path(runs_root) if runs_root else Path(os.environ.get("RUNS_ROOT", "runs"))
    _root.mkdir(parents=True, exist_ok=True)

    # ── imports (deferred so offline tests don't trigger network imports) ─────
    from unittest.mock import MagicMock, patch

    from src.agents.langgraph_agent import CodingAgent
    from src.benchmark.models import Task
    from src.benchmark.swebenchcl_loader import SWEBenchCLLoader
    from src.benchmark.task_env import TaskEnvironment
    from src.config.llm_factory import get_chat_client, main_model
    from src.memory.policies.no_memory import NoMemoryPolicy
    from src.memory.store import MemoryStore

    # ── load curriculum once so we can look up any task by ID ────────────────
    curriculum_path = os.environ.get(
        "CURRICULUM_PATH", "data/SWE-Bench-CL-Curriculum.json"
    )
    loader = SWEBenchCLLoader(curriculum_path=curriculum_path)
    all_sequences = loader.load_all_sequences()
    # Build a flat task-id → Task lookup
    _task_lookup: dict[str, Task] = {}
    for seq in all_sequences:
        for t in seq.tasks:
            _task_lookup[t.task_id] = t

    results: dict[str, dict[str, Any]] = {}

    for task_meta in smoke_tasks:
        task_id = task_meta["task_id"]
        run_id = f"smoke_{task_id}_{uuid.uuid4().hex[:8]}"
        run_dir = _root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"[smoke] Running {task_id} → {run_dir}")
        t0 = time.time()

        try:
            # Fetch the Task dataclass from the curriculum
            task_obj = _task_lookup.get(task_id)
            if task_obj is None:
                raise ValueError(
                    f"Task {task_id!r} not found in curriculum {curriculum_path}. "
                    "Check smoke_tasks.json or regenerate with preflight_retrieval_aware.py."
                )
            # Build a dict for solve_task (it expects a dict, not a dataclass)
            task_dict: dict[str, Any] = {
                "task_id": task_obj.task_id,
                "repo": task_obj.repo,
                "base_commit": task_obj.base_commit,
                "issue_text": task_obj.issue_text,
                "test_patch": task_obj.test_patch,
                "gold_patch": task_obj.gold_patch,
                "created_at": task_obj.created_at,
                "sequence_index": task_obj.sequence_index,
                "difficulty_label": task_obj.difficulty_label,
            }

            # Minimal config (no docker eval — smoke only checks agent behavior)
            config = {
                "agent": {
                    "max_steps_per_task": 20,
                    "max_tool_calls_per_task": 80,
                    "max_test_runs_per_task": 5,
                    "max_wall_time_seconds": 600,
                    "temperature": 0,
                    "execution_backend": "local",
                },
                "memory": {"top_k": 5, "max_context_tokens": 2000},
            }

            # Memory store (no_memory policy — smoke doesn't test memory)
            with (
                patch("src.memory.store.OpenAI", return_value=MagicMock()),
                patch("src.memory.store.embedding_base_url", return_value="http://localhost"),
                patch("src.memory.store.embedding_api_key", return_value="x"),
                patch("src.memory.store.faiss") as mock_faiss,
            ):
                mock_faiss.IndexFlatL2.return_value = MagicMock()
                memory_store = MemoryStore(
                    run_id=run_id,
                    policy_name="no_memory",
                    embedding_dim=768,
                    embedding_model="nomic-embed-text-v2-moe",
                    run_dir=run_dir,
                )

            policy = NoMemoryPolicy()

            # Task env: TaskEnvironment takes a Task dataclass; checkout via
            # checkout_clean_repo() (not checkout()).
            env = TaskEnvironment(task=task_obj)
            env.checkout_clean_repo()
            task_env = env

            agent = CodingAgent(
                memory_store=memory_store,
                policy=policy,
                config=config,
                task_env=task_env,
            )

            # Run the agent (THE ONLY NETWORK CALL in this file)
            agent_result = agent.solve_task(task_dict)

            task_env.cleanup()

        except Exception as e:
            logger.error(f"[smoke] {task_id} errored: {e}")
            agent_result = {
                "trajectory": [],
                "termination_reason": "error",
                "error_message": str(e),
            }

        elapsed = time.time() - t0

        # Evaluate trajectory
        trajectory = agent_result.get("trajectory", [])
        eval_result = evaluate_smoke_trajectory(trajectory, agent_result, task_meta)

        # Write RUN_COMPLETED.json if all checks pass
        if eval_result["passed"]:
            sentinel = run_dir / _RUN_COMPLETED
            sentinel.write_text(json.dumps({
                "task_id": task_id,
                "run_id": run_id,
                "passed": True,
                "checks": eval_result["checks"],
                "wall_time_seconds": elapsed,
                "tool_mode": agent_result.get("tool_mode", "fixed"),
            }, indent=2))
            logger.info(f"[smoke] {task_id}: PASS ({elapsed:.1f}s)")
        else:
            logger.warning(
                f"[smoke] {task_id}: FAIL — {eval_result['failures']}"
            )

        results[task_id] = {
            "passed": eval_result["passed"],
            "checks": eval_result["checks"],
            "failures": eval_result["failures"],
            "run_dir": str(run_dir),
            "task_result": agent_result,
        }

    return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(
        description="Run smoke checks on large-file tasks (Task 4b)."
    )
    parser.add_argument("--runs-root", default=None, help="Output directory for runs")
    parser.add_argument("--task-ids", nargs="*", help="Specific task IDs to run")
    args = parser.parse_args()

    results = run_smoke(task_ids=args.task_ids, runs_root=args.runs_root)

    passed = sum(1 for r in results.values() if r["passed"])
    total = len(results)
    print(f"\n{'='*60}")
    print(f"Smoke results: {passed}/{total} tasks passed all checks")
    print(f"{'='*60}")
    for task_id, r in results.items():
        status = "PASS" if r["passed"] else "FAIL"
        print(f"  {status}  {task_id}")
        for f in r.get("failures", []):
            print(f"       ✗ {f}")
    sys.exit(0 if passed == total else 1)
