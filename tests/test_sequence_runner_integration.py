"""Integration tests for SequenceRunner's handling of policy retrieval tuples
and archive-delta logging (build-to-pilot plan 2.1 + 2.6 / repair-plan Tasks 1 & 5).

policy.retrieve() returns list[tuple[float, MemoryRecord]]; the runner must
normalize these to log fields (ids/scores/types/ages) without calling .get(),
and must record the prune delta captured around policy.maintain().
"""

from pathlib import Path
from unittest.mock import Mock

from src.benchmark.models import Task
from src.benchmark.sequence_runner import SequenceRunner
from src.memory.record import MemoryRecord


def make_record(memory_id: str, sequence_index: int = 0) -> MemoryRecord:
    return MemoryRecord(
        memory_id=memory_id,
        task_id=f"task-{sequence_index}",
        repo="django/django",
        sequence_index=sequence_index,
        memory_type="bug_fix",
        outcome="pass",
        issue_summary="Issue summary",
        patch_summary="diff --git a/file.py b/file.py",
        failure_summary=None,
        test_summary="tests passed",
        files_touched=["file.py"],
        functions_touched=[],
        commands_run=["pytest"],
        retrieved_memory_ids_used=[],
        embedding_text="Issue:\nIssue summary\nDiff:\ndiff --git a/file.py b/file.py",
        embedding_vector_id="",
        token_length=16,
        raw_trace_ref=None,
        use_count=0,
        last_retrieved_at_step=None,
        success_after_retrieval_count=0,
        failure_after_retrieval_count=0,
        importance_score=0.0,
        is_consolidated=False,
        source_memory_ids=None,
        is_archived=False,
        archived_reason=None,
        archived_at_step=None,
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
    )


def make_task(sequence_index: int = 3) -> Task:
    return Task(
        task_id="django__django-1",
        repo="django/django",
        base_commit="abc123",
        issue_text="Fix bug",
        test_patch="",
        gold_patch="",
        created_at="2024-01-01T00:00:00Z",
        sequence_index=sequence_index,
        difficulty_label="medium",
    )


AGENT_RESULT = {
    "patch_generated": True,
    "syntax_error": False,
    "timeout": False,
    "prompt_tokens": 10,
    "completion_tokens": 5,
    "total_tokens": 15,
    "estimated_cost_usd": 0.01,
    "tool_calls": 2,
    "test_runs": 1,
    "files_read": ["file.py"],
    "files_modified": ["file.py"],
    "error_message": None,
}


def make_runner(tmp_path: Path, monkeypatch) -> SequenceRunner:
    monkeypatch.chdir(tmp_path)  # isolate runs/ under tmp
    policy = Mock()
    policy.name = "full_memory"
    config = {
        "memory": {"top_k": 5, "max_context_tokens": 2000},
        "evaluation": {"docker_image": "fake", "timeout_seconds": 1},
        "experiment": {"pilot_mode": {"enabled": False, "log_retrieval_quality": False}},
    }
    return SequenceRunner(run_id="test-run", policy=policy, config=config)


def test_build_task_result_accepts_policy_retrieval_tuples(tmp_path, monkeypatch):
    runner = make_runner(tmp_path, monkeypatch)
    task = make_task(sequence_index=3)
    memories = [(0.72, make_record("MEM-001", sequence_index=1))]

    result = runner._build_task_result(
        task=task,
        seed=1,
        agent_result=AGENT_RESULT,
        eval_result={"resolved": 1},
        retrieved_memories=memories,
        memory_stats_before={"active_count": 1, "total_tokens": 16},
        memory_stats_after={"active_count": 2, "total_tokens": 32},
        task_wall_time=1.5,
        pruned_memory_ids=[],
        consolidated_memory_ids=[],
    )

    assert result.retrieved_memory_ids == ["MEM-001"]
    assert result.retrieved_memory_scores == [0.72]
    assert result.retrieved_memory_types == ["bug_fix"]
    assert result.retrieved_memory_ages == [2]


def test_reflect_and_write_extracts_ids_from_policy_retrieval_tuples(tmp_path, monkeypatch):
    runner = make_runner(tmp_path, monkeypatch)
    task = make_task(sequence_index=3)
    memories = [(0.72, make_record("MEM-001", sequence_index=1))]
    captured = {}

    def fake_reflect_and_write_memory(**kwargs):
        captured["retrieved_memory_ids"] = kwargs["retrieved_memory_ids"]
        return None

    monkeypatch.setattr(
        "src.benchmark.sequence_runner.reflect_and_write_memory",
        fake_reflect_and_write_memory,
    )

    runner._reflect_and_write(
        task=task,
        agent_result={"trajectory": [], "patch": "diff"},
        eval_result={"resolved": 1, "error": None},
        retrieved_memories=memories,
    )

    assert captured["retrieved_memory_ids"] == ["MEM-001"]


def test_build_task_result_records_pruned_memory_ids(tmp_path, monkeypatch):
    runner = make_runner(tmp_path, monkeypatch)
    task = make_task(sequence_index=3)

    result = runner._build_task_result(
        task=task,
        seed=1,
        agent_result=AGENT_RESULT,
        eval_result={"resolved": 1},
        retrieved_memories=[],
        memory_stats_before={"active_count": 1, "total_tokens": 16},
        memory_stats_after={"active_count": 1, "total_tokens": 16},
        task_wall_time=1.5,
        pruned_memory_ids=["MEM-OLD"],
        consolidated_memory_ids=[],
    )

    assert result.pruned_memory_ids == ["MEM-OLD"]
    assert result.consolidated_memory_ids == []


def test_log_trajectory_writes_actions_only(tmp_path, monkeypatch):
    """plan 5.4: per-task trajectory file (v5 §11.3) — actions + observations, no CoT."""
    import json
    from pathlib import Path

    runner = make_runner(tmp_path, monkeypatch)
    task = make_task(sequence_index=3)
    agent_result = {
        "trajectory": [
            {"action": "read_file", "action_input": {"path": "a.py"}, "observation_summary": "120 lines"},
            {"action": "write_file", "action_input": {"path": "a.py"}, "observation_summary": "Wrote a.py"},
        ]
    }

    runner._log_trajectory(task=task, seed=2, agent_result=agent_result)

    path = Path("runs") / "test-run" / "trajectories" / f"{task.task_id}.json"
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["task_id"] == task.task_id
    assert data["seed"] == 2
    assert [s["action"] for s in data["steps"]] == ["read_file", "write_file"]
    assert data["steps"][0]["step"] == 1
    assert all("reasoning" not in s and "thought" not in s for s in data["steps"])
