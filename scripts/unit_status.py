"""unit_status — single-point done-decision for the fleet shard runner.

Returns "complete" | "failed" | "incomplete" for a given (run_id, runs_root)
pair by inspecting the sentinel files written by src.benchmark.completion:

  RUN_COMPLETED.json  -> "complete"   (skip — do NOT re-run)
  RUN_FAILED.json     -> "failed"     (re-queue after archive_prior_attempt)
  neither / dir gone  -> "incomplete" (re-queue after archive_prior_attempt)

The shell calls this module as a subprocess:

    status=$(.venv/bin/python scripts/unit_status.py <run_id> <runs_root>)
    # exits 0 and prints one of: complete | failed | incomplete

Keeping the decision here (not inlined in bash) means:
  - it is unit-testable (tests/test_unit_status.py)
  - the definition stays in one place alongside the completion sentinels
  - the shell never duplicates the path-construction logic
"""

from __future__ import annotations

import sys
from pathlib import Path

from src.benchmark.completion import is_run_complete


def unit_status(run_id: str, runs_root: "str | Path") -> str:
    """Return the completion status for a single run unit.

    Args:
        run_id:    The run identifier (matches the manifest ``run_id`` field,
                   e.g. ``no_memory_django_django_sequence_seed1``).
        runs_root: Base directory under which run directories live.  May be a
                   string path or a :class:`~pathlib.Path`.

    Returns:
        ``"complete"``   — ``RUN_COMPLETED.json`` is present; skip this unit.
        ``"failed"``     — ``RUN_FAILED.json`` is present (no ``RUN_COMPLETED.json``);
                           archive and re-queue.
        ``"incomplete"`` — Neither sentinel is present (or the directory does not
                           exist yet); archive any leftovers and re-queue.
    """
    run_dir = Path(runs_root) / run_id

    # Priority 1: completed sentinel wins regardless of any failure marker.
    if is_run_complete(run_dir):
        return "complete"

    # Priority 2: explicit failure marker.
    if (run_dir / "RUN_FAILED.json").exists():
        return "failed"

    # Default: missing dir or partial run without any terminal marker.
    return "incomplete"


# ---------------------------------------------------------------------------
# CLI entry-point — prints status to stdout so the shell can capture it:
#   status=$(.venv/bin/python scripts/unit_status.py <run_id> <runs_root>)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(
            "usage: python scripts/unit_status.py <run_id> <runs_root>",
            file=sys.stderr,
        )
        sys.exit(1)
    print(unit_status(sys.argv[1], sys.argv[2]))
