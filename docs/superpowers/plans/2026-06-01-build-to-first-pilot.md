# Build-to-First-Pilot Implementation Plan (Ollama Cloud)

> **Goal:** Take the thesis codebase from "tests pass on leaf modules but cannot run an experiment" to a **first valid pilot** (2 sequences × 6 conditions × 1 seed) on Ollama Cloud, faithful to THESIS_FINAL_v5.md except the four declared deviations (D1–D4 in CLAUDE.md).
>
> **Source of truth:** THESIS_FINAL_v5.md. **Contract:** CLAUDE.md. **Runbook:** AGENTS.md.
> **For agentic workers:** use `superpowers:subagent-driven-development` or `superpowers:executing-plans`; TDD per task. Each task: write failing test → implement → `make test` → commit.

This plan supersedes nothing in the 2026-05-27 repair plan; it **absorbs** that plan as Phase 2 and continues to the pilot.

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
- [ ] **2.10 Decide on `coding_agent.py`**: it is unused dead code (only `langgraph_agent.CodingAgent` is wired). Delete it OR mark clearly. (Ask user; default: delete after Phase 4 to avoid editing the wrong agent.)

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
> **Remaining in Phase 4:** 4.5 real reflection LLM (`reflection.py:_extract_reflection_data` still naive truncation) and 4.6 real CLS summary (`cls_consolidation` still placeholder f-string). Both route through `get_chat_client()`/`summary_model()`. End-to-end validation against a live model needs the Ollama key.

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

## Phase 5 — Real eval_v3 + CL-F1 + cost-as-tokens
- [ ] **5.1** Rebuild `evaluator.py` around the public `swebench` harness: apply the candidate patch on top of `base_commit`, run `FAIL_TO_PASS`/`PASS_TO_PASS` from `test_patch`, parse the real JSON report → `resolved`. Remove the invalid `--timeout=` docker flag. Reconcile with `task_env` (the eval must see the agent's edits). Build/pull the eval image; implement `make setup`/`make verify-env`.
- [ ] **5.2** Real CL-F1: `aggregate_results.py:124` calls `cl_metrics.compute_cl_metrics`; implement the **anchor-probe** re-evaluation (v5 FD#29 PRIMARY) for the off-diagonal `a_{i,j}`; full matrix is supplementary. Replace `cl_metrics.build_accuracy_matrix` "assumes no forgetting" forward-fill (L174–184).
- [ ] **5.3** Cost-as-tokens (D3): `cost_tracker` honors `cost_metric_mode`; when `!= usd`, record `total_tokens`/`wall_time`, do **not** raise on unknown model names. Wire `CostTracker` into `sequence_runner` (+ `write_cost_summary`). `pareto.py` `metric_x` → `mean_total_tokens`.
- [ ] **5.4** Wire `TrajectoryLogger` into `sequence_runner` (per task). 4 mandatory log streams now all produced.

**Acceptance:** one task end-to-end yields a genuine `resolved` 0/1 from the real harness; all 4 log streams written; CL-F1 computed from a real matrix on a 2-task toy.

---

## Phase 6 — Run entry point + smoke
- [ ] **6.1** Add `__main__`/argparse to `experiment_runner.py` (`--policy --seed --pilot --sequences`); wire `make pilot`/`make run-condition`/`make run-all` to `_generate_run_matrix` (8×6×3=144). Add checkpoint/resume (Ollama quota/concurrency: Pro=3, 5h/7d resets).
- [ ] **6.2** Replace `smoke_test.main` mock sequence with a real curriculum sequence (a repo that clones cleanly). Run `make smoke` (NoMemory first to avoid the memory path), gate >15% pass.

**Acceptance:** `make smoke` runs a real task end-to-end on Ollama Cloud and writes valid logs.

---

## Phase 7 — Pilot + calibration
- [ ] **7.1** `make pilot` = 2 seq × 6 cond × 1 seed = 12 runs; all 6 policies run without crashing; snapshots/events/trajectories/cost all produced; CL-F1 computes.
- [ ] **7.2** Calibrate `top_k` + `max_context_tokens` (Friday gate) and Type-Aware Decay `decay_d` per type (Week-4) — **re-validate under the nomic embedder (D2)**. Then `freeze_calibration_params()`; LOCK.
- [ ] **7.3** (Pre-144, analysis correctness, not blocking pilot) Fix `glmm.py` fake `glmer` import (R/lme4 primary or bambi/pymc); `feature_importance` scaler-leak + GBM `sample_weight` + real features from `memory_events.jsonl`; rank-biserial zero-diff handling; `behavioral.py` array alignment.

**Acceptance:** a clean 12-run pilot with valid CL-F1 + cost(tokens) Pareto inputs; hyperparameters frozen → ready for 144.

---

## Cross-cutting reminders
- Every code-changing task ships with a pytest asserting the relevant frozen invariant.
- Disclose D1–D4 in thesis Methods; propose a dated override note for v5 §0.1 (do not silently edit the locked file).
- Do not introduce conditions 7/8/9; do not change retrieval scoring; do not embed raw trajectories; keep the embedder identical across all conditions/seeds.
