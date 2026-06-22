"""Unit tests for ExperimentRunner.

This module tests the experiment orchestrator that executes all 8 sequences
for each of 6 policies with 3 independent runs per combination.

**Validates: Requirements 16**

Test Coverage:
1. Initialization and configuration validation
2. Policy initialization for all 6 policies
3. Run matrix generation (144 runs)
4. Pilot mode (12 runs)
5. Specific combination execution
6. Seed reproducibility
7. Frozen invariants enforcement

Requirements: 16
Design: THESIS_FINAL_v5.md §12, §16
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.benchmark.experiment_runner import (
    ExperimentRunner,
    RunConfig,
)
from src.benchmark.models import Sequence, Task
from src.benchmark.sequence_runner import SequenceResult
from src.errors import UsageLimitError
from src.memory.policies.cls_consolidation import CLSConsolidationPolicy
from src.memory.policies.full_memory import FullMemoryPolicy
from src.memory.policies.no_memory import NoMemoryPolicy
from src.memory.policies.random_prune import RandomPrunePolicy
from src.memory.policies.recency_prune import RecencyPrunePolicy
from src.memory.policies.type_aware_decay import TypeAwareDecayPolicy


@pytest.fixture
def mock_config():
    """Mock configuration dictionary."""
    return {
        "experiment": {
            "name": "test_experiment",
            "seeds": [1, 2, 3],
        },
        "memory": {
            "max_records": 100,
        },
    }


@pytest.fixture
def mock_sequences():
    """Mock 8 sequences for testing."""
    sequences = []
    for i in range(8):
        tasks = []
        for j in range(15):  # Minimum 15 tasks per sequence
            task = Task(
                task_id=f"repo{i}__task{j}",
                repo=f"repo{i}/repo{i}",
                base_commit=f"commit{j}",
                issue_text=f"Issue {j}",
                test_patch=f"test patch {j}",
                gold_patch=f"gold patch {j}",
                created_at=f"2020-01-{j+1:02d}T00:00:00Z",
                sequence_index=j,
                difficulty_label="medium",
            )
            tasks.append(task)

        sequence = Sequence(
            sequence_name=f"repo{i}",
            repo=f"repo{i}/repo{i}",
            tasks=tasks,
            task_count=len(tasks),
        )
        sequences.append(sequence)

    return sequences


@pytest.fixture
def mock_curriculum_file(tmp_path, mock_sequences):
    """Create mock curriculum JSON file."""
    curriculum_path = tmp_path / "curriculum.json"

    curriculum_data = {
        "sequences": [
            {
                "sequence_name": seq.sequence_name,
                "repo": seq.repo,
                "tasks": [
                    {
                        "task_id": task.task_id,
                        "repo": task.repo,
                        "base_commit": task.base_commit,
                        "issue_text": task.issue_text,
                        "test_patch": task.test_patch,
                        "gold_patch": task.gold_patch,
                        "created_at": task.created_at,
                        "sequence_index": task.sequence_index,
                        "difficulty_label": task.difficulty_label,
                    }
                    for task in seq.tasks
                ],
            }
            for seq in mock_sequences
        ]
    }

    with open(curriculum_path, "w", encoding="utf-8") as f:
        json.dump(curriculum_data, f)

    return curriculum_path


class TestExperimentRunnerInitialization:
    """Test ExperimentRunner initialization and configuration validation."""

    def test_initialization_success(self, mock_config, mock_curriculum_file):
        """Test successful initialization with valid config and curriculum."""
        runner = ExperimentRunner(
            config=mock_config,
            curriculum_path=mock_curriculum_file,
        )

        assert runner.config == mock_config
        assert len(runner.sequences) == 8
        assert len(runner.seeds) == 3
        assert runner.results_dir.exists()

    def test_initialization_validates_8_sequences(self, mock_config, tmp_path):
        """Test that initialization fails if not exactly 8 sequences."""
        # Create curriculum with only 5 sequences
        curriculum_path = tmp_path / "curriculum.json"
        curriculum_data = {
            "sequences": [
                {
                    "sequence_name": f"repo{i}",
                    "repo": f"repo{i}/repo{i}",
                    "tasks": [
                        {
                            "task_id": f"repo{i}__task0",
                            "repo": f"repo{i}/repo{i}",
                            "base_commit": "commit0",
                            "issue_text": "Issue 0",
                            "test_patch": "test patch 0",
                            "gold_patch": "gold patch 0",
                            "created_at": "2020-01-01T00:00:00Z",
                            "sequence_index": 0,
                            "difficulty_label": "medium",
                        }
                        for _ in range(15)
                    ],
                }
                for i in range(5)  # Only 5 sequences
            ]
        }

        with open(curriculum_path, "w", encoding="utf-8") as f:
            json.dump(curriculum_data, f)

        with pytest.raises(ValueError, match="Curriculum must contain exactly 8 sequences"):
            ExperimentRunner(
                config=mock_config,
                curriculum_path=curriculum_path,
            )

    def test_initialization_validates_3_seeds(self, mock_curriculum_file):
        """Test that initialization fails if not exactly 3 seeds."""
        config = {
            "experiment": {
                "seeds": [1, 2],  # Only 2 seeds
            },
            "memory": {
                "max_records": 100,
            },
        }

        with pytest.raises(ValueError, match="Expected exactly 3 seeds"):
            ExperimentRunner(
                config=config,
                curriculum_path=mock_curriculum_file,
            )


class TestPolicyInitialization:
    """Test policy initialization for all 6 policies."""

    def test_initialize_no_memory_policy(self, mock_config, mock_curriculum_file):
        """Test No Memory policy initialization."""
        runner = ExperimentRunner(
            config=mock_config,
            curriculum_path=mock_curriculum_file,
        )

        policy = runner._initialize_policy("no_memory")

        assert isinstance(policy, NoMemoryPolicy)
        assert policy.name == "no_memory"

    def test_initialize_full_memory_policy(self, mock_config, mock_curriculum_file):
        """Test Full Memory policy initialization."""
        runner = ExperimentRunner(
            config=mock_config,
            curriculum_path=mock_curriculum_file,
        )

        policy = runner._initialize_policy("full_memory")

        assert isinstance(policy, FullMemoryPolicy)
        assert policy.name == "full_memory"

    def test_initialize_random_prune_policy(self, mock_config, mock_curriculum_file):
        """Test Random Prune policy initialization with seed."""
        runner = ExperimentRunner(
            config=mock_config,
            curriculum_path=mock_curriculum_file,
        )

        policy = runner._initialize_policy("random_prune", seed=42)

        assert isinstance(policy, RandomPrunePolicy)
        assert policy.name == "random_prune"
        assert policy.seed == 42
        assert policy.max_records == 100

    def test_initialize_random_prune_requires_seed(self, mock_config, mock_curriculum_file):
        """Test Random Prune policy requires seed."""
        runner = ExperimentRunner(
            config=mock_config,
            curriculum_path=mock_curriculum_file,
        )

        with pytest.raises(ValueError, match="Random Prune requires a seed"):
            runner._initialize_policy("random_prune", seed=None)

    def test_initialize_recency_prune_policy(self, mock_config, mock_curriculum_file):
        """Test Recency Prune policy initialization."""
        runner = ExperimentRunner(
            config=mock_config,
            curriculum_path=mock_curriculum_file,
        )

        policy = runner._initialize_policy("recency_prune")

        assert isinstance(policy, RecencyPrunePolicy)
        assert policy.name == "recency_prune"
        assert policy.max_records == 100

    def test_initialize_type_aware_decay_policy(self, mock_config, mock_curriculum_file):
        """Test Type-Aware Decay policy initialization."""
        runner = ExperimentRunner(
            config=mock_config,
            curriculum_path=mock_curriculum_file,
        )

        policy = runner._initialize_policy("type_aware_decay")

        assert isinstance(policy, TypeAwareDecayPolicy)
        assert policy.name == "type_aware_decay"
        assert policy.max_records == 100

    def test_initialize_cls_consolidation_policy(self, mock_config, mock_curriculum_file):
        """Test CLS Consolidation policy initialization."""
        runner = ExperimentRunner(
            config=mock_config,
            curriculum_path=mock_curriculum_file,
        )

        policy = runner._initialize_policy("cls_consolidation")

        assert isinstance(policy, CLSConsolidationPolicy)
        assert policy.name == "cls_consolidation"
        assert policy.max_records == 100

    def test_initialize_unknown_policy_raises_error(self, mock_config, mock_curriculum_file):
        """Test unknown policy name raises ValueError."""
        runner = ExperimentRunner(
            config=mock_config,
            curriculum_path=mock_curriculum_file,
        )

        with pytest.raises(ValueError, match="Unknown policy"):
            runner._initialize_policy("unknown_policy")


class TestRunMatrixGeneration:
    """Test run matrix generation (144 runs)."""

    def test_generate_full_run_matrix(self, mock_config, mock_curriculum_file):
        """Test full run matrix: 8 sequences × 6 policies × 3 seeds = 144 runs."""
        runner = ExperimentRunner(
            config=mock_config,
            curriculum_path=mock_curriculum_file,
        )

        run_configs = runner._generate_run_matrix()

        # Verify total count
        assert len(run_configs) == 144  # 8 × 6 × 3

        # Verify all sequences included
        sequence_names = {rc.sequence_name for rc in run_configs}
        assert len(sequence_names) == 8

        # Verify all policies included
        policy_names = {rc.policy_name for rc in run_configs}
        assert policy_names == {
            "no_memory",
            "full_memory",
            "random_prune",
            "recency_prune",
            "type_aware_decay",
            "cls_consolidation",
        }

        # Verify all seeds included
        seeds = {rc.seed for rc in run_configs}
        assert seeds == {1, 2, 3}

        # Verify each combination appears exactly once
        combinations = {
            (rc.sequence_name, rc.policy_name, rc.seed)
            for rc in run_configs
        }
        assert len(combinations) == 144

    def test_generate_run_matrix_with_policy_filter(self, mock_config, mock_curriculum_file):
        """Test run matrix with policy filter."""
        runner = ExperimentRunner(
            config=mock_config,
            curriculum_path=mock_curriculum_file,
        )

        run_configs = runner._generate_run_matrix(policy_filter="type_aware_decay")

        # Verify only filtered policy included
        assert len(run_configs) == 24  # 8 sequences × 1 policy × 3 seeds
        assert all(rc.policy_name == "type_aware_decay" for rc in run_configs)

    def test_generate_run_matrix_with_sequence_filter(self, mock_config, mock_curriculum_file):
        """Test run matrix with sequence filter."""
        runner = ExperimentRunner(
            config=mock_config,
            curriculum_path=mock_curriculum_file,
        )

        run_configs = runner._generate_run_matrix(sequence_filter="repo0")

        # Verify only filtered sequence included
        assert len(run_configs) == 18  # 1 sequence × 6 policies × 3 seeds
        assert all(rc.sequence_name == "repo0" for rc in run_configs)

    def test_generate_run_matrix_unique_run_ids(self, mock_config, mock_curriculum_file):
        """Test that all run_ids are unique."""
        runner = ExperimentRunner(
            config=mock_config,
            curriculum_path=mock_curriculum_file,
        )

        run_configs = runner._generate_run_matrix()

        run_ids = [rc.run_id for rc in run_configs]
        assert len(run_ids) == len(set(run_ids))  # All unique


class TestRunExecution:
    """Test run execution and result saving."""

    @patch("src.benchmark.experiment_runner.SequenceRunner")
    def test_execute_run_success(
        self,
        mock_sequence_runner_class,
        mock_config,
        mock_curriculum_file,
        mock_sequences,
    ):
        """Test successful run execution."""
        # Mock SequenceRunner
        mock_runner_instance = Mock()
        mock_result = SequenceResult(
            sequence_name="repo0",
            repo="repo0/repo0",
            policy_name="no_memory",
            seed=1,
            total_tasks=15,
            completed_tasks=15,
            resolved_tasks=10,
            failed_tasks=5,
            timeout_tasks=0,
            total_wall_time=100.0,
            total_cost_usd=5.0,
            error_message=None,
            run_id="test_run_id",
        )
        mock_runner_instance.run_sequence.return_value = mock_result
        mock_sequence_runner_class.return_value = mock_runner_instance

        runner = ExperimentRunner(
            config=mock_config,
            curriculum_path=mock_curriculum_file,
        )

        run_config = RunConfig(
            run_id="test_run_id",
            sequence_name="repo0",
            policy_name="no_memory",
            seed=1,
            sequence_index=0,
            policy_index=0,
            seed_index=0,
        )

        result = runner._execute_run(run_config, mock_sequences[0])

        assert result == mock_result
        mock_sequence_runner_class.assert_called_once()
        mock_runner_instance.run_sequence.assert_called_once()

    def test_save_run_result(self, mock_config, mock_curriculum_file, tmp_path):
        """Test saving run result to file."""
        runner = ExperimentRunner(
            config=mock_config,
            curriculum_path=mock_curriculum_file,
        )
        runner.results_dir = tmp_path

        run_config = RunConfig(
            run_id="test_run_id",
            sequence_name="repo0",
            policy_name="no_memory",
            seed=1,
            sequence_index=0,
            policy_index=0,
            seed_index=0,
        )

        result = SequenceResult(
            sequence_name="repo0",
            repo="repo0/repo0",
            policy_name="no_memory",
            seed=1,
            total_tasks=15,
            completed_tasks=15,
            resolved_tasks=10,
            failed_tasks=5,
            timeout_tasks=0,
            total_wall_time=100.0,
            total_cost_usd=5.0,
            error_message=None,
            run_id="test_run_id",
        )

        runner._save_run_result(run_config, result)

        # Verify file created
        result_file = tmp_path / "test_run_id_result.json"
        assert result_file.exists()

        # Verify content
        with open(result_file, encoding="utf-8") as f:
            data = json.load(f)

        assert "run_config" in data
        assert "result" in data
        assert data["run_config"]["run_id"] == "test_run_id"
        assert data["result"]["resolved_tasks"] == 10


class TestPilotMode:
    """Test pilot experiment mode (12 runs)."""

    @patch("src.benchmark.experiment_runner.SequenceRunner")
    def test_pilot_experiment_12_runs(
        self,
        mock_sequence_runner_class,
        mock_config,
        mock_curriculum_file,
    ):
        """Test pilot experiment generates 12 runs (2 sequences × 6 policies × 1 seed)."""
        # Mock SequenceRunner
        mock_runner_instance = Mock()
        mock_result = SequenceResult(
            sequence_name="repo0",
            repo="repo0/repo0",
            policy_name="no_memory",
            seed=1,
            total_tasks=15,
            completed_tasks=15,
            resolved_tasks=10,
            failed_tasks=5,
            timeout_tasks=0,
            total_wall_time=100.0,
            total_cost_usd=5.0,
            error_message=None,
            run_id="test_run_id",
        )
        mock_runner_instance.run_sequence.return_value = mock_result
        mock_sequence_runner_class.return_value = mock_runner_instance

        runner = ExperimentRunner(
            config=mock_config,
            curriculum_path=mock_curriculum_file,
        )

        summary = runner.run_pilot_experiment(num_sequences=2)

        # Verify 12 runs executed
        assert summary.total_runs == 12  # 2 × 6 × 1
        assert summary.total_sequences == 2
        assert summary.total_policies == 6
        assert summary.total_seeds == 1

    @patch("src.benchmark.experiment_runner.SequenceRunner")
    def test_pilot_uses_first_seed_only(
        self,
        mock_sequence_runner_class,
        mock_config,
        mock_curriculum_file,
    ):
        """Test pilot experiment uses only first seed."""
        # Mock SequenceRunner
        mock_runner_instance = Mock()
        mock_result = SequenceResult(
            sequence_name="repo0",
            repo="repo0/repo0",
            policy_name="no_memory",
            seed=1,
            total_tasks=15,
            completed_tasks=15,
            resolved_tasks=10,
            failed_tasks=5,
            timeout_tasks=0,
            total_wall_time=100.0,
            total_cost_usd=5.0,
            error_message=None,
            run_id="test_run_id",
        )
        mock_runner_instance.run_sequence.return_value = mock_result
        mock_sequence_runner_class.return_value = mock_runner_instance

        runner = ExperimentRunner(
            config=mock_config,
            curriculum_path=mock_curriculum_file,
        )

        runner.run_pilot_experiment(num_sequences=2)

        # Verify all calls used seed=1
        for call in mock_runner_instance.run_sequence.call_args_list:
            assert call[1]["seed"] == 1


class TestSpecificCombination:
    """Test specific sequence-policy-seed combination execution."""

    @patch("src.benchmark.experiment_runner.SequenceRunner")
    def test_run_specific_combination(
        self,
        mock_sequence_runner_class,
        mock_config,
        mock_curriculum_file,
    ):
        """Test running specific combination."""
        # Mock SequenceRunner
        mock_runner_instance = Mock()
        mock_result = SequenceResult(
            sequence_name="repo0",
            repo="repo0/repo0",
            policy_name="type_aware_decay",
            seed=2,
            total_tasks=15,
            completed_tasks=15,
            resolved_tasks=10,
            failed_tasks=5,
            timeout_tasks=0,
            total_wall_time=100.0,
            total_cost_usd=5.0,
            error_message=None,
            run_id="test_run_id",
        )
        mock_runner_instance.run_sequence.return_value = mock_result
        mock_sequence_runner_class.return_value = mock_runner_instance

        runner = ExperimentRunner(
            config=mock_config,
            curriculum_path=mock_curriculum_file,
        )

        result = runner.run_specific_combination(
            sequence_name="repo0",
            policy_name="type_aware_decay",
            seed=2,
        )

        assert result.sequence_name == "repo0"
        assert result.policy_name == "type_aware_decay"
        assert result.seed == 2

    def test_run_specific_combination_unknown_sequence(
        self,
        mock_config,
        mock_curriculum_file,
    ):
        """Test running specific combination with unknown sequence raises error."""
        runner = ExperimentRunner(
            config=mock_config,
            curriculum_path=mock_curriculum_file,
        )

        with pytest.raises(ValueError, match="Unknown sequence"):
            runner.run_specific_combination(
                sequence_name="unknown_sequence",
                policy_name="no_memory",
                seed=1,
            )


class TestFrozenInvariants:
    """Test frozen invariants enforcement."""

    def test_frozen_invariant_8_sequences(self, mock_config, mock_curriculum_file):
        """Test Frozen Invariant #1: All 8 official SWE-Bench-CL sequences."""
        runner = ExperimentRunner(
            config=mock_config,
            curriculum_path=mock_curriculum_file,
        )

        # Verify exactly 8 sequences loaded
        assert len(runner.sequences) == 8

    def test_frozen_invariant_3_seeds_all_conditions(self, mock_config, mock_curriculum_file):
        """Test Frozen Invariant #2: 3 seeds for ALL 6 conditions."""
        runner = ExperimentRunner(
            config=mock_config,
            curriculum_path=mock_curriculum_file,
        )

        run_configs = runner._generate_run_matrix()

        # Verify each policy has 3 seeds
        for policy_name in [
            "no_memory",
            "full_memory",
            "random_prune",
            "recency_prune",
            "type_aware_decay",
            "cls_consolidation",
        ]:
            policy_runs = [rc for rc in run_configs if rc.policy_name == policy_name]
            seeds_used = {rc.seed for rc in policy_runs}
            assert seeds_used == {1, 2, 3}, f"Policy {policy_name} missing seeds"

    def test_frozen_invariant_seeds_initialize_rngs(self, mock_config, mock_curriculum_file):
        """Test seeds initialize RNGs for Random Prune."""
        runner = ExperimentRunner(
            config=mock_config,
            curriculum_path=mock_curriculum_file,
        )

        # Initialize Random Prune with different seeds
        policy1 = runner._initialize_policy("random_prune", seed=1)
        policy2 = runner._initialize_policy("random_prune", seed=2)

        # Verify different seeds produce different RNG states
        assert policy1.seed != policy2.seed
        assert policy1.rng.random() != policy2.rng.random()


class TestUsageLimitFailClosed:
    """C5 (THESIS_REVIEW): provider quota must ABORT the matrix, not continue it.

    Before the fix, the matrix loop's generic ``except Exception`` swallowed
    UsageLimitError, incremented failed_runs, and marched through all 144 runs —
    producing an apparently-complete but invalid 0-resolved matrix.
    """

    def test_run_full_experiment_aborts_on_usage_limit(
        self, mock_config, mock_curriculum_file, monkeypatch
    ):
        runner = ExperimentRunner(
            config=mock_config,
            curriculum_path=mock_curriculum_file,
        )

        calls = {"n": 0}

        def _raise(run_config, sequence):
            calls["n"] += 1
            raise UsageLimitError("429 weekly usage limit reached")

        monkeypatch.setattr(runner, "_execute_run", _raise)

        with pytest.raises(UsageLimitError):
            runner.run_full_experiment()

        # Aborted on the FIRST quota error — did not iterate the rest of the matrix.
        assert calls["n"] == 1

    def test_run_pilot_aborts_on_usage_limit(
        self, mock_config, mock_curriculum_file, monkeypatch
    ):
        runner = ExperimentRunner(
            config=mock_config,
            curriculum_path=mock_curriculum_file,
        )

        def _raise(run_config, sequence):
            raise UsageLimitError("429 weekly usage limit reached")

        monkeypatch.setattr(runner, "_execute_run", _raise)

        with pytest.raises(UsageLimitError):
            runner.run_pilot_experiment(num_sequences=2)


class TestSentinelGatedCompletion:
    """Task 5d: orchestrators must gate completed_runs on RUN_COMPLETED.json.

    Before the fix, any returned run_sequence() was counted as completed and
    a success {run_id}_result.json was written, regardless of whether the run
    produced the RUN_COMPLETED.json sentinel.  That is how the old matrix logged
    "144 complete" with 28 partial units.

    Fix: after run_sequence() returns, check (runs_root / run_id /
    RUN_COMPLETED.json).exists(); only then count + write the success result.
    If absent: increment failed_runs, record the run_id, skip the success write.
    """

    def _make_result(self, run_id: str, seq_name: str = "repo0") -> SequenceResult:
        return SequenceResult(
            sequence_name=seq_name,
            repo=f"{seq_name}/{seq_name}",
            policy_name="no_memory",
            seed=1,
            total_tasks=15,
            completed_tasks=15,
            resolved_tasks=10,
            failed_tasks=5,
            timeout_tasks=0,
            total_wall_time=100.0,
            total_cost_usd=5.0,
            error_message=None,
            run_id=run_id,
        )

    # ------------------------------------------------------------------
    # run_full_experiment
    # ------------------------------------------------------------------

    def test_full_experiment_incomplete_run_not_counted(
        self, mock_config, mock_curriculum_file, tmp_path, monkeypatch
    ):
        """run_full_experiment: a run that returned but has NO sentinel is
        counted as failed, NOT completed, and no success result is written."""
        monkeypatch.setenv("RUNS_ROOT", str(tmp_path / "runs"))
        runner = ExperimentRunner(
            config=mock_config,
            curriculum_path=mock_curriculum_file,
        )
        runner.results_dir = tmp_path / "raw"
        runner.results_dir.mkdir(parents=True, exist_ok=True)

        def _fake_execute(run_config, sequence):
            # Return a result but do NOT write RUN_COMPLETED.json → incomplete.
            return self._make_result(run_config.run_id, sequence.sequence_name)

        monkeypatch.setattr(runner, "_execute_run", _fake_execute)

        summary = runner.run_full_experiment()

        # None of the 144 runs wrote a sentinel → all should be failed/incomplete.
        assert summary.completed_runs == 0
        assert summary.failed_runs == 144
        assert len(summary.failed_run_ids) == 144
        # No success result files should exist.
        result_files = list(runner.results_dir.glob("*_result.json"))
        assert result_files == [], f"Unexpected result files: {result_files}"

    def test_full_experiment_complete_run_counted(
        self, mock_config, mock_curriculum_file, tmp_path, monkeypatch
    ):
        """run_full_experiment: a run WITH RUN_COMPLETED.json is counted
        as completed and its success result file is written."""
        runs_root = tmp_path / "runs"
        monkeypatch.setenv("RUNS_ROOT", str(runs_root))
        runner = ExperimentRunner(
            config=mock_config,
            curriculum_path=mock_curriculum_file,
        )
        runner.results_dir = tmp_path / "raw"
        runner.results_dir.mkdir(parents=True, exist_ok=True)

        def _fake_execute(run_config, sequence):
            # Write the sentinel so the orchestrator gate passes.
            run_dir = runs_root / run_config.run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "RUN_COMPLETED.json").write_text(
                '{"validated_at": "2026-01-01T00:00:00+00:00"}', encoding="utf-8"
            )
            return self._make_result(run_config.run_id, sequence.sequence_name)

        monkeypatch.setattr(runner, "_execute_run", _fake_execute)

        summary = runner.run_full_experiment()

        assert summary.completed_runs == 144
        assert summary.failed_runs == 0
        assert summary.failed_run_ids == []
        result_files = list(runner.results_dir.glob("*_result.json"))
        assert len(result_files) == 144

    # ------------------------------------------------------------------
    # run_pilot_experiment
    # ------------------------------------------------------------------

    def test_pilot_incomplete_run_not_counted(
        self, mock_config, mock_curriculum_file, tmp_path, monkeypatch
    ):
        """run_pilot_experiment: incomplete run (no sentinel) counted as failed."""
        monkeypatch.setenv("RUNS_ROOT", str(tmp_path / "runs"))
        runner = ExperimentRunner(
            config=mock_config,
            curriculum_path=mock_curriculum_file,
        )
        runner.results_dir = tmp_path / "raw"
        runner.results_dir.mkdir(parents=True, exist_ok=True)

        def _fake_execute(run_config, sequence):
            return self._make_result(run_config.run_id, sequence.sequence_name)

        monkeypatch.setattr(runner, "_execute_run", _fake_execute)

        summary = runner.run_pilot_experiment(num_sequences=2)

        # 2 seqs × 6 policies × 1 seed = 12 runs, none complete.
        assert summary.total_runs == 12
        assert summary.completed_runs == 0
        assert summary.failed_runs == 12

    def test_pilot_complete_run_counted(
        self, mock_config, mock_curriculum_file, tmp_path, monkeypatch
    ):
        """run_pilot_experiment: run WITH sentinel counted, result file written."""
        runs_root = tmp_path / "runs"
        monkeypatch.setenv("RUNS_ROOT", str(runs_root))
        runner = ExperimentRunner(
            config=mock_config,
            curriculum_path=mock_curriculum_file,
        )
        runner.results_dir = tmp_path / "raw"
        runner.results_dir.mkdir(parents=True, exist_ok=True)

        def _fake_execute(run_config, sequence):
            run_dir = runs_root / run_config.run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "RUN_COMPLETED.json").write_text(
                '{"validated_at": "2026-01-01T00:00:00+00:00"}', encoding="utf-8"
            )
            return self._make_result(run_config.run_id, sequence.sequence_name)

        monkeypatch.setattr(runner, "_execute_run", _fake_execute)

        summary = runner.run_pilot_experiment(num_sequences=2)

        assert summary.total_runs == 12
        assert summary.completed_runs == 12
        assert summary.failed_runs == 0
        result_files = list(runner.results_dir.glob("*_result.json"))
        assert len(result_files) == 12

    # ------------------------------------------------------------------
    # run_condition
    # ------------------------------------------------------------------

    def test_condition_incomplete_run_not_counted(
        self, mock_config, mock_curriculum_file, tmp_path, monkeypatch
    ):
        """run_condition: incomplete run (no sentinel) counted as failed."""
        monkeypatch.setenv("RUNS_ROOT", str(tmp_path / "runs"))
        runner = ExperimentRunner(
            config=mock_config,
            curriculum_path=mock_curriculum_file,
        )
        runner.results_dir = tmp_path / "raw"
        runner.results_dir.mkdir(parents=True, exist_ok=True)

        def _fake_execute(run_config, sequence):
            return self._make_result(run_config.run_id, sequence.sequence_name)

        monkeypatch.setattr(runner, "_execute_run", _fake_execute)

        summary = runner.run_condition(policy_name="no_memory", seed=1)

        # 8 sequences × 1 policy × 1 seed = 8 runs, none complete.
        assert summary.total_runs == 8
        assert summary.completed_runs == 0
        assert summary.failed_runs == 8

    def test_condition_complete_run_counted(
        self, mock_config, mock_curriculum_file, tmp_path, monkeypatch
    ):
        """run_condition: run WITH sentinel counted, result file written."""
        runs_root = tmp_path / "runs"
        monkeypatch.setenv("RUNS_ROOT", str(runs_root))
        runner = ExperimentRunner(
            config=mock_config,
            curriculum_path=mock_curriculum_file,
        )
        runner.results_dir = tmp_path / "raw"
        runner.results_dir.mkdir(parents=True, exist_ok=True)

        def _fake_execute(run_config, sequence):
            run_dir = runs_root / run_config.run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "RUN_COMPLETED.json").write_text(
                '{"validated_at": "2026-01-01T00:00:00+00:00"}', encoding="utf-8"
            )
            return self._make_result(run_config.run_id, sequence.sequence_name)

        monkeypatch.setattr(runner, "_execute_run", _fake_execute)

        summary = runner.run_condition(policy_name="no_memory", seed=1)

        assert summary.total_runs == 8
        assert summary.completed_runs == 8
        assert summary.failed_runs == 0
        result_files = list(runner.results_dir.glob("*_result.json"))
        assert len(result_files) == 8
