"""Tests for cost tracking functionality.

Requirements: 27
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.metrics.cost_tracker import (
    PRICING,
    CostTracker,
    EmbeddingCallCost,
    LLMCallCost,
    RunCostSummary,
    TaskCostSummary,
    check_budget_alert,
    generate_daily_cost_report,
)


class TestLLMCallCost:
    """Tests for LLMCallCost dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        cost = LLMCallCost(
            call_id="llm_001",
            call_type="agent",
            model="gpt-4o-mini",
            prompt_tokens=1000,
            completion_tokens=500,
            total_tokens=1500,
            estimated_cost_usd=0.0009,
            timestamp="2024-01-01T00:00:00",
            task_id="task_001",
            metadata={"temperature": 0},
        )

        result = cost.to_dict()

        assert result["call_id"] == "llm_001"
        assert result["call_type"] == "agent"
        assert result["model"] == "gpt-4o-mini"
        assert result["prompt_tokens"] == 1000
        assert result["completion_tokens"] == 500
        assert result["total_tokens"] == 1500
        assert result["estimated_cost_usd"] == 0.0009
        assert result["task_id"] == "task_001"
        assert result["metadata"]["temperature"] == 0


class TestEmbeddingCallCost:
    """Tests for EmbeddingCallCost dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        cost = EmbeddingCallCost(
            call_id="emb_001",
            model="text-embedding-3-small",
            tokens=500,
            estimated_cost_usd=0.00001,
            timestamp="2024-01-01T00:00:00",
            task_id="task_001",
            memory_id="mem_001",
            metadata={},
        )

        result = cost.to_dict()

        assert result["call_id"] == "emb_001"
        assert result["model"] == "text-embedding-3-small"
        assert result["tokens"] == 500
        assert result["estimated_cost_usd"] == 0.00001
        assert result["task_id"] == "task_001"
        assert result["memory_id"] == "mem_001"


class TestTaskCostSummary:
    """Tests for TaskCostSummary dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        summary = TaskCostSummary(
            task_id="task_001",
            agent_llm_cost=0.001,
            classifier_cost=0.0001,
            consolidation_cost=0.0,
            embedding_cost=0.00001,
            total_cost=0.00111,
            agent_llm_calls=2,
            classifier_calls=1,
            consolidation_calls=0,
            embedding_calls=1,
            agent_tokens=1500,
            classifier_tokens=200,
            consolidation_tokens=0,
            embedding_tokens=500,
        )

        result = summary.to_dict()

        assert result["task_id"] == "task_001"
        assert result["agent_llm_cost"] == 0.001
        assert result["classifier_cost"] == 0.0001
        assert result["total_cost"] == 0.00111
        assert result["agent_llm_calls"] == 2
        assert result["classifier_calls"] == 1


class TestRunCostSummary:
    """Tests for RunCostSummary dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        task_cost = TaskCostSummary(task_id="task_001", total_cost=0.001)

        summary = RunCostSummary(
            run_id="run_001",
            policy="type_aware_decay",
            sequence_name="django",
            seed=1,
            total_cost=0.001,
            agent_llm_cost=0.0009,
            classifier_cost=0.0001,
            consolidation_cost=0.0,
            embedding_cost=0.00001,
            total_llm_calls=3,
            total_embedding_calls=1,
            total_tokens=2000,
            tasks_completed=1,
            start_time="2024-01-01T00:00:00",
            end_time="2024-01-01T01:00:00",
            task_costs=[task_cost],
        )

        result = summary.to_dict()

        assert result["run_id"] == "run_001"
        assert result["policy"] == "type_aware_decay"
        assert result["sequence_name"] == "django"
        assert result["seed"] == 1
        assert result["total_cost"] == 0.001
        assert result["tasks_completed"] == 1
        assert len(result["task_costs"]) == 1


class TestCostTracker:
    """Tests for CostTracker class."""

    @pytest.fixture
    def temp_run_dir(self):
        """Create temporary run directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def tracker(self, temp_run_dir):
        """Create CostTracker instance."""
        return CostTracker(run_id="test_run", run_dir=temp_run_dir)

    def test_initialization(self, tracker, temp_run_dir):
        """Test tracker initialization."""
        assert tracker.run_id == "test_run"
        assert tracker.run_dir == temp_run_dir
        assert len(tracker.llm_calls) == 0
        assert len(tracker.embedding_calls) == 0
        assert len(tracker.task_costs) == 0
        assert tracker.run_summary is None

    def test_start_run(self, tracker):
        """Test starting a run."""
        tracker.start_run(policy="type_aware_decay", sequence_name="django", seed=1)

        assert tracker.run_summary is not None
        assert tracker.run_summary.run_id == "test_run"
        assert tracker.run_summary.policy == "type_aware_decay"
        assert tracker.run_summary.sequence_name == "django"
        assert tracker.run_summary.seed == 1
        assert tracker.run_summary.start_time is not None

    def test_track_llm_call_agent(self, tracker):
        """Test tracking agent LLM call."""
        tracker.start_run(policy="test_policy", sequence_name="test_seq", seed=1)

        cost = tracker.track_llm_call(
            call_type="agent",
            model="gpt-4o-mini",
            prompt_tokens=1000,
            completion_tokens=500,
            task_id="task_001",
        )

        # Verify cost calculation
        expected_cost = (1000 / 1_000_000) * PRICING["gpt-4o-mini"]["input"] + \
                       (500 / 1_000_000) * PRICING["gpt-4o-mini"]["output"]

        assert cost.call_type == "agent"
        assert cost.model == "gpt-4o-mini"
        assert cost.prompt_tokens == 1000
        assert cost.completion_tokens == 500
        assert cost.total_tokens == 1500
        assert cost.estimated_cost_usd == pytest.approx(expected_cost)
        assert cost.task_id == "task_001"

        # Verify tracking
        assert len(tracker.llm_calls) == 1
        assert tracker.run_summary.total_llm_calls == 1
        assert tracker.run_summary.agent_llm_cost == pytest.approx(expected_cost)
        assert tracker.run_summary.total_cost == pytest.approx(expected_cost)

    def test_track_llm_call_classifier(self, tracker):
        """Test tracking classifier LLM call."""
        tracker.start_run(policy="test_policy", sequence_name="test_seq", seed=1)

        cost = tracker.track_llm_call(
            call_type="classifier",
            model="gpt-4o-mini",
            prompt_tokens=200,
            completion_tokens=50,
            task_id="task_001",
        )

        expected_cost = (200 / 1_000_000) * PRICING["gpt-4o-mini"]["input"] + \
                       (50 / 1_000_000) * PRICING["gpt-4o-mini"]["output"]

        assert cost.call_type == "classifier"
        assert cost.estimated_cost_usd == pytest.approx(expected_cost)
        assert tracker.run_summary.classifier_cost == pytest.approx(expected_cost)

    def test_track_llm_call_consolidation(self, tracker):
        """Test tracking consolidation LLM call."""
        tracker.start_run(policy="test_policy", sequence_name="test_seq", seed=1)

        cost = tracker.track_llm_call(
            call_type="consolidation",
            model="gpt-4o-mini",
            prompt_tokens=500,
            completion_tokens=200,
            task_id="task_001",
        )

        expected_cost = (500 / 1_000_000) * PRICING["gpt-4o-mini"]["input"] + \
                       (200 / 1_000_000) * PRICING["gpt-4o-mini"]["output"]

        assert cost.call_type == "consolidation"
        assert cost.estimated_cost_usd == pytest.approx(expected_cost)
        assert tracker.run_summary.consolidation_cost == pytest.approx(expected_cost)

    def test_track_llm_call_invalid_model(self, tracker):
        """Test tracking LLM call with invalid model."""
        tracker.start_run(policy="test_policy", sequence_name="test_seq", seed=1)

        with pytest.raises(ValueError, match="No pricing available"):
            tracker.track_llm_call(
                call_type="agent",
                model="invalid-model",
                prompt_tokens=1000,
                completion_tokens=500,
            )

    def test_track_embedding_call(self, tracker):
        """Test tracking embedding call."""
        tracker.start_run(policy="test_policy", sequence_name="test_seq", seed=1)

        cost = tracker.track_embedding_call(
            model="text-embedding-3-small",
            tokens=500,
            task_id="task_001",
            memory_id="mem_001",
        )

        expected_cost = (500 / 1_000_000) * PRICING["text-embedding-3-small"]["input"]

        assert cost.model == "text-embedding-3-small"
        assert cost.tokens == 500
        assert cost.estimated_cost_usd == pytest.approx(expected_cost)
        assert cost.task_id == "task_001"
        assert cost.memory_id == "mem_001"

        # Verify tracking
        assert len(tracker.embedding_calls) == 1
        assert tracker.run_summary.total_embedding_calls == 1
        assert tracker.run_summary.embedding_cost == pytest.approx(expected_cost)

    def test_track_embedding_call_invalid_model(self, tracker):
        """Test tracking embedding call with invalid model."""
        tracker.start_run(policy="test_policy", sequence_name="test_seq", seed=1)

        with pytest.raises(ValueError, match="No pricing available"):
            tracker.track_embedding_call(
                model="invalid-embedding-model",
                tokens=500,
            )

    def test_task_cost_aggregation(self, tracker):
        """Test task-level cost aggregation."""
        tracker.start_run(policy="test_policy", sequence_name="test_seq", seed=1)
        tracker.start_task("task_001")

        # Track multiple calls for same task
        tracker.track_llm_call(
            call_type="agent",
            model="gpt-4o-mini",
            prompt_tokens=1000,
            completion_tokens=500,
            task_id="task_001",
        )

        tracker.track_llm_call(
            call_type="classifier",
            model="gpt-4o-mini",
            prompt_tokens=200,
            completion_tokens=50,
            task_id="task_001",
        )

        tracker.track_embedding_call(
            model="text-embedding-3-small",
            tokens=500,
            task_id="task_001",
        )

        # Complete task
        task_cost = tracker.complete_task("task_001")

        # Verify aggregation
        assert task_cost.task_id == "task_001"
        assert task_cost.agent_llm_calls == 1
        assert task_cost.classifier_calls == 1
        assert task_cost.embedding_calls == 1
        assert task_cost.agent_tokens == 1500
        assert task_cost.classifier_tokens == 250
        assert task_cost.embedding_tokens == 500
        assert task_cost.total_cost > 0

    def test_complete_run(self, tracker):
        """Test completing a run."""
        tracker.start_run(policy="test_policy", sequence_name="test_seq", seed=1)

        # Track some calls
        tracker.start_task("task_001")
        tracker.track_llm_call(
            call_type="agent",
            model="gpt-4o-mini",
            prompt_tokens=1000,
            completion_tokens=500,
            task_id="task_001",
        )
        tracker.complete_task("task_001")

        # Complete run
        run_summary = tracker.complete_run()

        assert run_summary.run_id == "test_run"
        assert run_summary.tasks_completed == 1
        assert run_summary.end_time is not None
        assert run_summary.total_cost > 0

    def test_write_cost_summary(self, tracker, temp_run_dir):
        """Test writing cost summary to file."""
        tracker.start_run(policy="test_policy", sequence_name="test_seq", seed=1)

        # Track some calls
        tracker.start_task("task_001")
        tracker.track_llm_call(
            call_type="agent",
            model="gpt-4o-mini",
            prompt_tokens=1000,
            completion_tokens=500,
            task_id="task_001",
        )
        tracker.complete_task("task_001")
        tracker.complete_run()

        # Write summary
        summary_file = tracker.write_cost_summary()

        # Verify file exists
        assert summary_file.exists()
        assert summary_file == temp_run_dir / "cost_summary.json"

        # Verify content
        with open(summary_file) as f:
            data = json.load(f)

        assert data["run_id"] == "test_run"
        assert data["policy"] == "test_policy"
        assert data["sequence_name"] == "test_seq"
        assert data["seed"] == 1
        assert data["tasks_completed"] == 1
        assert data["total_cost"] > 0
        assert len(data["task_costs"]) == 1

    def test_get_task_cost(self, tracker):
        """Test getting task cost."""
        tracker.start_run(policy="test_policy", sequence_name="test_seq", seed=1)
        tracker.start_task("task_001")
        tracker.track_llm_call(
            call_type="agent",
            model="gpt-4o-mini",
            prompt_tokens=1000,
            completion_tokens=500,
            task_id="task_001",
        )

        task_cost = tracker.get_task_cost("task_001")

        assert task_cost is not None
        assert task_cost.task_id == "task_001"
        assert task_cost.agent_llm_calls == 1

        # Non-existent task
        assert tracker.get_task_cost("task_999") is None

    def test_get_run_cost(self, tracker):
        """Test getting run cost."""
        # Before start_run
        assert tracker.get_run_cost() is None

        # After start_run
        tracker.start_run(policy="test_policy", sequence_name="test_seq", seed=1)
        run_cost = tracker.get_run_cost()

        assert run_cost is not None
        assert run_cost.run_id == "test_run"
        assert run_cost.policy == "test_policy"


class TestDailyCostReport:
    """Tests for daily cost report generation."""

    @pytest.fixture
    def temp_runs_dir(self):
        """Create temporary runs directory with sample data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runs_dir = Path(tmpdir)

            # Create sample run directories with cost summaries
            for i in range(3):
                run_dir = runs_dir / f"run_{i:03d}"
                run_dir.mkdir()

                summary = {
                    "run_id": f"run_{i:03d}",
                    "policy": "type_aware_decay" if i % 2 == 0 else "full_memory",
                    "sequence_name": "django",
                    "seed": i,
                    "total_cost": 10.0 + i,
                    "agent_llm_cost": 8.0 + i,
                    "classifier_cost": 1.0,
                    "consolidation_cost": 0.5,
                    "embedding_cost": 0.5,
                    "total_llm_calls": 100,
                    "total_embedding_calls": 50,
                    "total_tokens": 100000,
                    "tasks_completed": 10,
                    "start_time": f"2024-01-0{i+1}T00:00:00",
                    "end_time": f"2024-01-0{i+1}T01:00:00",
                    "task_costs": [],
                }

                with open(run_dir / "cost_summary.json", "w") as f:
                    json.dump(summary, f)

            yield runs_dir

    def test_generate_daily_cost_report(self, temp_runs_dir):
        """Test generating daily cost report."""
        report = generate_daily_cost_report(temp_runs_dir)

        assert report["total_runs"] == 3
        assert report["total_cost"] == pytest.approx(33.0)  # 10 + 11 + 12

        # Check cost by policy
        assert "type_aware_decay" in report["cost_by_policy"]
        assert "full_memory" in report["cost_by_policy"]
        assert report["cost_by_policy"]["type_aware_decay"] == pytest.approx(22.0)  # 10 + 12
        assert report["cost_by_policy"]["full_memory"] == pytest.approx(11.0)

        # Check cost by date
        assert "2024-01-01" in report["cost_by_date"]
        assert "2024-01-02" in report["cost_by_date"]
        assert "2024-01-03" in report["cost_by_date"]

        # Check runs list
        assert len(report["runs"]) == 3

        # Verify report file was written
        report_file = temp_runs_dir / "daily_cost_report.json"
        assert report_file.exists()

    def test_generate_daily_cost_report_empty_dir(self):
        """Test generating report with no runs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report = generate_daily_cost_report(tmpdir)

            assert report["total_runs"] == 0
            assert report["total_cost"] == 0.0
            assert len(report["cost_by_policy"]) == 0
            assert len(report["cost_by_date"]) == 0

    def test_generate_daily_cost_report_nonexistent_dir(self):
        """Test generating report with nonexistent directory."""
        report = generate_daily_cost_report("/nonexistent/path")

        assert report["total_runs"] == 0
        assert report["total_cost"] == 0.0


class TestBudgetAlert:
    """Tests for budget alert functionality."""

    @pytest.fixture
    def temp_runs_dir_with_costs(self):
        """Create temporary runs directory with sample data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runs_dir = Path(tmpdir)

            # Create run with today's date
            from datetime import datetime
            today = datetime.utcnow().strftime("%Y-%m-%d")

            run_dir = runs_dir / "run_001"
            run_dir.mkdir()

            summary = {
                "run_id": "run_001",
                "policy": "type_aware_decay",
                "sequence_name": "django",
                "seed": 1,
                "total_cost": 150.0,
                "agent_llm_cost": 120.0,
                "classifier_cost": 20.0,
                "consolidation_cost": 5.0,
                "embedding_cost": 5.0,
                "total_llm_calls": 1000,
                "total_embedding_calls": 500,
                "total_tokens": 1000000,
                "tasks_completed": 50,
                "start_time": f"{today}T00:00:00",
                "end_time": f"{today}T01:00:00",
                "task_costs": [],
            }

            with open(run_dir / "cost_summary.json", "w") as f:
                json.dump(summary, f)

            yield runs_dir

    def test_check_budget_alert_no_alert(self, temp_runs_dir_with_costs):
        """Test budget check with no alerts."""
        alert = check_budget_alert(
            temp_runs_dir_with_costs,
            daily_budget=200.0,
            total_budget=1000.0,
        )

        assert alert["daily_cost"] == 150.0
        assert alert["total_cost"] == 150.0
        assert alert["daily_budget"] == 200.0
        assert alert["total_budget"] == 1000.0
        assert alert["daily_alert"] is False
        assert alert["total_alert"] is False
        assert alert["daily_remaining"] == 50.0
        assert alert["total_remaining"] == 850.0

    def test_check_budget_alert_daily_exceeded(self, temp_runs_dir_with_costs):
        """Test budget check with daily budget exceeded."""
        alert = check_budget_alert(
            temp_runs_dir_with_costs,
            daily_budget=100.0,
            total_budget=1000.0,
        )

        assert alert["daily_alert"] is True
        assert alert["total_alert"] is False
        assert alert["daily_remaining"] == 0.0

    def test_check_budget_alert_total_exceeded(self, temp_runs_dir_with_costs):
        """Test budget check with total budget exceeded."""
        alert = check_budget_alert(
            temp_runs_dir_with_costs,
            daily_budget=200.0,
            total_budget=100.0,
        )

        assert alert["daily_alert"] is False
        assert alert["total_alert"] is True
        assert alert["total_remaining"] == 0.0

    def test_check_budget_alert_both_exceeded(self, temp_runs_dir_with_costs):
        """Test budget check with both budgets exceeded."""
        alert = check_budget_alert(
            temp_runs_dir_with_costs,
            daily_budget=100.0,
            total_budget=100.0,
        )

        assert alert["daily_alert"] is True
        assert alert["total_alert"] is True


class TestPricingConstants:
    """Tests for pricing constants."""

    def test_pricing_structure(self):
        """Test that pricing dictionary has expected structure."""
        assert "gpt-4o-mini" in PRICING
        assert "gpt-4o" in PRICING
        assert "text-embedding-3-small" in PRICING
        assert "text-embedding-3-large" in PRICING

        # Check GPT-4o-mini pricing
        assert "input" in PRICING["gpt-4o-mini"]
        assert "output" in PRICING["gpt-4o-mini"]
        assert PRICING["gpt-4o-mini"]["input"] == 0.150
        assert PRICING["gpt-4o-mini"]["output"] == 0.600

        # Check embedding pricing
        assert "input" in PRICING["text-embedding-3-small"]
        assert "output" in PRICING["text-embedding-3-small"]
        assert PRICING["text-embedding-3-small"]["input"] == 0.020
        assert PRICING["text-embedding-3-small"]["output"] == 0.0

    def test_cost_calculation_accuracy(self):
        """Test that cost calculations are accurate."""
        # GPT-4o-mini: 1000 input + 500 output tokens
        input_cost = (1000 / 1_000_000) * 0.150
        output_cost = (500 / 1_000_000) * 0.600
        total_cost = input_cost + output_cost

        assert input_cost == pytest.approx(0.00015)
        assert output_cost == pytest.approx(0.0003)
        assert total_cost == pytest.approx(0.00045)

        # text-embedding-3-small: 500 tokens
        embedding_cost = (500 / 1_000_000) * 0.020
        assert embedding_cost == pytest.approx(0.00001)
