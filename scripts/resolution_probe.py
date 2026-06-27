"""Resolution probe (Spike-Week diagnostic, NOT part of the pre-registered run).

Estimates the agent's raw resolution rate across a SPREAD of repositories so we
can detect a floor effect (resolution ~ 0 across the board => H1-H5 lose power)
BEFORE committing to the full pilot/144 runs. Uses the No-Memory policy (the
cleanest measure of base agent capability) and the real container-exec + eval
pipeline. Per-task resolved flag + generated-patch length are reported so we can
judge whether patches are reasonable attempts or garbage.

Run on the x86_64 droplet:  .venv/bin/python -m scripts.resolution_probe
"""

from __future__ import annotations

import logging
import sys

from src.benchmark.smoke_test import create_smoke_test_sequence
from src.benchmark.swebenchcl_loader import SWEBenchCLLoader
from src.config.loader import load_config
from src.memory.policies.no_memory import NoMemoryPolicy
from src.benchmark.sequence_runner import SequenceRunner

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("resolution_probe")

CURRICULUM = "data/SWE-Bench-CL-Curriculum.json"
SEED = 42
TASKS_PER_SEQ = 2
# A spread across repos (all first tasks are 'easy' difficulty per metadata).
TARGET_SEQUENCES = [
    "django_django_sequence",
    "sympy_sympy_sequence",
    "pytest-dev_pytest_sequence",
    "sphinx-doc_sphinx_sequence",
    "scikit-learn_scikit-learn_sequence",
]


def main() -> int:
    config = load_config()
    loader = SWEBenchCLLoader(CURRICULUM)
    names = set(loader.get_sequence_names())

    rows = []
    for seq_name in TARGET_SEQUENCES:
        if seq_name not in names:
            logger.warning("sequence %s not found; available=%s", seq_name, sorted(names))
            continue
        sequence = loader.get_sequence_by_name(seq_name)
        tasks = create_smoke_test_sequence(sequence, TASKS_PER_SEQ)
        policy = NoMemoryPolicy()
        runner = SequenceRunner(run_id=f"probe_{seq_name}_{SEED}", policy=policy, config=config)
        for task in tasks:
            try:
                tr = runner._execute_task(task, SEED)
                rows.append(
                    {
                        "seq": seq_name,
                        "task": task.task_id,
                        "resolved": tr.resolved,
                        "patch_generated": tr.patch_generated,
                        "timeout": tr.timeout,
                        "tool_calls": tr.tool_calls,
                        "tokens": tr.total_tokens,
                    }
                )
            except Exception as e:  # never let one task kill the probe
                logger.error("task %s crashed: %s", task.task_id, e, exc_info=True)
                rows.append({"seq": seq_name, "task": task.task_id, "resolved": "ERR", "err": str(e)})
        try:
            runner.memory_store.close()
        except Exception:
            pass

    print("\n========== RESOLUTION PROBE SUMMARY ==========")
    resolved = sum(1 for r in rows if r.get("resolved") == 1)
    total = len(rows)
    for r in rows:
        print(r)
    print(f"\nRESOLVED {resolved}/{total} = {100.0 * resolved / max(total, 1):.1f}%")
    print("==============================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
