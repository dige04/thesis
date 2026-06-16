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

## Cost & verification
- **Budget:** ≤ 20 re-evals/run × 144 runs ≈ **2,880 extra agent runs** — fold into the §22.1 projection.
- **Acceptance:** on one real completed run, produce `anchor_probe.json`; confirm `aggregate_sequence_results` flips that cell's `cl_f1_source` to `"anchor_probe"` and `cl_f1` is no longer the resolved-rate proxy. Add one integration test using a real (or recorded) run dir as a fixture.
- **Verify the index map** end-to-end: anchor position i re-evaluates the task at `sequence_index i-1` against the snapshot `after_task_{p-1}`.
