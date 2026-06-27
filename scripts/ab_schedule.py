"""A/B schedule generator for instrument-health runs (Task 5e).

Produces a deterministic, shuffled list of 36 run cells:
  sequences {pytest-dev_pytest_sequence, scikit-learn_scikit-learn_sequence}
  × policies {no_memory, full_memory, recency_prune}
  × seeds {1, 2, 3}
  × tool_modes {legacy, fixed}

= 2 × 3 × 3 × 2 = 36 cells.

Each cell is a dict:
    {
        "run_id":        str  — includes tool_mode so legacy/fixed never collide,
        "policy":        str,
        "sequence_name": str,
        "seed":          int,
        "tool_mode":     str,
    }

The execution order is a deterministic shuffle seeded by ``seed`` (the integer
argument to ab_schedule).  The 36 canonical run_ids are invariant across seeds;
only the order changes.

Usage
-----
    python -m scripts.ab_schedule            # print JSON schedule (seed=20260622)
    python -m scripts.ab_schedule --seed 42  # custom seed
"""
from __future__ import annotations

import json
import random
import sys
from typing import Sequence

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SEQUENCES: list[str] = [
    "pytest-dev_pytest_sequence",
    "scikit-learn_scikit-learn_sequence",
]

POLICIES: list[str] = [
    "no_memory",
    "full_memory",
    "recency_prune",
]

SEEDS: list[int] = [1, 2, 3]

TOOL_MODES: list[str] = ["legacy", "fixed"]

_DEFAULT_SEED = 20260622


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def ab_schedule(seed: int = _DEFAULT_SEED) -> list[dict]:
    """Return the 36-cell A/B schedule in a deterministic shuffled order.

    Args:
        seed: Integer seed for the shuffle order.  The set of 36 cells is
              identical regardless of *seed*; only the execution order differs.

    Returns:
        List of 36 dicts, each with keys:
        ``run_id``, ``policy``, ``sequence_name``, ``seed``, ``tool_mode``.
    """
    cells: list[dict] = []
    for seq in SEQUENCES:
        for policy in POLICIES:
            for exp_seed in SEEDS:
                for tool_mode in TOOL_MODES:
                    run_id = f"{policy}_{seq}_seed{exp_seed}_{tool_mode}"
                    cells.append(
                        {
                            "run_id": run_id,
                            "policy": policy,
                            "sequence_name": seq,
                            "seed": exp_seed,
                            "tool_mode": tool_mode,
                        }
                    )

    # Deterministic shuffle: reproducible across calls, different per seed value
    random.Random(seed).shuffle(cells)
    return cells


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------


def _parse_args(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Print A/B schedule as JSON.")
    parser.add_argument(
        "--seed",
        type=int,
        default=_DEFAULT_SEED,
        help=f"Shuffle seed (default: {_DEFAULT_SEED})",
    )
    args = parser.parse_args(argv)
    return args.seed


if __name__ == "__main__":
    _seed = _parse_args()
    print(json.dumps(ab_schedule(_seed), indent=2))
