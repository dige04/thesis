"""Tests for the real swebench harness invocation in SWEBenchEvaluator (Phase 5.1).

Docker/swebench are not invoked for real here: subprocess.run is monkeypatched to
write a fake report file (and the empty-patch short-circuit is checked to NOT
invoke the harness). Verifies prediction handling, the arm64 namespace flag, and
report-file -> resolved verdict.
"""

import json
import subprocess
from pathlib import Path

from src.benchmark import evaluator as ev_mod
from src.benchmark.evaluator import SWEBenchEvaluator
from src.benchmark.models import Task


def _task(tid="django__django-1"):
    return Task(
        task_id=tid, repo="django/django", base_commit="c0", issue_text="i",
        test_patch="", gold_patch="", created_at="2020-01-01T00:00:00Z",
        sequence_index=0, difficulty_label="easy",
    )


def test_empty_patch_unresolved_without_invoking_harness(monkeypatch):
    called = []
    monkeypatch.setattr(ev_mod.subprocess, "run", lambda *a, **k: called.append(a))
    ev = SWEBenchEvaluator()
    res = ev.evaluate_patch(_task(), "   \n  ")
    assert res.success is True and res.passed is False
    assert called == []  # short-circuit: no harness invocation for an empty patch


def _fake_run_writing_report(report_payload):
    """Return a subprocess.run stand-in that writes {model}.{run_id}.json in cwd."""
    def fake_run(cmd, **kw):
        assert "--namespace" in cmd
        # arm64: namespace must be empty (build locally, do not pull x86 images)
        assert cmd[cmd.index("--namespace") + 1] == ""
        run_id = cmd[cmd.index("--run_id") + 1]
        cwd = Path(kw["cwd"])
        (cwd / f"memory_pruning_agent.{run_id}.json").write_text(json.dumps(report_payload))
        return subprocess.CompletedProcess(cmd, 0, "harness done", "")
    return fake_run


def test_resolved_from_report_file(monkeypatch, tmp_path):
    task = _task("django__django-7")
    monkeypatch.setattr(
        ev_mod.subprocess, "run",
        _fake_run_writing_report({"resolved_ids": [task.task_id], "resolved_instances": 1}),
    )
    ev = SWEBenchEvaluator()
    res = ev.evaluate_patch(task, "diff --git a/x b/x\n+y\n", work_dir=str(tmp_path))
    assert res.success is True and res.passed is True


def test_unresolved_when_id_absent_from_report(monkeypatch, tmp_path):
    task = _task("django__django-9")
    monkeypatch.setattr(
        ev_mod.subprocess, "run",
        _fake_run_writing_report({"resolved_ids": ["someone__else-1"]}),
    )
    ev = SWEBenchEvaluator()
    res = ev.evaluate_patch(task, "diff --git a/x b/x\n+y\n", work_dir=str(tmp_path))
    assert res.success is True and res.passed is False


def test_predictions_file_written_with_patch(monkeypatch, tmp_path):
    task = _task("django__django-3")
    captured = {}

    def fake_run(cmd, **kw):
        cwd = Path(kw["cwd"])
        preds = (cwd / "predictions.jsonl").read_text()
        captured["preds"] = json.loads(preds)
        run_id = cmd[cmd.index("--run_id") + 1]
        (cwd / f"memory_pruning_agent.{run_id}.json").write_text(json.dumps({"resolved_ids": []}))
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(ev_mod.subprocess, "run", fake_run)
    ev = SWEBenchEvaluator()
    ev.evaluate_patch(task, "MYPATCH", work_dir=str(tmp_path))
    assert captured["preds"]["instance_id"] == "django__django-3"
    assert captured["preds"]["model_patch"] == "MYPATCH"
    assert captured["preds"]["model_name_or_path"] == "memory_pruning_agent"
