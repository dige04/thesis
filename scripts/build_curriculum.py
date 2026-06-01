#!/usr/bin/env python3
"""Build data/SWE-Bench-CL-Curriculum.json from the official upstream source.

PURPOSE
-------
The thesis loader (``src/benchmark/swebenchcl_loader.py``) and data models
(``src/benchmark/models.py``) require a curriculum JSON in a specific *flat*
shape. The official SWE-Bench-CL curriculum published by the benchmark authors
uses a different, *nested* shape. This script reads the upstream file and emits
the exact shape the loader validates, performing only mechanical field-mapping
and a single documented label collapse. No tasks are dropped, reordered, or
synthesized.

SOURCE
------
Official repository: https://github.com/thomasjoshi/agents-never-forget
File:                data/SWE-Bench-CL-Curriculum.json  (default branch ``main``)
Raw URL:             https://raw.githubusercontent.com/thomasjoshi/agents-never-forget/main/data/SWE-Bench-CL-Curriculum.json

The upstream file's own ``metadata`` block self-describes it as
"SWE-Bench-CL" v1.0.0, 8 sequences, 273 total tasks, generated 2025-05-08.

UPSTREAM (SOURCE) STRUCTURE
---------------------------
Top level: object with keys ``metadata``, ``evaluation_metrics``, ``sequences``.
``sequences`` is a list of 8 objects, each:
    {
      "id":         "django_django_sequence",   # sequence identifier
      "repo":       "django/django",
      "num_tasks":  50,
      "tasks":      [ ... ],                       # already in chronological order
      "statistics": { ... }                        # ignored
    }
Each task object:
    {
      "metadata": {
          "instance_id": "django__django-9296",
          "repo":        "django/django",
          "base_commit": "84322a29...",
          "created_at":  "2017-10-27T11:10:04+00:00",
          "difficulty":  "<15 min fix"             # one of 4 time buckets
      },
      "task": {
          "problem_statement": "...",              # the GitHub issue text
          "hints_text":        "..."               # ignored
      },
      "evaluation": {
          "patch":        "diff --git ...",        # the GOLD solution diff
          "test_patch":   "diff --git ...",        # the test diff
          "FAIL_TO_PASS": [...],                    # ignored here
          "PASS_TO_PASS": [...]                     # ignored here
      },
      "continual_learning": {
          "sequence_position": 1,                  # 1-BASED position in sequence
          "difficulty_score":  1,                  # 1..4, aligned with metadata.difficulty
          "dependencies":      [...],               # ignored
          "modified_files":    [...]               # ignored
      }
    }

TARGET (LOADER) STRUCTURE  (see THESIS_FINAL_v5.md §2.2)
-------------------------------------------------------
    {
      "sequences": [
        {
          "sequence_name": "<upstream id>",
          "repo":          "<repo>",
          "tasks": [
            {
              "task_id":          "<metadata.instance_id>",
              "repo":             "<metadata.repo>",
              "base_commit":      "<metadata.base_commit>",
              "issue_text":       "<task.problem_statement>",
              "test_patch":       "<evaluation.test_patch>",
              "gold_patch":       "<evaluation.patch>",
              "created_at":       "<metadata.created_at>",
              "sequence_index":   <continual_learning.sequence_position - 1>,  # 0-BASED
              "difficulty_label": "easy" | "medium" | "hard"
            },
            ...
          ],
          "task_count": <len(tasks)>
        },
        ... (exactly 8)
      ]
    }

FIELD MAPPING (mechanical, 1:1)
-------------------------------
    task_id          <- metadata.instance_id
    repo             <- metadata.repo  (verified equal to the sequence repo)
    base_commit      <- metadata.base_commit
    issue_text       <- task.problem_statement
    test_patch       <- evaluation.test_patch      (the TEST diff)
    gold_patch       <- evaluation.patch           (the SOLUTION diff)
    created_at       <- metadata.created_at
    sequence_index   <- continual_learning.sequence_position - 1   (upstream is 1-based;
                        loader requires 0-based == list position)
    difficulty_label <- collapse of metadata.difficulty (see below)

JUDGEMENT CALL — DIFFICULTY LABEL COLLAPSE (4 -> 3)
---------------------------------------------------
The loader's Task.__post_init__ restricts difficulty_label to exactly
{"easy", "medium", "hard"} (3 levels), and THESIS_FINAL_v5.md §2.2 shows
"difficulty_label" sourced "from SWE-Bench metadata". The upstream metadata
uses the *standard SWE-Bench* 4-level human time-to-fix annotation:
    "<15 min fix"      (difficulty_score 1)  -> easy
    "15 min - 1 hour"  (difficulty_score 2)  -> medium
    "1-4 hours"        (difficulty_score 3)  -> hard
    ">4 hours"         (difficulty_score 4)  -> hard
The two "hard" buckets are merged because they are the rarest (12 and 2 tasks
respectively, 14/273 total) and both denote multi-hour, structurally complex
fixes. This is the only semantic transformation; it preserves the ordinal
difficulty axis used by the GLMM (THESIS_FINAL_v5.md §15) and is consistent
across all sequences. The mapping is keyed on difficulty_score (robust to any
whitespace variation in the label string) and cross-checked against the label.

NOTHING ELSE IS CHANGED
-----------------------
- All 8 sequences are kept (no subsetting).
- No task is dropped (all 273 retained); every sequence has >=15 tasks.
- Task order is taken from sequence_position; the loader re-sorts by
  sequence_index defensively, so output is emitted already sorted.
- sequence_name is the upstream sequence ``id`` verbatim.

USAGE
-----
    python3 scripts/build_curriculum.py \
        --source /tmp/source-curriculum.json \
        --out    data/SWE-Bench-CL-Curriculum.json

If --source is omitted the script downloads the raw upstream file via urllib.
Validation uses only the Python standard library (no faiss/openai/torch import).
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

RAW_SOURCE_URL = (
    "https://raw.githubusercontent.com/thomasjoshi/agents-never-forget/"
    "main/data/SWE-Bench-CL-Curriculum.json"
)

ALLOWED_DIFFICULTY = ("easy", "medium", "hard")

# Map upstream difficulty_score (1..4) -> thesis 3-level label.
# Score is preferred over the free-text label because it is integer-stable.
SCORE_TO_LABEL = {
    1: "easy",    # "<15 min fix"
    2: "medium",  # "15 min - 1 hour"
    3: "hard",    # "1-4 hours"
    4: "hard",    # ">4 hours"
}

# Secondary check: upstream free-text label -> expected label (for cross-validation).
TEXT_TO_LABEL = {
    "<15 min fix": "easy",
    "15 min - 1 hour": "medium",
    "1-4 hours": "hard",
    ">4 hours": "hard",
}


def load_source(source: Path | None) -> dict[str, Any]:
    """Load the upstream curriculum from a local path or by downloading it."""
    if source is not None:
        with open(source, encoding="utf-8") as f:
            return json.load(f)
    print(f"[build_curriculum] Downloading source from {RAW_SOURCE_URL}", file=sys.stderr)
    with urllib.request.urlopen(RAW_SOURCE_URL) as resp:  # noqa: S310 (trusted GitHub raw URL)
        return json.loads(resp.read().decode("utf-8"))


def difficulty_label(task: dict[str, Any]) -> str:
    """Derive the 3-level difficulty_label from upstream fields.

    Prefers continual_learning.difficulty_score; falls back to metadata.difficulty
    text. Raises if neither yields a valid mapping or if the two disagree.
    """
    score = task.get("continual_learning", {}).get("difficulty_score")
    text = task.get("metadata", {}).get("difficulty")

    label_from_score = SCORE_TO_LABEL.get(score) if score is not None else None
    label_from_text = TEXT_TO_LABEL.get(text) if text is not None else None

    if label_from_score is not None and label_from_text is not None:
        if label_from_score != label_from_text:
            raise ValueError(
                f"Difficulty mismatch for task: score={score!r} -> {label_from_score} "
                f"but text={text!r} -> {label_from_text}"
            )
        return label_from_score
    if label_from_score is not None:
        return label_from_score
    if label_from_text is not None:
        return label_from_text
    raise ValueError(
        f"Cannot map difficulty: score={score!r}, text={text!r} are both unknown"
    )


def transform_task(task: dict[str, Any], expected_repo: str) -> dict[str, Any]:
    """Map one upstream task object to the flat loader schema."""
    meta = task["metadata"]
    tsk = task["task"]
    ev = task["evaluation"]
    cl = task["continual_learning"]

    repo = meta["repo"]
    if repo != expected_repo:
        raise ValueError(
            f"Task {meta.get('instance_id')!r} repo {repo!r} "
            f"!= sequence repo {expected_repo!r}"
        )

    position_1based = cl["sequence_position"]
    return {
        "task_id": meta["instance_id"],
        "repo": repo,
        "base_commit": meta["base_commit"],
        "issue_text": tsk["problem_statement"],
        "test_patch": ev["test_patch"],
        "gold_patch": ev["patch"],
        "created_at": meta["created_at"],
        "sequence_index": position_1based - 1,  # upstream 1-based -> loader 0-based
        "difficulty_label": difficulty_label(task),
    }


def transform(source: dict[str, Any]) -> dict[str, Any]:
    """Transform the full upstream curriculum into the loader schema."""
    src_sequences = source["sequences"]
    out_sequences = []
    for seq in src_sequences:
        repo = seq["repo"]
        tasks = [transform_task(t, repo) for t in seq["tasks"]]
        # Emit already sorted by sequence_index (loader re-sorts defensively anyway).
        tasks.sort(key=lambda t: t["sequence_index"])
        out_sequences.append(
            {
                "sequence_name": seq["id"],
                "repo": repo,
                "tasks": tasks,
                "task_count": len(tasks),
            }
        )
    return {"sequences": out_sequences}


def validate(curriculum: dict[str, Any]) -> None:
    """Validate the emitted curriculum against every loader/model constraint.

    Uses only stdlib so it runs even before the project venv finishes installing.
    Mirrors the checks in SWEBenchCLLoader and the Task/Sequence dataclasses.
    """
    assert isinstance(curriculum, dict), "top level must be an object"
    assert "sequences" in curriculum, "missing top-level 'sequences' key"
    seqs = curriculum["sequences"]
    assert isinstance(seqs, list), "'sequences' must be a list"
    assert len(seqs) == 8, f"must have exactly 8 sequences, got {len(seqs)}"

    required_task_fields = (
        "task_id",
        "repo",
        "base_commit",
        "issue_text",
        "test_patch",
        "gold_patch",
        "created_at",
        "sequence_index",
        "difficulty_label",
    )

    seen_task_ids: set[str] = set()
    for seq in seqs:
        name = seq.get("sequence_name")
        repo = seq.get("repo")
        tasks = seq.get("tasks")
        assert name, "sequence missing sequence_name"
        assert repo, f"sequence {name} missing repo"
        assert isinstance(tasks, list) and tasks, f"sequence {name} has no tasks"
        assert seq.get("task_count") == len(tasks), (
            f"sequence {name}: task_count {seq.get('task_count')} != len {len(tasks)}"
        )
        assert len(tasks) >= 15, (
            f"sequence {name} must have >=15 tasks, got {len(tasks)}"
        )
        for i, t in enumerate(tasks):
            for field in required_task_fields:
                assert field in t, f"{name} task {i} missing field {field}"
            assert t["task_id"], f"{name} task {i} empty task_id"
            assert t["base_commit"], f"{name} task {i} empty base_commit"
            assert isinstance(t["sequence_index"], int), (
                f"{name} task {i} sequence_index not int"
            )
            assert t["sequence_index"] == i, (
                f"{name} task {i}: sequence_index {t['sequence_index']} != position {i}"
            )
            assert t["repo"] == repo, (
                f"{name} task {i}: repo {t['repo']} != sequence repo {repo}"
            )
            assert t["difficulty_label"] in ALLOWED_DIFFICULTY, (
                f"{name} task {i}: bad difficulty_label {t['difficulty_label']!r}"
            )
            assert t["task_id"] not in seen_task_ids, (
                f"duplicate task_id {t['task_id']}"
            )
            seen_task_ids.add(t["task_id"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Path to upstream SWE-Bench-CL-Curriculum.json. "
        "If omitted, downloads from the official GitHub raw URL.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "SWE-Bench-CL-Curriculum.json",
        help="Output path for the transformed curriculum.",
    )
    args = parser.parse_args()

    source = load_source(args.source)
    curriculum = transform(source)
    validate(curriculum)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(curriculum, f, ensure_ascii=False, indent=2)

    n_tasks = sum(s["task_count"] for s in curriculum["sequences"])
    print(
        f"[build_curriculum] Wrote {args.out} "
        f"({len(curriculum['sequences'])} sequences, {n_tasks} tasks).",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
