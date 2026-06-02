# AGENTS.md — Contract & Runbook for Agentic Tools

> For any coding agent (Claude Code, Codex, Cursor, aider, Gemini, …) working in this repo.
> **`CLAUDE.md` is the primary contract and `THESIS_FINAL_v5.md` is the design source of truth.** This file mirrors the rules and adds the operational runbook for running on Ollama Cloud. When this file and CLAUDE.md disagree, CLAUDE.md wins.

## What this repository is

Research code for a master's thesis: **Memory Pruning and Forgetting Policies for AI Coding Agents**. Six memory policies × 8 SWE-Bench-CL sequences × 3 seeds = **144 controlled runs**, evaluated with `eval_v3`, analyzed with sequence-level non-parametric statistics + task-level GLMM.

## Golden rules (do not violate without asking the user)

1. **Do not redesign during implementation.** Implement v5 faithfully. v5 §0.1 lists frozen decisions; §24 is the anti-creep manifesto.
2. **Six conditions, locked.** No conditions 7/8/9.
3. **Frozen invariants** (full table in CLAUDE.md): 8 official sequences with no re-ordering; 3 seeds × 6 conditions = 144; max 20 steps/task hard-fail; embedding payload `[Issue + Final Error + Final Diff]` < 7500 tokens; **pure cosine retrieval identical across all conditions**; best-item-**LAST** injection; 5-type taxonomy (`architectural, api_change, bug_fix, test_update, config`); Type-Aware Decay = `base × age^{-d} × (1+retrieval_count)^{0.5}`; CLS every k=5 tasks; Wilcoxon on N=8 sequence means + Holm; rank-biserial `r_rb` (NOT Cliff's delta); PR-AUC + VIF; GLMM binomial/logit; 5000-iter BCa; same-repo retrieval only.
4. **Do not** embed raw trajectories, write chain-of-thought to logs, use accuracy for the helpful/harmful prediction, collapse `outcome` into `memory_type`, or check in `runs/`, `results/raw/`, `*.faiss`, `*.sqlite`, the dataset JSON, or wandb cache.
5. **Log everything from Day 1** (v5 §11): `task_results.jsonl`, `memory_events.jsonl`, per-task trajectory files, before/after memory snapshots. Missing fields cannot be recovered.
6. **TDD.** New file → read the relevant v5 section → write the file → write a pytest (at minimum assert frozen invariants hold) → `make lint` + `make test`.

## Runtime deviations from pre-registration (Ollama Cloud)

The experiment runs on **Ollama Cloud**, not GPT-5.4 (user-authorized 2026-06-01). See the deviation table **D1–D4 in CLAUDE.md** (model, embedder, cost metric, classifier structured-output). All four must be disclosed in the thesis Methods. The model is held constant across all conditions/seeds, so between-policy comparisons remain valid; absolute numbers are not comparable to GPT-5.4 baselines.

## Running on Ollama Cloud

### Provider architecture
- **Chat / agent / summary / classifier** → Ollama **Cloud**, OpenAI-compatible at `https://ollama.com/v1` (needs an API key). Path is `/v1`, **not** `/api/v1`.
- **Embeddings** → local Ollama daemon at `http://localhost:11434/v1` (Ollama Cloud serves **no** embedding model).
- Both clients are built by **`src/config/llm_factory.py`** from `.env`. **Never set a global `OPENAI_BASE_URL`** — it would redirect embeddings to a cloud endpoint that has no embedder and break retrieval.

### One-time setup
```bash
# 1. Python env + deps
python -m venv .venv && .venv/bin/python -m pip install -e ".[dev]"

# 2. Dataset (already fetched by scripts/build_curriculum.py → data/SWE-Bench-CL-Curriculum.json)
#    Re-fetch/rebuild if needed:
.venv/bin/python scripts/build_curriculum.py        # downloads from thomasjoshi/agents-never-forget

# 3. Ollama Cloud auth (generative models)
ollama signin                                       # authenticate against ollama.com
#    create an API key at https://ollama.com/settings/keys

# 4. Local Ollama embedder (embeddings)
ollama serve &                                      # if not already running
ollama pull nomic-embed-text-v2-moe                 # 768-dim; or qwen3-embedding:0.6b (1024-dim)

# 5. Configure
cp .env.example .env                                # then fill LLM_CHAT_API_KEY
```

### `.env` (template in `.env.example`)
| Var | Default | Purpose |
|---|---|---|
| `LLM_CHAT_BASE_URL` | `https://ollama.com/v1` | chat endpoint |
| `LLM_CHAT_API_KEY` | *(required)* | ollama.com key |
| `LLM_MAIN_MODEL` | `qwen3-coder:480b-cloud` | coding agent |
| `LLM_SUMMARY_MODEL` | `gpt-oss:20b-cloud` | reflection + CLS summary |
| `LLM_CLASSIFIER_MODEL` | `gpt-oss:20b-cloud` | 5-type classifier |
| `EMBEDDING_BASE_URL` | `http://localhost:11434/v1` | local embedder |
| `EMBEDDING_API_KEY` | `ollama` | ignored locally but required |
| `EMBEDDING_MODEL` | `nomic-embed-text-v2-moe` | embedder |
| `EMBEDDING_DIM` | `768` | **must** match embedder; rebuild FAISS if changed |
| `COST_METRIC_MODE` | `tokens` | `usd` \| `tokens` \| `walltime` |

Env vars override `configs/base.yaml`. The repo stays runnable on OpenAI/GPT-5.4 by editing `.env` only.

### Quotas (verify live at ollama.com/settings)
Ollama Cloud is subscription/GPU-time based. **Concurrency caps: Free=1, Pro=3, Max=10.** Quotas reset every **5h** (session) and **7d** (weekly). A 480B model over 144 runs × up to 20 steps/task is heavy — run sequentially (≤ tier cap), checkpoint/resume, and spread across reset windows.

### Verify wiring before any run
```bash
.venv/bin/python - <<'PY'
from src.config import llm_factory as f
c = f.get_chat_client()
print(c.chat.completions.create(model=f.main_model(),
      messages=[{"role":"user","content":"say ok"}], temperature=0).choices[0].message.content)
e = f.get_embedding_client()
print(len(e.embeddings.create(model=f.embedding_model(), input="hi").data[0].embedding))  # expect EMBEDDING_DIM
PY
```

## Execution model (arm64 unified container — locked 2026-06-02, deviation D5)

- **Host:** local **arm64 macOS** (Docker `linux/arm64`). NOT the v5 §0.1 #4/#5 x86_64 VPS. Keep ≥ ~60 GB free; build-on-demand + prune images between tasks.
- **Per task:** one live container started from the swebench **arm64 instance image** (repo @ `base_commit` + deps installed). The ReAct agent's tools act *inside* it via `docker exec` (writes via `docker cp`/stdin); `get_patch` = in-container `git diff`. The ReAct loop + LLM stay on the host → Ollama Cloud; only tool *effects* relocate.
- **Eval ground-truth:** loaded from canonical **`princeton-nlp/SWE-bench_Verified`** by `instance_id` (`FAIL_TO_PASS`/`PASS_TO_PASS`/`version`/`environment_setup_commit`; the curriculum JSON dropped these). Curriculum = ordering + `issue_text` only. Eval applies `test_patch` + runs F2P/P2P in the same/fresh instance container.
- **Build-probe (Phase 5.0, GATE):** before any run, probe all 273 ids for Verified coverage + arm64 buildability → deterministic exclusion list (applied identically across all 6×3). Escalate to x86_64 if >15%/sequence unbuildable.
- **Throughput:** sequential-first (1 run at a time); task-boundary checkpoint/resume via `after_task` snapshots survives the Ollama 5h/7d resets. Parallelism ≤3 (Pro cap) only after the pilot is stable.

## Current build status (verified 2026-06-01 — read before implementing)

⚠️ **The experiment CANNOT produce a valid data point yet.** Tests pass on leaf modules, but the integration spine is stubbed/broken. Blockers, in dependency order:

| Area | Status | Notes |
|---|---|---|
| `src/agents/langgraph_agent.py` | **partial (2026-06-01)** | `solve_task` now runs the real v5 §4.4 ReAct tool-use loop (binds chat client, 8 tools via `AgentTools`, `LimitTracker`, `git diff` patch, no-CoT trajectory, token usage). Reflection/write/maintain left to the runner. Still TODO: real reflection LLM (`reflection.py`) + CLS summary LLM, and live-model validation (needs Ollama key). |
| `src/benchmark/evaluator.py` (eval_v3) | **partial (2026-06-02)** | `--timeout=` bug fixed; JSON-report parsing real + tested (no substring). Harness execution (apply patch, FAIL_TO_PASS/PASS_TO_PASS, images) pending live Docker env + `swebench` dep. |
| `src/analysis/aggregate_results.py` CL-F1 | **partial (2026-06-02)** | anchor-probe §14.2 math (`compute_anchor_probe_cl_metrics`) + `cl_f1_source` provenance done; labeled `resolved_rate_proxy` fallback. Anchor-probe data collection (runner re-eval) pending real eval. |
| Tuple/dict crash | **bug** | `policy.retrieve()` returns `list[tuple[float, MemoryRecord]]`; callers in `sequence_runner.py` (608, 683–691) and `langgraph_agent.py` (298, 326–336) call `.get()` → crashes all 5 memory conditions. Repair plan Task 1. |
| CLS `memory_type="consolidated_summary"` | **bug** | rejected by `record.py` validator (5 types). Fix = assign cluster **majority** type. Crashes 24 CLS runs. |
| `reflection.py` / CLS summary | **done (2026-06-02)** | both call the LLM (JSON-mode + Pydantic + fallback). reflection §9.2 schema (deterministic outcome/files); CLS §P5 summary capped 350 tok (tiktoken), majority type kept. |
| Run entry point | **missing** | `make pilot/run-all` are `echo` TODOs; `ExperimentRunner` has no CLI. |
| Repair plan `docs/superpowers/plans/2026-05-27-memory-runner-integration-repair.md` | **unapplied** | Tasks 1–6 (tuple, same-repo FAISS, embedding construction, decay persistence, archive deltas, loader no-reorder). |
| Trajectory + cost logging | **unwired** | `TrajectoryLogger` + `CostTracker` not called by `sequence_runner`. |
| Off-by-one limits | **bug** | `> max_steps` allows 21; should be `>=`. |
| Analysis bugs | **bugs** | `glmm.py` fake `glmer` import; feature_importance scaler-leak/GBM-weight/placeholder-features; rank-biserial zero-diff handling. (Analysis stage — not needed to *run*.) |

### Path to first pilot (see `docs/superpowers/plans/2026-06-01-build-to-first-pilot.md`)
1. ✅ env + deps + dataset + Ollama scaffolding (done 2026-06-01)
2. Bugfix slice: repair plan Tasks 1–6 + CLS majority-type + off-by-one + agent tuple bug
3. Wire `llm_factory` into `store.py` / `classifier.py` (+ JSON-mode classifier) and the new agent/reflection/CLS LLM calls
4. Real LangGraph agent loop + wire `tools.py` + `task_env`
5. Real `eval_v3` (around `swebench`) + real CL-F1/anchor-probe + cost-as-tokens
6. Run entry point (`experiment_runner` CLI + Makefile) + trajectory/cost logging
7. `make smoke` on 1 real task → `make pilot` (2 seq × 6 cond × 1 seed) → calibrate → lock → 144 runs

## Calibration windows (unchanged from v5)
- `top_k` + `max_context_tokens`: confirm at Spike-Week Friday gate (defaults 5 / 2000). **Re-validate under the new embedder (D2).**
- Type-Aware Decay `decay_d` per type: **NOT calibrated** (locked per v5 D-0.3, §8 P4). The per-type values are theoretical and frozen at design time. The Week-4 pilot is a *sanity check only* — if Type-Aware underperforms Random Prune it is a real signal carried into the main run, not a calibration trigger.
- After calibration, all hyperparameters are frozen; any later change forces a full 144-run re-run.

## Commands
`make setup` · `make verify-env` · `make smoke` · `make pilot` · `make run-condition POLICY=… SEED=…` · `make run-all` · `make aggregate` · `make stats` · `make plots` · `make lint` · `make test` · `make typecheck` · `make cost-report`
(Several are still `echo` TODO stubs — see build status.)

## Communication
The user is a master's researcher; communicates in Vietnamese; expects substantive synthesis and honest pushback. Technical content (code, schemas, paper terms) stays in English. Evaluate any scope expansion against v5 §24 first.

---
> **In one line:** Implement v5 faithfully on Ollama Cloud; the four deviations (D1–D4 in CLAUDE.md) are declared and disclosed, nothing else changes.
