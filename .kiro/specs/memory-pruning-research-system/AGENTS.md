<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-02 | Updated: 2026-06-02 -->

# memory-pruning-research-system

## Purpose
The Kiro spec triad that formalizes the thesis system as requirements → design → tasks, all derived from `THESIS_FINAL_v5.md`. Useful for tracing a `src/` module back to its requirement number (module docstrings cite "Requirements: N") and its design section.

## Key Files
| File | Description |
|------|-------------|
| `requirements.md` | Numbered requirements + glossary. The "Requirements: N" tags in `src/` docstrings refer here. Restates the 144-run scope and the frozen constraints. |
| `design.md` | Technical design: core principle (codebase resets per task, external memory persists), component/interface breakdown, mirrors v5 §3–§17. |
| `tasks.md` | Discrete, testable implementation tasks (the build checklist `TASK_*.md` files at repo root correspond to these). |
| `.config.kiro` | Kiro spec config. |

## For AI Agents

### Working In This Directory
- These specs are **downstream of v5**. If a spec and `THESIS_FINAL_v5.md` conflict, v5 is authoritative — do not "fix" v5 to match a spec.
- Requirement numbers are stable references used throughout the code; keep them consistent if editing.

## Dependencies

### Internal
- Source: `THESIS_FINAL_v5.md`. Realized by `src/**` (each module cites its requirement).

<!-- MANUAL: -->
