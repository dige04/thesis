<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-02 | Updated: 2026-06-02 -->

# src

## Purpose
Implementation of the v5 experiment: a single frozen LLM solves SWE-Bench-CL tasks under six memory policies, with logging, metrics, and statistical analysis. Every module maps to a section of `THESIS_FINAL_v5.md` (the source of truth) and many enforce a *frozen invariant* (see root `AGENTS.md` / `CLAUDE.md`). Do not redesign here — implement v5 faithfully.

## Key Files
| File | Description |
|------|-------------|
| `__init__.py` | Package marker. |
| `errors.py` | Centralized custom exceptions + error-handling strategy (v5 §error handling; Reqs 2,4,5,6,14,15,17,26). Defines fail-fast vs. degrade behavior per failure class. |

## Subdirectories
| Directory | Purpose |
|-----------|---------|
| `agents/` | LangGraph ReAct coding agent, tools, prompts, hard execution limits (see `agents/AGENTS.md`). |
| `memory/` | MemoryRecord, two-layer store (SQLite+FAISS), shared retriever, reflection, classifier, and the 6 policies (see `memory/AGENTS.md`). |
| `benchmark/` | SWE-Bench-CL loader, Docker task env, eval_v3 wrapper, sequence/experiment runners, CL metrics (see `benchmark/AGENTS.md`). |
| `metrics/` | Cost tracking (token/usd/walltime), retrieval quality, behavioral metrics (see `metrics/AGENTS.md`). |
| `analysis/` | Aggregation, Wilcoxon/BCa/rank-biserial, GLMM, feature importance, Pareto, plots, tables (see `analysis/AGENTS.md`). |
| `config/` | YAML loader/freezer, provider-agnostic LLM factory, calibration utilities (see `config/AGENTS.md`). |
| `logging/` | Mandatory JSONL/snapshot loggers for task results, memory events, trajectories (see `logging/AGENTS.md`). |

## For AI Agents

### Working In This Directory
- **Read the cited v5 section before editing any file.** Each module docstring names its v5 §, Requirement, and any frozen invariant it enforces.
- A change that touches a frozen decision (root `AGENTS.md` golden rule #3) must be surfaced to the user, never applied silently.
- Generative-model access is **provider-agnostic** via `config/llm_factory.py` — never instantiate an OpenAI client or read `OPENAI_BASE_URL` directly; chat and embeddings use **separate** clients (Ollama Cloud has no embedder).
- Logging is mandatory: any task-executing code path must emit the four artifacts (see `logging/AGENTS.md`). Missing fields cannot be recovered.

### Testing Requirements
- `make lint` (ruff + mypy) and `make test` (pytest) before declaring done.
- New file → write a pytest in `tests/` that at minimum asserts the frozen invariant holds (e.g. embedding size, identical retrieval).

### Common Patterns
- Temperature=0 for all LLM calls (reproducibility).
- Frozen invariants are enforced in code at the point named in the root invariant table — keep them there.

## Dependencies

### Internal
- All `src/**` modules depend on `config/loader.py` (config) and `config/llm_factory.py` (clients). Most task-path code depends on `logging/`.

### External
- `langgraph` / `langchain`, `faiss`, `openai` SDK (pointed at Ollama Cloud), `pydantic`, `tiktoken`, `numpy`, `scipy`, `statsmodels`, `scikit-learn`, `matplotlib`, `docker`.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
