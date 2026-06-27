# Thesis Pilot-to-Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the thesis from strong protocol plus simulated report to an audit-valid pilot, then to the full 144-run matrix and final thesis report.

**Architecture:** Keep `THESIS_FINAL_v5.md` as design source of truth; use root `AGENTS.md` and a new `AMENDMENTS.md` as the runtime/amendment layer. The implementation path gates data collection behind smoke, pruning/manipulation checks, complete cost telemetry, anchor-probe CL-F1, and reproducible analysis commands.

**Tech Stack:** Python, pytest, Ruff, mypy, Docker/SWE-bench `eval_v3`, SQLite + FAISS memory store, Typst thesis reports, OpenCode Zen go chat models, local Ollama embedding endpoint.

---

## Current evidence

- `configs/base.yaml` now uses `memory.max_records: 10`, so pruning can fire within 19–50 task sequences.
- `configs/base.yaml` uses `temperature: 1` for current Kimi-family model path; this is an amendment from v5 temperature 0 and must be centrally disclosed.
- `Makefile` routes `smoke`, `pilot`, `run-condition`, and `run-all` to Python entry points, but `aggregate`, `stats`, and `plots` remain TODO echo targets.
- `src/benchmark/sequence_runner.py` now wires trajectories, patches, memory events, snapshots, and cost tracking; swarm audit also produced one observed single-task data point.
- Observed single-task data point: NoMemory, `pytest-dev__pytest-5262`, seed 1, resolved=1, `patch_generated=true`, SWE-bench eval passed, wall time ~152s, total tokens ~61,938, with overrides `agent.execution_backend = "local"` and `evaluation.namespace = ""`; all mandatory logs were produced.
- Remaining risk is audit-valid sequence execution and anchor-probe CL-F1, not whether the pipeline can ever complete one task.
- `src/analysis/statistical_tests.py` still needs TOST; `src/analysis/glmm.py` still imports a non-existent `statsmodels.formula.api.glmer`; `src/analysis/feature_importance.py` still contains placeholder feature extraction.
- `paper/thesis_report_simulated.typ` and `.pdf` are simulation artifacts only for thesis results; the single-task operational evidence above is real but does not support H1–H5.
- Swarm completeness audit reports the current x86_64 `swebench` namespace is not pullable in this environment; the minimum reproducible path is to commit or pass the local-backend/empty-namespace config used for the valid task, run build-probe or targeted smoke, then scale to one-policy sequence.

---

### Task 1: Lock amendments and runtime facts

**Files:**
- Create: `AMENDMENTS.md`
- Modify: `configs/base.yaml`
- Modify: `src/config/loader.py`
- Modify later after advisor sign-off: `AGENTS.md`, `README.md`, `paper/thesis_draft.typ`

- [ ] **Step 1: Create amendment record**

Create `AMENDMENTS.md` with these dated entries:

```markdown
# Pre-registration Amendments and Runtime Deviations

## A1 — Binding memory budget

- Date: 2026-06-14
- Change: `memory.max_records` changed from 100 to 10.
- Reason: all official sequence lengths are 19–50 tasks, so cap 100 never binds when writing one record per task; Random/Recency/Type-Aware would be operationally identical to Full Memory.
- Validity condition: cap is applied identically to Random Prune, Recency Prune, Type-Aware Decay, and CLS fallback; Full Memory remains the boundary baseline and ignores pruning caps by design.
- Disclosure: Methods → Deviations from pre-registration.

## A2 — Temperature setting

- Date: 2026-06-14
- Change: agent/reflection temperature changed from 0 to 1.
- Reason: selected Kimi-family model endpoint rejects temperature 0.
- Validity condition: temperature is held constant across all policies, sequences, and seeds.
- Disclosure: Methods → Deviations from pre-registration.

## D1–D5 — Runtime deviations

Summarize the provider/model, embedder, cost metric, classifier structured-output path, and final execution host/image path exactly as run.
```

- [ ] **Step 2: Remove frozen decay params from calibration list**

In `src/config/loader.py`, remove `type_aware_decay.type_params` from any calibration allowlist. Decay values are frozen by v5 D-0.3 and cannot be pilot-tuned.

- [ ] **Step 3: Verify amendment invariants**

Run:

```bash
.venv/bin/python -m pytest tests/test_config_integration.py -v
```

Expected: PASS. If a test still expects `max_records: 100` or temperature 0, update the test to assert the amendment and cite `AMENDMENTS.md`.

---

### Task 2: Close retrieval and policy contract bugs

**Files:**
- Modify: `src/memory/policies/no_memory.py`
- Modify: `src/memory/store.py`
- Modify: `src/memory/policies/cls_consolidation.py` if replacement links are not persisted through events
- Test: `tests/test_memory_policy_invariants.py` or nearest existing policy test

- [ ] **Step 1: Normalize NoMemory return contract**

Make `NoMemoryPolicy.retrieve(...)` return an empty list of scored tuples, i.e. `list[tuple[float, MemoryRecord]]`, matching `MemoryPolicy` and every other policy.

- [ ] **Step 2: Persist or event-log CLS replacement provenance**

Ensure source memory id → consolidated summary id can be reconstructed from `memory_events.jsonl`. Either persist `replacement_id` in SQLite archive metadata or emit complete `log_consolidate` events immediately after maintenance.

- [ ] **Step 3: Run focused policy tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_cls_consolidation_policy.py tests/test_memory_policy_invariants.py -v
```

Expected: PASS. If `tests/test_memory_policy_invariants.py` does not exist, use the closest existing policy test and add a regression that all `retrieve()` methods return tuple-shaped results.

---

### Task 3: Prove execution path with smoke

**Files:**
- Inspect only unless failures require fixes: `src/benchmark/smoke_test.py`, `src/benchmark/task_env.py`, `src/agents/tools.py`, `src/benchmark/evaluator.py`
- Artifacts: `runs/<smoke-run-id>/task_results.jsonl`, `memory_events.jsonl`, `trajectories/*.json`, `memory/snapshots/*.json`, `cost_summary.json`

- [ ] **Step 1: Verify environment wiring**

Run:

```bash
make verify-env
```

Expected: chat client can call OpenCode Zen go; embedding client returns vector length matching `EMBEDDING_DIM`; Docker and required dataset paths are available.

- [ ] **Step 1a: Reproduce the observed single-task data point through an explicit config path**

The swarm audit already resolved `pytest-dev__pytest-5262` under these overrides:

```yaml
agent:
  execution_backend: "local"
evaluation:
  namespace: ""
```

Expected: NoMemory, seed 1, `pytest-dev__pytest-5262` resolves or at least produces the same mandatory logs. If the final execution target is container backend, pre-build/retain instance images before `SequenceRunner` starts; otherwise keep local backend for smoke/pilot and disclose it in `AMENDMENTS.md`.

- [ ] **Step 2: Run smoke**

Run:

```bash
make smoke
```

Expected hard plumbing gate: no schema/infrastructure errors, non-empty patch field for attempted tasks, real eval verdicts are 0/1, and all four mandatory log streams exist.

- [ ] **Step 3: Inspect smoke artifacts**

Manually inspect the generated run directory. Required files:

```text
task_results.jsonl
memory_events.jsonl
trajectories/<task_id>.json
memory/snapshots/before_task_*.json
memory/snapshots/after_task_*.json
cost_summary.json
```

Do not require high solve rate at this gate; require valid instrumentation.

---

### Task 4: Run manipulation-check pilot before full pilot

**Files:**
- Modify if needed: `src/analysis/retrieval_overlap.py`
- Modify if needed: `src/benchmark/sequence_runner.py`
- Artifacts: `runs/*/memory_events.jsonl`, `runs/*/retrieval_overlap.jsonl`, `runs/*/cost_summary.json`

- [ ] **Step 1: Run one short sequence across six policies**

Run a small condition set before the 12-run pilot. Use the shortest stable sequence available in the curriculum.

```bash
.venv/bin/python -m src.benchmark.experiment_runner --mode pilot --num-sequences 1 --curriculum data/SWE-Bench-CL-Curriculum.json
```

Expected: six runs for one seed, all producing complete logs.

- [ ] **Step 2: Check pruning fires**

For Random, Recency, Type-Aware, and CLS fallback, confirm `archive` or `consolidate` events appear after active count exceeds 10.

- [ ] **Step 3: Check retrieval manipulation reaches prompt-visible context**

Generate or inspect `retrieval_overlap.jsonl`. Expected: median retrieved-ID Jaccard between pruning policies and Full Memory is below 0.9. If overlap is above 0.9, stop and diagnose budget/retrieval before scaling.

---

### Task 5: Implement primary CL-F1 and analysis gates

**Files:**
- Modify: `src/benchmark/sequence_runner.py` or a new benchmark probe module
- Modify: `src/analysis/aggregate_results.py`
- Modify: `src/analysis/statistical_tests.py`
- Modify: `src/analysis/glmm.py`
- Modify: `src/analysis/feature_importance.py`
- Modify: `Makefile`
- Tests: existing analysis tests plus new TOST/GLMM fixture tests

- [ ] **Step 1: Produce anchor-probe data**

Add the primary anchor-probe producer that writes `anchor_probe.json` for each run. It must implement v5 §14.2: five deterministic anchors and four probe points per sequence.

- [ ] **Step 2: Reject proxy CL-F1 in final analysis**

`aggregate_results.py` may keep `resolved_rate_proxy` for development, but final stats must refuse proxy CL-F1 unless a simulation/test flag is explicit.

- [ ] **Step 3: Add TOST**

Implement TOST with SESOI ±0.03 and emit v5 H1a outcome labels A/B/C/D.

- [ ] **Step 4: Fix GLMM path**

Replace the non-existent `statsmodels.formula.api.glmer` path with either a working Python model or an R `lme4::glmer` bridge approved by the advisor.

- [ ] **Step 5: Wire Make targets**

Replace echo-only targets:

```bash
make aggregate
make stats
make plots
```

Expected: each command reads raw/fixture logs, validates schema, and writes deterministic artifacts under `results/aggregated/`, `results/tables/`, or `results/plots/`.

---

### Task 6: Run 12-run pilot and advisor gate

**Files/artifacts:**
- `runs/`
- `results/raw/`
- `results/aggregated/`
- `paper/thesis_draft.typ` only after pilot facts are known

- [ ] **Step 1: Run pilot**

Run:

```bash
make pilot
```

Expected: 2 sequences × 6 policies × 1 seed = 12 complete runs.

- [ ] **Step 2: Generate pilot report**

Run:

```bash
make aggregate
make stats
make plots
```

Expected: pilot table includes missingness, policy firing, retrieval overlap, cost completeness, and CL-F1 source.

- [ ] **Step 3: Advisor go/no-go**

Proceed to 144 runs only if:

- no silent provider/infrastructure fallbacks;
- pruning fires in every relevant policy;
- retrieval overlap differs from Full Memory;
- cost summary is complete;
- anchor-probe CL-F1 is available;
- analysis commands reproduce pilot tables.

---

### Task 7: Replace simulated report with generated thesis results

**Files:**
- Modify: `paper/thesis_draft.typ`
- Keep as scaffold only: `paper/thesis_report_simulated.typ`
- Output: `paper/thesis_draft.pdf`

- [ ] **Step 1: Preserve simulation artifact**

Keep `paper/thesis_report_simulated.typ` as a planning scaffold. Do not cite it as evidence.

- [ ] **Step 2: Generate final thesis tables from analysis outputs**

Populate Results only from generated analysis artifacts, not manual transcription.

- [ ] **Step 3: Update Methods and Deviations**

Correct provider, host/image path, sequence task counts, max-record amendment, temperature amendment, cost metric, classifier JSON-mode path, and any build exclusions.

- [ ] **Step 4: Compile thesis**

Run:

```bash
typst compile paper/thesis_draft.typ paper/thesis_draft.pdf
```

Expected: PDF compiles, contains no `[PENDING DATA]` boxes in final empirical sections, and every result number traces to generated artifacts.
