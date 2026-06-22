"""Sequence runner for orchestrating task execution across a sequence.

This module implements the main orchestrator that ties together all components:
agent, memory, evaluation, and logging. It executes all tasks in a sequence
while maintaining persistent memory across task boundaries.

Key responsibilities:
- Initialize memory store with selected policy at sequence start
- For each task: retrieve memories, execute agent, evaluate, reflect, maintain
- Generate memory snapshots before/after each task
- Handle failures gracefully (repository checkout failures fail entire sequence)
- Return sequence-level results

Requirements: 18, 27
Design: THESIS_FINAL_v5.md §2, §16
Frozen Invariants:
- Clean repository checkout per task (frozen decision #2)
- Fail entire sequence on repository errors
- Generate before/after snapshots at EVERY task boundary
- Max 20 steps per task (frozen decision #3)
"""

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.agents.langgraph_agent import CodingAgent
from src.benchmark.evaluator import SWEBenchEvaluator
from src.benchmark.models import Sequence, Task
from src.benchmark.task_env import RepositoryCheckoutError, TaskEnvironment
from src.errors import UsageLimitError
from src.logging.memory_event_logger import MemoryEventLogger
from src.logging.memory_snapshot_logger import MemorySnapshotLogger
from src.logging.task_logger import TaskResult, TaskResultLogger
from src.logging.trajectory_logger import TrajectoryLogger
from src.memory.policies.base import MemoryPolicy
from src.memory.reflection import ReflectionError, reflect_and_write_memory
from src.memory.store import MemoryStore
from src.metrics.cost_tracker import CostTracker
from src.metrics.retrieval_quality import (
    RetrievalQualityMetrics,
    compute_retrieval_quality,
)

logger = logging.getLogger(__name__)


def _runs_root() -> Path:
    """Root directory for run outputs (default ``runs``).

    Overridable via the ``RUNS_ROOT`` env var so a run on a different model/
    provider (e.g. the MiniMax M3 matrix -> ``runs_m3``) writes to a fresh tree
    and never mixes with prior runs on the same host.
    """
    return Path(os.environ.get("RUNS_ROOT", "runs"))


@dataclass
class SequenceResult:
    """Result of executing a complete sequence.

    Attributes:
        sequence_name: Name of the sequence (e.g., "django")
        repo: Repository name (e.g., "django/django")
        policy_name: Name of the memory policy used
        seed: Random seed for reproducibility
        total_tasks: Total number of tasks in the sequence
        completed_tasks: Number of tasks successfully completed
        resolved_tasks: Number of tasks that passed evaluation
        failed_tasks: Number of tasks that failed
        timeout_tasks: Number of tasks that timed out
        total_wall_time: Total wall time for the sequence in seconds
        total_cost_usd: Total estimated cost in USD
        error_message: Error message if sequence failed (None if successful)
        run_id: Unique identifier for this run
    """

    sequence_name: str
    repo: str
    policy_name: str
    seed: int
    total_tasks: int
    completed_tasks: int
    resolved_tasks: int
    failed_tasks: int
    timeout_tasks: int
    total_wall_time: float
    total_cost_usd: float
    error_message: str | None
    run_id: str
    # C8: tasks that raised a non-fatal error and produced NO TaskResult row —
    # tracked separately so a matrix with silently missing rows is not counted as
    # complete (THESIS_REVIEW blocker #10). Defaults keep existing constructors valid.
    errored_tasks: int = 0
    error_task_ids: list[str] = field(default_factory=list)


class SequenceRunner:
    """Orchestrator for executing all tasks in a sequence.

    This class is the main entry point for running a complete sequence with
    a specific memory policy. It coordinates:
    - Memory store initialization and persistence
    - Task environment setup (clean repo checkout)
    - Agent execution with memory retrieval
    - Evaluation with eval_v3 harness
    - Reflection and memory writing
    - Policy maintenance (prune/consolidate)
    - Logging and snapshot generation

    Attributes:
        run_id: Unique identifier for this run
        policy: Memory policy instance
        config: Configuration dictionary
        memory_store: Persistent memory store (SQLite + FAISS)
        evaluator: SWE-Bench evaluator instance
        task_logger: Task results logger
        memory_event_logger: Memory events logger
        snapshot_logger: Memory snapshot logger
        run_dir: Directory for this run's outputs
    """

    def __init__(
        self,
        run_id: str,
        policy: MemoryPolicy,
        config: dict[str, Any],
    ):
        """Initialize sequence runner.

        Args:
            run_id: Unique identifier for this run
            policy: Memory policy instance (one of 6)
            config: Configuration dictionary with all parameters

        Raises:
            ValueError: If required config parameters are missing
        """
        self.run_id = run_id
        self.policy = policy
        self.config = config

        # Setup run directory (RUNS_ROOT-overridable; isolates the M3 matrix)
        self.run_dir = _runs_root() / run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

        # Initialize memory store — pass run_dir so memory.db/.faiss/snapshots
        # all land under self.run_dir (which respects RUNS_ROOT via _runs_root()).
        self.memory_store = MemoryStore(
            run_id=run_id,
            policy_name=policy.name,
            embedding_dim=config.get("memory", {}).get("embedding_dim", 1536),
            embedding_model=config.get("memory", {}).get(
                "embedding_model", "text-embedding-3-small"
            ),
            run_dir=self.run_dir,
        )

        # Initialize evaluator. ``namespace`` controls image source: "" builds
        # the instance image locally (arm64/D5); "swebench" PULLS the prebuilt
        # x86_64 image from Docker Hub (native x86_64 host — fast, no local build).
        eval_cfg = config.get("evaluation", {})
        self.evaluator = SWEBenchEvaluator(
            docker_image=eval_cfg.get("docker_image", "swebench/eval_v3:latest"),
            timeout_seconds=eval_cfg.get("timeout_seconds", 300),
            dataset_name=eval_cfg.get("dataset_name", "princeton-nlp/SWE-bench_Verified"),
            namespace=eval_cfg.get("namespace", ""),
        )

        # Initialize loggers
        self.task_logger = TaskResultLogger(run_dir=self.run_dir)
        self.memory_event_logger = MemoryEventLogger(
            log_file_path=self.run_dir / "memory_events.jsonl",
            policy_name=policy.name,
        )
        self.snapshot_logger = MemorySnapshotLogger(
            snapshot_dir=self.run_dir / "memory" / "snapshots",
            run_id=run_id,
            policy_name=policy.name,
        )

        # Check if pilot mode is enabled for retrieval quality logging
        self.pilot_mode_enabled = config.get("experiment", {}).get("pilot_mode", {}).get("enabled", False)
        self.log_retrieval_quality = config.get("experiment", {}).get("pilot_mode", {}).get("log_retrieval_quality", False)

        # Initialize retrieval quality metrics storage
        self.retrieval_quality_metrics: list[RetrievalQualityMetrics] = []

        # Cost tracker — writes the 4th mandatory log stream cost_summary.json.
        # Mode comes from config (D3: "tokens" for Ollama flat-rate; under any
        # non-"usd" mode unknown model names do not raise — tokens stay
        # authoritative). v5 §1570 Pareto cost axis = total tokens.
        self.cost_tracker = CostTracker(
            run_id=run_id,
            run_dir=self.run_dir,
            cost_metric_mode=config.get("evaluation", {}).get("cost_metric_mode", "usd"),
        )

        logger.info(
            f"Initialized SequenceRunner: run_id={run_id}, "
            f"policy={policy.name}, run_dir={self.run_dir}, "
            f"pilot_mode={self.pilot_mode_enabled}, log_retrieval_quality={self.log_retrieval_quality}"
        )

    def run_sequence(self, sequence: Sequence, seed: int) -> SequenceResult:
        """Execute all tasks in a sequence with persistent memory.

        This is the main entry point for running a complete sequence. It:
        1. Initializes memory store with selected policy
        2. For each task in sequence:
           - Generate "before_task" memory snapshot
           - Set up clean task environment (checkout repository)
           - Retrieve relevant memories using policy.retrieve()
           - Execute coding agent with retrieved context
           - Evaluate generated patch with eval_v3 harness
           - Run reflection step to create memory record
           - Write memory record using policy.write()
           - Run policy maintenance (prune/consolidate if needed)
           - Generate "after_task" memory snapshot
           - Log all results and events
        3. Handle failures gracefully
        4. Return sequence-level results

        Args:
            sequence: Sequence instance with ordered tasks
            seed: Random seed for reproducibility

        Returns:
            SequenceResult with aggregate statistics

        Raises:
            RepositoryCheckoutError: If repository checkout fails (fails entire sequence)

        Requirements:
            - Requirement 18: Log all task results and memory events
            - Requirement 27: Generate snapshots at every task boundary
            - Frozen decision #2: Clean repo checkout per task
            - Frozen decision #3: Max 20 steps per task
        """
        logger.info(
            f"Starting sequence: {sequence.sequence_name} "
            f"({sequence.task_count} tasks) with policy={self.policy.name}, seed={seed}"
        )

        # Start cost tracking for this run (must precede any track_*_call).
        try:
            self.cost_tracker.start_run(
                policy=self.policy.name,
                sequence_name=sequence.sequence_name,
                seed=seed,
            )
            # E1: the runner now surfaces every v5 §1582 cost-axis call type
            # (agent + reflection + classifier + CLS consolidation + embedding),
            # so total_tokens is the COMPLETE Pareto cost axis for this run.
            self.cost_tracker.mark_pareto_cost_complete()
        except Exception as e:  # cost tracking is auxiliary, never fatal
            logger.warning(f"cost_tracker.start_run failed: {e}")

        sequence_start_time = time.time()
        completed_tasks = 0
        resolved_tasks = 0
        failed_tasks = 0
        timeout_tasks = 0
        total_cost_usd = 0.0
        error_message = None
        errored_tasks = 0
        error_task_ids: list[str] = []

        try:
            # Execute each task in sequence
            for task in sequence.tasks:
                logger.info(
                    f"Starting task {task.sequence_index + 1}/{sequence.task_count}: "
                    f"{task.task_id}"
                )

                try:
                    # Execute single task
                    task_result = self._execute_task(task, seed)

                    # Update counters
                    completed_tasks += 1
                    if task_result.resolved == 1:
                        resolved_tasks += 1
                    else:
                        failed_tasks += 1
                    if task_result.timeout:
                        timeout_tasks += 1
                    total_cost_usd += task_result.estimated_cost_usd

                    logger.info(
                        f"Completed task {task.task_id}: "
                        f"resolved={task_result.resolved}, "
                        f"timeout={task_result.timeout}, "
                        f"cost=${task_result.estimated_cost_usd:.4f}"
                    )

                except RepositoryCheckoutError as e:
                    # Repository checkout failures fail the entire sequence
                    # (Frozen decision #2)
                    error_message = f"Repository checkout failed for {task.task_id}: {e}"
                    logger.error(error_message)
                    raise

                except UsageLimitError as e:
                    # Provider quota exhausted — FATAL. Abort the whole run; the
                    # model can no longer be called, so every remaining task would
                    # be a silent invalid 0-resolved. Resume after quota/billing.
                    error_message = f"ABORTING run — provider usage limit: {e}"
                    logger.error(error_message)
                    raise

                except Exception as e:
                    # Non-fatal task error: NO TaskResult row was written, so this
                    # task did NOT complete. Track it separately (C8) rather than
                    # inflating completed_tasks/failed_tasks — otherwise the run looks
                    # complete while rows are silently missing (review blocker #10).
                    error_message = f"Task {task.task_id} failed with error: {e}"
                    logger.error(error_message, exc_info=True)
                    errored_tasks += 1
                    error_task_ids.append(task.task_id)

        except RepositoryCheckoutError:
            # Re-raise repository errors to fail the sequence
            raise

        except UsageLimitError:
            # Re-raise provider quota errors to abort the run (and the experiment).
            raise

        except Exception as e:
            # Unexpected sequence-level error
            error_message = f"Sequence failed with unexpected error: {e}"
            logger.error(error_message, exc_info=True)

        finally:
            # Close memory store
            self.memory_store.close()

            # Save retrieval quality metrics if pilot mode enabled
            if self.pilot_mode_enabled and self.log_retrieval_quality and self.retrieval_quality_metrics:
                self._save_retrieval_quality_metrics()

            # Write the 4th mandatory log stream (cost_summary.json). Never let
            # a cost-bookkeeping failure mask the real sequence result.
            try:
                self.cost_tracker.complete_run()
                self.cost_tracker.write_cost_summary()
            except Exception as e:
                logger.warning(f"cost_tracker write failed: {e}")

        # Calculate total wall time
        total_wall_time = time.time() - sequence_start_time

        # Build sequence result
        result = SequenceResult(
            sequence_name=sequence.sequence_name,
            repo=sequence.repo,
            policy_name=self.policy.name,
            seed=seed,
            total_tasks=sequence.task_count,
            completed_tasks=completed_tasks,
            resolved_tasks=resolved_tasks,
            failed_tasks=failed_tasks,
            timeout_tasks=timeout_tasks,
            total_wall_time=total_wall_time,
            total_cost_usd=total_cost_usd,
            error_message=error_message,
            run_id=self.run_id,
            errored_tasks=errored_tasks,
            error_task_ids=error_task_ids,
        )

        logger.info(
            f"Sequence completed: {sequence.sequence_name} - "
            f"resolved={resolved_tasks}/{sequence.task_count}, "
            f"failed={failed_tasks}, timeout={timeout_tasks}, "
            f"time={total_wall_time:.1f}s, cost=${total_cost_usd:.2f}"
        )

        return result

    def _execute_task(self, task: Task, seed: int) -> TaskResult:
        """Execute a single task with full pipeline.

        This method orchestrates the complete task execution pipeline:
        1. Generate "before_task" memory snapshot
        2. Set up clean task environment (checkout repository)
        3. Retrieve relevant memories
        4. Execute agent
        5. Evaluate patch
        6. Reflect and write memory
        7. Maintain policy (prune/consolidate)
        8. Generate "after_task" memory snapshot
        9. Log results

        Args:
            task: Task instance to execute
            seed: Random seed for reproducibility

        Returns:
            TaskResult with all execution details

        Raises:
            RepositoryCheckoutError: If repository checkout fails
        """
        task_start_time = time.time()

        # Begin per-task cost attribution (auxiliary; never fatal).
        try:
            self.cost_tracker.start_task(task.task_id)
        except Exception as e:
            logger.warning(f"cost_tracker.start_task failed for {task.task_id}: {e}")

        # Step 1: Generate "before_task" memory snapshot
        logger.debug(f"Generating before_task snapshot for {task.task_id}")
        memory_stats_before = self.memory_store.stats()
        self.snapshot_logger.log_snapshot(
            step=task.sequence_index,
            boundary="before_task",
            active_records=self.memory_store.active_records(),
            current_step=task.sequence_index,
        )

        # Step 2: Set up clean task environment (checkout repository)
        logger.debug(f"Setting up task environment for {task.task_id}")
        task_env = TaskEnvironment(task)

        try:
            # Checkout clean repository (may raise RepositoryCheckoutError)
            task_env.checkout_clean_repo()

            # Step 3: Retrieve relevant memories
            logger.debug(f"Retrieving memories for {task.task_id}")
            retrieved_memories = self._retrieve_memories(task)

            # Step 4: Execute agent
            logger.debug(f"Executing agent for {task.task_id}")
            agent_result = self._execute_agent(task, task_env, retrieved_memories)

            # Persist the agent trajectory (v5 §11.3: actions + observations
            # only, NO chain-of-thought) — one of the 4 mandatory log streams.
            self._log_trajectory(task, seed, agent_result)

            # Persist the generated patch for failure analysis (v5 §18) and
            # patch-quality inspection. Otherwise it is lost — eval runs the
            # harness in a temp dir that is removed afterwards.
            try:
                patches_dir = self.run_dir / "patches"
                patches_dir.mkdir(parents=True, exist_ok=True)
                (patches_dir / f"{task.task_id}.patch").write_text(
                    agent_result.get("patch", "") or "", encoding="utf-8"
                )
            except Exception as e:
                logger.warning(f"failed to persist patch for {task.task_id}: {e}")

            # Record the agent LLM call for cost_summary.json (v5 §1570 Pareto
            # cost axis = total tokens). Reflection/classifier/consolidation/
            # embedding tokens are surfaced separately below (E1) via
            # _track_memory_phase_costs, making total_tokens the COMPLETE cost
            # axis (pareto_cost_complete=True). Never fatal.
            try:
                self.cost_tracker.track_llm_call(
                    call_type="agent",
                    model=self.config.get("agent", {}).get("main_model", "unknown"),
                    prompt_tokens=int(agent_result.get("prompt_tokens", 0) or 0),
                    completion_tokens=int(agent_result.get("completion_tokens", 0) or 0),
                    task_id=task.task_id,
                )
            except Exception as e:
                logger.warning(f"cost_tracker.track_llm_call failed for {task.task_id}: {e}")

            # Step 5: Evaluate patch
            logger.debug(f"Evaluating patch for {task.task_id}")
            eval_result = self._evaluate_patch(task, agent_result["patch"], task_env)

            # Step 6: Reflect and write memory. The usage_sink collects the
            # reflection + classifier LLM token usage for cost telemetry (E1).
            logger.debug(f"Reflecting and writing memory for {task.task_id}")
            memory_usage_sink: list[dict[str, Any]] = []
            memory_record = self._reflect_and_write(
                task=task,
                agent_result=agent_result,
                eval_result=eval_result,
                retrieved_memories=retrieved_memories,
                usage_sink=memory_usage_sink,
            )

            # Step 7: Maintain policy (prune/consolidate). C6: distinguishes
            # consolidation from pruning and emits the correct memory events so
            # consolidation is reconstructable from the mandatory log (v5 §11).
            logger.debug(f"Running policy maintenance for {task.task_id}")
            maintenance = self._run_policy_maintenance(task)
            pruned_memory_ids = maintenance["pruned_memory_ids"]
            consolidated_memory_ids = maintenance["consolidated_memory_ids"]

            # E1: aggregate the memory-phase token cost (reflection + classifier
            # from the sink, CLS consolidation drained from the policy, and all
            # embeddings drained from the store) into cost_summary.json. This is
            # what makes total_tokens a COMPLETE Pareto axis. Never fatal.
            self._track_memory_phase_costs(task.task_id, memory_usage_sink)

            # Step 8: Generate "after_task" memory snapshot (with prune delta)
            logger.debug(f"Generating after_task snapshot for {task.task_id}")
            memory_stats_after = self.memory_store.stats()
            self.snapshot_logger.log_snapshot(
                step=task.sequence_index,
                boundary="after_task",
                active_records=self.memory_store.active_records(),
                archived_this_step=maintenance["archived_delta"],
                current_step=task.sequence_index,
            )

            # Step 9: Build and log task result
            task_wall_time = time.time() - task_start_time
            task_result = self._build_task_result(
                task=task,
                seed=seed,
                agent_result=agent_result,
                eval_result=eval_result,
                retrieved_memories=retrieved_memories,
                memory_stats_before=memory_stats_before,
                memory_stats_after=memory_stats_after,
                task_wall_time=task_wall_time,
                pruned_memory_ids=pruned_memory_ids,
                consolidated_memory_ids=consolidated_memory_ids,
            )

            self.task_logger.log_task_result(task_result)

            # Finalize per-task cost attribution (auxiliary; never fatal).
            try:
                self.cost_tracker.complete_task(task.task_id)
            except Exception as e:
                logger.warning(f"cost_tracker.complete_task failed for {task.task_id}: {e}")

            return task_result

        finally:
            # Always cleanup task environment
            task_env.cleanup()

    def _run_policy_maintenance(self, task: Task) -> dict[str, list[str]]:
        """Run policy maintenance and emit the correct memory events (C6).

        Distinguishes pruning from consolidation: a memory archived because it was
        folded into a summary is a CONSOLIDATION, not a prune, and is logged via
        ``log_consolidate`` with the source->summary ``replacement_id`` rather than
        ``log_archive``. The source->summary link is reconstructed from each newly
        created consolidated record's ``source_memory_ids`` (persisted on the
        record), so no schema migration is needed and consolidation is fully
        reconstructable from ``memory_events.jsonl`` alone.

        Returns a dict with:
            - ``archived_delta``: every memory newly archived this step (prunes +
              consolidation sources) — what left the active set, for the snapshot.
            - ``pruned_memory_ids``: memories removed by pruning only.
            - ``consolidated_memory_ids``: source memories folded into summaries.
        """
        step = task.sequence_index
        archived_before = set(self.memory_store.archived_memory_ids_at_step(step))
        consolidated_before = {
            r.memory_id
            for r in self.memory_store.active_records()
            if r.is_consolidated
        }

        self.policy.maintain(self.memory_store)

        archived_delta = sorted(
            set(self.memory_store.archived_memory_ids_at_step(step)) - archived_before
        )

        # New consolidated summaries created this step → source->summary map.
        new_summaries = [
            r
            for r in self.memory_store.active_records()
            if r.is_consolidated and r.memory_id not in consolidated_before
        ]
        source_to_summary = {
            src_id: summary.memory_id
            for summary in new_summaries
            for src_id in (summary.source_memory_ids or [])
        }

        pruned_memory_ids = [m for m in archived_delta if m not in source_to_summary]
        consolidated_memory_ids = [m for m in archived_delta if m in source_to_summary]

        for pruned_id in pruned_memory_ids:
            self.memory_event_logger.log_archive(
                memory_id=pruned_id,
                step=step,
                task_id=task.task_id,
                repo=task.repo,
                reason=self.policy.name,
            )
        for source_id in consolidated_memory_ids:
            self.memory_event_logger.log_consolidate(
                memory_id=source_id,
                replacement_id=source_to_summary[source_id],
                step=step,
                task_id=task.task_id,
                repo=task.repo,
                metadata={"policy": self.policy.name},
            )

        return {
            "archived_delta": archived_delta,
            "pruned_memory_ids": pruned_memory_ids,
            "consolidated_memory_ids": consolidated_memory_ids,
        }

    def _track_memory_phase_costs(
        self, task_id: str, usage_sink: list[dict[str, Any]] | None
    ) -> None:
        """Aggregate memory-phase token cost into the CostTracker (E1).

        Surfaces every non-agent v5 §1582 cost-axis call type so total_tokens is
        a COMPLETE Pareto cost axis:
          - reflection + classifier LLM calls (from the per-task usage_sink),
          - CLS consolidation LLM calls (drained from the policy, if it
            consolidates),
          - all embedding calls — write, consolidation, retrieval query —
            drained from the store (single _generate_embedding choke point).

        Cost tracking is auxiliary and must never break a run, so the whole body
        is wrapped and only logged on failure.
        """
        try:
            # Reflection + classifier usage routed through the per-task sink.
            for entry in usage_sink or []:
                self.cost_tracker.track_llm_call(
                    call_type=entry.get("call_type", "reflection"),
                    model=entry.get("model", "unknown"),
                    prompt_tokens=int(entry.get("prompt_tokens", 0) or 0),
                    completion_tokens=int(entry.get("completion_tokens", 0) or 0),
                    task_id=task_id,
                )

            # CLS consolidation usage (only the CLS policy emits these).
            drain_consolidation = getattr(
                self.policy, "drain_consolidation_usage", None
            )
            if callable(drain_consolidation):
                for entry in drain_consolidation():
                    self.cost_tracker.track_llm_call(
                        call_type=entry.get("call_type", "consolidation"),
                        model=entry.get("model", "unknown"),
                        prompt_tokens=int(entry.get("prompt_tokens", 0) or 0),
                        completion_tokens=int(entry.get("completion_tokens", 0) or 0),
                        task_id=task_id,
                    )

            # Embedding usage (write + consolidation + retrieval query).
            for entry in self.memory_store.drain_embedding_usage():
                self.cost_tracker.track_embedding_call(
                    model=entry.get("model", "unknown"),
                    tokens=int(entry.get("tokens", 0) or 0),
                    task_id=task_id,
                )
        except Exception as e:
            logger.warning(
                f"cost_tracker memory-phase tracking failed for {task_id}: {e}"
            )

    def _retrieve_memories(self, task: Task) -> list[dict[str, Any]]:
        """Retrieve relevant memories for a task.

        Uses the policy's retrieve method which MUST use shared_retrieve
        for all policies except No Memory (Frozen Invariant #5).

        Args:
            task: Task instance

        Returns:
            List of retrieved memory dictionaries (sorted ascending: best LAST)
        """
        top_k = self.config.get("memory", {}).get("top_k", 5)
        token_budget = self.config.get("memory", {}).get("max_context_tokens", 2000)

        # Retrieve memories using policy (pure cosine, identical across policies)
        retrieved = self.policy.retrieve(
            task=task,
            memory_store=self.memory_store,
            top_k=top_k,
            token_budget=token_budget,
        )

        logger.debug(
            f"Retrieved {len(retrieved)} memories for {task.task_id} "
            f"(top_k={top_k}, budget={token_budget})"
        )

        # Compute retrieval quality metrics if pilot mode enabled
        if self.pilot_mode_enabled and self.log_retrieval_quality:
            all_available = self.memory_store.active_records()
            quality_metrics = compute_retrieval_quality(
                task=task,
                # C7: convert policy (score, record) tuples to the dict shape
                # compute_retrieval_quality expects (it calls .get) — passing the
                # raw tuples crashed every memory-enabled pilot run with
                # AttributeError ('tuple' object has no attribute 'get').
                retrieved_memories=[
                    {
                        "memory_id": rec.memory_id,
                        "repo": rec.repo,
                        "sequence_index": rec.sequence_index,
                        "memory_type": rec.memory_type,
                        "outcome": rec.outcome,
                    }
                    for _, rec in retrieved
                ],
                all_available_memories=[
                    {
                        "memory_id": rec.memory_id,
                        "repo": rec.repo,
                        "sequence_index": rec.sequence_index,
                        "memory_type": rec.memory_type,
                        "outcome": rec.outcome,
                    }
                    for rec in all_available
                ],
                relevance_criteria={
                    "same_repo": True,
                    "same_type": False,
                    "temporal_window": None,
                    "success_only": False,
                },
            )
            self.retrieval_quality_metrics.append(quality_metrics)
            logger.debug(
                f"Retrieval quality for {task.task_id}: "
                f"precision@{quality_metrics.k}={quality_metrics.precision_at_k:.3f}, "
                f"recall@{quality_metrics.k}={quality_metrics.recall_at_k:.3f}, "
                f"MRR={quality_metrics.mrr:.3f}, "
                f"NDCG@{quality_metrics.k}={quality_metrics.ndcg_at_k:.3f}"
            )

        return retrieved

    def _execute_agent(
        self,
        task: Task,
        task_env: TaskEnvironment,
        retrieved_memories: list[tuple[float, Any]],
    ) -> dict[str, Any]:
        """Execute coding agent on a task.

        Args:
            task: Task instance
            task_env: Task environment with clean repository
            retrieved_memories: Retrieved memories (sorted ascending: best LAST)

        Returns:
            Dictionary with agent execution results:
                - patch: Generated patch string
                - patch_generated: Whether patch was generated
                - timeout: Whether agent timed out
                - syntax_error: Whether syntax errors occurred
                - error_message: Error message if any
                - trajectory: List of action-observation pairs
                - tool_calls: Number of tool calls
                - test_runs: Number of test runs
                - files_read: List of files read
                - files_modified: List of files modified
                - commands_run: List of commands executed
                - prompt_tokens: Number of prompt tokens
                - completion_tokens: Number of completion tokens
                - total_tokens: Total tokens
                - estimated_cost_usd: Estimated cost in USD
        """
        # Create agent instance
        agent = CodingAgent(
            memory_store=self.memory_store,
            policy=self.policy,
            config=self.config,
            task_env=task_env,
        )

        # Build task dictionary for agent
        task_dict = {
            "task_id": task.task_id,
            "repo": task.repo,
            "base_commit": task.base_commit,
            "issue_text": task.issue_text,
            "sequence_index": task.sequence_index,
        }

        # Execute agent. C4: pass the single authoritative retrieval so the agent
        # uses exactly the memories the runner retrieved and logged — no second,
        # divergent retrieval (and no duplicated embedding query) inside solve_task.
        result = agent.solve_task(task_dict, retrieved_memories=retrieved_memories)

        return result

    def _evaluate_patch(
        self,
        task: Task,
        patch: str,
        task_env: TaskEnvironment,
    ) -> dict[str, Any]:
        """Evaluate generated patch using eval_v3 harness.

        Args:
            task: Task instance
            patch: Generated patch string
            task_env: Task environment with repository

        Returns:
            Dictionary with evaluation results:
                - resolved: 1 if passed, 0 if failed
                - success: Whether evaluation completed without errors
                - passed: Whether patch passed tests
                - error: Error message if evaluation failed
                - execution_time: Time taken for evaluation
        """
        if not patch:
            # No patch generated
            return {
                "resolved": 0,
                "success": True,
                "passed": False,
                "error": None,
                "execution_time": 0.0,
            }

        # Evaluate patch using eval_v3 harness
        eval_result = self.evaluator.evaluate_patch(
            task=task,
            patch=patch,
            work_dir=str(task_env.working_dir) if task_env.working_dir else None,
        )

        return {
            "resolved": 1 if eval_result.passed else 0,
            "success": eval_result.success,
            "passed": eval_result.passed,
            "error": eval_result.error,
            "execution_time": eval_result.execution_time,
        }

    def _log_trajectory(
        self,
        task: Task,
        seed: int,
        agent_result: dict[str, Any],
    ) -> None:
        """Write the per-task trajectory file (v5 §11.3).

        Records action + action_input + observation_summary only — the agent's
        free-text reasoning is never persisted (no chain-of-thought).
        """
        traj_logger = TrajectoryLogger(
            run_id=self.run_id,
            task_id=task.task_id,
            policy=self.policy.name,
            seed=seed,
            run_dir=self.run_dir,  # unify: trajectories land under the same root as task_results/memory
        )
        for i, step in enumerate(agent_result.get("trajectory", []), start=1):
            traj_logger.log_step(
                step=i,
                action=step.get("action", ""),
                action_input=step.get("action_input", ""),
                observation_summary=step.get("observation_summary", ""),
            )
        traj_logger.save()

    def _retrieved_memory_ids(
        self,
        retrieved_memories: list[tuple[float, Any]],
    ) -> list[str]:
        """Return memory IDs from policy retrieval tuples ``(score, record)``."""
        return [record.memory_id for _, record in retrieved_memories]

    def _retrieved_memory_log_fields(
        self,
        task: Task,
        retrieved_memories: list[tuple[float, Any]],
    ) -> dict[str, list[Any]]:
        """Build task-result log fields from policy retrieval tuples.

        policy.retrieve()/shared_retrieve return ``list[tuple[float, MemoryRecord]]``;
        normalization to id/score/type/age lists happens only here, at the
        logging boundary (the retrieval API stays tuple-shaped).
        """
        return {
            "ids": [record.memory_id for _, record in retrieved_memories],
            "scores": [float(score) for score, _ in retrieved_memories],
            "types": [record.memory_type for _, record in retrieved_memories],
            "ages": [
                max(0, task.sequence_index - record.sequence_index)
                for _, record in retrieved_memories
            ],
        }

    def _reflect_and_write(
        self,
        task: Task,
        agent_result: dict[str, Any],
        eval_result: dict[str, Any],
        retrieved_memories: list[tuple[float, Any]],
        usage_sink: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        """Run reflection step and write memory record.

        Args:
            task: Task instance
            agent_result: Agent execution results
            eval_result: Evaluation results
            retrieved_memories: Retrieved memories used
            usage_sink: Optional list collecting the reflection + classifier LLM
                token usage for cost telemetry (E1).

        Returns:
            Memory record dictionary if successful, None if reflection failed
        """
        # Build trajectory from agent result
        trajectory = {
            "steps": agent_result.get("trajectory", []),
            "files_read": agent_result.get("files_read", []),
            "files_modified": agent_result.get("files_modified", []),
            "commands_run": agent_result.get("commands_run", []),
            "test_output": eval_result.get("error", ""),
        }

        # Build evaluation result for reflection
        reflection_eval_result = {
            "resolved": eval_result["resolved"] == 1,
            "error_message": eval_result.get("error"),
            "test_output": eval_result.get("error"),
        }

        # Extract retrieved memory IDs from policy tuples (score, record)
        retrieved_memory_ids = self._retrieved_memory_ids(retrieved_memories)

        try:
            # Run reflection and write memory
            memory_record = reflect_and_write_memory(
                task=task,
                trajectory=trajectory,
                patch=agent_result.get("patch"),
                evaluation_result=reflection_eval_result,
                memory_store=self.memory_store,
                policy=self.policy,
                retrieved_memory_ids=retrieved_memory_ids,
                sequence_index=task.sequence_index,
                model=self.config.get("reflection", {}).get("model", "gpt-4o-mini"),
                temperature=self.config.get("reflection", {}).get("temperature", 0.0),
                usage_sink=usage_sink,
            )

            if memory_record:
                # Log memory write event
                self.memory_event_logger.log_write(
                    memory_id=memory_record.memory_id,
                    step=task.sequence_index,
                    task_id=task.task_id,
                    repo=task.repo,
                    metadata={
                        "memory_type": memory_record.memory_type,
                        "token_length": memory_record.token_length,
                        "outcome": memory_record.outcome,
                    },
                )

                return {
                    "memory_id": memory_record.memory_id,
                    "memory_type": memory_record.memory_type,
                    "outcome": memory_record.outcome,
                }

            return None

        except ReflectionError as e:
            # Reflection failed - log but continue
            logger.warning(
                f"Reflection failed for {task.task_id}: {e}. "
                f"Continuing without writing memory."
            )
            return None

    def _build_task_result(
        self,
        task: Task,
        seed: int,
        agent_result: dict[str, Any],
        eval_result: dict[str, Any],
        retrieved_memories: list[tuple[float, Any]],
        memory_stats_before: dict[str, Any],
        memory_stats_after: dict[str, Any],
        task_wall_time: float,
        pruned_memory_ids: list[str] | None = None,
        consolidated_memory_ids: list[str] | None = None,
    ) -> TaskResult:
        """Build TaskResult from execution data.

        Args:
            task: Task instance
            seed: Random seed
            agent_result: Agent execution results
            eval_result: Evaluation results
            retrieved_memories: Retrieved memories
            memory_stats_before: Memory stats before task
            memory_stats_after: Memory stats after task
            task_wall_time: Task wall time in seconds

        Returns:
            TaskResult instance ready for logging
        """
        # Extract retrieved memory data from policy tuples (score, record)
        retrieved_fields = self._retrieved_memory_log_fields(task, retrieved_memories)
        retrieved_memory_ids = retrieved_fields["ids"]
        retrieved_memory_scores = retrieved_fields["scores"]
        retrieved_memory_types = retrieved_fields["types"]
        retrieved_memory_ages = retrieved_fields["ages"]

        # Calculate syntax error rate
        syntax_error_rate = (
            1.0 if agent_result.get("syntax_error", False) else 0.0
        )

        return TaskResult(
            # Run identification
            run_id=self.run_id,
            policy=self.policy.name,
            seed=seed,
            repo=task.repo,
            task_id=task.task_id,
            sequence_index=task.sequence_index,
            # Task outcome
            resolved=eval_result["resolved"],
            patch_generated=agent_result.get("patch_generated", False),
            patch_applied=eval_result["resolved"] == 1,
            syntax_error=agent_result.get("syntax_error", False),
            timeout=agent_result.get("timeout", False),
            # Token usage & costs
            prompt_tokens=agent_result.get("prompt_tokens", 0),
            completion_tokens=agent_result.get("completion_tokens", 0),
            total_tokens=agent_result.get("total_tokens", 0),
            estimated_cost_usd=agent_result.get("estimated_cost_usd", 0.0),
            task_api_cost=agent_result.get("estimated_cost_usd", 0.0),
            # Authoritative per-call-type token accounting (incl. consolidation)
            # lives in cost_summary.json (E1, pareto_cost_complete=True). This
            # per-task USD field stays 0.0 under the D3 tokens cost metric.
            consolidation_llm_cost=0.0,
            # Execution metrics
            wall_time_seconds=task_wall_time,
            tool_calls=agent_result.get("tool_calls", 0),
            test_runs=agent_result.get("test_runs", 0),
            files_read=len(agent_result.get("files_read", [])),
            files_modified=len(agent_result.get("files_modified", [])),
            syntax_error_rate=syntax_error_rate,
            # Retrieved memories
            retrieved_memory_ids=retrieved_memory_ids,
            retrieved_memory_scores=retrieved_memory_scores,
            retrieved_memory_types=retrieved_memory_types,
            retrieved_memory_ages=retrieved_memory_ages,
            # Memory state
            memory_count_before=memory_stats_before["active_count"],
            memory_count_after=memory_stats_after["active_count"],
            memory_tokens_before=memory_stats_before["total_tokens"],
            memory_tokens_after=memory_stats_after["total_tokens"],
            # Memory operations (captured around policy.maintain())
            pruned_memory_ids=pruned_memory_ids or [],
            consolidated_memory_ids=consolidated_memory_ids or [],
            # Task metadata
            task_difficulty=task.difficulty_label,
            error_message=agent_result.get("error_message"),
        )

    def _save_retrieval_quality_metrics(self) -> None:
        """Save retrieval quality metrics to file for pilot analysis.

        Saves individual task metrics and aggregated statistics to
        runs/{run_id}/retrieval_quality_metrics.json for calibration analysis.
        """
        import json
        from dataclasses import asdict

        from src.metrics.retrieval_quality import aggregate_retrieval_quality

        # Aggregate metrics
        aggregated = aggregate_retrieval_quality(self.retrieval_quality_metrics)

        # Build output data
        output = {
            "run_id": self.run_id,
            "policy_name": self.policy.name,
            "aggregated_metrics": aggregated,
            "per_task_metrics": [
                asdict(metrics) for metrics in self.retrieval_quality_metrics
            ],
        }

        # Save to file
        output_file = self.run_dir / "retrieval_quality_metrics.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)

        logger.info(
            f"Saved retrieval quality metrics to {output_file}: "
            f"mean_precision@k={aggregated['mean_precision_at_k']:.3f}, "
            f"mean_recall@k={aggregated['mean_recall_at_k']:.3f}, "
            f"mean_MRR={aggregated['mean_mrr']:.3f}, "
            f"mean_NDCG@k={aggregated['mean_ndcg_at_k']:.3f}"
        )
