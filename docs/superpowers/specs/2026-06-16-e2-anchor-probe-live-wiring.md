# Spec — E2 anchor-probe LIVE WIRING (run-host implementation)

**Date:** 2026-06-16 · **Status:** core done (`src/benchmark/anchor_probe.py`), live wiring pending · **Run on:** the droplet (needs Docker + Kimi + a completed run). **Do NOT edit `sequence_runner.py`** — this is a standalone post-hoc producer, run after a sequence's forward pass.

## What already exists (done + tested, `tests/test_anchor_probe.py`)

`src/benchmark/anchor_probe.py`:
- `anchor_indices(T)` / `probe_points(T)` — §14.2 schedule, **1-indexed** positions. T=30 → anchors `[3,9,15,21,27]`, probes `[8,15,23,30]`.
- `online_resolved_from_task_results(run_dir)` — reads `a_{i,i}` (0/1 per task, sequence order) from `task_results.jsonl`.
- `build_anchor_probe_record(..., restore_memory_fn, solve_and_eval_fn)` — orchestrates re-evaluation with the two live functions **injected**, returns the dict that `load_anchor_probe_data` → `compute_anchor_probe_cl_metrics` consume.
- `write_anchor_probe(run_dir, record)` — writes `anchor_probe.json`.

Output already round-trips through the real aggregation path (verified). Once `anchor_probe.json` exists per run, `aggregate_sequence_results` reports `cl_f1_source="anchor_probe"` instead of the proxy.

## The three live pieces to implement

### 1. `restore_memory_fn(probe_p) -> memory_state`
Reconstruct the memory state **as it was after the p-th task**.
- **Index map (critical):** probe `p` is 1-indexed → snapshot file `memory/snapshots/after_task_{p-1}.json` (snapshots are 0-indexed; `after_task_0.json` = after the 1st task — confirmed against `runs/smoke_test_django_django_sequence_42/`).
- Read that snapshot's `active_records` → the set of active `memory_id`s at p.
- Load the **full** records (content + embedding payload) for those ids from `memory/memory.db` (the snapshot has only `{memory_id, importance_score, memory_type}`; archived records stay in the db, so all ids resolve).
- Build a retrievable structure restricted to that active set so `shared_retrieve` can run against it. **Check first:** does `memory.db` persist the embedding vector? If yes, rebuild the FAISS index from stored vectors. If not, re-embed via the **same** Ollama embedder (`nomic-embed-text-v2-moe`, deterministic) — must be the identical embedder (Invariant #5 / D2).

### 2. `solve_and_eval_fn(anchor_task_id, memory_state) -> 0|1`
Re-run the agent on the anchor task with the restored memory, score with the canonical evaluator.
- **Anchor task lookup:** anchor position `i` (1-indexed) → the task at `sequence_index == i-1` in the sequence (`anchor_task_ids[i] = sequence.tasks[i-1].task_id`).
- Clean checkout via `ContainerBackend` (x86_64 swebench image), retrieve against `memory_state`, run `CodingAgent.solve_task(task, retrieved_memories=...)`, get the patch, run `SWEBenchEvaluator` → `resolved` 0/1. **Reuse the existing agent + evaluator paths** (same as the forward run).
- **temp=1 caveat (amendment A2):** re-evaluation is non-deterministic. Seed it and keep **one** re-eval per `(i,p)` cell per §14.2 (budget bound 4×5=20/run); disclose the resulting estimator noise in Limitations.

### 3. `produce_anchor_probe(run_dir, sequence) -> Path`
Top-level wiring (new CLI / `make anchor-probe`, called after each sequence completes):
- `online_resolved = online_resolved_from_task_results(run_dir)`.
- Build `anchor_task_ids` from the sequence (position i → `tasks[i-1].task_id`).
- Call `build_anchor_probe_record(...)` with the real `restore_memory_fn` / `solve_and_eval_fn`.
- `write_anchor_probe(run_dir, record)`.

## LOCKED DESIGN (2026-06-17 — feasibility confirmed against gate-3 `memory.db`)

**Key finding: no re-embedding of stored records needed.** `memory_records` persists
`sequence_index`, `is_archived`, `archived_at_step`, and `embedding_vector_id`; the
vectors live in `memory.faiss` keyed by that id. So memory-state-after-`p` is
reconstructable from the run's own `memory.db` + `memory.faiss` (Ollama/nomic is
needed only to embed the anchor's *query* at retrieval time).

`restore_memory_fn(run_dir, p)` (the only genuinely new code):
1. Copy `runs/<run>/memory/{memory.db,memory.faiss}` → a temp run dir `runs/_ap_tmp_<...>/memory/`.
2. On the temp DB, set archived-state-as-of-`p`:
   `UPDATE memory_records SET is_archived = CASE WHEN sequence_index <= :p AND (archived_at_step IS NULL OR archived_at_step > :p) THEN 0 ELSE 1 END;`
   (records created after `p` → excluded; records archived after `p` → active again; records archived ≤`p` → stay archived.)
3. `MemoryStore(run_id="_ap_tmp_<...>", policy_name=..., embedding_dim=768, embedding_model="nomic-embed-text-v2-moe")` — loads the temp DB + FAISS; `active_records()` now returns the active-at-`p` set. **`shared_retrieve` runs unchanged → Invariant #5 preserved exactly.**

`solve_and_eval_fn` — **reuse `sequence_runner`'s proven path, do not reimplement**:
`shared_retrieve(anchor_task, restored_store, top_k, budget)` → `CodingAgent(memory_store=restored_store, policy, config, task_env).solve_task(task_dict, retrieved_memories=...)` → `SWEBenchEvaluator.evaluate_patch(task, patch, work_dir)` → `1 if passed else 0`. Construct `task_env` (ContainerBackend, x86_64 swebench image) exactly as `sequence_runner._execute_agent` does.

Index map (unchanged): anchor position `i` (1-indexed) → `sequence.tasks[i-1]`; probe `p` uses `archived_at_step`/`sequence_index` ≤ `p` (so the snapshot files aren't even needed — the DB is authoritative).

## Cost & verification
- **Budget:** ≤ 20 re-evals/run × 144 runs ≈ **2,880 extra agent runs** — fold into the §22.1 projection.
- **Acceptance:** on one real completed run, produce `anchor_probe.json`; confirm `aggregate_sequence_results` flips that cell's `cl_f1_source` to `"anchor_probe"` and `cl_f1` is no longer the resolved-rate proxy. Add one integration test using a real (or recorded) run dir as a fixture.
- **Verify the index map** end-to-end: anchor position i re-evaluates the task at `sequence_index i-1` against the snapshot `after_task_{p-1}`.
