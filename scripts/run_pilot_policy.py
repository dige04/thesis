"""Run ONE memory policy over the pilot sequences (Spike-Week pilot, real config).

The pilot is 6 policies x 2 sequences x 1 seed = 12 runs. experiment_runner's
pilot mode runs all 6 policies sequentially; to parallelize across policies on
the droplet we launch one process per policy (see scripts/run_pilot.sh, capped at
3 concurrent). This uses the REAL config (max_records, CLS thresholds, container
backend, swebench namespace) — NOT the validation overrides.

Memory is per-sequence: a fresh policy + fresh MemoryStore per sequence (memory
accumulates WITHIN a sequence, never across repos).

Usage:  .venv/bin/python -m scripts.run_pilot_policy --policy type_aware_decay --seed 1
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import sys
from pathlib import Path

from src.benchmark.sequence_runner import SequenceRunner
from src.benchmark.swebenchcl_loader import SWEBenchCLLoader
from src.config.loader import load_config
from src.memory.policies.cls_consolidation import CLSConsolidationPolicy
from src.memory.policies.full_memory import FullMemoryPolicy
from src.memory.policies.no_memory import NoMemoryPolicy
from src.memory.policies.random_prune import RandomPrunePolicy
from src.memory.policies.recency_prune import RecencyPrunePolicy
from src.memory.policies.type_aware_decay import TypeAwareDecayPolicy

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("run_pilot_policy")

DEFAULT_SEQUENCES = "django_django_sequence,pytest-dev_pytest_sequence"


def build_policy(name: str, seed: int, max_records: int):
    if name == "no_memory":
        return NoMemoryPolicy()
    if name == "full_memory":
        return FullMemoryPolicy()
    if name == "random_prune":
        return RandomPrunePolicy(seed=seed, max_records=max_records)
    if name == "recency_prune":
        return RecencyPrunePolicy(max_records=max_records)
    if name == "type_aware_decay":
        return TypeAwareDecayPolicy(max_records=max_records)
    if name == "cls_consolidation":
        return CLSConsolidationPolicy(max_records=max_records)
    raise ValueError(f"Unknown policy: {name}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--policy", required=True)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--sequences", default=DEFAULT_SEQUENCES)
    p.add_argument("--curriculum", default="data/SWE-Bench-CL-Curriculum.json")
    args = p.parse_args(argv)

    config = load_config()
    max_records = config.get("memory", {}).get("max_records", 100)
    loader = SWEBenchCLLoader(args.curriculum)

    results_dir = Path("results/raw")
    results_dir.mkdir(parents=True, exist_ok=True)

    for seq_name in [s.strip() for s in args.sequences.split(",") if s.strip()]:
        sequence = loader.get_sequence_by_name(seq_name)
        if sequence is None:
            logger.error("sequence %s not found; skipping", seq_name)
            continue
        # Fresh policy + store per sequence (memory does not cross repos).
        policy = build_policy(args.policy, args.seed, max_records)
        run_id = f"pilot_{args.policy}_{seq_name}_seed{args.seed}"
        logger.info("=== PILOT %s on %s (%d tasks) ===", args.policy, seq_name, sequence.task_count)
        runner = SequenceRunner(run_id=run_id, policy=policy, config=config)
        result = runner.run_sequence(sequence=sequence, seed=args.seed)
        out = results_dir / f"{run_id}_result.json"
        out.write_text(json.dumps(dataclasses.asdict(result), indent=2), encoding="utf-8")
        logger.info(
            "PILOT DONE %s/%s: resolved=%d/%d -> %s",
            args.policy, seq_name, result.resolved_tasks, result.total_tasks, out,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
