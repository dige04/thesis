"""E7 — interdependence & memory-lift analysis (THESIS_REVIEW.md #19 / E7).

The thesis's load-bearing construct-validity question: are the SWE-Bench-CL
sequences genuinely *interdependent*, and does memory actually *help*? Every task
starts from its own clean checkout, so chronology alone does not establish that
earlier-task memory benefits later tasks. If Full ≈ No-Memory and tasks share no
structure, the forgetting question is moot regardless of policy — so this is a
GATE on interpreting the main results, not an afterthought.

Two pure, log-driven estimators (run on the real gate-3 / full-run output):

  * :func:`memory_lift_by_position` — Full minus No-Memory resolved rate, overall
    and split early/late. If memory helps because of interdependence, the benefit
    should concentrate LATER in the sequence (``late_minus_early > 0``).
  * :func:`structural_interdependence` — do later tasks touch files that earlier
    tasks already touched? Uses each task's gold-patch file set (a pre-declared
    structural criterion, not a hand label).

Both take clean inputs so they are unit-testable; thin adapters
(:func:`sequence_task_files`, :func:`parse_patch_files`) extract from the logged
shapes (gold patches).
"""

from typing import Any


def parse_patch_files(patch: str) -> set[str]:
    """Extract the set of files touched by a unified / ``git`` diff.

    Handles ``diff --git a/X b/Y`` headers and ``---/+++`` hunks (stripping the
    ``a/`` / ``b/`` prefix and ignoring ``/dev/null`` for adds/deletes).
    """
    files: set[str] = set()
    for line in (patch or "").splitlines():
        if line.startswith("diff --git "):
            seg = line[len("diff --git ") :].strip()
            if " b/" in seg:
                files.add(seg.split(" b/", 1)[1].strip())
        elif line.startswith(("+++ ", "--- ")):
            path = line[4:].split("\t", 1)[0].strip()
            if not path or path == "/dev/null":
                continue
            for prefix in ("a/", "b/"):
                if path.startswith(prefix):
                    path = path[len(prefix) :]
                    break
            files.add(path)
    return files


def sequence_task_files(gold_patches: list[str]) -> list[set[str]]:
    """Map each task's gold patch to its touched-file set (sequence order)."""
    return [parse_patch_files(p) for p in gold_patches]


def structural_interdependence(task_files: list[set[str]]) -> dict[str, Any]:
    """Quantify how much each task reuses files touched by *earlier* tasks.

    For task ``i`` (i >= 1), prior-overlap is the fraction of its own files that
    appear in the union of all earlier tasks' files:
    ``|files_i ∩ (∪_{j<i} files_j)| / |files_i|`` (0 if task ``i`` touches no
    files). Task 0 has no prior and is fixed at 0.

    Returns:
        Dict with ``per_task_prior_overlap`` (len n; task 0 = 0.0),
        ``mean_prior_overlap`` (mean over tasks 1..n-1), ``frac_tasks_with_dependency``
        (fraction of tasks 1..n-1 with overlap > 0), and ``n_tasks``.
    """
    n = len(task_files)
    per_task: list[float] = []
    seen: set[str] = set()

    for i, files in enumerate(task_files):
        if i == 0 or not files:
            per_task.append(0.0)
        else:
            overlap = len(files & seen) / len(files)
            per_task.append(overlap)
        seen |= files

    if n < 2:
        mean_overlap = 0.0
        frac_dep = 0.0
    else:
        later = per_task[1:]
        mean_overlap = sum(later) / len(later)
        frac_dep = sum(1 for o in later if o > 0.0) / len(later)

    return {
        "per_task_prior_overlap": per_task,
        "mean_prior_overlap": float(mean_overlap),
        "frac_tasks_with_dependency": float(frac_dep),
        "n_tasks": n,
    }


def memory_lift_by_position(
    no_memory: list[int], full: list[int]
) -> dict[str, Any]:
    """Full minus No-Memory resolved rate — overall and split early/late.

    Both inputs are aligned by sequence position (``[i]`` is the same task under
    each condition; valid because Invariant #1 fixes the sequence order). The
    early/late split is the interdependence signal: if memory helps *because*
    later tasks build on earlier ones, the benefit concentrates late
    (``late_minus_early > 0``).

    Raises:
        ValueError: if the two arrays differ in length.
    """
    if len(no_memory) != len(full):
        raise ValueError(
            f"no_memory (len {len(no_memory)}) and full (len {len(full)}) "
            "must be aligned by position."
        )
    n = len(full)

    def _mean(xs: list[int]) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    per_position = [int(full[i]) - int(no_memory[i]) for i in range(n)]
    overall_lift = _mean(full) - _mean(no_memory)

    half = n // 2
    first_half_lift = _mean(full[:half]) - _mean(no_memory[:half])
    second_half_lift = _mean(full[half:]) - _mean(no_memory[half:])

    return {
        "overall_lift": float(overall_lift),
        "per_position_lift": per_position,
        "first_half_lift": float(first_half_lift),
        "second_half_lift": float(second_half_lift),
        "late_minus_early": float(second_half_lift - first_half_lift),
        "n_tasks": n,
    }
