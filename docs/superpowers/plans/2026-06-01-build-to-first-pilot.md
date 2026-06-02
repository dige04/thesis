# Build-to-First-Pilot Implementation Plan (Ollama Cloud)

> **Goal:** Take the thesis codebase from "tests pass on leaf modules but cannot run an experiment" to a **first valid pilot** (2 sequences × 6 conditions × 1 seed) on Ollama Cloud, faithful to THESIS_FINAL_v5.md except the four declared deviations (D1–D4 in CLAUDE.md).
>
> **Source of truth:** THESIS_FINAL_v5.md. **Contract:** CLAUDE.md. **Runbook:** AGENTS.md.
> **For agentic workers:** use `superpowers:subagent-driven-development` or `superpowers:executing-plans`; TDD per task. Each task: write failing test → implement → `make test` → commit.

This plan supersedes nothing in the 2026-05-27 repair plan; it **absorbs** that plan as Phase 2 and continues to the pilot.

---

## Architecture decisions locked 2026-06-02 (grill-me session)

These resolve the central tension the original plan under-specified: the agent ran against a **bare `git clone`** (no installed deps), while eval was a Docker placeholder. The decisions below make `resolved` trustworthy and re-sequence the critical path. They are the binding interpretation for Phases 4–7.

| # | Decision | Outcome |
|---|----------|---------|
| A | **Exec env** | **Unified swebench container** — the agent acts *inside* the per-task instance image; eval runs in the same environment. |
| B | **Compute host** | **Local arm64 macOS** (clear/expand SSD). Not the v5 §0.1-#5 x86_64 VPS. |
| C | **Architecture deviation** | **New declared deviation D5: arm64** (overrides v5 §0.1 #4/#5). Valid because architecture is held constant across all 6×3; absolute resolve non-comparable to leaderboards. Disclose in Methods. |
| D | **Unbuildable-task policy** | **Spike-Week build-probe across all 273**; tasks that won't build on arm64 are **excluded identically across all 6 conditions** + disclosed (sanctioned by v5 §0.1 #6 "documented compute trade-off"), with exact per-seq counts. **Escalate to x86_64 host if >15%/seq unbuildable.** |
| E | **Eval ground-truth** | **Load canonical SWE-bench_Verified by `instance_id`** for `FAIL_TO_PASS`/`PASS_TO_PASS`/`version`/`environment_setup_commit` (the curriculum dropped these). Curriculum stays presentation/ordering only. Probe confirms id coverage + flags any task outside Verified. |
| F | **Agent harness** | **Keep the custom ReAct loop.** NOT Claude Code (violates D1, forfeits controlled context injection #20, step caps #21, CoT-free logging), NOT a SWE-agent re-architecture. |
| G | **Tool backend** | **`docker exec` backend behind `AgentTools`** — writes via `docker cp`/stdin, `get_patch` = in-container `git diff`, one live container/task from the instance image. ReAct loop + LLM stay on host → Ollama Cloud; only tool *effects* relocate. |
| H | **Anchor-probe** | **Pilot is forward-only.** Validate the §14.2 estimator on the 2-task toy **+ one real pilot sequence**; enable full anchor-probe for the 144. |
| I | **Pilot sequences** | **django (50) + pytest (19)** — pure-Python, lowest arm64 risk, one canonical repo. |
| J | **`decay_d`** | **v5 D-0.3 wins** — frozen at theoretical §8-P4 values; pilot = sanity check, no re-tuning. CLAUDE.md calibration-window #2 is wrong and gets corrected (proposed diff, user-approved). |
| K | **Throughput** | **Sequential-first + task-boundary checkpoint/resume** (reuse `after_task` snapshots). Parallelism ≤3 (Ollama Pro cap) only after the pilot is stable. |
| L | **Smoke gate** | **Hard plumbing gate** (4 log streams + non-empty patch + real swebench 0/1 + container/resume) **+ soft capability** (≥1/3 easy tasks, NoMemory first; 0/3 → investigate, not auto-abort). |
| M | **Dead code (2.10)** | **Delete `coding_agent.py` now**, migrate Invariant-#21 (step-cap) tests onto `langgraph_agent.CodingAgent`. |

**Settled by v5 (constraints, not choices):** Pareto cost axis (§1570) = main + reflection + classifier + consolidation tokens, **excluding anchor-probe** (measurement overhead); embeddings local/flat (D2) → not counted. Implementation must (1) add a `reflection` `call_type` to `cost_tracker` (currently `agent|classifier|consolidation`), (2) tag + exclude anchor-probe tokens from the Pareto sum.

**Doc obligations:** D5 → CLAUDE.md deviation table + v5 §0.1 dated override note (locked files: propose diffs, don't auto-edit). `decay_d` → CLAUDE.md calibration-window #2 correction. arm64 runbook → AGENTS.md.

---

## Status legend
`[x]` done · `[ ]` todo · `[~]` partial

## Phase 0 — Foundation  ✅ DONE (2026-06-01)
- [x] Python venv + `pip install -e ".[dev]"` (all deps import).
- [x] Dataset acquired: `scripts/build_curriculum.py` → `data/SWE-Bench-CL-Curriculum.json` (8 seq, 273 tasks, loads through real `SWEBenchCLLoader`). **Open Q:** confirm the 4→3 difficulty collapse mapping (`>4h` and `1-4h` → `hard`) is acceptable.
- [x] Ollama scaffolding: `src/config/llm_factory.py` (two-client factory), `.env.example`, `configs/base.yaml` (Ollama model names, embedding under `memory:`, `embedding_dim: 768`, `reflection:` section, `cost_metric_mode: tokens`), `src/config/loader.py` loads `.env`.
- [x] Docs: CLAUDE.md deviation table D1–D4; AGENTS.md runbook.
- **Baseline:** 745 tests pass; 2 trivial setup failures (missing `runs/`/`results/` dirs); 11 `test_memory_retriever` ERRORS — root cause: bare `OpenAI()` refuses to construct without a key (fixed by Phase 3 Task 3.1).

---

## Phase 1 — Provider plumbing fixes that unblock tests  ✅ DONE (2026-06-01)
- [x] **1.1** Created `runs/`, `logs/`, `results/{raw,aggregated,plots}/` with tracked `.gitkeep` (+ `.gitignore` negations); `tests/test_setup.py` → 7 pass.
- [x] **1.2** `tests/test_llm_factory.py` (13 tests): precedence, `embedding_dim()` int coercion, distinct chat/embedding base_urls, `reset_clients()`.
- [x] **3.1 (pulled forward)** `store.py` builds its embedding client via `llm_factory.get_embedding_client` semantics — `OpenAI(base_url=embedding_base_url(), api_key=embedding_api_key())` — so it constructs without `OPENAI_API_KEY`. The `OpenAI` symbol is kept so existing mocks still patch `src.memory.store.OpenAI`.

> **Carry-over:** the 11 `tests/test_memory_retriever.py` tests are still RED. They are **pre-existing** (baseline = errors): their `temp_memory_store` fixture never mocked embeddings, so they make a real call to `localhost:11434`. My change flipped them error→fail (construction now succeeds). FIX (Phase 3 test-infra): add a deterministic embedding mock to that fixture **without** breaking the pure-cosine/best-last ordering assertions. Net suite: 745→**774 pass**, 13→11 red, no green→red regression.

---

## Phase 2 — Bugfix slice (absorbs 2026-05-27 repair plan + extras)  ✅ DONE (2026-06-01)
All items below applied test-first (RED→GREEN). 2.1/2.3/2.4/2.6/2.2 done by main agent; 2.5/2.7/2.8/2.9 by a parallel bugfix workflow. **Correction to 2.9:** the report's "off-by-one (`>`→`>=`)" was WRONG — the limit counters are *post-increment*, so `>` already gives the exact "20 allowed, 21 force-fail" boundary (Invariant #3); flipping to `>=` would wrongly allow only 19. The real defect was the `AgentTimeoutError` positional-arg mismatch in `coding_agent.py`, now fixed to the canonical `errors.AgentTimeoutError` signature. `limit_tracker.py` was already correct and left unchanged.

Apply each with its test (TDD). Files/lines are from the 2026-06-01 verified review.

- [ ] **2.1 Tuple/dict in `sequence_runner.py`** (repair Task 1): add `_retrieved_memory_ids` / `_retrieved_memory_log_fields`; extend `_build_task_result` with `pruned_memory_ids`/`consolidated_memory_ids`. Lines 608, 683–691.
- [ ] **2.2 Tuple/dict in `langgraph_agent.py`** (repair plan EXCLUDED this — add it): unpack `(score, record)` at 298 and 326–336. (Will be largely rewritten in Phase 4; fix now so retrieval doesn't crash.)
- [ ] **2.3 Same-repo FAISS scoring** (repair Task 2): exact per-candidate `reconstruct` scoring in `store.py::search`. Test: same-repo candidate not hidden by 100+ cross-repo vectors.
- [ ] **2.4 Store owns embedding construction** (repair Task 3): `reflection.py` stops pre-setting `embedding_text`; `store.add()` runs the truncating `embedding_utils.construct_embedding_text`. Test: nonzero `token_length`, `Issue:`/`Diff:` format, <7500 enforced.
- [ ] **2.5 Persist decay scores** (repair Task 4): `type_aware_decay.maintain()` calls `memory_store.update_importance_score(id, score)`. Test: scores appear in snapshots.
- [ ] **2.6 Archive deltas + events** (repair Task 5): add `store.archived_memory_ids_at_step()`; capture deltas around `policy.maintain()`; call `log_archive`/`log_consolidate`; pass `archived_this_step` to after-task snapshot; real `pruned_memory_ids`/`consolidated_memory_ids` into `_build_task_result`. Implement the `store.archive()` event-logging TODO (L547).
- [ ] **2.7 Loader no-reorder** (repair Task 6): replace `tasks.sort(...)` with `ValueError` on out-of-order (Invariant #1). Update any test expecting reordering.
- [ ] **2.8 CLS majority-type** (Bug 1): `cls_consolidation._consolidate_cluster` assigns the cluster **majority** `memory_type` instead of `"consolidated_summary"` (keeps Invariant #7). Remove the duplicate `_consolidate` def. Test: consolidated record has a valid type and `add()` succeeds.
- [ ] **2.9 Off-by-one** (Issue 7): `>` → `>=` in `limit_tracker.py` (100/116/132/148) and `coding_agent.py` (136). Test: 20th step allowed, 21st force-fails. Fix `AgentTimeoutError` positional-arg mismatch in `coding_agent.py`.
- [ ] **2.10 Delete `coding_agent.py`** (DECIDED 2026-06-02 → decision M): it is production-dead (only `langgraph_agent.CodingAgent` is wired; sole remaining reference is a comment). Delete the module **now**, before the Phase-4 container-backend rework, so there is a single agent to modify. Migrate the Invariant-#21 step/tool/test-cap assertions + `AgentTimeoutError` signature tests in `tests/test_agent_limits.py` (and refs in `tests/test_config*.py`) onto `langgraph_agent.CodingAgent`; drop tests that only exercised the dead module.

**Acceptance:** all 6 policies' `policy.retrieve()` results flow through the runner without `AttributeError`; CLS consolidation constructs a valid record; `make test` green.

---

## Phase 3 — Wire `llm_factory` + JSON-mode classifier
- [ ] **3.1 `store.py`**: `OpenAI()` → `llm_factory.get_embedding_client()`; `embedding_model`/`embedding_dim` from config (already plumbed via `memory.*`). FAISS `IndexFlatIP(self.embedding_dim)`. **Clears the 11 retriever ERRORS** (client always has a key). Test: store constructs with no `OPENAI_API_KEY` in env.
- [ ] **3.2 `classifier.py`**: `OpenAI(api_key=...)` → `get_chat_client()`; model from `llm_factory.classifier_model()` (drop hardcoded `MODEL`); replace `beta.chat.completions.parse` with `chat.completions.create(response_format={"type":"json_object"})` + Pydantic validation + bounded retry (method already has `retry_count`). Keep temp 0, 5-type enum. Test: parses valid JSON; falls back/raises uniformly on invalid after N retries; **log failure rate**.
- [ ] **3.3 Embedding-dim sanity**: assert the live embedder's vector length == `embedding_dim` at store init (fail fast on mismatch). Test with a stubbed client.

**Acceptance:** retriever tests pass; classifier returns the 5-type label via JSON mode against a stubbed OpenAI-compatible client.

---

## Phase 4 — Real coding agent (the gate)  🟡 IN PROGRESS (2026-06-01)
> **Done:** the v5 §4.4 ReAct tool-use loop is implemented in `CodingAgent.solve_task` (`langgraph_agent.py`): binds the chat client (`get_chat_client`/`main_model`, temp 0), exposes the 8 §4.3 tools (+`finish`) as OpenAI tool schemas, wires the already-functional `AgentTools` against `task_env.working_dir`, iterates under `LimitTracker` (strict max-20 / 80 / 5), generates the patch via `git diff`, records the trajectory as action+observation only (no CoT, §11.3), and accumulates token usage. Reflection/write/maintain (nodes 10–12) are left to `SequenceRunner` — fixes the latent double-`maintain()`. The legacy 12-node graph is superseded (still built in `__init__`; harmless). Tested with a fake tool-calling client over a real temp git repo: edits a file → non-empty patch; never-finish → force-fail at step 21 (`tests/test_agent_react_loop.py`).
> **Phase 3.2 (classifier)** done — JSON-mode + factory + retry (committed separately).
> **4.5 reflection LLM** ✅ (2026-06-02): `_extract_reflection_data` calls the LLM (JSON-mode + `ReflectionSummary` Pydantic, §9.2 schema); `outcome`/`files_touched` stay deterministic; falls back to naive truncation on any LLM failure (never crashes the task). `embedding_text` still left to the store (#4).
> **4.6 CLS summary LLM** ✅ (2026-06-02): `_generate_summary` calls the LLM (§P5 prompt, JSON-mode + `ConsolidationSummary` Pydantic), composes the consolidated content, caps at 350 tokens via tiktoken (real `count_tokens`), keeps majority `memory_type` (#7) + `is_consolidated`; falls back to placeholder on failure.
> **Remaining in Phase 4:**
> - **4.8 (NEW, decision A+G) — container execution backend.** The loop currently wires `AgentTools` against `task_env.working_dir`, a **bare `git clone` with no installed deps** → `run_command`/`run_tests` are meaningless. Introduce an execution-backend seam behind `AgentTools`: a **container backend** maps `read/write/edit/search/list/run_command/run_tests` to `docker exec` against one live per-task container started from the swebench **instance image** (deps installed); writes via `docker cp`/stdin; `get_patch` = `docker exec … git diff`. Keep a `LocalBackend` (current behavior) for unit tests. The ReAct loop, `LimitTracker`, trajectory logging, and LLM/Ollama path are unchanged — only tool *effects* relocate into the container. This supersedes 4.2's "execute against the checked-out repo via `task_env`".
> - **4.9** end-to-end validation against a live model (needs the Ollama key) — now run *inside* the instance container.

Original task list (4.1–4.4, 4.7 ✅ via the loop above):
- [ ] **4.1** Bind a chat model in `langgraph_agent.py` via `get_chat_client()` + `main_model()`, temp 0, with tool-calling.
- [ ] **4.2** Wire `src/agents/tools.py` (read/write/edit/search/list/run_command/run_tests/get_patch) into the nodes; execute against the checked-out repo via `self.task_env` (plumbed at L133, currently unused). Enforce limits via `LimitTracker` (post-2.9).
- [ ] **4.3** Implement `planning → code_search → file_editing → test_execution → repair_loop → final_patch_generation`; `final_patch_generation` returns a real `git diff` (else `_evaluate_patch` short-circuits to `resolved=0`).
- [ ] **4.4** Implement `memory_write` node: classify + `policy.write` so memory accumulates. Best-item-LAST injection already correct in `prompts.py` — keep it.
- [ ] **4.5** Implement real reflection LLM (`reflection.py:201`) via `get_chat_client()` + `summary_model()`; structured summary of issue/error/diff (still routed through the truncating embedder from 2.4).
- [ ] **4.6** Implement real CLS summary (`cls_consolidation.py:565/572`) via `summary_model()`; `tiktoken` token_length.
- [ ] **4.7** Trajectory schema: action + action_input + observation_summary only — **no chain-of-thought** (Invariant / v5 §11.3).

**Acceptance:** on one real curriculum task, the agent produces a non-empty patch and the trajectory logs actions+observations (no CoT). Respect 20-step hard fail.

---

## Phase 5 — Real eval_v3 + CL-F1 + cost-as-tokens  🟡 PARTIAL (2026-06-02)

- [ ] **5.0 (NEW, GATE — decisions D+E) — build-probe + canonical-Verified join.** Before any real run, a one-off Spike-Week probe over **all 273 instance_ids**:
  - **Coverage:** confirm every curriculum `instance_id` resolves in `princeton-nlp/SWE-bench_Verified` (HF). Flag any task that falls outside Verified (→ would need full SWE-bench, worse arm64 image coverage). Pull `FAIL_TO_PASS`/`PASS_TO_PASS`/`version`/`environment_setup_commit` for the join.
  - **Buildability:** attempt the swebench **arm64** image build/pull per instance; record success + build time. Produce a **deterministic exclusion list** (unbuildable-on-arm64 tasks), persisted to a tracked artifact so the exclusion is identical across all 6 conditions × 3 seeds.
  - **Gate:** if **>15% of any sequence** is unbuildable → escalate to an x86_64 host (revisit decision B). Else proceed; disclose exact per-seq exclusion counts (D5 sample restriction, sanctioned by v5 §0.1 #6).
  - Confirms django + pytest (the pilot pair, decision I) build cleanly.
- [~] **5.1** `evaluator.py`: ✅ fixed the invalid `--timeout=` docker flag; ✅ replaced substring parsing with real JSON-report parsing (`_resolved_from_report` accepts `{resolved}`, per-instance `{task_id:{resolved}}`, and `resolved_ids`/`resolved_instances` lists), tested in `tests/test_evaluator_parsing.py` (8 tests incl. "substring 'failed' must not flip the verdict"). **STILL PENDING (needs live Docker env + `swebench` dependency):** rebuild the harness invocation around the **public `swebench` package** (add to `pyproject.toml`) — load the **canonical SWE-bench_Verified row by `instance_id`** (decision E) for `FAIL_TO_PASS`/`PASS_TO_PASS`/`version`/`env_setup_commit`, apply the agent's patch on `base_commit` **inside the same instance image the agent edited** (decision A+G), run F2P/P2P, parse the real report. Reconcile with the 4.8 container backend so eval sees the agent's edits (extract patch via in-container `git diff`, then eval in the same/fresh instance container). Build-on-demand + prune between tasks (72 GB constraint). `make setup`/`verify-env`. The current `docker run` command is a structural placeholder; parsing is real.
- [~] **5.2** ✅ `cl_metrics.compute_anchor_probe_cl_metrics` implements §14.2 verbatim (Plasticity/Stability_anchor/CL_F1); ✅ `aggregate_results` uses it when anchor-probe data is present, else a clearly-marked `cl_f1_source="resolved_rate_proxy"` (never a silent placeholder). Data contract: `runs/{run_id}/anchor_probe.json`. **STILL PENDING:** the anchor-probe DATA COLLECTION (runner re-evaluates anchors against later snapshots) — depends on 5.1 real eval. Full-matrix path (§14.3) left as supplementary. **(decision H) The pilot does NOT collect anchor-probe data** — validate the estimator on the 2-task toy **+ one real pilot sequence**, then enable full §14.2 collection for the 144. Anchor-probe re-eval token usage must be **tagged and excluded** from the Pareto cost sum (v5 §1570).
- [~] **5.3** Cost-as-tokens (D3): ✅ `cost_tracker` takes `cost_metric_mode` (default "usd" preserves tests; non-USD → no raise on unknown model, USD recorded 0, tokens authoritative). ✅ `pareto.py` `metric_x` default → `mean_total_tokens`. **STILL PENDING (v5 §1570 fidelity):** (a) add a **`reflection`** value to `cost_tracker`'s `call_type` enum (currently only `agent|classifier|consolidation`) so the reflection LLM call is counted per §925/§1570; (b) tag anchor-probe re-eval tokens so they are **excluded** from the Pareto sum; (c) finish `CostTracker`-into-runner wiring so `cost_summary.json` (the 4th mandatory log stream) is written.
- [x] **5.4** ✅ `TrajectoryLogger` wired into `sequence_runner._execute_task` (per task, action+observation only, no CoT). 3 of 4 mandatory log streams now produced by a run (cost_summary.json pending full CostTracker wiring).

**Acceptance (revised):** parsing + math + plumbing done and unit-tested; the two live-env pieces (real harness execution, anchor-probe re-eval) are explicitly pending the Ollama key + Docker images.

---

## Phase 6 — Run entry point + smoke
- [ ] **6.1** Add `__main__`/argparse to `experiment_runner.py` (`--policy --seed --pilot --sequences`); wire `make pilot`/`make run-condition`/`make run-all` to `_generate_run_matrix` (8×6×3=144). **(decision K) Execution = sequential-first** (1 run at a time) for observability + to avoid laptop RAM/quota thrash. **Checkpoint/resume at the task boundary** by reusing the already-logged `after_task` memory snapshots: on restart, detect an existing `run_dir`, replay memory state from the latest snapshot, and skip completed tasks — so a crash or an Ollama **5h/7d quota reset** resumes mid-sequence. Bounded parallelism (≤3, the Pro cap) is a *post-pilot* switch, not built now.
- [ ] **6.2** Replace `smoke_test.main` mock sequence with a real curriculum sequence (NoMemory first to avoid the memory path), drawing **`difficulty_label == "easy"`** tasks from the pilot repos. **(decision L) Two-part gate:**
  - **Hard plumbing gate (GO/NO-GO):** all 4 mandatory log streams written, a **non-empty patch** generated, the swebench harness returns a **real 0/1** (not an error), and container build + checkout + checkpoint/resume all work.
  - **Soft capability check:** ≥1/3 resolved on the easy tasks (preserves v5's >15% number). **0/3 → investigate** (prompt/tool-use/harness), re-probe on more tasks; do **not** auto-abort the thesis on 3-task variance.

**Acceptance:** `make smoke` passes the hard plumbing gate end-to-end on Ollama Cloud (real `resolved`, valid logs) and the soft capability check is recorded.

---

## Phase 7 — Pilot + calibration
- [ ] **7.1** `make pilot` = **django (50) + pytest (19)** × 6 cond × 1 seed = 12 runs (decision I), **forward-only** (no anchor-probe, decision H), executed **sequentially with checkpoint/resume** (decision K). All 6 policies run without crashing; snapshots/events/trajectories/cost all produced; CL-F1 computes via the `resolved_rate_proxy` path (forward-only) with the anchor-probe estimator separately validated on the 2-task toy + one real pilot sequence.
- [ ] **7.2** Calibrate **`top_k` + `max_context_tokens` only** (Friday gate) — **re-validate under the nomic embedder (D2)**, change *once*, then `freeze_calibration_params()`; LOCK. **`decay_d` is NOT calibrated** (decision J / v5 D-0.3 §796): it stays at the theoretical §8-P4 values; the pilot's Type-Aware Decay result is a *sanity check carried into the main run*, never a tuning input. (CLAUDE.md calibration-window #2 to be corrected to match — see doc diffs.)
- [ ] **7.3** (Pre-144, analysis correctness, not blocking pilot) Fix `glmm.py` fake `glmer` import (R/lme4 primary or bambi/pymc); `feature_importance` scaler-leak + GBM `sample_weight` + real features from `memory_events.jsonl`; rank-biserial zero-diff handling; `behavioral.py` array alignment.

**Acceptance:** a clean 12-run pilot with valid CL-F1 + cost(tokens) Pareto inputs; hyperparameters frozen → ready for 144.

---

## Cross-cutting reminders
- Every code-changing task ships with a pytest asserting the relevant frozen invariant.
- Disclose **D1–D5** in thesis Methods (D5 = arm64 architecture + its arm64-buildability sample restriction); propose a dated override note for v5 §0.1 (do not silently edit the locked file).
- Do not introduce conditions 7/8/9; do not change retrieval scoring; do not embed raw trajectories; keep the embedder identical across all conditions/seeds.
