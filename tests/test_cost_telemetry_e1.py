"""E1 — all-call cost & footprint telemetry (THESIS_REVIEW.md §5 E1).

The runner historically tracked ONLY the agent LLM call, so cost_summary.json
set ``pareto_cost_complete=False`` and the Pareto / H1b / H3 axes were invalid.
E1 surfaces usage from every cost-axis call type (agent + reflection + classifier
+ CLS consolidation + embeddings) into the CostTracker and flips the flag to
True. These tests pin each surfacing mechanism plus the runner wiring.

All offline / mocked — no live provider.
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch

from src.benchmark.models import Sequence, Task
from src.benchmark.sequence_runner import SequenceRunner
from src.memory.record import MemoryRecord
from src.metrics.cost_tracker import CostTracker, usage_from_chat_response


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _chat_resp(content: str, prompt_tokens: int, completion_tokens: int) -> Mock:
    """A Mock chat response mimicking the OpenAI SDK shape, with usage."""
    usage = Mock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    usage.total_tokens = prompt_tokens + completion_tokens
    msg = Mock()
    msg.content = content
    choice = Mock()
    choice.message = msg
    resp = Mock()
    resp.choices = [choice]
    resp.usage = usage
    return resp


def _chat_client(resp: Mock) -> Mock:
    client = Mock()
    client.chat.completions.create.return_value = resp
    return client


def _make_record(memory_id: str, sequence_index: int = 0) -> MemoryRecord:
    return MemoryRecord(
        memory_id=memory_id,
        task_id=f"task-{sequence_index}",
        repo="django/django",
        sequence_index=sequence_index,
        memory_type="bug_fix",
        outcome="pass",
        issue_summary="Issue summary about a null deref",
        patch_summary="add a guard clause",
        failure_summary=None,
        test_summary="tests passed",
        files_touched=["a/b.py"],
        functions_touched=["foo"],
        commands_run=["pytest"],
        retrieved_memory_ids_used=[],
        embedding_text="Issue: x\n\nPatch: y",
        embedding_vector_id="",
        token_length=8,
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


# ─────────────────────────────────────────────────────────────────────────────
# usage_from_chat_response
# ─────────────────────────────────────────────────────────────────────────────
class TestUsageFromChatResponse:
    def test_extracts_int_usage(self):
        resp = _chat_resp("{}", prompt_tokens=11, completion_tokens=7)
        assert usage_from_chat_response(resp) == (11, 7)

    def test_missing_usage_returns_zero(self):
        resp = Mock()
        resp.usage = None
        assert usage_from_chat_response(resp) == (0, 0)

    def test_non_numeric_usage_returns_zero(self):
        # A bare Mock auto-creates .usage.prompt_tokens as a Mock (not an int);
        # the helper must NOT raise and must report 0 rather than a Mock.
        assert usage_from_chat_response(Mock()) == (0, 0)


# ─────────────────────────────────────────────────────────────────────────────
# classifier — optional usage_sink
# ─────────────────────────────────────────────────────────────────────────────
class TestClassifierUsageSink:
    @patch("src.memory.classifier.get_aux_client")
    def test_classify_appends_usage_to_sink(self, mock_get_client):
        resp = _chat_resp(
            '{"memory_type": "bug_fix", "reasoning": "guard"}',
            prompt_tokens=40,
            completion_tokens=12,
        )
        mock_get_client.return_value = _chat_client(resp)

        from src.memory.classifier import MemoryClassifier

        sink: list[dict] = []
        result = MemoryClassifier().classify(
            issue_summary="i",
            patch_summary="p",
            files_touched=[],
            functions_touched=[],
            usage_sink=sink,
        )

        assert result == "bug_fix"
        assert len(sink) == 1
        entry = sink[0]
        assert entry["call_type"] == "classifier"
        assert entry["prompt_tokens"] == 40
        assert entry["completion_tokens"] == 12

    @patch("src.memory.classifier.get_aux_client")
    def test_classify_without_sink_still_works(self, mock_get_client):
        resp = _chat_resp(
            '{"memory_type": "config", "reasoning": "settings"}', 5, 5
        )
        mock_get_client.return_value = _chat_client(resp)

        from src.memory.classifier import MemoryClassifier

        # No usage_sink → unchanged behaviour, returns the type, no crash.
        assert MemoryClassifier().classify(
            issue_summary="i", patch_summary="p",
            files_touched=[], functions_touched=[],
        ) == "config"


# ─────────────────────────────────────────────────────────────────────────────
# reflection — usage_sink collects BOTH the reflection call and the classifier
# call it triggers internally
# ─────────────────────────────────────────────────────────────────────────────
class TestReflectionUsageSink:
    @patch("src.memory.classifier.get_aux_client")
    @patch("src.memory.reflection.get_aux_client")
    def test_collects_reflection_and_classifier_usage(
        self, mock_reflection_client, mock_classifier_client
    ):
        from src.memory.reflection import reflect_and_write_memory

        reflection_json = (
            '{"issue_summary": "s", "patch_summary": "p", '
            '"failure_summary": null, "test_summary": null, '
            '"functions_touched": ["foo"]}'
        )
        mock_reflection_client.return_value = _chat_client(
            _chat_resp(reflection_json, prompt_tokens=100, completion_tokens=30)
        )
        mock_classifier_client.return_value = _chat_client(
            _chat_resp(
                '{"memory_type": "bug_fix", "reasoning": "r"}',
                prompt_tokens=50,
                completion_tokens=8,
            )
        )

        task = Mock()
        task.task_id = "django__django-1"
        task.repo = "django/django"
        task.issue_text = "Fix bug"

        sink: list[dict] = []
        record = reflect_and_write_memory(
            task=task,
            trajectory={"files_modified": ["a.py"], "files_read": [],
                        "commands_run": ["pytest"], "functions_touched": []},
            patch="+fix",
            evaluation_result={"resolved": True, "error_message": None,
                               "test_output": "ok"},
            memory_store=Mock(),
            policy=Mock(name="full_memory"),
            retrieved_memory_ids=[],
            sequence_index=0,
            usage_sink=sink,
        )

        assert record is not None
        call_types = sorted(e["call_type"] for e in sink)
        assert call_types == ["classifier", "reflection"]
        reflection_entry = next(e for e in sink if e["call_type"] == "reflection")
        classifier_entry = next(e for e in sink if e["call_type"] == "classifier")
        assert reflection_entry["prompt_tokens"] == 100
        assert reflection_entry["completion_tokens"] == 30
        assert classifier_entry["prompt_tokens"] == 50
        assert classifier_entry["completion_tokens"] == 8


# ─────────────────────────────────────────────────────────────────────────────
# store — _generate_embedding instrumentation + drain
# ─────────────────────────────────────────────────────────────────────────────
class TestStoreEmbeddingUsage:
    def _store(self, tmp_path):
        from src.memory.store import MemoryStore

        return MemoryStore(
            run_id=str(tmp_path / "embrun"),
            policy_name="test",
            embedding_dim=8,
            embedding_model="nomic-embed-text-v2-moe",
        )

    def test_generate_embedding_records_usage_from_response(self, tmp_path):
        store = self._store(tmp_path)
        resp = Mock()
        item = Mock()
        item.embedding = [0.1] * 8
        resp.data = [item]
        usage = Mock()
        usage.total_tokens = 123
        usage.prompt_tokens = 123
        resp.usage = usage
        store.openai_client = Mock()
        store.openai_client.embeddings.create.return_value = resp

        store._generate_embedding("some text to embed")

        drained = store.drain_embedding_usage()
        assert len(drained) == 1
        assert drained[0]["model"] == "nomic-embed-text-v2-moe"
        assert drained[0]["tokens"] == 123
        # Drain clears the buffer.
        assert store.drain_embedding_usage() == []

    def test_generate_embedding_falls_back_to_tiktoken_when_usage_absent(self, tmp_path):
        store = self._store(tmp_path)
        resp = Mock()
        item = Mock()
        item.embedding = [0.2] * 8
        resp.data = [item]
        resp.usage = Mock()  # .total_tokens is a Mock → not an int → fallback
        store.openai_client = Mock()
        store.openai_client.embeddings.create.return_value = resp

        store._generate_embedding("hello world this is a longer piece of text")

        drained = store.drain_embedding_usage()
        assert len(drained) == 1
        # tiktoken count of the text — must be a positive int (no Mock leakage).
        assert isinstance(drained[0]["tokens"], int)
        assert drained[0]["tokens"] > 0


# ─────────────────────────────────────────────────────────────────────────────
# CLS consolidation — usage drain
# ─────────────────────────────────────────────────────────────────────────────
class TestCLSConsolidationUsage:
    @patch("src.memory.policies.cls_consolidation.get_aux_client")
    def test_generate_summary_records_consolidation_usage(self, mock_get_client):
        from src.memory.policies.cls_consolidation import CLSConsolidationPolicy

        consolidation_json = (
            '{"summary": "s", "common_files": ["a.py"], '
            '"recurring_pattern": "p", "successful_strategy": "x", '
            '"failure_traps": "t", "test_commands": ["pytest"]}'
        )
        mock_get_client.return_value = _chat_client(
            _chat_resp(consolidation_json, prompt_tokens=300, completion_tokens=90)
        )

        policy = CLSConsolidationPolicy(max_records=10)
        cluster = [_make_record(f"M{i}", sequence_index=i) for i in range(3)]

        policy._generate_summary(cluster)

        drained = policy.drain_consolidation_usage()
        assert len(drained) == 1
        assert drained[0]["call_type"] == "consolidation"
        assert drained[0]["prompt_tokens"] == 300
        assert drained[0]["completion_tokens"] == 90
        assert policy.drain_consolidation_usage() == []


# ─────────────────────────────────────────────────────────────────────────────
# CostTracker.mark_pareto_cost_complete
# ─────────────────────────────────────────────────────────────────────────────
class TestParetoCostCompleteFlag:
    def test_mark_sets_flag_on_run_summary(self, tmp_path):
        ct = CostTracker(run_id="r", run_dir=tmp_path, cost_metric_mode="tokens")
        ct.start_run(policy="full_memory", sequence_name="seq", seed=1)
        assert ct.run_summary.pareto_cost_complete is False  # honest default
        ct.mark_pareto_cost_complete()
        assert ct.run_summary.pareto_cost_complete is True

    def test_flag_persists_to_written_summary(self, tmp_path):
        ct = CostTracker(run_id="r", run_dir=tmp_path, cost_metric_mode="tokens")
        ct.start_run(policy="full_memory", sequence_name="seq", seed=1)
        ct.mark_pareto_cost_complete()
        ct.complete_run()
        data = json.loads(Path(ct.write_cost_summary()).read_text())
        assert data["pareto_cost_complete"] is True


# ─────────────────────────────────────────────────────────────────────────────
# runner wiring — _track_memory_phase_costs aggregates all buckets; run_sequence
# marks the run cost-complete
# ─────────────────────────────────────────────────────────────────────────────
def _runner(tmp_path, monkeypatch, policy_name="full_memory") -> SequenceRunner:
    monkeypatch.chdir(tmp_path)
    policy = Mock()
    policy.name = policy_name
    config = {
        "memory": {"embedding_dim": 8, "top_k": 5, "max_context_tokens": 2000},
        "evaluation": {"cost_metric_mode": "tokens"},
    }
    return SequenceRunner(run_id="costrun", policy=policy, config=config)


class TestRunnerCostAggregation:
    def test_track_memory_phase_costs_aggregates_all_buckets(self, tmp_path, monkeypatch):
        runner = _runner(tmp_path, monkeypatch)
        runner.cost_tracker.start_run(policy="full_memory", sequence_name="s", seed=1)
        runner.cost_tracker.start_task("t1")

        # Reflection + classifier usage arriving via the per-task usage sink.
        usage_sink = [
            {"call_type": "reflection", "model": "kimi", "prompt_tokens": 100, "completion_tokens": 30},
            {"call_type": "classifier", "model": "kimi", "prompt_tokens": 50, "completion_tokens": 8},
        ]
        # Consolidation usage drained from the policy.
        runner.policy.drain_consolidation_usage = Mock(return_value=[
            {"call_type": "consolidation", "model": "kimi", "prompt_tokens": 300, "completion_tokens": 90},
        ])
        # Embedding usage drained from the store.
        monkeypatch.setattr(
            runner.memory_store, "drain_embedding_usage",
            Mock(return_value=[{"model": "nomic", "tokens": 64}, {"model": "nomic", "tokens": 8}]),
        )

        runner._track_memory_phase_costs("t1", usage_sink)

        task_cost = runner.cost_tracker.get_task_cost("t1")
        assert task_cost.reflection_tokens == 130
        assert task_cost.classifier_tokens == 58
        assert task_cost.consolidation_tokens == 390
        assert task_cost.embedding_tokens == 72
        assert task_cost.embedding_calls == 2

    def test_run_sequence_marks_pareto_cost_complete(self, tmp_path, monkeypatch):
        runner = _runner(tmp_path, monkeypatch, policy_name="no_memory")
        fake = Mock(resolved=1, timeout=False, estimated_cost_usd=0.0)
        monkeypatch.setattr(runner, "_execute_task", lambda task, seed: fake)

        # Sequence enforces >= 15 tasks (frozen decision #1).
        tasks = [
            Task(
                task_id=f"django__django-{i}", repo="django/django",
                base_commit="c0", issue_text="issue", test_patch="",
                gold_patch="", created_at="2020-01-01T00:00:00Z",
                sequence_index=i, difficulty_label="easy",
            )
            for i in range(15)
        ]
        seq = Sequence(
            sequence_name="django_django_sequence",
            repo="django/django",
            tasks=tasks,
            task_count=15,
        )
        runner.run_sequence(seq, seed=1)

        data = json.loads((Path("runs") / "costrun" / "cost_summary.json").read_text())
        assert data["pareto_cost_complete"] is True
