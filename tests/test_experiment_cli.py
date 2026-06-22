"""Tests for the experiment_runner CLI entry point and the run_condition /
pilot-sequence-names additions (Phase 6.1 / build-to-pilot Commit 4).

_execute_run is mocked throughout, so no SequenceRunner / network / Docker is
touched — these tests exercise dispatch, matrix selection, and summaries only.

Task 5d note: the sentinel gate (is_run_complete) is also patched to return True
in these dispatch-only tests — they test matrix selection / CLI wiring, not
the sentinel logic (which is covered by TestSentinelGatedCompletion in
test_experiment_runner.py).
"""

import json
from unittest.mock import Mock, patch

import pytest

from src.benchmark import experiment_runner as er
from src.benchmark.experiment_runner import ExperimentRunner

# The 8 official-style sequence names; first two are the decision-I pilot pair.
SEQ_NAMES = [
    "django", "pytest", "sympy", "sphinx",
    "matplotlib", "scikit-learn", "astropy", "xarray",
]


@pytest.fixture
def cfg():
    return {
        "experiment": {"name": "test", "seeds": [1, 2, 3]},
        "memory": {"max_records": 100},
    }


@pytest.fixture
def curriculum_file(tmp_path):
    """8-sequence curriculum (15 ascending tasks each) written to a temp file."""
    sequences = []
    for name in SEQ_NAMES:
        tasks = [
            {
                "task_id": f"{name}__{name}-{j}",
                "repo": f"{name}/{name}",
                "base_commit": f"commit{j}",
                "issue_text": f"Issue {j}",
                "test_patch": f"test patch {j}",
                "gold_patch": f"gold patch {j}",
                "created_at": f"2020-01-{j + 1:02d}T00:00:00Z",
                "sequence_index": j,
                "difficulty_label": "easy" if j < 5 else "medium",
            }
            for j in range(15)
        ]
        sequences.append(
            {"sequence_name": name, "repo": f"{name}/{name}", "tasks": tasks}
        )
    path = tmp_path / "curriculum.json"
    path.write_text(json.dumps({"sequences": sequences}), encoding="utf-8")
    return path


def _fake_result():
    return Mock(resolved_tasks=1, total_tasks=15, total_cost_usd=0.0)


class TestRunConditionAndPilot:
    def test_run_condition_runs_all_8_sequences_one_seed(self, cfg, curriculum_file):
        runner = ExperimentRunner(config=cfg, curriculum_path=curriculum_file)
        with patch.object(ExperimentRunner, "_execute_run", return_value=_fake_result()) as ex, \
                patch.object(ExperimentRunner, "_save_run_result"), \
                patch("src.benchmark.experiment_runner.is_run_complete", return_value=True):
            summary = runner.run_condition(policy_name="type_aware_decay", seed=2)
        assert summary.total_runs == 8          # 8 sequences x 1 policy x 1 seed
        assert summary.completed_runs == 8
        assert summary.total_policies == 1
        # every run used seed=2
        seeds_used = {call.args[0].seed for call in ex.call_args_list}
        assert seeds_used == {2}

    def test_run_condition_rejects_bad_seed(self, cfg, curriculum_file):
        runner = ExperimentRunner(config=cfg, curriculum_path=curriculum_file)
        with pytest.raises(ValueError, match="No runs generated"):
            runner.run_condition(policy_name="no_memory", seed=99)

    def test_pilot_with_explicit_sequence_names(self, cfg, curriculum_file):
        runner = ExperimentRunner(config=cfg, curriculum_path=curriculum_file)
        with patch.object(ExperimentRunner, "_execute_run", return_value=_fake_result()), \
                patch.object(ExperimentRunner, "_save_run_result"), \
                patch("src.benchmark.experiment_runner.is_run_complete", return_value=True):
            summary = runner.run_pilot_experiment(sequence_names=["django", "pytest"])
        assert summary.total_runs == 12         # 2 sequences x 6 policies x 1 seed
        assert summary.total_sequences == 2

    def test_pilot_unknown_sequence_name_raises(self, cfg, curriculum_file):
        runner = ExperimentRunner(config=cfg, curriculum_path=curriculum_file)
        with pytest.raises(ValueError, match="Unknown pilot sequence"):
            runner.run_pilot_experiment(sequence_names=["does-not-exist"])

    def test_pilot_default_first_n(self, cfg, curriculum_file):
        runner = ExperimentRunner(config=cfg, curriculum_path=curriculum_file)
        with patch.object(ExperimentRunner, "_execute_run", return_value=_fake_result()), \
                patch.object(ExperimentRunner, "_save_run_result"), \
                patch("src.benchmark.experiment_runner.is_run_complete", return_value=True):
            summary = runner.run_pilot_experiment(num_sequences=2)
        assert summary.total_runs == 12
        assert summary.total_sequences == 2


class TestMainCLI:
    def test_main_pilot_dispatch(self, cfg, curriculum_file):
        with patch.object(er, "load_config", return_value=cfg), \
                patch.object(ExperimentRunner, "_execute_run", return_value=_fake_result()), \
                patch.object(ExperimentRunner, "_save_run_result"), \
                patch("src.benchmark.experiment_runner.is_run_complete", return_value=True):
            summary = er.main([
                "--mode", "pilot",
                "--sequences", "django,pytest",
                "--curriculum", str(curriculum_file),
            ])
        assert summary.total_runs == 12
        assert summary.total_sequences == 2

    def test_main_condition_requires_policy_and_seed(self, cfg, curriculum_file):
        with patch.object(er, "load_config", return_value=cfg):
            with pytest.raises(SystemExit):
                er.main(["--mode", "condition", "--curriculum", str(curriculum_file)])

    def test_main_condition_dispatch(self, cfg, curriculum_file):
        with patch.object(er, "load_config", return_value=cfg), \
                patch.object(ExperimentRunner, "_execute_run", return_value=_fake_result()), \
                patch.object(ExperimentRunner, "_save_run_result"), \
                patch("src.benchmark.experiment_runner.is_run_complete", return_value=True):
            summary = er.main([
                "--mode", "condition",
                "--policy", "recency_prune",
                "--seed", "1",
                "--curriculum", str(curriculum_file),
            ])
        assert summary.total_runs == 8
        assert summary.total_policies == 1
