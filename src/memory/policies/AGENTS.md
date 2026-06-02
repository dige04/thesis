<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-02 | Updated: 2026-06-02 -->

# policies

## Purpose
The **six locked experimental conditions** (v5 §8). Each is one file inheriting `base.MemoryPolicy`. Policies differ **only** in storage decisions (`write` / `maintain` — what to keep, archive, or consolidate); they all read through `memory/retriever.py::shared_retrieve` so retrieval is identical. **Six is locked — do not propose conditions 7/8/9** (root anti-pattern; v5 §24).

## Key Files
| File | Description |
|------|-------------|
| `base.py` | `MemoryPolicy` ABC. Enforces the three operations `retrieve` / `write` / `maintain`. **Invariant:** every policy except No Memory MUST use `shared_retrieve()` — isolates policy differences to storage. |
| `no_memory.py` | **P0** — control. Stores nothing, retrieves nothing. The only policy that does not use `shared_retrieve()`. Isolates the effect of having memory at all. |
| `full_memory.py` | **P1** — upper-bound baseline. Stores everything, never prunes, but still retrieves top-k under the same budget. "Store everything; retrieve top-k" — NOT "append everything into the prompt". |
| `random_prune.py` | **P2** — volume-only baseline. Archives random memories at capacity (seeded RNG, 3 seeds). Isolates the volume effect from semantic selection. |
| `recency_prune.py` | **P3** — FIFO. Retains the most recent, archives oldest by `sequence_index`. Tests whether recency alone suffices. |
| `type_aware_decay.py` | **P4** — semantic prioritization. Anderson-Schooler multiplicative power-law: `score = base(type) × age^(−d(type)) × (1+retrieval_count)^0.5` (invariant #8). Archives lowest-scoring first. Per-type `decay_d` is **frozen at design time** (v5 D-0.3, §8 P4) — **not** calibrated; the Week-4 pilot is a sanity check only. |
| `cls_consolidation.py` | **P5** — abstractive compression. Every **k=5 tasks** (fixed, NOT trigger-on-overflow, invariant #9) clusters old memories and LLM-summarizes; falls back to Type-Aware Decay if still over budget. |

## For AI Agents

### Working In This Directory
- **Do not change frozen formula parameters** without a documented calibration result (root anti-pattern). P4's formula and P5's k=5 are locked.
- All policies write/archive via the store and **emit memory events** (`logging/memory_event_logger.py`) — write, archive, consolidate. Snapshots are taken at task boundaries.
- A policy's `retrieve()` returns `list[tuple[float, MemoryRecord]]` — callers must unpack the tuple, not call `.get()` (see the tuple/dict crash in root build status).
- CLS replacement records must carry a valid taxonomy type (cluster **majority** type), never `consolidated_summary`.

### Testing Requirements
- One test per policy: `test_no_memory_policy.py`, `test_full_memory_policy.py`, `test_random_prune_policy.py`, `test_recency_prune_policy.py`, `test_type_aware_decay_policy.py`, `test_cls_consolidation_policy.py`, plus `test_memory_policy_base.py`. Assert identical retrieval and the locked formula/schedule.

### Common Patterns
- `maintain()` is where pruning/consolidation happens, called at the policy's cadence; `write()` adds the per-task record.

## Dependencies

### Internal
- `memory/retriever.py`, `memory/store.py`, `memory/record.py`, `config/loader.py` (budget, k), `config/llm_factory.py` (CLS summary LLM).

### External
- `numpy` (decay scoring), `tiktoken` (CLS summary cap).

<!-- MANUAL: -->
