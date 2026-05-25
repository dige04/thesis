"""Unit tests for pilot mode and calibration support.

Tests:
- Pilot mode configuration loading
- Retrieval quality metrics computation
- Calibration parameter updates
- Calibration locking

Requirements: 30
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.config.calibration import (
    analyze_pilot_results,
    lock_calibration,
    update_calibration_params,
)
from src.config.loader import ConfigLoader, load_config
from src.errors import ConfigFrozenError
from src.metrics.retrieval_quality import (
    RetrievalQualityMetrics,
    aggregate_retrieval_quality,
    compute_retrieval_quality,
)


class TestPilotModeConfiguration:
    """Test pilot mode configuration loading."""

    def test_pilot_mode_config_present(self):
        """Test that pilot_mode configuration is present in base.yaml."""
        config = load_config()

        assert "experiment" in config
        assert "pilot_mode" in config["experiment"]

        pilot_config = config["experiment"]["pilot_mode"]
        assert "enabled" in pilot_config
        assert "num_sequences" in pilot_config
        assert "num_seeds" in pilot_config
        assert "log_retrieval_quality" in pilot_config
        assert "calibration_locked" in pilot_config

    def test_pilot_mode_defaults(self):
        """Test pilot mode default values."""
        config = load_config()
        pilot_config = config["experiment"]["pilot_mode"]

        assert pilot_config["enabled"] is False
        assert pilot_config["num_sequences"] == 2
        assert pilot_config["num_seeds"] == 1
        assert pilot_config["log_retrieval_quality"] is True
        assert pilot_config["calibration_locked"] is False


class TestRetrievalQualityMetrics:
    """Test retrieval quality metrics computation."""

    def test_compute_retrieval_quality_basic(self):
        """Test basic retrieval quality computation."""

        # Mock task
        class MockTask:
            task_id = "test-task-1"
            repo = "test/repo"
            sequence_index = 5

        task = MockTask()

        # Mock retrieved memories (3 memories)
        retrieved = [
            {"memory_id": "mem-1", "similarity": 0.9},
            {"memory_id": "mem-2", "similarity": 0.8},
            {"memory_id": "mem-3", "similarity": 0.7},
        ]

        # Mock all available memories (5 memories, 4 relevant)
        all_available = [
            {
                "memory_id": "mem-1",
                "repo": "test/repo",
                "sequence_index": 1,
                "memory_type": "bug_fix",
                "outcome": "pass",
            },
            {
                "memory_id": "mem-2",
                "repo": "test/repo",
                "sequence_index": 2,
                "memory_type": "api_change",
                "outcome": "pass",
            },
            {
                "memory_id": "mem-3",
                "repo": "other/repo",
                "sequence_index": 3,
                "memory_type": "bug_fix",
                "outcome": "pass",
            },  # Different repo, not relevant
            {
                "memory_id": "mem-4",
                "repo": "test/repo",
                "sequence_index": 4,
                "memory_type": "test_update",
                "outcome": "fail",
            },  # Not retrieved
            {
                "memory_id": "mem-5",
                "repo": "test/repo",
                "sequence_index": 6,
                "memory_type": "config",
                "outcome": "pass",
            },  # Future memory, not available
        ]

        # Compute metrics
        metrics = compute_retrieval_quality(
            task=task,
            retrieved_memories=retrieved,
            all_available_memories=all_available,
            relevance_criteria={"same_repo": True},
        )

        # Assertions
        assert metrics.task_id == "test-task-1"
        assert metrics.k == 3
        assert metrics.num_retrieved == 3
        assert metrics.num_relevant_total == 3  # mem-1, mem-2, mem-4 (same repo, before task)
        assert metrics.num_relevant_retrieved == 2  # mem-1, mem-2 (mem-3 is different repo)
        assert metrics.precision_at_k == pytest.approx(2 / 3, abs=0.01)
        assert metrics.recall_at_k == pytest.approx(2 / 3, abs=0.01)
        assert metrics.mrr == pytest.approx(1.0, abs=0.01)  # First item is relevant

    def test_compute_retrieval_quality_no_relevant(self):
        """Test retrieval quality when no relevant memories exist."""

        class MockTask:
            task_id = "test-task-2"
            repo = "test/repo"
            sequence_index = 1

        task = MockTask()

        retrieved = [
            {"memory_id": "mem-1", "similarity": 0.9},
        ]

        all_available = [
            {
                "memory_id": "mem-1",
                "repo": "other/repo",
                "sequence_index": 0,
                "memory_type": "bug_fix",
                "outcome": "pass",
            },  # Different repo
        ]

        metrics = compute_retrieval_quality(
            task=task,
            retrieved_memories=retrieved,
            all_available_memories=all_available,
        )

        assert metrics.num_relevant_total == 0
        assert metrics.num_relevant_retrieved == 0
        assert metrics.precision_at_k == 0.0
        assert metrics.recall_at_k == 0.0
        assert metrics.mrr == 0.0
        assert metrics.ndcg_at_k == 0.0

    def test_aggregate_retrieval_quality(self):
        """Test aggregation of retrieval quality metrics."""
        metrics_list = [
            RetrievalQualityMetrics(
                task_id="task-1",
                k=5,
                precision_at_k=0.8,
                recall_at_k=0.6,
                mrr=1.0,
                ndcg_at_k=0.9,
                num_relevant_retrieved=4,
                num_relevant_total=5,
                num_retrieved=5,
            ),
            RetrievalQualityMetrics(
                task_id="task-2",
                k=5,
                precision_at_k=0.6,
                recall_at_k=0.5,
                mrr=0.5,
                ndcg_at_k=0.7,
                num_relevant_retrieved=3,
                num_relevant_total=6,
                num_retrieved=5,
            ),
        ]

        aggregated = aggregate_retrieval_quality(metrics_list)

        assert aggregated["mean_precision_at_k"] == pytest.approx(0.7, abs=0.01)
        assert aggregated["mean_recall_at_k"] == pytest.approx(0.55, abs=0.01)
        assert aggregated["mean_mrr"] == pytest.approx(0.75, abs=0.01)
        assert aggregated["mean_ndcg_at_k"] == pytest.approx(0.8, abs=0.01)
        assert aggregated["num_tasks"] == 2


class TestCalibrationParameterUpdates:
    """Test calibration parameter updates."""

    def test_update_top_k(self):
        """Test updating top_k calibration parameter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create temporary config file
            config_path = Path(tmpdir) / "test_config.yaml"
            config_path.write_text(
                """
experiment:
  name: "test"
agent:
  max_steps_per_task: 20
memory:
  top_k: 5
  max_context_tokens: 2000
  max_records: 100
  max_storage_tokens: 30000
  embedding_max_tokens: 7500
retrieval:
  scoring: "pure_cosine"
policies:
  type_aware_decay:
    type_params:
      architectural: {base: 1.0, decay: 0.05}
execution:
  docker_max_workers: 4
logging:
  save_raw_trajectory: true
evaluation:
  bootstrap_iterations: 5000
statistical:
  primary_test: "wilcoxon"
"""
            )

            # Update top_k
            update_calibration_params(config_path, top_k=10)

            # Verify update
            loader = ConfigLoader(str(config_path))
            config = loader.load()
            assert config["memory"]["top_k"] == 10

    def test_update_max_context_tokens(self):
        """Test updating max_context_tokens calibration parameter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_config.yaml"
            config_path.write_text(
                """
experiment:
  name: "test"
agent:
  max_steps_per_task: 20
memory:
  top_k: 5
  max_context_tokens: 2000
  max_records: 100
  max_storage_tokens: 30000
  embedding_max_tokens: 7500
retrieval:
  scoring: "pure_cosine"
policies:
  type_aware_decay:
    type_params:
      architectural: {base: 1.0, decay: 0.05}
execution:
  docker_max_workers: 4
logging:
  save_raw_trajectory: true
evaluation:
  bootstrap_iterations: 5000
statistical:
  primary_test: "wilcoxon"
"""
            )

            # Update max_context_tokens
            update_calibration_params(config_path, max_context_tokens=3000)

            # Verify update
            loader = ConfigLoader(str(config_path))
            config = loader.load()
            assert config["memory"]["max_context_tokens"] == 3000

    def test_lock_calibration_prevents_updates(self):
        """Test that locking calibration prevents further updates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_config.yaml"
            config_path.write_text(
                """
experiment:
  name: "test"
  pilot_mode:
    calibration_locked: false
agent:
  max_steps_per_task: 20
memory:
  top_k: 5
  max_context_tokens: 2000
  max_records: 100
  max_storage_tokens: 30000
  embedding_max_tokens: 7500
retrieval:
  scoring: "pure_cosine"
policies:
  type_aware_decay:
    type_params:
      architectural: {base: 1.0, decay: 0.05}
execution:
  docker_max_workers: 4
logging:
  save_raw_trajectory: true
evaluation:
  bootstrap_iterations: 5000
statistical:
  primary_test: "wilcoxon"
"""
            )

            # Lock calibration
            lock_calibration(config_path)

            # Verify calibration_locked flag is set
            loader = ConfigLoader(str(config_path))
            config = loader.load()
            assert config["experiment"]["pilot_mode"]["calibration_locked"] is True

            # Attempt to update should raise error
            loader.freeze_calibration_params()
            with pytest.raises(ConfigFrozenError):
                loader.update_calibration_param(("memory", "top_k"), 10)


class TestPilotResultsAnalysis:
    """Test pilot results analysis."""

    def test_analyze_pilot_results_empty_dir(self):
        """Test analyzing pilot results with empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            results_dir = Path(tmpdir)

            analysis = analyze_pilot_results(results_dir)

            assert analysis["per_policy_metrics"] == {}
            assert analysis["overall_metrics"] == {}
            assert analysis["recommendations"] == {}

    def test_analyze_pilot_results_with_metrics(self):
        """Test analyzing pilot results with sample metrics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            results_dir = Path(tmpdir)

            # Create sample metrics file
            run_dir = results_dir / "test_run_001"
            run_dir.mkdir(parents=True)

            metrics_data = {
                "run_id": "test_run_001",
                "policy_name": "type_aware_decay",
                "aggregated_metrics": {
                    "mean_precision_at_k": 0.7,
                    "mean_recall_at_k": 0.6,
                    "mean_mrr": 0.8,
                    "mean_ndcg_at_k": 0.75,
                    "num_tasks": 10,
                },
                "per_task_metrics": [],
            }

            metrics_file = run_dir / "retrieval_quality_metrics.json"
            with open(metrics_file, "w") as f:
                json.dump(metrics_data, f)

            # Analyze results
            analysis = analyze_pilot_results(results_dir)

            assert "type_aware_decay" in analysis["per_policy_metrics"]
            assert analysis["overall_metrics"]["mean_precision_at_k"] == pytest.approx(
                0.7, abs=0.01
            )
            assert "recommendations" in analysis
            assert "top_k" in analysis["recommendations"]
            assert "max_context_tokens" in analysis["recommendations"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
