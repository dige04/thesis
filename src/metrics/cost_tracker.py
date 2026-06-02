"""Cost tracking for all LLM and embedding calls in the memory pruning research system.

This module implements comprehensive cost tracking for:
- Agent LLM calls (GPT-4o-mini or similar)
- Type classifier calls (Structured Outputs)
- CLS consolidation LLM calls
- Embedding calls (text-embedding-3-small)

Costs are tracked at multiple levels:
- Per LLM/embedding call
- Per task
- Per run (sequence)
- Per experiment

Requirements: 27
Design: THESIS_FINAL_v5.md §27 (if exists)
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# OpenAI pricing (as of implementation date)
# Source: https://openai.com/api/pricing/
PRICING = {
    # GPT-4o-mini pricing (per 1M tokens)
    "gpt-4o-mini": {
        "input": 0.150,  # $0.150 per 1M input tokens
        "output": 0.600,  # $0.600 per 1M output tokens
    },
    # GPT-4o pricing (per 1M tokens)
    "gpt-4o": {
        "input": 2.50,  # $2.50 per 1M input tokens
        "output": 10.00,  # $10.00 per 1M output tokens
    },
    # text-embedding-3-small pricing (per 1M tokens)
    "text-embedding-3-small": {
        "input": 0.020,  # $0.020 per 1M tokens
        "output": 0.0,  # No output tokens for embeddings
    },
    # text-embedding-3-large pricing (per 1M tokens)
    "text-embedding-3-large": {
        "input": 0.130,  # $0.130 per 1M tokens
        "output": 0.0,  # No output tokens for embeddings
    },
}


@dataclass
class LLMCallCost:
    """Cost tracking for a single LLM call.

    Attributes:
        call_id: Unique identifier for this call
        call_type: Type of call (agent, classifier, consolidation)
        model: Model name (e.g., "gpt-4o-mini")
        prompt_tokens: Number of input tokens
        completion_tokens: Number of output tokens
        total_tokens: Total tokens (prompt + completion)
        estimated_cost_usd: Estimated cost in USD
        timestamp: When the call was made
        task_id: Associated task ID (if applicable)
        metadata: Additional metadata (e.g., temperature, max_tokens)
    """

    call_id: str
    call_type: str  # agent | classifier | consolidation
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    timestamp: str
    task_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "call_id": self.call_id,
            "call_type": self.call_type,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "timestamp": self.timestamp,
            "task_id": self.task_id,
            "metadata": self.metadata,
        }


@dataclass
class EmbeddingCallCost:
    """Cost tracking for a single embedding call.

    Attributes:
        call_id: Unique identifier for this call
        model: Model name (e.g., "text-embedding-3-small")
        tokens: Number of tokens embedded
        estimated_cost_usd: Estimated cost in USD
        timestamp: When the call was made
        task_id: Associated task ID (if applicable)
        memory_id: Associated memory ID (if applicable)
        metadata: Additional metadata
    """

    call_id: str
    model: str
    tokens: int
    estimated_cost_usd: float
    timestamp: str
    task_id: str | None = None
    memory_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "call_id": self.call_id,
            "model": self.model,
            "tokens": self.tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "timestamp": self.timestamp,
            "task_id": self.task_id,
            "memory_id": self.memory_id,
            "metadata": self.metadata,
        }


@dataclass
class TaskCostSummary:
    """Cost summary for a single task.

    Attributes:
        task_id: Task identifier
        agent_llm_cost: Total cost of agent LLM calls
        classifier_cost: Total cost of type classifier calls
        consolidation_cost: Total cost of consolidation LLM calls
        embedding_cost: Total cost of embedding calls
        total_cost: Total cost for this task
        agent_llm_calls: Number of agent LLM calls
        classifier_calls: Number of classifier calls
        consolidation_calls: Number of consolidation calls
        embedding_calls: Number of embedding calls
        agent_tokens: Total tokens used by agent
        classifier_tokens: Total tokens used by classifier
        consolidation_tokens: Total tokens used by consolidation
        embedding_tokens: Total tokens used by embeddings
    """

    task_id: str
    agent_llm_cost: float = 0.0
    classifier_cost: float = 0.0
    consolidation_cost: float = 0.0
    embedding_cost: float = 0.0
    total_cost: float = 0.0
    agent_llm_calls: int = 0
    classifier_calls: int = 0
    consolidation_calls: int = 0
    embedding_calls: int = 0
    agent_tokens: int = 0
    classifier_tokens: int = 0
    consolidation_tokens: int = 0
    embedding_tokens: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "task_id": self.task_id,
            "agent_llm_cost": self.agent_llm_cost,
            "classifier_cost": self.classifier_cost,
            "consolidation_cost": self.consolidation_cost,
            "embedding_cost": self.embedding_cost,
            "total_cost": self.total_cost,
            "agent_llm_calls": self.agent_llm_calls,
            "classifier_calls": self.classifier_calls,
            "consolidation_calls": self.consolidation_calls,
            "embedding_calls": self.embedding_calls,
            "agent_tokens": self.agent_tokens,
            "classifier_tokens": self.classifier_tokens,
            "consolidation_tokens": self.consolidation_tokens,
            "embedding_tokens": self.embedding_tokens,
        }


@dataclass
class RunCostSummary:
    """Cost summary for an entire run (sequence).

    Attributes:
        run_id: Run identifier
        policy: Policy name
        sequence_name: Sequence name
        seed: Random seed
        total_cost: Total cost for this run
        agent_llm_cost: Total cost of agent LLM calls
        classifier_cost: Total cost of type classifier calls
        consolidation_cost: Total cost of consolidation LLM calls
        embedding_cost: Total cost of embedding calls
        total_llm_calls: Total number of LLM calls
        total_embedding_calls: Total number of embedding calls
        total_tokens: Total tokens used
        tasks_completed: Number of tasks completed
        start_time: Run start timestamp
        end_time: Run end timestamp
        task_costs: Per-task cost summaries
    """

    run_id: str
    policy: str
    sequence_name: str
    seed: int
    total_cost: float = 0.0
    agent_llm_cost: float = 0.0
    classifier_cost: float = 0.0
    consolidation_cost: float = 0.0
    embedding_cost: float = 0.0
    total_llm_calls: int = 0
    total_embedding_calls: int = 0
    total_tokens: int = 0
    tasks_completed: int = 0
    start_time: str | None = None
    end_time: str | None = None
    task_costs: list[TaskCostSummary] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_id": self.run_id,
            "policy": self.policy,
            "sequence_name": self.sequence_name,
            "seed": self.seed,
            "total_cost": self.total_cost,
            "agent_llm_cost": self.agent_llm_cost,
            "classifier_cost": self.classifier_cost,
            "consolidation_cost": self.consolidation_cost,
            "embedding_cost": self.embedding_cost,
            "total_llm_calls": self.total_llm_calls,
            "total_embedding_calls": self.total_embedding_calls,
            "total_tokens": self.total_tokens,
            "tasks_completed": self.tasks_completed,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "task_costs": [tc.to_dict() for tc in self.task_costs],
        }


class CostTracker:
    """Comprehensive cost tracker for LLM and embedding calls.

    This class tracks costs at multiple levels:
    - Individual LLM/embedding calls
    - Per-task aggregation
    - Per-run aggregation
    - Cross-run daily reports

    Usage:
        >>> tracker = CostTracker(run_id="run_001", run_dir="runs/run_001")
        >>> tracker.start_run(policy="type_aware_decay", sequence_name="django", seed=1)
        >>>
        >>> # Track agent LLM call
        >>> tracker.track_llm_call(
        ...     call_type="agent",
        ...     model="gpt-4o-mini",
        ...     prompt_tokens=1000,
        ...     completion_tokens=500,
        ...     task_id="django__django-12345"
        ... )
        >>>
        >>> # Track embedding call
        >>> tracker.track_embedding_call(
        ...     model="text-embedding-3-small",
        ...     tokens=500,
        ...     task_id="django__django-12345",
        ...     memory_id="mem-001"
        ... )
        >>>
        >>> # Complete task
        >>> tracker.complete_task("django__django-12345")
        >>>
        >>> # Complete run
        >>> tracker.complete_run()
        >>> tracker.write_cost_summary()

    Requirements: 27
    """

    def __init__(self, run_id: str, run_dir: str | Path, cost_metric_mode: str = "usd"):
        """Initialize cost tracker for a run.

        Args:
            run_id: Unique identifier for this run
            run_dir: Directory for this run (e.g., runs/{run_id})
            cost_metric_mode: One of "usd" | "tokens" | "walltime". Under a
                non-USD mode (e.g. Ollama flat-rate, deviation D3) tokens are the
                authoritative cost proxy and unknown model names do NOT raise
                (per-token USD is meaningless); cost is recorded as 0.0.
        """
        self.run_id = run_id
        self.run_dir = Path(run_dir)
        self.cost_metric_mode = cost_metric_mode

        # Ensure run directory exists
        self.run_dir.mkdir(parents=True, exist_ok=True)

        # Initialize tracking state
        self.llm_calls: list[LLMCallCost] = []
        self.embedding_calls: list[EmbeddingCallCost] = []
        self.task_costs: dict[str, TaskCostSummary] = {}
        self.current_task_id: str | None = None

        # Run-level summary
        self.run_summary: RunCostSummary | None = None

        # Call counters for unique IDs
        self._llm_call_counter = 0
        self._embedding_call_counter = 0

        logger.info(f"Initialized CostTracker for run_id={run_id}")

    def start_run(self, policy: str, sequence_name: str, seed: int) -> None:
        """Start tracking a new run.

        Args:
            policy: Policy name
            sequence_name: Sequence name
            seed: Random seed
        """
        self.run_summary = RunCostSummary(
            run_id=self.run_id,
            policy=policy,
            sequence_name=sequence_name,
            seed=seed,
            start_time=datetime.utcnow().isoformat(),
        )

        logger.info(
            f"Started cost tracking for run: policy={policy}, "
            f"sequence={sequence_name}, seed={seed}"
        )

    def track_llm_call(
        self,
        call_type: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        task_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LLMCallCost:
        """Track a single LLM call and compute cost.

        Args:
            call_type: Type of call (agent, classifier, consolidation)
            model: Model name (e.g., "gpt-4o-mini")
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
            task_id: Associated task ID (if applicable)
            metadata: Additional metadata

        Returns:
            LLMCallCost instance with computed cost

        Raises:
            ValueError: If model pricing is not available
        """
        # Validate call type
        if call_type not in ("agent", "classifier", "consolidation"):
            logger.warning(
                f"Unknown call_type '{call_type}', should be one of: "
                f"agent, classifier, consolidation"
            )

        # Get pricing for model. Under a non-USD cost metric (e.g. Ollama
        # flat-rate, deviation D3) tokens are authoritative and per-token USD is
        # meaningless, so unknown models do NOT raise — cost is recorded as 0.
        if model in PRICING:
            pricing = PRICING[model]
        elif self.cost_metric_mode != "usd":
            pricing = {"input": 0.0, "output": 0.0}
        else:
            raise ValueError(
                f"No pricing available for model '{model}'. "
                f"Available models: {sorted(PRICING.keys())}"
            )

        # Compute cost
        input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (completion_tokens / 1_000_000) * pricing["output"]
        total_cost = input_cost + output_cost

        # Create cost record
        self._llm_call_counter += 1
        call_id = f"llm_{self.run_id}_{self._llm_call_counter:06d}"

        cost_record = LLMCallCost(
            call_id=call_id,
            call_type=call_type,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            estimated_cost_usd=total_cost,
            timestamp=datetime.utcnow().isoformat(),
            task_id=task_id or self.current_task_id,
            metadata=metadata or {},
        )

        # Store call
        self.llm_calls.append(cost_record)

        # Update task-level tracking
        if cost_record.task_id:
            self._update_task_cost(cost_record.task_id, llm_call=cost_record)

        # Update run-level tracking
        if self.run_summary:
            self.run_summary.total_llm_calls += 1
            self.run_summary.total_tokens += cost_record.total_tokens

            if call_type == "agent":
                self.run_summary.agent_llm_cost += total_cost
            elif call_type == "classifier":
                self.run_summary.classifier_cost += total_cost
            elif call_type == "consolidation":
                self.run_summary.consolidation_cost += total_cost

            self.run_summary.total_cost += total_cost

        logger.debug(
            f"Tracked LLM call: type={call_type}, model={model}, "
            f"tokens={cost_record.total_tokens}, cost=${total_cost:.6f}"
        )

        return cost_record

    def track_embedding_call(
        self,
        model: str,
        tokens: int,
        task_id: str | None = None,
        memory_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EmbeddingCallCost:
        """Track a single embedding call and compute cost.

        Args:
            model: Model name (e.g., "text-embedding-3-small")
            tokens: Number of tokens embedded
            task_id: Associated task ID (if applicable)
            memory_id: Associated memory ID (if applicable)
            metadata: Additional metadata

        Returns:
            EmbeddingCallCost instance with computed cost

        Raises:
            ValueError: If model pricing is not available
        """
        # Get pricing for model. Under a non-USD cost metric (e.g. Ollama
        # flat-rate, deviation D3) tokens are authoritative and per-token USD is
        # meaningless, so unknown models do NOT raise — cost is recorded as 0.
        if model in PRICING:
            pricing = PRICING[model]
        elif self.cost_metric_mode != "usd":
            pricing = {"input": 0.0, "output": 0.0}
        else:
            raise ValueError(
                f"No pricing available for model '{model}'. "
                f"Available models: {sorted(PRICING.keys())}"
            )

        # Compute cost (embeddings only have input tokens)
        total_cost = (tokens / 1_000_000) * pricing["input"]

        # Create cost record
        self._embedding_call_counter += 1
        call_id = f"emb_{self.run_id}_{self._embedding_call_counter:06d}"

        cost_record = EmbeddingCallCost(
            call_id=call_id,
            model=model,
            tokens=tokens,
            estimated_cost_usd=total_cost,
            timestamp=datetime.utcnow().isoformat(),
            task_id=task_id or self.current_task_id,
            memory_id=memory_id,
            metadata=metadata or {},
        )

        # Store call
        self.embedding_calls.append(cost_record)

        # Update task-level tracking
        if cost_record.task_id:
            self._update_task_cost(cost_record.task_id, embedding_call=cost_record)

        # Update run-level tracking
        if self.run_summary:
            self.run_summary.total_embedding_calls += 1
            self.run_summary.total_tokens += tokens
            self.run_summary.embedding_cost += total_cost
            self.run_summary.total_cost += total_cost

        logger.debug(
            f"Tracked embedding call: model={model}, "
            f"tokens={tokens}, cost=${total_cost:.6f}"
        )

        return cost_record

    def _update_task_cost(
        self,
        task_id: str,
        llm_call: LLMCallCost | None = None,
        embedding_call: EmbeddingCallCost | None = None,
    ) -> None:
        """Update task-level cost tracking.

        Args:
            task_id: Task identifier
            llm_call: LLM call to add (if any)
            embedding_call: Embedding call to add (if any)
        """
        # Initialize task cost summary if needed
        if task_id not in self.task_costs:
            self.task_costs[task_id] = TaskCostSummary(task_id=task_id)

        task_cost = self.task_costs[task_id]

        # Update from LLM call
        if llm_call:
            if llm_call.call_type == "agent":
                task_cost.agent_llm_cost += llm_call.estimated_cost_usd
                task_cost.agent_llm_calls += 1
                task_cost.agent_tokens += llm_call.total_tokens
            elif llm_call.call_type == "classifier":
                task_cost.classifier_cost += llm_call.estimated_cost_usd
                task_cost.classifier_calls += 1
                task_cost.classifier_tokens += llm_call.total_tokens
            elif llm_call.call_type == "consolidation":
                task_cost.consolidation_cost += llm_call.estimated_cost_usd
                task_cost.consolidation_calls += 1
                task_cost.consolidation_tokens += llm_call.total_tokens

            task_cost.total_cost += llm_call.estimated_cost_usd

        # Update from embedding call
        if embedding_call:
            task_cost.embedding_cost += embedding_call.estimated_cost_usd
            task_cost.embedding_calls += 1
            task_cost.embedding_tokens += embedding_call.tokens
            task_cost.total_cost += embedding_call.estimated_cost_usd

    def start_task(self, task_id: str) -> None:
        """Start tracking a new task.

        Args:
            task_id: Task identifier
        """
        self.current_task_id = task_id
        logger.debug(f"Started cost tracking for task: {task_id}")

    def complete_task(self, task_id: str) -> TaskCostSummary:
        """Complete task and return cost summary.

        Args:
            task_id: Task identifier

        Returns:
            TaskCostSummary for this task
        """
        if task_id not in self.task_costs:
            # Task had no costs (e.g., No Memory policy)
            self.task_costs[task_id] = TaskCostSummary(task_id=task_id)

        task_cost = self.task_costs[task_id]

        # Add to run summary
        if self.run_summary:
            self.run_summary.task_costs.append(task_cost)
            self.run_summary.tasks_completed += 1

        # Clear current task
        if self.current_task_id == task_id:
            self.current_task_id = None

        logger.info(
            f"Completed task {task_id}: total_cost=${task_cost.total_cost:.4f}"
        )

        return task_cost

    def complete_run(self) -> RunCostSummary:
        """Complete run and finalize cost summary.

        Returns:
            RunCostSummary for this run
        """
        if not self.run_summary:
            raise RuntimeError("Run not started. Call start_run() first.")

        self.run_summary.end_time = datetime.utcnow().isoformat()

        logger.info(
            f"Completed run {self.run_id}: "
            f"total_cost=${self.run_summary.total_cost:.2f}, "
            f"tasks={self.run_summary.tasks_completed}"
        )

        return self.run_summary

    def write_cost_summary(self) -> Path:
        """Write cost summary to cost_summary.json.

        Returns:
            Path to written cost summary file

        Requirements: 27 (Acceptance Criterion 3)
        """
        if not self.run_summary:
            raise RuntimeError("Run not started. Call start_run() first.")

        summary_file = self.run_dir / "cost_summary.json"

        with open(summary_file, "w") as f:
            json.dump(self.run_summary.to_dict(), f, indent=2)

        logger.info(f"Wrote cost summary to {summary_file}")

        return summary_file

    def get_task_cost(self, task_id: str) -> TaskCostSummary | None:
        """Get cost summary for a specific task.

        Args:
            task_id: Task identifier

        Returns:
            TaskCostSummary if task exists, None otherwise
        """
        return self.task_costs.get(task_id)

    def get_run_cost(self) -> RunCostSummary | None:
        """Get cost summary for the current run.

        Returns:
            RunCostSummary if run started, None otherwise
        """
        return self.run_summary


def generate_daily_cost_report(runs_dir: str | Path = "runs") -> dict[str, Any]:
    """Generate daily cost report across all active runs.

    This function aggregates costs from all cost_summary.json files
    in the runs directory to provide a daily spending overview.

    Args:
        runs_dir: Directory containing run subdirectories

    Returns:
        Dictionary containing:
            - total_cost: Total cost across all runs
            - total_runs: Number of runs processed
            - cost_by_policy: Cost breakdown by policy
            - cost_by_date: Cost breakdown by date
            - runs: List of individual run summaries

    Requirements: 27 (Acceptance Criterion 4)
    """
    runs_path = Path(runs_dir)

    if not runs_path.exists():
        logger.warning(f"Runs directory not found: {runs_path}")
        return {
            "total_cost": 0.0,
            "total_runs": 0,
            "cost_by_policy": {},
            "cost_by_date": {},
            "runs": [],
            "generated_at": datetime.utcnow().isoformat(),
        }

    # Collect all cost summaries
    run_summaries = []
    total_cost = 0.0
    cost_by_policy: dict[str, float] = {}
    cost_by_date: dict[str, float] = {}

    for run_dir in runs_path.iterdir():
        if not run_dir.is_dir():
            continue

        cost_summary_file = run_dir / "cost_summary.json"
        if not cost_summary_file.exists():
            continue

        try:
            with open(cost_summary_file) as f:
                summary = json.load(f)

            run_summaries.append(summary)

            # Aggregate costs
            run_cost = summary.get("total_cost", 0.0)
            total_cost += run_cost

            # By policy
            policy = summary.get("policy", "unknown")
            cost_by_policy[policy] = cost_by_policy.get(policy, 0.0) + run_cost

            # By date (extract date from start_time)
            start_time = summary.get("start_time")
            if start_time:
                date = start_time.split("T")[0]  # Extract YYYY-MM-DD
                cost_by_date[date] = cost_by_date.get(date, 0.0) + run_cost

        except Exception as e:
            logger.error(f"Failed to load cost summary from {cost_summary_file}: {e}")
            continue

    # Build report
    report = {
        "total_cost": total_cost,
        "total_runs": len(run_summaries),
        "cost_by_policy": cost_by_policy,
        "cost_by_date": cost_by_date,
        "runs": run_summaries,
        "generated_at": datetime.utcnow().isoformat(),
    }

    # Write report to runs directory
    report_file = runs_path / "daily_cost_report.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)

    logger.info(
        f"Generated daily cost report: total_cost=${total_cost:.2f}, "
        f"runs={len(run_summaries)}"
    )

    return report


def check_budget_alert(
    runs_dir: str | Path = "runs",
    daily_budget: float = 100.0,
    total_budget: float = 1000.0,
) -> dict[str, Any]:
    """Check if costs exceed budget thresholds and generate alerts.

    Args:
        runs_dir: Directory containing run subdirectories
        daily_budget: Daily spending limit in USD
        total_budget: Total experiment budget in USD

    Returns:
        Dictionary containing:
            - daily_cost: Cost for today
            - total_cost: Total cost across all runs
            - daily_budget: Daily budget limit
            - total_budget: Total budget limit
            - daily_alert: Whether daily budget exceeded
            - total_alert: Whether total budget exceeded
            - daily_remaining: Remaining daily budget
            - total_remaining: Remaining total budget
    """
    report = generate_daily_cost_report(runs_dir)

    # Get today's date
    today = datetime.utcnow().strftime("%Y-%m-%d")

    # Get today's cost
    daily_cost = report["cost_by_date"].get(today, 0.0)
    total_cost = report["total_cost"]

    # Check alerts
    daily_alert = daily_cost > daily_budget
    total_alert = total_cost > total_budget

    # Calculate remaining
    daily_remaining = max(0.0, daily_budget - daily_cost)
    total_remaining = max(0.0, total_budget - total_cost)

    alert_info = {
        "daily_cost": daily_cost,
        "total_cost": total_cost,
        "daily_budget": daily_budget,
        "total_budget": total_budget,
        "daily_alert": daily_alert,
        "total_alert": total_alert,
        "daily_remaining": daily_remaining,
        "total_remaining": total_remaining,
        "checked_at": datetime.utcnow().isoformat(),
    }

    # Log alerts
    if daily_alert:
        logger.warning(
            f"DAILY BUDGET ALERT: Spent ${daily_cost:.2f} today, "
            f"budget is ${daily_budget:.2f}"
        )

    if total_alert:
        logger.warning(
            f"TOTAL BUDGET ALERT: Spent ${total_cost:.2f} total, "
            f"budget is ${total_budget:.2f}"
        )

    return alert_info
