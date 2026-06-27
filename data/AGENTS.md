<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-02 | Updated: 2026-06-02 -->

# data

## Purpose
The benchmark dataset. Holds the SWE-Bench-CL curriculum used by every run. Built/refetched by `scripts/build_curriculum.py` from `github.com/thomasjoshi/agents-never-forget`.

## Key Files
| File | Description |
|------|-------------|
| `SWE-Bench-CL-Curriculum.json` | The 8 official sequences (15–80+ tasks each), chronologically ordered by creation date + difficulty. The single dataset the loader (`src/benchmark/swebenchcl_loader.py`) reads. |
| `README.md` | Notes on dataset provenance and rebuild. |

## For AI Agents

### Working In This Directory
- **Benchmark integrity is locked** (invariants #1/#16): do not re-order, subset (without documenting as a compute trade-off), or modify task curation.
- The curriculum JSON is large (~1.5 MB) and is part of the benchmark — but raw `runs/` outputs and generated artifacts are gitignored; check `.gitignore` before committing anything large.
- Rebuild with `.venv/bin/python scripts/build_curriculum.py` if the file is missing or stale.

## Dependencies

### Internal
- Produced by `scripts/build_curriculum.py`; consumed by `src/benchmark/swebenchcl_loader.py`.

<!-- MANUAL: -->
