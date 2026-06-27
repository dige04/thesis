# Memory Runner Integration Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the memory retrieval, reflection, pruning, and runner logging path internally consistent so non-`no_memory` sequence execution can produce trustworthy v5 artifacts.

**Architecture:** Keep retrieval policy APIs returning `list[tuple[float, MemoryRecord]]`; normalize only at logging and prompt boundaries. Make `MemoryStore` the owner of canonical embedding construction, same-repo similarity search, persisted importance scores, and archive metadata. Keep event and snapshot logging in `SequenceRunner`, where current task context is available.

**Tech Stack:** Python 3.11, pytest, SQLite, FAISS, NumPy, existing `src.memory`, `src.benchmark.sequence_runner`, and `src.logging` modules.

---

## Scope

This plan covers the first repair slice from the review swarm:

- Fix retrieval tuple/dict contract in `SequenceRunner`.
- Fix same-repo FAISS search so valid same-repo candidates cannot be hidden by cross-repo vectors.
- Fix reflection-to-store embedding construction and `token_length`.
- Persist Type-Aware Decay importance scores.
- Record archive deltas into snapshots and task logs.

This plan does not implement the real coding agent, real eval_v3 command, or analysis/statistics fixes. Those are independent follow-up plans.

## File Structure

- Modify `src/benchmark/sequence_runner.py`: normalize retrieved memory tuples for reflection, task logs, and retrieval quality; capture archive deltas around `policy.maintain()`.
- Modify `src/memory/store.py`: add exact candidate scoring for same-repo retrieval; expose archived IDs by step; make `archive()` return metadata.
- Modify `src/memory/reflection.py`: stop pre-setting `embedding_text`; let `MemoryStore.add()` construct canonical payload and token count.
- Modify `src/memory/policies/type_aware_decay.py`: persist computed `importance_score` values through `memory_store.update_importance_score()`.
- Modify `tests/test_memory_store.py`: add same-repo retrieval regression.
- Modify `tests/test_reflection_integration.py`: assert canonical embedding construction and nonzero `token_length`.
- Modify `tests/test_type_aware_decay_policy.py`: assert persisted scores appear in store snapshots.
- Modify `tests/test_experiment_runner.py` or create `tests/test_sequence_runner_integration.py`: assert runner handles tuple-shaped retrieval and logs archive deltas.

---

### Task 1: Normalize Retrieved Memory Tuples In SequenceRunner

**Files:**
- Modify: `src/benchmark/sequence_runner.py`
- Test: `tests/test_sequence_runner_integration.py`

- [ ] **Step 1: Write the failing tuple-normalization tests**

Create `tests/test_sequence_runner_integration.py` with the following content:

```python
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
        commands_run=["pytest"],
        embedding_text="Issue:\nIssue summary\nDiff:\ndiff --git a/file.py b/file.py",
        token_length=16,
    )


def make_runner(tmp_path: Path) -> SequenceRunner:
    policy = Mock()
    policy.name = "full_memory"
    config = {
        "memory": {"top_k": 5, "max_context_tokens": 2000},
        "evaluation": {"docker_image": "fake", "timeout_seconds": 1},
        "experiment": {"pilot_mode": {"enabled": False, "log_retrieval_quality": False}},
    }
    runner = SequenceRunner(run_id="test-run", policy=policy, config=config)
    runner.run_dir = tmp_path / "runs" / "test-run"
    runner.run_dir.mkdir(parents=True)
    return runner


def test_build_task_result_accepts_policy_retrieval_tuples(tmp_path):
    runner = make_runner(tmp_path)
    task = Task(
        task_id="django__django-1",
        repo="django/django",
        base_commit="abc123",
        issue_text="Fix bug",
        test_patch="",
        gold_patch="",
        created_at="2024-01-01T00:00:00Z",
        sequence_index=3,
        difficulty_label="medium",
    )
    memories = [(0.72, make_record("MEM-001", sequence_index=1))]

    result = runner._build_task_result(
        task=task,
        seed=1,
        agent_result={
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
        },
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
    runner = make_runner(tmp_path)
    task = Task(
        task_id="django__django-1",
        repo="django/django",
        base_commit="abc123",
        issue_text="Fix bug",
        test_patch="",
        gold_patch="",
        created_at="2024-01-01T00:00:00Z",
        sequence_index=3,
        difficulty_label="medium",
    )
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
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
pytest tests/test_sequence_runner_integration.py -v
```

Expected: FAIL because `_build_task_result()` does not accept `pruned_memory_ids` and `consolidated_memory_ids` yet, and because tuple-shaped memories do not support `.get()`.

- [ ] **Step 3: Add tuple helper methods to `SequenceRunner`**

In `src/benchmark/sequence_runner.py`, add this method inside `SequenceRunner` before `_reflect_and_write()`:

```python
    def _retrieved_memory_ids(
        self,
        retrieved_memories: list[tuple[float, Any]],
    ) -> list[str]:
        """Return memory IDs from policy retrieval tuples."""
        return [record.memory_id for _, record in retrieved_memories]

    def _retrieved_memory_log_fields(
        self,
        task: Task,
        retrieved_memories: list[tuple[float, Any]],
    ) -> dict[str, list[Any]]:
        """Build task-result fields from policy retrieval tuples."""
        return {
            "ids": [record.memory_id for _, record in retrieved_memories],
            "scores": [float(score) for score, _ in retrieved_memories],
            "types": [record.memory_type for _, record in retrieved_memories],
            "ages": [
                max(0, task.sequence_index - record.sequence_index)
                for _, record in retrieved_memories
            ],
        }
```

- [ ] **Step 4: Update `_reflect_and_write()` to use tuple helpers**

Replace the current retrieved ID extraction in `src/benchmark/sequence_runner.py`:

```python
        retrieved_memory_ids = [
            mem.get("memory_id", "") for mem in retrieved_memories
        ]
```

with:

```python
        retrieved_memory_ids = self._retrieved_memory_ids(retrieved_memories)
```

- [ ] **Step 5: Extend `_build_task_result()` signature and tuple handling**

Change `_build_task_result()` signature to:

```python
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
```

Replace the current retrieved-memory extraction block with:

```python
        retrieved_fields = self._retrieved_memory_log_fields(task, retrieved_memories)
        retrieved_memory_ids = retrieved_fields["ids"]
        retrieved_memory_scores = retrieved_fields["scores"]
        retrieved_memory_types = retrieved_fields["types"]
        retrieved_memory_ages = retrieved_fields["ages"]
```

Replace the hard-coded memory operation fields with:

```python
            pruned_memory_ids=pruned_memory_ids or [],
            consolidated_memory_ids=consolidated_memory_ids or [],
```

- [ ] **Step 6: Run tests for Task 1**

Run:

```bash
pytest tests/test_sequence_runner_integration.py -v
```

Expected: PASS for the two new tests.

- [ ] **Step 7: Commit**

```bash
git add src/benchmark/sequence_runner.py tests/test_sequence_runner_integration.py
git commit -m "fix: normalize retrieved memory tuples in sequence runner"
```

---

### Task 2: Score Same-Repo Candidates Exactly

**Files:**
- Modify: `src/memory/store.py`
- Test: `tests/test_memory_store.py`

- [ ] **Step 1: Write the failing same-repo regression test**

Append this test to `tests/test_memory_store.py`:

```python
import numpy as np


def test_same_repo_search_scores_all_candidates_even_when_global_hits_are_cross_repo(memory_store):
    query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    memory_store.embedding_dim = 3
    memory_store.faiss_index = __import__("faiss").IndexFlatIP(3)
    memory_store.vector_id_to_memory_id = {}

    def add_record(memory_id: str, repo: str, vector: list[float]) -> None:
        record = create_test_record(
            memory_id=memory_id,
            repo=repo,
            embedding_text=f"Issue:\n{memory_id}\nDiff:\ndiff",
            token_length=8,
        )
        vector_id = memory_store.faiss_index.ntotal
        vec = np.array(vector, dtype=np.float32)
        vec = vec / np.linalg.norm(vec)
        memory_store.faiss_index.add(vec.reshape(1, -1))
        record.embedding_vector_id = str(vector_id)
        memory_store.vector_id_to_memory_id[vector_id] = memory_id
        cursor = memory_store.conn.cursor()
        cursor.execute(
            """
            INSERT INTO memory_records (
                memory_id, task_id, repo, sequence_index,
                memory_type, outcome,
                issue_summary, patch_summary, failure_summary, test_summary,
                files_touched, functions_touched, commands_run,
                retrieved_memory_ids_used,
                embedding_text, embedding_vector_id,
                token_length, raw_trace_ref,
                use_count, last_retrieved_at_step,
                success_after_retrieval_count, failure_after_retrieval_count,
                importance_score, is_consolidated, source_memory_ids,
                is_archived, archived_reason, archived_at_step,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.memory_id, record.task_id, record.repo, record.sequence_index,
                record.memory_type, record.outcome,
                record.issue_summary, record.patch_summary, record.failure_summary, record.test_summary,
                "[]", "[]", "[]", "[]",
                record.embedding_text, record.embedding_vector_id,
                record.token_length, record.raw_trace_ref,
                record.use_count, record.last_retrieved_at_step,
                record.success_after_retrieval_count, record.failure_after_retrieval_count,
                record.importance_score, int(record.is_consolidated), None,
                int(record.is_archived), record.archived_reason, record.archived_at_step,
                record.created_at, record.updated_at,
            ),
        )
        memory_store.conn.commit()

    for idx in range(120):
        add_record(f"MEM-X-{idx}", "flask/flask", [1.0, 0.0, 0.0])
    add_record("MEM-DJANGO", "django/django", [0.5, 0.5, 0.0])

    results = memory_store.search(
        query_vector=query,
        top_k=1,
        repo="django/django",
        same_repo_only=True,
    )

    assert [record.memory_id for _, record in results] == ["MEM-DJANGO"]
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
pytest tests/test_memory_store.py::test_same_repo_search_scores_all_candidates_even_when_global_hits_are_cross_repo -v
```

Expected: FAIL because current search only inspects a limited number of global FAISS hits.

- [ ] **Step 3: Implement exact candidate scoring**

In `src/memory/store.py`, replace the FAISS global search/filter block inside `search()` with this code after query normalization:

```python
        scored_candidates: list[tuple[float, MemoryRecord]] = []
        for record in candidate_records:
            vector_id = int(record.embedding_vector_id)
            vector = self.faiss_index.reconstruct(vector_id).astype(np.float32)
            vector_norm = np.linalg.norm(vector)
            if vector_norm > 0:
                vector = vector / vector_norm
            similarity = float(np.dot(query_vector.astype(np.float32), vector))
            scored_candidates.append((similarity, record))

        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        return scored_candidates[:top_k]
```

Remove the old `search_k`, `self.faiss_index.search(...)`, and post-filter loop.

- [ ] **Step 4: Run the same-repo test**

Run:

```bash
pytest tests/test_memory_store.py::test_same_repo_search_scores_all_candidates_even_when_global_hits_are_cross_repo -v
```

Expected: PASS.

- [ ] **Step 5: Run existing retrieval tests**

Run:

```bash
pytest tests/test_memory_retriever.py tests/test_memory_store.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/memory/store.py tests/test_memory_store.py
git commit -m "fix: score same-repo memory candidates exactly"
```

---

### Task 3: Let MemoryStore Own Embedding Construction

**Files:**
- Modify: `src/memory/reflection.py`
- Test: `tests/test_reflection_integration.py`

- [ ] **Step 1: Write the failing reflection-store test**

Append this test to `tests/test_reflection_integration.py`:

```python
def test_reflection_leaves_embedding_construction_to_store(monkeypatch):
    captured = {}

    class FakePolicy:
        name = "full_memory"

        def write(self, memory_store, record):
            captured["embedding_text_before_store"] = record.embedding_text
            captured["token_length_before_store"] = record.token_length
            memory_store.add(record)

    class FakeStore:
        def add(self, record):
            from src.memory.embedding_utils import construct_embedding_text

            text, token_count, _ = construct_embedding_text(
                issue_summary=record.issue_summary,
                failure_summary=record.failure_summary,
                patch_summary=record.patch_summary,
            )
            record.embedding_text = text
            record.token_length = token_count
            captured["embedding_text_after_store"] = record.embedding_text
            captured["token_length_after_store"] = record.token_length

    task = {
        "task_id": "django__django-1",
        "repo": "django/django",
        "issue_text": "Fix query bug",
    }
    trajectory = {
        "files_modified": ["django/db/models/query.py"],
        "commands_run": ["pytest tests"],
        "test_output": "AssertionError",
    }
    evaluation_result = {"resolved": False, "error_message": "AssertionError"}

    record = reflect_and_write_memory(
        task=task,
        trajectory=trajectory,
        patch="diff --git a/django/db/models/query.py b/django/db/models/query.py",
        evaluation_result=evaluation_result,
        memory_store=FakeStore(),
        policy=FakePolicy(),
        retrieved_memory_ids=[],
        sequence_index=0,
    )

    assert captured["embedding_text_before_store"] == ""
    assert captured["token_length_before_store"] == 0
    assert captured["embedding_text_after_store"].startswith("Issue:\n")
    assert "\nDiff:\n" in captured["embedding_text_after_store"]
    assert captured["token_length_after_store"] > 0
    assert record.token_length > 0
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
pytest tests/test_reflection_integration.py::test_reflection_leaves_embedding_construction_to_store -v
```

Expected: FAIL because reflection pre-populates `embedding_text`.

- [ ] **Step 3: Remove reflection-side embedding construction**

In `src/memory/reflection.py`, remove the call to `construct_embedding_text()` in the function that creates `MemoryRecord`. Build the record with these fields:

```python
        embedding_text="",
        token_length=0,
```

Keep `issue_summary`, `failure_summary`, and `patch_summary` populated, because `MemoryStore.add()` needs those exact fields.

- [ ] **Step 4: Ensure returned record reflects store mutation**

In `src/memory/reflection.py`, keep the existing call path:

```python
    policy.write(memory_store, record)
    return record
```

Do not create a new record after `policy.write()`. `MemoryStore.add()` mutates the same `record` object with `embedding_text`, `token_length`, and `embedding_vector_id`.

- [ ] **Step 5: Run reflection tests**

Run:

```bash
pytest tests/test_reflection_integration.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/memory/reflection.py tests/test_reflection_integration.py
git commit -m "fix: centralize memory embedding construction in store"
```

---

### Task 4: Persist Type-Aware Decay Scores

**Files:**
- Modify: `src/memory/policies/type_aware_decay.py`
- Test: `tests/test_type_aware_decay_policy.py`

- [ ] **Step 1: Write the failing persistence test**

Append this test to `tests/test_type_aware_decay_policy.py`:

```python
def test_maintain_persists_importance_scores_to_store(mock_memory_store):
    records = [
        create_memory_record(memory_id="MEM-001", memory_type="architectural", sequence_index=0),
        create_memory_record(memory_id="MEM-002", memory_type="config", sequence_index=2),
    ]
    mock_memory_store.count_active.return_value = 2
    mock_memory_store.active_records.return_value = records
    mock_memory_store.update_importance_score = Mock()

    policy = TypeAwareDecayPolicy(max_records=10)
    policy.maintain(mock_memory_store)

    assert mock_memory_store.update_importance_score.call_count == 2
    updated_ids = {
        call.args[0] for call in mock_memory_store.update_importance_score.call_args_list
    }
    assert updated_ids == {"MEM-001", "MEM-002"}
    for call in mock_memory_store.update_importance_score.call_args_list:
        assert call.args[1] > 0
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
pytest tests/test_type_aware_decay_policy.py::test_maintain_persists_importance_scores_to_store -v
```

Expected: FAIL because `maintain()` only updates in-memory records.

- [ ] **Step 3: Persist each computed score**

In `src/memory/policies/type_aware_decay.py`, inside the `for record in active_records:` loop, immediately after setting `record.importance_score = score`, add:

```python
            memory_store.update_importance_score(record.memory_id, score)
```

- [ ] **Step 4: Run Type-Aware Decay tests**

Run:

```bash
pytest tests/test_type_aware_decay_policy.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/memory/policies/type_aware_decay.py tests/test_type_aware_decay_policy.py
git commit -m "fix: persist type-aware decay importance scores"
```

---

### Task 5: Capture Archive Deltas Around Policy Maintenance

**Files:**
- Modify: `src/memory/store.py`
- Modify: `src/benchmark/sequence_runner.py`
- Test: `tests/test_memory_store.py`
- Test: `tests/test_sequence_runner_integration.py`

- [ ] **Step 1: Add store test for archived IDs by step**

Append this test to `tests/test_memory_store.py`:

```python
def test_archived_memory_ids_at_step_returns_only_step_matches(memory_store, sample_memory_record):
    memory_store.add(sample_memory_record)
    memory_store.archive(
        memory_id=sample_memory_record.memory_id,
        reason="type_aware_decay",
        current_step=4,
    )

    assert memory_store.archived_memory_ids_at_step(4) == [sample_memory_record.memory_id]
    assert memory_store.archived_memory_ids_at_step(3) == []
```

- [ ] **Step 2: Run failing store test**

Run:

```bash
pytest tests/test_memory_store.py::test_archived_memory_ids_at_step_returns_only_step_matches -v
```

Expected: FAIL because `archived_memory_ids_at_step()` does not exist.

- [ ] **Step 3: Implement `archived_memory_ids_at_step()`**

Add this method to `MemoryStore` in `src/memory/store.py` after `archive()`:

```python
    def archived_memory_ids_at_step(self, step: int) -> list[str]:
        """Return memory IDs archived at a specific sequence step."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT memory_id FROM memory_records
            WHERE is_archived = 1 AND archived_at_step = ?
            ORDER BY memory_id
            """,
            (step,),
        )
        return [row[0] for row in cursor.fetchall()]
```

- [ ] **Step 4: Add runner archive-delta test**

Append this test to `tests/test_sequence_runner_integration.py`:

```python
def test_build_task_result_records_pruned_memory_ids(tmp_path):
    runner = make_runner(tmp_path)
    task = Task(
        task_id="django__django-1",
        repo="django/django",
        base_commit="abc123",
        issue_text="Fix bug",
        test_patch="",
        gold_patch="",
        created_at="2024-01-01T00:00:00Z",
        sequence_index=3,
        difficulty_label="medium",
    )

    result = runner._build_task_result(
        task=task,
        seed=1,
        agent_result={
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
        },
        eval_result={"resolved": 1},
        retrieved_memories=[],
        memory_stats_before={"active_count": 1, "total_tokens": 16},
        memory_stats_after={"active_count": 1, "total_tokens": 16},
        task_wall_time=1.5,
        pruned_memory_ids=["MEM-OLD"],
        consolidated_memory_ids=[],
    )

    assert result.pruned_memory_ids == ["MEM-OLD"]
```

- [ ] **Step 5: Update `_execute_task()` to collect archive deltas**

In `src/benchmark/sequence_runner.py`, replace this block:

```python
            self.policy.maintain(self.memory_store)
```

with:

```python
            archived_before = set(
                self.memory_store.archived_memory_ids_at_step(task.sequence_index)
            )
            self.policy.maintain(self.memory_store)
            archived_after = set(
                self.memory_store.archived_memory_ids_at_step(task.sequence_index)
            )
            pruned_memory_ids = sorted(archived_after - archived_before)
            consolidated_memory_ids: list[str] = []
```

Then pass `archived_this_step=pruned_memory_ids` to the after-task snapshot:

```python
            self.snapshot_logger.log_snapshot(
                step=task.sequence_index,
                boundary="after_task",
                active_records=self.memory_store.active_records(),
                archived_this_step=pruned_memory_ids,
                current_step=task.sequence_index,
            )
```

Then pass the IDs into `_build_task_result()`:

```python
                pruned_memory_ids=pruned_memory_ids,
                consolidated_memory_ids=consolidated_memory_ids,
```

- [ ] **Step 6: Run archive delta tests**

Run:

```bash
pytest tests/test_memory_store.py::test_archived_memory_ids_at_step_returns_only_step_matches tests/test_sequence_runner_integration.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/memory/store.py src/benchmark/sequence_runner.py tests/test_memory_store.py tests/test_sequence_runner_integration.py
git commit -m "fix: capture archived memory deltas in runner logs"
```

---

### Task 6: Reject Silent Reordering In SWE-Bench-CL Loader

**Files:**
- Modify: `src/benchmark/swebenchcl_loader.py`
- Test: `tests/test_swebenchcl_loader.py`

- [ ] **Step 1: Write failing loader-order test**

Append this test to `tests/test_swebenchcl_loader.py`:

```python
def test_loader_rejects_non_chronological_sequence_index_order(tmp_path):
    curriculum = {
        "sequences": [
            {
                "sequence_name": f"seq-{i}",
                "repo": f"owner/repo-{i}",
                "tasks": [
                    {
                        "task_id": f"task-{i}-0",
                        "repo": f"owner/repo-{i}",
                        "base_commit": "abc",
                        "issue_text": "Issue",
                        "test_patch": "",
                        "gold_patch": "",
                        "created_at": "2024-01-01T00:00:00Z",
                        "sequence_index": 1 if i == 0 else 0,
                        "difficulty_label": "medium",
                    },
                    {
                        "task_id": f"task-{i}-1",
                        "repo": f"owner/repo-{i}",
                        "base_commit": "def",
                        "issue_text": "Issue",
                        "test_patch": "",
                        "gold_patch": "",
                        "created_at": "2024-01-02T00:00:00Z",
                        "sequence_index": 0 if i == 0 else 1,
                        "difficulty_label": "medium",
                    },
                ],
            }
            for i in range(8)
        ]
    }
    path = tmp_path / "curriculum.json"
    path.write_text(json.dumps(curriculum))

    loader = SWEBenchCLLoader(path)

    with pytest.raises(ValueError, match="must already be ordered"):
        loader.load_all_sequences()
```

- [ ] **Step 2: Run failing loader test**

Run:

```bash
pytest tests/test_swebenchcl_loader.py::test_loader_rejects_non_chronological_sequence_index_order -v
```

Expected: FAIL because loader silently sorts.

- [ ] **Step 3: Replace sorting with validation**

In `src/benchmark/swebenchcl_loader.py`, replace:

```python
        tasks.sort(key=lambda t: t.sequence_index)
```

with:

```python
        sequence_indices = [task.sequence_index for task in tasks]
        if sequence_indices != sorted(sequence_indices):
            raise ValueError(
                f"Tasks in sequence '{sequence_name}' must already be ordered by "
                "sequence_index. Refusing to reorder official SWE-Bench-CL data."
            )
```

- [ ] **Step 4: Run loader tests**

Run:

```bash
pytest tests/test_swebenchcl_loader.py -v
```

Expected: PASS after updating any old test that expected reordering to now expect `ValueError`.

- [ ] **Step 5: Commit**

```bash
git add src/benchmark/swebenchcl_loader.py tests/test_swebenchcl_loader.py
git commit -m "fix: reject reordered swebench-cl sequences"
```

---

### Task 7: Verification Pass For This Repair Slice

**Files:**
- No source edits expected.

- [ ] **Step 1: Run targeted test set**

Run:

```bash
pytest \
  tests/test_sequence_runner_integration.py \
  tests/test_memory_store.py \
  tests/test_memory_retriever.py \
  tests/test_reflection_integration.py \
  tests/test_type_aware_decay_policy.py \
  tests/test_swebenchcl_loader.py \
  -v
```

Expected: PASS.

- [ ] **Step 2: Run lint on touched files**

Run:

```bash
ruff check \
  src/benchmark/sequence_runner.py \
  src/benchmark/swebenchcl_loader.py \
  src/memory/store.py \
  src/memory/reflection.py \
  src/memory/policies/type_aware_decay.py \
  tests/test_sequence_runner_integration.py \
  tests/test_memory_store.py \
  tests/test_reflection_integration.py \
  tests/test_type_aware_decay_policy.py \
  tests/test_swebenchcl_loader.py
```

Expected: PASS.

- [ ] **Step 3: Run full test suite when dependencies are installed**

Run:

```bash
make test
```

Expected: PASS. If the command fails with `pytest: No such file or directory`, install project dev dependencies first with:

```bash
python -m pip install -e ".[dev]"
```

- [ ] **Step 4: Commit verification updates if any**

```bash
git status --short
git add docs/superpowers/plans/2026-05-27-memory-runner-integration-repair.md
git commit -m "docs: plan memory runner integration repair"
```

---

## Self-Review

**Spec coverage:** This plan addresses the swarm blockers in memory/runner integration: tuple retrieval contract, same-repo retrieval, embedding construction, persisted decay scores, archive deltas, snapshots, and loader no-reordering. It deliberately leaves real agent execution, eval_v3, CLS summarization, and analysis/statistics for separate plans.

**Placeholder scan:** The plan avoids deferred implementation language in task bodies. Every code-changing step names the exact file and shows the exact code to add or replace.

**Type consistency:** Retrieval stays `list[tuple[float, MemoryRecord]]` across policy APIs. Conversion to lists of IDs/scores/types/ages happens only in `SequenceRunner` logging helpers. `MemoryStore.archived_memory_ids_at_step()` returns `list[str]`, which feeds both snapshot logging and `TaskResult.pruned_memory_ids`.
