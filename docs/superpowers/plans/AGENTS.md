<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-02 | Updated: 2026-06-02 -->

# docs/superpowers/plans

## Purpose
Dated, step-by-step implementation and repair plans for the build-to-pilot effort. These translate the locked v5 spec into ordered, executable tasks.

## Key Files
| File | Description |
|------|-------------|
| `2026-06-01-build-to-first-pilot.md` | The active 7-phase plan from env/deps through bugfix slice, real agent loop, real eval_v3, run entry point, to smoke → pilot → calibrate → lock → 144 runs. |
| `2026-05-27-memory-runner-integration-repair.md` | The bugfix slice (Tasks 1–6): tuple/dict retrieval contract, same-repo FAISS, embedding construction, decay persistence, archive deltas, loader no-reorder. |

## For AI Agents

### Working In This Directory
- Plans are working docs — update them as phases complete. Cross-check status against the table in root `AGENTS.md` ("Current build status").
- A plan never overrides a frozen invariant; if a plan step appears to, surface it to the user.

## Dependencies

### Internal
- Reference `src/` modules, `THESIS_FINAL_v5.md` sections, and root `AGENTS.md` build status.

<!-- MANUAL: -->
