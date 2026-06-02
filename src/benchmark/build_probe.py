"""Phase 5.0 build-probe (GATE) — decisions D + E, deviation D5.

Before any real run, probe all 273 curriculum instance_ids for:
  1. **Verified coverage** — every instance_id must resolve in
     ``princeton-nlp/SWE-bench_Verified`` (decision E). A miss signals
     CL/Verified version drift.
  2. **arm64 buildability** — attempt to build the swebench arm64 instance
     image (namespace="" => local build) and confirm the GOLD patch resolves on
     arm64. Failures become a **deterministic exclusion list**, applied
     identically across all 6 conditions × 3 seeds.

GATE: if >15% of any sequence is unbuildable, escalate to an x86_64 host
(revisit decision B). The exclusion list + per-sequence counts are written to a
tracked artifact and disclosed in Methods (sanctioned by v5 §0.1 #6
"documented compute trade-off").

The pure logic (coverage, exclusion, gate, artifact) is unit-tested with an
injected ``builder`` and ``verified_ids_loader``; the real build requires Docker
+ network and is exercised live.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.benchmark.swebenchcl_loader import SWEBenchCLLoader
from src.benchmark.verified_loader import verified_instance_ids

logger = logging.getLogger(__name__)

DEFAULT_ARTIFACT = "data/arm64_exclusions.json"
DEFAULT_DATASET = "princeton-nlp/SWE-bench_Verified"
ESCALATION_THRESHOLD = 0.15  # >15% of any sequence unbuildable -> escalate (decision D)

# Type aliases for the injectable seams.
VerifiedIdsLoader = Callable[[], set[str]]
Builder = Callable[[str], tuple[bool, float, str | None]]  # instance_id -> (ok, seconds, error)


@dataclass
class BuildResult:
    instance_id: str
    sequence_name: str
    in_verified: bool
    buildable: bool
    seconds: float
    error: str | None


def _default_builder(
    instance_id: str,
    *,
    dataset_name: str = DEFAULT_DATASET,
    namespace: str = "",
    timeout: int = 1800,
) -> tuple[bool, float, str | None]:
    """Build the arm64 instance image + confirm the GOLD patch resolves.

    Runs the swebench harness with ``--predictions_path gold`` scoped to one
    instance (namespace="" => local arm64 build). Gold resolving confirms the
    image builds AND the task is resolvable on arm64 (guards against silent
    arch-induced unresolvability — flagged in the methodology audit). Expensive;
    requires Docker + network.
    """
    # Lazy import to avoid any import cycle and keep build_probe importable
    # without the evaluator's transitive deps.
    from src.benchmark.evaluator import SWEBenchEvaluator

    run_id = f"probe_{instance_id}"
    start = time.time()
    cwd = Path(tempfile.mkdtemp(prefix="probe_"))
    try:
        subprocess.run(
            [
                sys.executable, "-m", "swebench.harness.run_evaluation",
                "--dataset_name", dataset_name,
                "--split", "test",
                "--predictions_path", "gold",   # harness synthesizes the gold patch
                "--instance_ids", instance_id,
                "--run_id", run_id,
                "--max_workers", "1",
                "--timeout", str(timeout),
                "--cache_level", "env",
                "--namespace", namespace,
            ],
            capture_output=True, text=True, timeout=timeout + 1800, check=False, cwd=cwd,
        )
        secs = time.time() - start
        # Read the run-report FILE (model_name_or_path == "gold"), NOT stdout —
        # substring-matching the human-readable stdout is unreliable. gold
        # resolving => the arm64 image built AND the task resolves on arm64.
        verdict = SWEBenchEvaluator()._read_report(cwd, "gold", run_id, instance_id)
        ok = verdict is True
        err = None if ok else "gold patch did not resolve on arm64 (build failed or unresolvable)"
        return ok, secs, err
    except subprocess.TimeoutExpired:
        return False, time.time() - start, "build/eval timeout"
    except Exception as e:  # pragma: no cover - env dependent
        return False, time.time() - start, f"{type(e).__name__}: {e}"
    finally:
        shutil.rmtree(cwd, ignore_errors=True)


def probe(
    curriculum_path: str | Path,
    *,
    verified_ids_loader: VerifiedIdsLoader | None = None,
    builder: Builder | None = None,
    build: bool = True,
) -> dict[str, Any]:
    """Probe coverage + arm64 buildability across the whole curriculum.

    Args:
        curriculum_path: SWE-Bench-CL curriculum JSON.
        verified_ids_loader: ``() -> set[instance_id]`` (defaults to loading
            SWE-bench_Verified); injectable for offline tests.
        builder: ``instance_id -> (ok, seconds, error)``; defaults to the
            harness gold-build probe. Injectable for offline tests.
        build: if False, coverage-only (skip the expensive arm64 build probe;
            uncovered instances are still excluded).

    Returns a summary dict (see ``_summarize``).
    """
    loader = SWEBenchCLLoader(curriculum_path)
    sequences = loader.load_all_sequences()
    verified = (verified_ids_loader or verified_instance_ids)()
    do_build = builder or _default_builder

    results: list[BuildResult] = []
    for seq in sequences:
        for task in seq.tasks:
            iid = task.task_id
            in_v = iid in verified
            if not in_v:
                results.append(BuildResult(iid, seq.sequence_name, False, False, 0.0,
                                           "not in SWE-bench_Verified"))
                continue
            if not build:
                results.append(BuildResult(iid, seq.sequence_name, True, True, 0.0, None))
                continue
            ok, secs, err = do_build(iid)
            results.append(BuildResult(iid, seq.sequence_name, True, ok, secs, err))

    return _summarize(sequences, results)


def _summarize(sequences: list, results: list[BuildResult]) -> dict[str, Any]:
    exclusions = sorted(r.instance_id for r in results if not r.buildable)
    excl_set = set(exclusions)

    per_sequence: dict[str, Any] = {}
    escalate: list[str] = []
    for seq in sequences:
        ids = [t.task_id for t in seq.tasks]
        excl = [i for i in ids if i in excl_set]
        frac = len(excl) / len(ids) if ids else 0.0
        per_sequence[seq.sequence_name] = {
            "total": len(ids),
            "excluded": len(excl),
            "fraction": round(frac, 4),
            "excluded_ids": excl,
        }
        if frac > ESCALATION_THRESHOLD:
            escalate.append(seq.sequence_name)

    missing = sorted(r.instance_id for r in results if not r.in_verified)
    return {
        "exclusions": exclusions,
        "not_in_verified": missing,
        "per_sequence": per_sequence,
        "escalate_sequences": escalate,
        "threshold": ESCALATION_THRESHOLD,
        "results": [asdict(r) for r in results],
    }


def write_artifact(summary: dict[str, Any], path: str | Path = DEFAULT_ARTIFACT) -> Path:
    """Write the deterministic exclusion artifact (tracked; applied across 6×3)."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    artifact = {
        "exclusions": summary["exclusions"],
        "not_in_verified": summary["not_in_verified"],
        "per_sequence": summary["per_sequence"],
        "escalate_sequences": summary["escalate_sequences"],
        "threshold": summary["threshold"],
    }
    out.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")
    logger.info(f"Wrote exclusion artifact: {out} ({len(summary['exclusions'])} excluded)")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="build_probe",
        description="Phase 5.0 build-probe: Verified coverage + arm64 buildability gate.",
    )
    parser.add_argument("--curriculum", default="data/SWE-Bench-CL-Curriculum.json")
    parser.add_argument("--artifact", default=DEFAULT_ARTIFACT)
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="coverage-only: skip the (expensive, Docker-bound) arm64 build probe",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    summary = probe(args.curriculum, build=not args.no_build)
    write_artifact(summary, args.artifact)

    print("\nBuild-probe per-sequence (arm64 unbuildable / total):")
    for seq, info in summary["per_sequence"].items():
        flag = "  <-- ESCALATE" if info["fraction"] > ESCALATION_THRESHOLD else ""
        print(f"  {seq:35s} {info['excluded']:3d}/{info['total']:<3d} ({info['fraction'] * 100:5.1f}%){flag}")
    if summary["not_in_verified"]:
        print(f"\nNOT in SWE-bench_Verified ({len(summary['not_in_verified'])}): {summary['not_in_verified']}")

    if summary["escalate_sequences"]:
        print(f"\nGATE FAIL: >{ESCALATION_THRESHOLD * 100:.0f}% unbuildable in: "
              f"{summary['escalate_sequences']} -> escalate to x86_64 host (decision B).")
        return 1
    print(f"\nGATE PASS: no sequence exceeds {ESCALATION_THRESHOLD * 100:.0f}% arm64-unbuildable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
