# Swarm Review Synthesis — 2026-06-17

**Context:** 5 parallel explore agents reviewed the thesis codebase on branch `feat/analysis-e3-e2-e7`. The 1-seed matrix (36 runs) is running on droplet PID 1436049 and should finish ~2026-06-18 06Z. This synthesis merges their findings into a single prioritized risk board.

**Method:** Read-only review across five domains: (1) analysis pipeline & reproducibility, (2) agent/memory runtime correctness, (3) benchmark/evaluation & metrics, (4) config/logging/docs/paper, (5) test suite & build hygiene.

---

## TL;DR — what blocks `make results` and the paper

| # | Risk | Severity | Blocks |
|---|---|---|---|
| 1 | Off-by-one step limit (`>` not `>=`) allows **21 turns** instead of frozen 20. | **blocker** | validity |
| 2 | `run_condition` swallows `UsageLimitError`, can corrupt matrix under quota. | **blocker** | matrix integrity |
| 3 | No resume/skip-completed logic (E5); multi-day matrix cannot safely restart. | **blocker** | operational reliability |
| 4 | `make lint` fails (59 ruff errors); `make typecheck` fails (88 mypy errors). | **must-fix** | TDD gate / merge readiness |
| 5 | E4 feature importance emits **zero positive class** (hardcoded placeholders). | **blocker** | v5 §16 output |
| 6 | `make results` artifact set is incomplete — missing GLMM, failure analysis, retrieval-overlap manipulation check, performance/cost tables. | **blocker** | full v5 results |
| 7 | No runtime provenance artifact (E5): git/config/model/embedder/hashes not logged. | **must-fix** | reproducibility |
| 8 | Config/code/docs drift on seeds (3 vs 1), CLS threshold (10 vs 5), host arch (arm64 vs x86_64), temperature (0 vs 1). | **must-fix / disclosure** | consistency & Methods accuracy |

Less urgent but important: snapshot boundary names mismatch v5, memory-event types are missing `retrieve`/`update_score`/`snapshot`, classifier failure rate not logged, no generic anchor-probe driver.

---

## Blockers — must be resolved before declaring the pipeline valid

### B1. Off-by-one step limit
- **Where:** `src/agents/limit_tracker.py:100,116,132`
- **Issue:** `if self.step_count > self.max_steps:` permits step_count to reach 21 before failing.
- **Fix:** change all limit checks to `>=`.
- **Caveat:** The running matrix started with this bug. Decide whether to (a) accept the 21-turn data as a disclosed deviation, or (b) restart the matrix. Given the deadline, **disclose** is likely the only practical option.

### B2. `run_condition` swallows provider quota errors
- **Where:** `src/benchmark/experiment_runner.py:728`
- **Issue:** generic `except Exception` catches `UsageLimitError` and continues, hiding quota exhaustion.
- **Fix:** add `except UsageLimitError: raise` before the generic catch.
- **Caveat:** Same as B1 — already-running matrix may have silently continued through quota issues. Check logs for `EXIT=` and `UsageLimitError`.

### B3. No resume/skip-completed logic
- **Where:** `src/benchmark/experiment_runner.py` (E5)
- **Issue:** `run_full_experiment` always restarts from run 1; no skip-if-`task_results.jsonl` exists.
- **Fix:** add `--resume` flag and skip logic; log skipped run_ids.
- **Impact:** Critical for a multi-day 144/48-run matrix.

### B4. E4 feature importance is scientifically unsound
- **Where:** `src/analysis/feature_importance.py:102-138, 328, 334`
- **Issue:** Hardcoded placeholders (`file_overlap=0.0`, `memory_outcome="unknown"`) cause the weak-label rule to label every row `neutral` → binary label all zeros → PR-AUC undefined. Also global scaler fit before CV leaks label information.
- **Fix options:**
  - **(a) Fix properly:** load real values from `memory_events.jsonl`/snapshots, implement LOSO/fold-local scaling, fix GBM class-weight path.
  - **(b) Drop from thesis:** disclose omission and remove from `make results`.
- **Recommendation:** Given 10-day deadline and the finding that memory effects are null/negative, **drop E4 from the primary thesis** and disclose. A broken feature-importance section is worse than no section.

### B5. `make results` does not produce the full v5 artifact set
- **Where:** `scripts/run_analysis.py`
- **Currently produces:** aggregation, Wilcoxon+TOST stats, two Pareto plots, E7 tables.
- **Missing:** GLMM, failure analysis, retrieval-overlap manipulation check, performance-summary/cost-breakdown tables.
- **Fix:** add stages for each missing artifact, gating on required inputs and preserving current skip-with-warning behavior.

---

## Must-fix — should be done before paper submission

### M1. Build hygiene (`make lint` / `make typecheck`)
- `make lint`: 59 ruff errors (whitespace, unused vars, import sorting, B905 zip-without-strict).
- `make typecheck`: 88 mypy errors; mix of missing stubs and real type mismatches.
- **Fix:** run `ruff check --fix`; install stubs; fix real type mismatches in `sequence_runner.py`, `langgraph_agent.py`, `classifier.py`, `aggregate_results.py`.
- **Note:** `make lint` currently does **not** invoke `make typecheck`; the lint gate is incomplete.

### M2. Runtime provenance (E5)
- **Where:** `src/config/loader.py`, `src/logging/*`, `src/metrics/cost_tracker.py`
- **Issue:** No run artifact records git commit, config hash, model/embedder IDs, architecture, timestamps.
- **Fix:** add `RunProvenanceLogger` that writes `runs/{run_id}/run_provenance.json` before the first task. Minimum fields: git SHA (dirty flag), canonical config hash, curriculum hash, requested/returned model names, embedder model/dim, host arch, package-lock hash, timestamp.

### M3. A2-CLS disclosure hygiene
- **Where:** `src/memory/classifier.py:5,166,216`, `src/memory/policies/cls_consolidation.py:738,771`, `src/agents/prompts.py:8`, `CLAUDE.md` D4, `AMENDMENTS.md` A2
- **Issue:** Code/docstrings still claim `temperature=0` while executable code passes `TEMPERATURE=1`.
- **Fix:** update all docstrings/comments; make `AMENDMENTS.md` A2 explicitly name the classifier; add classifier failure-rate counter.

### M4. CLS threshold/config drift
- **Where:** `configs/base.yaml:112` says `old_memory_threshold: 10`; `src/memory/policies/cls_consolidation.py:51` uses `5`; `tests/test_config_integration.py:129` asserts `10`.
- **Fix:** align to A3 (`5`) everywhere, or make the runner actually read the YAML value.

### M5. Seed-count drift (A6)
- **Where:** `configs/base.yaml:7` lists `[1,2,3]`; `src/benchmark/experiment_runner.py:157-163` enforces 3 seeds; `tests/test_experiment_runner.py:296-305` asserts 144 runs.
- **Issue:** Live matrix uses 1 seed / 48 runs.
- **Fix options:**
  - Encode A6 in config/code/tests (1 seed, relax validation, update matrix-count test).
  - Keep 3 seeds in config and document that the 1-seed matrix is manually orchestrated via `run-condition`.
- **Recommendation:** Encode A6; the current state is confusing and tests will fail if anyone runs `run_all`.

### M6. Host-architecture documentation drift (C2 / D5)
- **Where:** `CLAUDE.md:27`, root `AGENTS.md`, `README.md:20-93`, `src/agents/AGENTS.md:7`, `configs/base.yaml:116-127`
- **Issue:** Docs still describe arm64 macOS / Ollama Cloud while execution is x86_64 droplet / OpenCode Zen go.
- **Fix:** pick `configs/base.yaml:39-41` (`instance_arch: x86_64`, `namespace: swebench`) as source of truth; update all runbooks and AMENDMENTS.md D5.

### M7. Snapshot boundary names
- **Where:** `src/logging/memory_snapshot_logger.py:125`, `src/benchmark/sequence_runner.py:496`
- **Issue:** Snapshots use `before_task` / `after_task`; v5 §11.4 expects/implies `after_prune` (and three boundaries in the pseudocode).
- **Fix:** align boundary names with v5, or formally amend v5 and update all consumers (anchor-probe restoration).

### M8. Memory-event types
- **Where:** `src/logging/memory_event_logger.py:40`
- **Issue:** Only `write`/`archive`/`consolidate` logged; v5 §11.2 lists `retrieve`, `update_score`, `snapshot`.
- **Fix:** add missing event types, or amend v5/AMENDMENTS.md to narrow the required set before data collection finishes.

### M9. Cost reporting label mismatch
- **Where:** `src/analysis/result_tables.py:241`, `src/analysis/aggregate_results.py:190`
- **Issue:** Cost tables label values as USD (`$...`) and read `estimated_cost_usd` regardless of `COST_METRIC_MODE=tokens`.
- **Fix:** derive labels and aggregate field from active `cost_metric_mode`.

---

## Disclosure-only — not bugs, but must be in Methods/Amendments

| Item | Files | Action |
|---|---|---|
| A1 record cap | `configs/base.yaml:60`, `AMENDMENTS.md` | Disclose that `max_records=10` is the binding budget (below shortest sequence). |
| A2 classifier temp=1 | `classifier.py`, `AMENDMENTS.md` | Update comments + log failure rate; disclose in Methods. |
| A3 CLS inert | `cls_consolidation.py`, gate-3 findings | Disclose that CLS degenerates to Type-Aware fallback on SWE-Bench-CL due to sparse clusters. |
| A4 footprint framing | `paper/thesis_draft.typ`, `AMENDMENTS.md` | Confirm H1b is footprint/latency, not token savings. |
| A5 anchor-probe scope | `aggregate_results.py`, gate-3 findings | Decide scope (recommend: skip full; accept proxy CL-F1 with caveat). |
| A6 1 seed | `configs/base.yaml`, `AMENDMENTS.md` | Disclose reduced replication as deadline-driven limitation. |
| D5 x86_64 droplet | `CLAUDE.md`, `AGENTS.md`, `README.md` | Sync docs and disclose host deviation. |
| C7-rel retrieval relevance | `src/metrics/retrieval_quality.py:158-170` | Do not report precision/recall without structural relevance criterion; use `retrieval_overlap.py` for manipulation check. |

---

## Post-results — do after data lands

1. Populate `paper/thesis_draft.typ` Results/Discussion from generated tables (W2).
2. Migrate `datetime.utcnow()` → `datetime.now(timezone.utc)`.
3. Consolidate duplicate `plot_pareto_frontier` implementations.
4. Add analysis-module test coverage.
5. Fix proxy `compute_stability` triangle bug in `cl_metrics.py` (unused path).
6. Add generic anchor-probe CLI if A5 keeps full probe.

---

## Open advisor decisions (need user call)

1. **B1 / B2 / B3 vs. running matrix.** The matrix is already ~hours in with these bugs. Do we (a) let it finish and disclose the 21-turn + no-resume behavior, or (b) stop, patch, and restart? **Rec: let it finish; disclose.** Restart costs another ~27h and budget.
2. **B4 E4 scope.** Fix feature importance or drop it from the thesis? **Rec: drop** (deadline + null result makes it low value; broken code is a liability).
3. **A5 anchor-probe scope.** Run full anchor-probe on 48/144 runs, linchpin subset only, or accept proxy CL-F1? **Rec: accept proxy CL-F1** (gate-3 stability saturated at 1.0; full probe is expensive and uninformative).
4. **M5 seed count.** Encode A6 (1 seed) in config/tests, or keep 3 seeds and document manual orchestration? **Rec: encode A6**.
5. **M7 snapshot boundaries / M8 event types.** Align with v5 or amend v5? **Rec: amend v5 to match current two-boundary + three-event logging** to avoid re-instrumenting the running matrix.
6. **M2 provenance minimum set.** What fields are required for the thesis audit trail? **Rec: git SHA, config hash, curriculum hash, model/embedder IDs, host arch, timestamp.**

---

## Recommended next actions (in order)

1. **Do not restart the running matrix.** Let it finish; patch the analysis pipeline locally while waiting.
2. **Fix `make lint` / `make typecheck`** so the TDD gate is trustworthy.
3. **Patch B2 (`run_condition` quota leak) and B3 (resume logic)** in local code so a second matrix / restart is safe.
4. **Fix M3–M6 disclosure/config drift** (A2 comments, CLS threshold, seeds, host arch).
5. **Complete `make results` artifact set** by wiring missing stages.
6. **Decide B4 (E4) and A5 (anchor-probe)** and implement the chosen scope.
7. **Implement M2 provenance** for any new runs.
8. **When matrix finishes:** rsync runs → `make results` → populate paper.

---

## Files touched by recommended fixes

- `src/agents/limit_tracker.py` (B1)
- `src/benchmark/experiment_runner.py` (B2, B3)
- `src/analysis/feature_importance.py` (B4 — if keeping)
- `scripts/run_analysis.py` (B5)
- `src/memory/classifier.py`, `src/memory/policies/cls_consolidation.py`, `src/agents/prompts.py` (M3)
- `configs/base.yaml` (M4, M5, M6)
- `tests/test_config_integration.py`, `tests/test_experiment_runner.py` (M4, M5)
- `CLAUDE.md`, `README.md`, `src/agents/AGENTS.md`, `AMENDMENTS.md` (M3, M6)
- `src/logging/memory_snapshot_logger.py`, `src/benchmark/sequence_runner.py` (M7)
- `src/logging/memory_event_logger.py`, `src/benchmark/sequence_runner.py` (M8)
- `src/analysis/result_tables.py`, `src/analysis/aggregate_results.py` (M9)
- New: `src/logging/run_provenance_logger.py` (M2)

---

*Generated by agent swarm + synthesis. Spot-check blockers before applying.*
