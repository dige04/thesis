"""Experiment matrix execution orchestrator.

This module implements the ExperimentRunner that executes all 8 sequences
for each of 6 policies with 3 independent runs per combination, totaling
144 controlled runs.

**Validates: Requirements 16**

Key responsibilities:
- Load all 8 sequences from SWE-Bench-CL
- Initialize all 6 policies (No Memory, Full Memory, Random Prune, Recency Prune,
  Type-Aware Decay, CLS Consolidation)
- Generate run matrix: 8 sequences × 6 policies × 3 seeds = 144 runs
- Execute each run with SequenceRunner
- Track progress and aggregate results
- Support resuming from failures
- Generate experiment summary report

Frozen Invariants (THESIS_FINAL_v5.md §0.1):
- All 8 official SWE-Bench-CL sequences (Invariant #1)
- 3 seeds for ALL 6 conditions (Invariant #2)
- Seeds initialize RNGs for Random Prune and stochastic components

Requirements: 16
Design: THESIS_FINAL_v5.md §12, §16
"""

import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.benchmark.models import Sequence
from src.benchmark.sequence_runner import SequenceResult, SequenceRunner
from src.benchmark.swebenchcl_loader import SWEBenchCLLoader
from src.memory.policies.base import MemoryPolicy
from src.memory.policies.cls_consolidation import CLSConsolidationPolicy
from src.memory.policies.full_memory import FullMemoryPolicy
from src.memory.policies.no_memory import NoMemoryPolicy
from src.memory.policies.random_prune import RandomPrunePolicy
from src.memory.policies.recency_prune import RecencyPrunePolicy
from src.memory.policies.type_aware_decay import TypeAwareDecayPolicy

logger = logging.getLogger(__name__)


@dataclass
class RunConfig:
    """Configuration for a single run.

    Attributes:
        run_id: Unique identifier for this run
        sequence_name: Name of the sequence (e.g., "django")
        policy_name: Name of the memory policy
        seed: Random seed for reproducibility
        sequence_index: Index of sequence in experiment (0-7)
        policy_index: Index of policy in experiment (0-5)
        seed_index: Index of seed in experiment (0-2)
    """

    run_id: str
    sequence_name: str
    policy_name: str
    seed: int
    sequence_index: int
    policy_index: int
    seed_index: int


@dataclass
class ExperimentSummary:
    """Summary of experiment execution.

    Attributes:
        total_runs: Total number of runs in experiment (144)
        completed_runs: Number of runs completed successfully
        failed_runs: Number of runs that failed
        total_sequences: Total number of sequences (8)
        total_policies: Total number of policies (6)
        total_seeds: Total number of seeds per policy-sequence pair (3)
        total_wall_time: Total wall time for experiment in seconds
        total_cost_usd: Total estimated cost in USD
        start_time: Experiment start timestamp
        end_time: Experiment end timestamp
        failed_run_ids: List of run_ids that failed
    """

    total_runs: int
    completed_runs: int
    failed_runs: int
    total_sequences: int
    total_policies: int
    total_seeds: int
    total_wall_time: float
    total_cost_usd: float
    start_time: str
    end_time: str
    failed_run_ids: list[str]


class ExperimentRunner:
    """Orchestrator for executing the full experiment matrix.

    This class is the main entry point for running all 144 runs
    (8 sequences × 6 policies × 3 seeds). It coordinates:
    - Loading all 8 SWE-Bench-CL sequences
    - Initializing all 6 memory policies
    - Generating the run matrix
    - Executing each run with SequenceRunner
    - Tracking progress and costs
    - Handling failures gracefully
    - Generating experiment summary

    Attributes:
        config: Configuration dictionary with all parameters
        curriculum_path: Path to SWE-Bench-CL-Curriculum.json
        loader: SWE-Bench-CL dataset loader
        sequences: List of 8 loaded sequences
        seeds: List of 3 seeds for reproducibility
        results_dir: Directory for experiment results
    """

    def __init__(
        self,
        config: dict[str, Any],
        curriculum_path: str | Path,
    ):
        """Initialize experiment runner.

        Args:
            config: Configuration dictionary with all parameters
            curriculum_path: Path to SWE-Bench-CL-Curriculum.json file

        Raises:
            ValueError: If config is missing required parameters
            FileNotFoundError: If curriculum file does not exist
        """
        self.config = config
        self.curriculum_path = Path(curriculum_path)

        # Initialize loader and load all 8 sequences
        self.loader = SWEBenchCLLoader(curriculum_path=self.curriculum_path)
        self.sequences = self.loader.load_all_sequences()

        # Validate we have exactly 8 sequences (Frozen Invariant #1)
        if len(self.sequences) != 8:
            raise ValueError(
                f"Expected exactly 8 sequences, got {len(self.sequences)}. "
                f"This violates Frozen Invariant #1."
            )

        # Get seeds from config (Frozen Invariant #2: 3 seeds for ALL 6 conditions)
        self.seeds = config.get("experiment", {}).get("seeds", [1, 2, 3])
        if len(self.seeds) != 3:
            raise ValueError(
                f"Expected exactly 3 seeds, got {len(self.seeds)}. "
                f"This violates Frozen Invariant #2."
            )

        # Setup results directory
        self.results_dir = Path("results") / "raw"
        self.results_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"Initialized ExperimentRunner: "
            f"{len(self.sequences)} sequences, "
            f"{len(self.seeds)} seeds, "
            f"total runs = {len(self.sequences) * 6 * len(self.seeds)}"
        )

    def _initialize_policy(
        self,
        policy_name: str,
        seed: int | None = None
    ) -> MemoryPolicy:
        """Initialize a memory policy instance.

        Args:
            policy_name: Name of the policy to initialize
            seed: Random seed (required for Random Prune, ignored for others)

        Returns:
            Initialized MemoryPolicy instance

        Raises:
            ValueError: If policy_name is unknown
        """
        max_records = self.config.get("memory", {}).get("max_records", 100)

        if policy_name == "no_memory":
            return NoMemoryPolicy()

        elif policy_name == "full_memory":
            return FullMemoryPolicy()

        elif policy_name == "random_prune":
            if seed is None:
                raise ValueError("Random Prune requires a seed")
            return RandomPrunePolicy(seed=seed, max_records=max_records)

        elif policy_name == "recency_prune":
            return RecencyPrunePolicy(max_records=max_records)

        elif policy_name == "type_aware_decay":
            return TypeAwareDecayPolicy(max_records=max_records)

        elif policy_name == "cls_consolidation":
            return CLSConsolidationPolicy(max_records=max_records)

        else:
            raise ValueError(f"Unknown policy: {policy_name}")

    def _generate_run_matrix(
        self,
        policy_filter: str | None = None,
        sequence_filter: str | None = None,
    ) -> list[RunConfig]:
        """Generate the full run matrix.

        Creates 144 run configurations (8 sequences × 6 policies × 3 seeds).
        Optionally filters by policy or sequence for pilot mode.

        Args:
            policy_filter: If provided, only include this policy
            sequence_filter: If provided, only include this sequence

        Returns:
            List of RunConfig objects, one per run

        Notes:
            - Each run has a unique run_id (UUID)
            - Seeds are used for all policies (not just Random Prune)
            - Run order is deterministic: sequences outer loop, policies middle, seeds inner
        """
        run_configs = []

        # Define all 6 policies (Frozen Invariant #2)
        policy_names = [
            "no_memory",
            "full_memory",
            "random_prune",
            "recency_prune",
            "type_aware_decay",
            "cls_consolidation",
        ]

        # Filter policies if requested
        if policy_filter:
            if policy_filter not in policy_names:
                raise ValueError(f"Unknown policy filter: {policy_filter}")
            policy_names = [policy_filter]

        # Filter sequences if requested
        sequences = self.sequences
        if sequence_filter:
            sequences = [s for s in sequences if s.sequence_name == sequence_filter]
            if not sequences:
                raise ValueError(f"Unknown sequence filter: {sequence_filter}")

        # Generate run matrix
        for seq_idx, sequence in enumerate(sequences):
            for policy_idx, policy_name in enumerate(policy_names):
                for seed_idx, seed in enumerate(self.seeds):
                    # Generate unique run_id
                    run_id = f"{sequence.sequence_name}_{policy_name}_seed{seed}_{uuid.uuid4().hex[:8]}"

                    run_config = RunConfig(
                        run_id=run_id,
                        sequence_name=sequence.sequence_name,
                        policy_name=policy_name,
                        seed=seed,
                        sequence_index=seq_idx,
                        policy_index=policy_idx,
                        seed_index=seed_idx,
                    )

                    run_configs.append(run_config)

        logger.info(
            f"Generated run matrix: {len(run_configs)} runs "
            f"({len(sequences)} sequences × {len(policy_names)} policies × {len(self.seeds)} seeds)"
        )

        return run_configs

    def _execute_run(
        self,
        run_config: RunConfig,
        sequence: Sequence,
    ) -> SequenceResult:
        """Execute a single run.

        Args:
            run_config: Configuration for this run
            sequence: Sequence to execute

        Returns:
            SequenceResult with execution details

        Raises:
            Exception: If run fails (caller handles gracefully)
        """
        logger.info(
            f"Starting run {run_config.run_id}: "
            f"sequence={run_config.sequence_name}, "
            f"policy={run_config.policy_name}, "
            f"seed={run_config.seed}"
        )

        # Initialize policy
        policy = self._initialize_policy(
            policy_name=run_config.policy_name,
            seed=run_config.seed,
        )

        # Initialize sequence runner
        runner = SequenceRunner(
            run_id=run_config.run_id,
            policy=policy,
            config=self.config,
        )

        # Execute sequence
        result = runner.run_sequence(
            sequence=sequence,
            seed=run_config.seed,
        )

        logger.info(
            f"Completed run {run_config.run_id}: "
            f"resolved={result.resolved_tasks}/{result.total_tasks}, "
            f"cost=${result.total_cost_usd:.2f}"
        )

        return result

    def _save_run_result(
        self,
        run_config: RunConfig,
        result: SequenceResult,
    ) -> None:
        """Save run result to results directory.

        Args:
            run_config: Configuration for this run
            result: SequenceResult to save
        """
        result_file = self.results_dir / f"{run_config.run_id}_result.json"

        result_data = {
            "run_config": asdict(run_config),
            "result": asdict(result),
        }

        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(result_data, f, indent=2)

        logger.debug(f"Saved run result to {result_file}")

    def _save_experiment_summary(
        self,
        summary: ExperimentSummary,
    ) -> None:
        """Save experiment summary to results directory.

        Args:
            summary: ExperimentSummary to save
        """
        summary_file = self.results_dir / "experiment_summary.json"

        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(asdict(summary), f, indent=2)

        logger.info(f"Saved experiment summary to {summary_file}")

    def run_full_experiment(self) -> ExperimentSummary:
        """Execute the full experiment matrix (144 runs).

        This is the main entry point for running all 144 runs:
        8 sequences × 6 policies × 3 seeds.

        Returns:
            ExperimentSummary with aggregate statistics

        Notes:
            - Runs are executed sequentially (no parallelization within this method)
            - Failures are logged but do not stop the experiment
            - Progress is logged after each run
            - Results are saved incrementally (one file per run)
            - Final summary is saved at the end
        """
        logger.info("Starting full experiment: 144 runs (8 sequences × 6 policies × 3 seeds)")

        start_time = time.time()
        start_timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        # Generate full run matrix
        run_configs = self._generate_run_matrix()

        # Track results
        completed_runs = 0
        failed_runs = 0
        failed_run_ids = []
        total_cost_usd = 0.0

        # Execute each run
        for idx, run_config in enumerate(run_configs, start=1):
            logger.info(f"Run {idx}/{len(run_configs)}: {run_config.run_id}")

            try:
                # Get sequence
                sequence = next(
                    s for s in self.sequences
                    if s.sequence_name == run_config.sequence_name
                )

                # Execute run
                result = self._execute_run(run_config, sequence)

                # Save result
                self._save_run_result(run_config, result)

                # Update counters
                completed_runs += 1
                total_cost_usd += result.total_cost_usd

                # Log progress
                logger.info(
                    f"Progress: {completed_runs}/{len(run_configs)} completed, "
                    f"{failed_runs} failed, "
                    f"total cost=${total_cost_usd:.2f}"
                )

            except Exception as e:
                # Log failure but continue
                failed_runs += 1
                failed_run_ids.append(run_config.run_id)

                logger.error(
                    f"Run {run_config.run_id} failed: {e}",
                    exc_info=True
                )

                # Log progress
                logger.info(
                    f"Progress: {completed_runs}/{len(run_configs)} completed, "
                    f"{failed_runs} failed"
                )

        # Calculate total wall time
        end_time = time.time()
        end_timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        total_wall_time = end_time - start_time

        # Build experiment summary
        summary = ExperimentSummary(
            total_runs=len(run_configs),
            completed_runs=completed_runs,
            failed_runs=failed_runs,
            total_sequences=len(self.sequences),
            total_policies=6,
            total_seeds=len(self.seeds),
            total_wall_time=total_wall_time,
            total_cost_usd=total_cost_usd,
            start_time=start_timestamp,
            end_time=end_timestamp,
            failed_run_ids=failed_run_ids,
        )

        # Save summary
        self._save_experiment_summary(summary)

        logger.info(
            f"Experiment complete: "
            f"{completed_runs}/{len(run_configs)} runs completed, "
            f"{failed_runs} failed, "
            f"time={total_wall_time:.1f}s, "
            f"cost=${total_cost_usd:.2f}"
        )

        return summary

    def run_pilot_experiment(
        self,
        num_sequences: int = 2,
    ) -> ExperimentSummary:
        """Execute pilot experiment (2 sequences × 6 policies × 1 seed = 12 runs).

        This is used for calibration during Spike Week and Week 4.

        Args:
            num_sequences: Number of sequences to include (default 2)

        Returns:
            ExperimentSummary with aggregate statistics

        Notes:
            - Uses only the first seed (seed=1)
            - Uses first num_sequences sequences
            - Otherwise identical to full experiment
        """
        logger.info(
            f"Starting pilot experiment: "
            f"{num_sequences} sequences × 6 policies × 1 seed = {num_sequences * 6} runs"
        )

        start_time = time.time()
        start_timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        # Generate pilot run matrix (first num_sequences, all policies, first seed only)
        pilot_sequences = self.sequences[:num_sequences]
        pilot_seed = self.seeds[0]

        policy_names = [
            "no_memory",
            "full_memory",
            "random_prune",
            "recency_prune",
            "type_aware_decay",
            "cls_consolidation",
        ]

        run_configs = []
        for seq_idx, sequence in enumerate(pilot_sequences):
            for policy_idx, policy_name in enumerate(policy_names):
                run_id = f"{sequence.sequence_name}_{policy_name}_seed{pilot_seed}_pilot_{uuid.uuid4().hex[:8]}"

                run_config = RunConfig(
                    run_id=run_id,
                    sequence_name=sequence.sequence_name,
                    policy_name=policy_name,
                    seed=pilot_seed,
                    sequence_index=seq_idx,
                    policy_index=policy_idx,
                    seed_index=0,
                )

                run_configs.append(run_config)

        logger.info(f"Generated pilot run matrix: {len(run_configs)} runs")

        # Track results
        completed_runs = 0
        failed_runs = 0
        failed_run_ids = []
        total_cost_usd = 0.0

        # Execute each run
        for idx, run_config in enumerate(run_configs, start=1):
            logger.info(f"Pilot run {idx}/{len(run_configs)}: {run_config.run_id}")

            try:
                # Get sequence
                sequence = next(
                    s for s in pilot_sequences
                    if s.sequence_name == run_config.sequence_name
                )

                # Execute run
                result = self._execute_run(run_config, sequence)

                # Save result
                self._save_run_result(run_config, result)

                # Update counters
                completed_runs += 1
                total_cost_usd += result.total_cost_usd

                # Log progress
                logger.info(
                    f"Pilot progress: {completed_runs}/{len(run_configs)} completed, "
                    f"{failed_runs} failed, "
                    f"total cost=${total_cost_usd:.2f}"
                )

            except Exception as e:
                # Log failure but continue
                failed_runs += 1
                failed_run_ids.append(run_config.run_id)

                logger.error(
                    f"Pilot run {run_config.run_id} failed: {e}",
                    exc_info=True
                )

                # Log progress
                logger.info(
                    f"Pilot progress: {completed_runs}/{len(run_configs)} completed, "
                    f"{failed_runs} failed"
                )

        # Calculate total wall time
        end_time = time.time()
        end_timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        total_wall_time = end_time - start_time

        # Build experiment summary
        summary = ExperimentSummary(
            total_runs=len(run_configs),
            completed_runs=completed_runs,
            failed_runs=failed_runs,
            total_sequences=num_sequences,
            total_policies=6,
            total_seeds=1,
            total_wall_time=total_wall_time,
            total_cost_usd=total_cost_usd,
            start_time=start_timestamp,
            end_time=end_timestamp,
            failed_run_ids=failed_run_ids,
        )

        # Save summary
        self._save_experiment_summary(summary)

        logger.info(
            f"Pilot experiment complete: "
            f"{completed_runs}/{len(run_configs)} runs completed, "
            f"{failed_runs} failed, "
            f"time={total_wall_time:.1f}s, "
            f"cost=${total_cost_usd:.2f}"
        )

        return summary

    def run_specific_combination(
        self,
        sequence_name: str,
        policy_name: str,
        seed: int,
    ) -> SequenceResult:
        """Execute a specific sequence-policy-seed combination.

        This is useful for debugging or re-running failed runs.

        Args:
            sequence_name: Name of the sequence to run
            policy_name: Name of the policy to use
            seed: Random seed for reproducibility

        Returns:
            SequenceResult with execution details

        Raises:
            ValueError: If sequence_name or policy_name is unknown
        """
        logger.info(
            f"Running specific combination: "
            f"sequence={sequence_name}, policy={policy_name}, seed={seed}"
        )

        # Get sequence
        sequence = self.loader.get_sequence_by_name(sequence_name)
        if sequence is None:
            raise ValueError(f"Unknown sequence: {sequence_name}")

        # Generate run config
        run_id = f"{sequence_name}_{policy_name}_seed{seed}_specific_{uuid.uuid4().hex[:8]}"

        run_config = RunConfig(
            run_id=run_id,
            sequence_name=sequence_name,
            policy_name=policy_name,
            seed=seed,
            sequence_index=0,
            policy_index=0,
            seed_index=0,
        )

        # Execute run
        result = self._execute_run(run_config, sequence)

        # Save result
        self._save_run_result(run_config, result)

        return result
