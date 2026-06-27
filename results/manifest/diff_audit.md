# Task −1 Baseline Diff Audit (2026-06-23)

**Branch:** `feat/analysis-e3-e2-e7` · **HEAD:** `8f0fe3b` · `main`: `a205791`
**Uncommitted (tracked):** 18 files, +743 / −109. Plus untracked (below).

## Key finding (changes the baseline plan)
The tracked uncommitted changes are **the code that actually ran the 144-run matrix** — not random WIP. Evidence: `edit_file` is changed from the old hand-rolled `_apply_diff` parser → **`git apply`** (the version whose "Could not apply" error appears throughout the matrix trajectories); `sequence_runner` gains `RUNS_ROOT` support + 402/429 `UsageLimitError` fatal handling + incomplete-task tracking ("rows silently missing, review blocker #10"); `limit_tracker` carries the temp=1 (A2) amendment. These reference prior-review blockers (THESIS_REVIEW C5/C8/#8/#10).

**⇒ The intended runtime baseline = HEAD `8f0fe3b` + these tracked changes**, committed. A clean worktree from `8f0fe3b` (as the spec's Task −1 literally said) would **drop the matrix-running code** — so we deviate: commit the tracked runtime changes onto a new branch `rerun/instrument-fix`, then `baseline_sha` = that commit.

## Category A — RUNTIME BASELINE (recommend: COMMIT to `rerun/instrument-fix`)
Tracked src/tests that ran the matrix + prior-review fixes:
- `src/agents/tools.py` (+71, edit_file→git apply), `prompts.py` (+2), `limit_tracker.py` (+21, temp=1/A2)
- `src/benchmark/sequence_runner.py` (+239, RUNS_ROOT + usage-limit + incomplete-task tracking + pareto cost), `experiment_runner.py` (+21, usage-limit)
- `src/errors.py` (+8, 402/429 fatal), `src/memory/store.py` (+39 — NOT the run_dir fix; D-8 still open), `metrics/cost_tracker.py` (+59), `metrics/retrieval_quality.py` (+13)
- `tests/`: test_limit_tracker, test_agent_limits, test_agents_tools, test_experiment_runner, test_sequence_runner_integration (+139), test_usage_limit (+96)
- `AMENDMENTS.md` (+19), `.gitignore` (+6), `docs/superpowers/specs/2026-06-16-e2-anchor-probe-live-wiring.md` (+20)

## Category B — MUST NOT COMMIT (secrets / scratch → .gitignore or leave)
- **Secrets:** `.env.kimigo`, `.env.bak.keys` → never commit; verify in `.gitignore`.
- Scratch: `tmp/`, `example.zip`, `example_contents/`, `contents/`, `output/`, `results_test/`, `skills-lock.json`, `.claude/`, `.agents/`.

## Category C — ARTIFACTS / DOCS (not part of the runtime baseline; keep, decide later)
- `results/` (OLD matrix aggregates/plots — the INCOMPLETE 4,675-row matrix; reference only, superseded by `results_v2`), `paper/` (thesis writing), `docs/` (handoffs/reviews), `scripts/` (12 new — analysis/preflight), `THESIS_REVIEW.md`, `thesis-deep-review-prompt.md`.

## Proposed baseline (STOP — needs user confirmation)
1. New branch `rerun/instrument-fix` from current state.
2. Commit **Category A** as the runtime baseline → `baseline_sha`.
3. Confirm **Category B secrets** are gitignored (do NOT commit `.env.*`).
4. Category C stays uncommitted/untracked (outputs + notes), not part of `baseline_sha`.
5. Then generate `results/manifest/runs_144.json` and proceed to Phase A.

**Open questions for the user:** (a) Confirm Category A is the runtime baseline to commit. (b) Confirm `.env.kimigo`/`.env.bak.keys` are secrets to gitignore (not commit). (c) Any Category-A file you consider WIP-not-baseline? (d) Any Category-C script that should be committed as baseline (vs treated as analysis output)?
