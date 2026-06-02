<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-02 | Updated: 2026-06-02 -->

# scripts

## Purpose
Standalone operational scripts run outside the experiment loop — currently dataset construction.

## Key Files
| File | Description |
|------|-------------|
| `build_curriculum.py` | Downloads SWE-Bench-CL from `github.com/thomasjoshi/agents-never-forget` and writes `data/SWE-Bench-CL-Curriculum.json` (the 8 sequences, chronological). Run once during setup; re-run to refresh. |

## For AI Agents

### Working In This Directory
- The curriculum must preserve the **8 official sequences with no re-ordering** (invariant #1). Do not alter task curation/ordering in this script.
- Run via `.venv/bin/python scripts/build_curriculum.py`.

## Dependencies

### External
- `datasets` / `huggingface_hub` (dataset fetch), `requests`.

### Internal
- Output consumed by `src/benchmark/swebenchcl_loader.py`.

<!-- MANUAL: -->
