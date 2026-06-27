"""Tests for the CostTracker `reflection` call_type and the cost_summary.json
wiring into SequenceRunner (build-to-pilot Commit 4b, Phase 5.3a/5.3c).

cost_summary.json is the 4th mandatory log stream (v5 §11). The Pareto cost
axis (v5 §1570) is total tokens under D3.
"""

import json
from pathlib import Path
from unittest.mock import Mock

from src.benchmark.models import Sequence, Task
from src.benchmark.sequence_runner import SequenceRunner
from src.metrics.cost_tracker import CostTracker


def test_reflection_call_type_is_tracked(tmp_path):
    """A 'reflection' LLM call lands in the reflection buckets (not warned-away)."""
    ct = CostTracker(run_id="r", run_dir=tmp_path, cost_metric_mode="tokens")
    ct.start_run(policy="full_memory", sequence_name="seq", seed=1)
    ct.start_task("t1")
    ct.track_llm_call(
        call_type="reflection",
        model="gpt-oss:20b-cloud",   # unknown to PRICING; tokens mode -> 0 usd, no raise
        prompt_tokens=100,
        completion_tokens=50,
        task_id="t1",
    )
    ct.complete_task("t1")
    ct.complete_run()
    path = ct.write_cost_summary()

    data = json.loads(Path(path).read_text())
    assert data["reflection_cost"] == 0.0          # tokens mode, unknown model
    assert data["total_tokens"] == 150             # tokens always accumulate
    assert data["task_costs"][0]["reflection_calls"] == 1
    assert data["task_costs"][0]["reflection_tokens"] == 150


def _easy_tasks(n: int, repo: str = "django/django") -> list[Task]:
    return [
        Task(
            task_id=f"django__django-{i}",
            repo=repo,
            base_commit="c0",
            issue_text="issue",
            test_patch="",
            gold_patch="",
            created_at="2020-01-01T00:00:00Z",
            sequence_index=i,
            difficulty_label="easy",
        )
        for i in range(n)
    ]


def test_run_sequence_writes_cost_summary(tmp_path, monkeypatch):
    """run_sequence produces runs/<run_id>/cost_summary.json (4th log stream)."""
    monkeypatch.chdir(tmp_path)  # isolate runs/ under tmp
    policy = Mock()
    policy.name = "no_memory"
    config = {
        "memory": {"embedding_dim": 768},
        "evaluation": {"cost_metric_mode": "tokens"},
    }
    runner = SequenceRunner(run_id="smoke_r", policy=policy, config=config)
    assert isinstance(runner.cost_tracker, CostTracker)

    # Mock the heavy per-task pipeline; we only assert the cost stream is flushed.
    fake = Mock(resolved=1, timeout=False, estimated_cost_usd=0.0)
    monkeypatch.setattr(runner, "_execute_task", lambda task, seed: fake)

    seq = Sequence(
        sequence_name="django_django_sequence",
        repo="django/django",
        tasks=_easy_tasks(15),
        task_count=15,
    )
    runner.run_sequence(seq, seed=1)

    cost_path = Path("runs") / "smoke_r" / "cost_summary.json"
    assert cost_path.exists(), "cost_summary.json (4th mandatory log stream) not written"
    data = json.loads(cost_path.read_text())
    assert data["run_id"] == "smoke_r"
    assert data["policy"] == "no_memory"
    assert data["sequence_name"] == "django_django_sequence"
    assert "total_tokens" in data
    assert "reflection_cost" in data  # enum extension present in schema
    assert data["end_time"] is not None  # complete_run() ran before write
