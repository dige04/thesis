<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-02 | Updated: 2026-06-02 -->

# tests/agents

## Purpose
Agent-specific unit tests, focused on the hard execution limits that are frozen invariants.

## Key Files
| File | Description |
|------|-------------|
| `test_limit_tracker.py` | Verifies `LimitTracker` enforces max 20 steps (hard force-fail), 80 tool calls, 5 test runs, 20-min wall time, and records which limit tripped. Guard the `>=` boundary (no 21st step). |

## For AI Agents

### Working In This Directory
- These tests pin frozen invariant #3 — keep them strict; do not relax a threshold to make a test pass.

### Dependencies
- Targets `src/agents/limit_tracker.py`. Uses `pytest`.

<!-- MANUAL: -->
