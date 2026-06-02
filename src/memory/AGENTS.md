<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-02 | Updated: 2026-06-02 -->

# memory

## Purpose
The memory subsystem: how task experience is represented, stored, retrieved, written, and typed. The central design principle is **separation of storage policy from retrieval policy** — all six conditions share one retrieval function (pure cosine, identical) so the experimental contrast is attributable to *storage* decisions only. Implements v5 §5 (representation), §6 (store backend), §7 (retrieval), §9 (writing/reflection), §10 (classifier).

## Key Files
| File | Description |
|------|-------------|
| `record.py` | `MemoryRecord` dataclass. `memory_type` (5 content types) and `outcome` (pass/fail/partial/unknown) are **orthogonal axes — never collapsed** (root anti-pattern). `embedding_text = [Issue + Final Error + Final Diff]` only, < 7500 tokens. The validator rejects non-taxonomy types (note CLS `consolidated_summary` bug in root build status — fix is majority cluster type). |
| `store.py` | `MemoryStore` — two-layer storage: SQLite (metadata, usage, lifecycle, active/archived split) + FAISS (vectors). Enforces `_verify_embedding_size` (invariant #4) and same-repo retrieval (invariant #16). |
| `embedding_utils.py` | Builds/validates the embedding payload; truncates `patch_summary` from the end if over budget. No metadata in the embedded text. |
| `retriever.py` | `shared_retrieve()` — **the single retrieval path for all policies except No Memory**. Pure cosine similarity, identical scoring (invariant #5), best-item-LAST ordering (#6), same-repo only (#16). No bonuses/penalties — ever. |
| `reflection.py` | Post-task reflection (v5 §9.2): extracts issue/patch/errors/tests from the trajectory, calls the classifier, builds a `MemoryRecord`, hands it to the active policy's `write()`. LLM-backed (JSON-mode + Pydantic + fallback). Deterministic outcome/files. |
| `classifier.py` | 5-type classifier (v5 §10): `architectural, api_change, bug_fix, test_update, config`. Content-based (NOT outcome), temp=0. Under deviation D4 uses JSON-mode/Ollama `format` + Pydantic, not OpenAI `parse`. Log + report failure rate; handle failures identically across conditions. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `policies/` | The six memory policies, one file each, all inheriting `base.MemoryPolicy` (see `policies/AGENTS.md`). |

## For AI Agents

### Working In This Directory
- **Retrieval scoring is frozen.** Do not add recency/type/outcome bonuses to `shared_retrieve` — that would confound the experiment. Storage policies differ; retrieval does not.
- Embedding payload is `[Issue + Final Error + Final Diff]` only and must stay < 7500 tokens — never embed raw trajectories (the 8K embedder cap truncates silently → garbage).
- `memory_type` ≠ `outcome`. Keep them orthogonal in every feature/analysis path.
- Embedder is provider-agnostic via `config/llm_factory.py` (local Ollama `nomic-embed-text-v2-moe`, 768-d under D2). `EMBEDDING_DIM` must match the FAISS index; rebuild the index if it changes.

### Testing Requirements
- `tests/test_memory_record.py`, `test_memory_store.py`, `test_memory_store_faiss.py`, `test_memory_retriever.py`, `test_classifier_basic.py`, `test_reflection_integration.py`. Assert invariants: embedding size, identical retrieval across policies.

### Common Patterns
- Policies call `shared_retrieve()` for reads and only differ in `write()`/`maintain()` (what to keep/archive/consolidate).

## Dependencies

### Internal
- `config/llm_factory.py` (chat + embedding clients), `config/loader.py` (budgets, top_k), `logging/memory_event_logger.py` + `logging/memory_snapshot_logger.py`.

### External
- `faiss`, `sqlite3`, `pydantic`, `tiktoken`, `numpy`.

<!-- MANUAL: -->
