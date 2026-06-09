"""Memory-policy machinery validation (Spike-Week diagnostic, NOT pre-registered).

The resolution probe used only No-Memory. This exercises ALL 6 policies end-to-end
on a short task slice to confirm the memory machinery works and to surface
policy-specific bugs BEFORE the ~10-14h full pilot:
  - retrieve (shared cosine) returns memories once some accumulate
  - reflect_and_write persists typed records
  - maintain() actually PRUNES (Random/Recency/Type-Aware) / CONSOLIDATES (CLS)

To make prune/consolidate fire within a short slice we shrink the budget:
  memory.max_records = 3   (so >3 active triggers pruning)
  CLS OLD_MEMORY_THRESHOLD/MIN_CLUSTER_SIZE lowered so consolidation can fire.
These overrides are VALIDATION-ONLY (machinery smoke), not the pre-registered run.

Run on the droplet:  .venv/bin/python -m scripts.policy_validation
"""

from __future__ import annotations

import json
import logging
import sys
from collections import Counter

from src.benchmark.smoke_test import create_smoke_test_sequence
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
logger = logging.getLogger("policy_validation")

CURRICULUM = "data/SWE-Bench-CL-Curriculum.json"
SEED = 42
N_TASKS = 6
MAX_RECORDS = 3
SEQ = "django_django_sequence"


def build_policies():
    cls = CLSConsolidationPolicy(max_records=MAX_RECORDS)
    # Validation-only: force consolidation to be reachable within N_TASKS.
    cls.OLD_MEMORY_THRESHOLD = 2
    cls.MIN_CLUSTER_SIZE = 2
    return [
        ("no_memory", NoMemoryPolicy()),
        ("full_memory", FullMemoryPolicy()),
        ("random_prune", RandomPrunePolicy(seed=SEED, max_records=MAX_RECORDS)),
        ("recency_prune", RecencyPrunePolicy(max_records=MAX_RECORDS)),
        ("type_aware_decay", TypeAwareDecayPolicy(max_records=MAX_RECORDS)),
        ("cls_consolidation", cls),
    ]


def summarize(run_dir) -> dict:
    events = Counter()
    ev_path = run_dir / "memory_events.jsonl"
    if ev_path.exists():
        for line in ev_path.read_text().splitlines():
            try:
                events[json.loads(line).get("event_type", "?")] += 1
            except Exception:
                pass
    resolved = 0
    tr_path = run_dir / "task_results.jsonl"
    if tr_path.exists():
        for line in tr_path.read_text().splitlines():
            try:
                resolved += int(json.loads(line).get("resolved", 0) == 1)
            except Exception:
                pass
    return {"events": dict(events), "resolved": resolved}


def main() -> int:
    config = load_config()
    config.setdefault("memory", {})["max_records"] = MAX_RECORDS

    loader = SWEBenchCLLoader(CURRICULUM)
    sequence = loader.get_sequence_by_name(SEQ)
    tasks = create_smoke_test_sequence(sequence, N_TASKS)

    rows = []
    for name, policy in build_policies():
        run_id = f"polval_{name}_{SEED}"
        logger.info("=== POLICY %s ===", name)
        runner = SequenceRunner(run_id=run_id, policy=policy, config=config)
        err = None
        try:
            for task in tasks:
                runner._execute_task(task, SEED)
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            logger.error("policy %s crashed: %s", name, e, exc_info=True)
        finally:
            try:
                runner.memory_store.close()
            except Exception:
                pass
        s = summarize(runner.run_dir)
        s.update({"policy": name, "error": err})
        rows.append(s)
        logger.info("policy %s -> %s", name, s)

    print("\n========== POLICY VALIDATION SUMMARY ==========")
    for r in rows:
        print(r)
    crashed = [r["policy"] for r in rows if r["error"]]
    print(f"\ncrashed policies: {crashed or 'NONE'}")
    print("===============================================")
    return 1 if crashed else 0


if __name__ == "__main__":
    sys.exit(main())
