# CLAUDE.md — Project Memory for Claude Code

> Read this first. Read it on every session. It is the contract.

## What this repository is

Research code for a master's thesis: **Memory Pruning and Forgetting Policies for AI Coding Agents — Impact on Performance Across Sequential Tasks**.

We run six memory policies (No Memory, Full Memory, Random Prune, Recency Prune, Type-Aware Decay, CLS Consolidation) across all 8 SWE-Bench-CL sequences × 3 seeds = **144 controlled runs** on a single frozen LLM (originally GPT-5.4 in v5 — **now Ollama Cloud**; see *Runtime deviations from pre-registration* below), evaluate with the standard `eval_v3` harness, and analyze with sequence-level non-parametric statistics and task-level GLMM. The thesis tests whether proactive forgetting matches or beats full-memory accumulation on the Pareto frontier of CL-F1 vs cost.

## Single source of truth

**`THESIS_FINAL_v5.md`** is authoritative for every design question. When in doubt, read it — do not invent. Specific cross-references appear throughout this file.

If you (Claude Code) ever feel inclined to add a condition, change a formula, swap a statistical test, or modify a frozen decision: STOP and ask the user. Section 0.1 of v5 lists 26 frozen decisions; Section 24 (Anti-creep manifesto) lists what is explicitly out of scope.

## Runtime deviations from pre-registration (2026-06-01, user-authorized)

The experiment is being executed on **Ollama Cloud** instead of GPT-5.4. The user authorized this explicitly (resource/access constraint). These are **declared deviations** from v5's frozen decisions — they must be disclosed in the thesis Methods ("Deviations from pre-registration") and are NOT silent design changes. The full operational runbook lives in **`AGENTS.md`**.

| # | Deviation | What changed | Why it stays valid / how to disclose |
|---|---|---|---|
| D1 | **Model**: GPT-5.4 → `qwen3-coder:480b-cloud` (agent), `gpt-oss:20b-cloud` (summary + classifier) | `configs/base.yaml` model names; clients via `src/config/llm_factory.py` | Model is held **constant across all 6 conditions × 3 seeds**, so it is a fixed factor — between-policy comparisons (H1–H5) remain valid. Absolute resolution rates are **not** comparable to GPT-5.4 / SWE-Bench leaderboards. Disclose. |
| D2 | **Embedder**: `text-embedding-3-small` (1536-d) → local Ollama `nomic-embed-text-v2-moe` (768-d) | `memory.embedding_model` + `memory.embedding_dim`; FAISS index dim | Does NOT violate Invariant #4 (which bounds the <7500-token *payload*, not embedder identity). Invariant #5 still holds **iff** the same embedder is used across all 6 conditions + 3 seeds. Re-validate `top_k`/`max_context_tokens` under the new embedder during calibration. Disclose embedder + dim. |
| D3 | **Cost metric**: per-token USD → token-count (`tokens`) proxy | `evaluation.cost_metric_mode`; `cost_tracker`; Pareto x-axis | Ollama is flat-rate (GPU-time); per-call USD is meaningless. Pareto CL-F1-vs-cost uses total tokens (a provider-independent compute proxy); wall-time is secondary. Disclose the cost operationalization. |
| D4 | **Classifier structured output**: OpenAI `beta.chat.completions.parse` → JSON-mode / Ollama-native `format` + Pydantic validation | `src/memory/classifier.py` | Ollama ignores OpenAI `json_schema` `response_format` (ollama/ollama #10001). Same 5-type, temp-0 task (Invariant #7). Log + report the classifier failure rate; handle failures identically across conditions. |
| D5 | **Compute host + architecture**: x86_64 VPS (v5 §0.1 #4/#5) → local **arm64 macOS**, Docker `linux/arm64`; swebench **arm64** instance images; Spike-Week build-probe (Phase 5.0) → deterministic exclusion list | `configs/base.yaml` `execution.*`; `src/benchmark/evaluator.py` + container backend; build-probe artifact | Architecture is held **constant across all 6 conditions × 3 seeds**, so it is a fixed factor — between-policy comparisons (H1–H5) remain valid. Absolute resolution rates are **not** comparable to x86_64 / SWE-Bench leaderboards. arm64-unbuildable tasks are excluded **identically across all conditions** (sanctioned by v5 §0.1 #6 "documented compute trade-off"); disclose exact per-sequence counts. Escalate to an x86_64 host if >15% of any sequence is unbuildable. Disclose architecture + exclusion list. |

**Provider config is env-driven.** Endpoints/keys/models come from `.env` (template: `.env.example`) via `src/config/llm_factory.py`; env vars override `base.yaml`. Never set a global `OPENAI_BASE_URL` — chat and embeddings use **separate** clients (Ollama Cloud has no embedding model). The code remains runnable on OpenAI/GPT-5.4 by editing `.env` only, so the deviation is reversible.

Everything else in v5 stays frozen. The 16 invariants below are unaffected by D1–D5 except as noted (D2 touches the embedder used at #4/#5; D5 overrides the host/architecture at #4/#5; the *rules* at #4/#5 are unchanged).

## Frozen invariants — never violate without asking

These are the most load-bearing decisions. Full list in v5 §0.1.

| # | Invariant | Where enforced in code |
|---|---|---|
| 1 | All 8 official SWE-Bench-CL sequences, no self-generated, no re-ordering | `benchmark/swebenchcl_loader.py` |
| 2 | 3 seeds for **all 6 conditions** (not just Random Prune) — total 144 runs | `configs/base.yaml` |
| 3 | Max 20 steps per task, hard force-fail | `agents/coding_agent.py` |
| 4 | Embedding payload = `[Issue + Final Error + Final Diff]` only, < 7500 tokens | `memory/store.py::_verify_embedding_size` |
| 5 | Retrieval scoring = **pure cosine, identical across all 6 conditions** — no bonuses, no penalties | `memory/retriever.py::shared_retrieve` |
| 6 | Injection order = relevance-sorted, **best item LAST** (Lost-in-the-Middle fix) | `agents/coding_agent.py::build_prompt_context` |
| 7 | 5-type taxonomy: `architectural`, `api_change`, `bug_fix`, `test_update`, `config` — NOT outcome-based | `memory/classifier.py` |
| 8 | Type-Aware Decay formula = `base × age^{-d(type)} × (1+retrieval_count)^{0.5}` (multiplicative, Anderson-Schooler) | `memory/policies/type_aware_decay.py` |
| 9 | CLS consolidation = fixed every k=5 tasks (NOT trigger-on-overflow) | `memory/policies/cls_consolidation.py` |
| 10 | Memory-item labels are **associated**, not causal | All feature-analysis code |
| 11 | Primary statistical test = Wilcoxon signed-rank on N=8 sequence-level means, Holm correction on 5 pre-registered contrasts | `analysis/statistical_tests.py` |
| 12 | Effect size = rank-biserial r_rb (NOT Cohen's d, NOT Cliff's delta) | `analysis/statistical_tests.py` |
| 13 | Feature analysis uses **PR-AUC + VIF check** (NOT accuracy, NOT ROC-AUC) | `analysis/feature_importance.py` |
| 14 | Task-level analysis = GLMM with binomial/logit, crossed random effect on task_id | `analysis/glmm.py` |
| 15 | Bootstrap = 5000 iterations, BCa method | `analysis/statistical_tests.py` |
| 16 | Same-repo retrieval only in main experiment | `memory/store.py::search` |

## Anti-patterns (DO NOT do these)

- Do not propose adding conditions 7, 8, 9. Six is locked.
- Do not change frozen formula parameters without an explicit calibration result documented.
- Do not modify retrieval scoring to add bonuses/penalties. Pure cosine, identical across conditions.
- Do not embed raw trajectories. The 8K embedder cap will silently truncate and produce garbage.
- Do not use Cliff's delta — use rank-biserial r_rb. They look similar but the thesis is locked on r_rb.
- Do not use McNemar test on per-task data — it inflates effective N (pseudo-replication). Use Wilcoxon on sequence means.
- Do not use accuracy for the helpful/harmful prediction — the class is ~20% positive. Use PR-AUC.
- Do not collapse `outcome` into `memory_type`. They are orthogonal axes.
- Do not write the agent's private chain-of-thought to trajectory logs. Action summaries + observations only.
- Do not check in `runs/`, `results/raw/`, `*.faiss`, `*.sqlite`, or wandb cache. See `.gitignore`.
- Do not auto-modify locked files (`THESIS_FINAL_v5.md`, this `CLAUDE.md`). Propose diffs in PR description and ask.

## Repository layout (v5 §3.2)

```
src/
  agents/         # LangGraph coding agent + tools + prompts
  memory/         # MemoryRecord, MemoryStore, retriever, reflection, classifier
    policies/     # 6 policies, one file each, all inherit from base.MemoryPolicy
  benchmark/      # SWE-Bench-CL loader, task env (Docker), eval_v3 wrapper, sequence runner, CL-metrics
  metrics/        # correctness, CL, efficiency, retrieval quality, Pareto, behavioral
  analysis/       # aggregation, statistical tests, GLMM, feature importance, plots
  configs/        # base.yaml + per-policy YAMLs

runs/             # gitignored — per-run task results, memory events, trajectories, snapshots
results/          # raw, aggregated, plots, tables
logs/             # gitignored
tests/            # pytest
```

## Commands (fill in as setup progresses)

```bash
# Environment
make setup                 # install deps, build Docker images
make verify-env            # check API keys, VPS resources, FAISS, Docker

# Spike Week
make smoke                 # 3-task smoke run on eval_v3 — Day 1 gate (>15% pass = GO)
make pilot                 # 2 sequences × 6 conditions × 1 seed = 12 runs

# Full experiment
make run-condition POLICY=type_aware_decay SEED=1
make run-all               # 144 runs (long-running, monitored via wandb + tmux)

# Analysis
make aggregate
make stats
make plots

# Lint / test
make lint                  # ruff + mypy
make test                  # pytest
make typecheck

# Cost monitoring
make cost-report           # daily spend summary from wandb
```

These commands are placeholders. Implement them in `Makefile` during Spike Week. Match the names — analysis scripts will call them by name.

## Calibration windows

Two things are **TBD until calibration** and should not be hard-coded prematurely:

1. **`top_k` and `max_context_tokens`** — confirmed at end of **Spike Week (Friday gate)**. Defaults: `top_k=5`, `max_context_tokens=2000`. If pilot shows different optima, change *once*, then lock. **Re-validate under the D2 embedder (`nomic-embed-text-v2-moe`, 768-d).**
2. **Type-Aware Decay `decay_d` per type** — **NOT calibrated.** Frozen at the theoretical v5 §8 P4 values (locked per v5 D-0.3, §796/§1721/§1783). The Week-4 pilot is a *sanity check only*; `decay_d` is **never re-tuned** from pilot data (one-knob-per-type fitting on 2 sequences would overfit and break pre-registration). The earlier "confirmed at end of Week 4 pilot / one-parameter-per-type calibration" wording was an error (it contradicted v5 D-0.3) — corrected 2026-06-02. v5 is authoritative.

After Spike Week, the only calibrated hyperparameters (`top_k`, `max_context_tokens`) are frozen for the full 144 runs. `decay_d` is frozen at design time, not calibrated. Any later change to a frozen value requires re-running everything.

## Logging is mandatory

Every task must produce:

- A row in `runs/{run_id}/task_results.jsonl` (schema in v5 §11.1)
- Events appended to `runs/{run_id}/memory_events.jsonl` (schema in v5 §11.2)
- A trajectory file `runs/{run_id}/trajectories/{task_id}.json` (schema in v5 §11.3)
- Memory snapshots `before_task_{n}.json` and `after_task_{n}.json` in `runs/{run_id}/memory/snapshots/`

If a field is missing at run time, it cannot be recovered. **Log everything from Day 1.** Schema changes mid-experiment invalidate prior runs.

## When implementing a new file

1. Read the relevant v5 section for that component.
2. Write the file. Match the schemas in v5 §11 and the YAML in v5 §13.
3. Write a corresponding pytest in `tests/` — at minimum, test that frozen invariants hold (e.g., `test_embedding_size_assert`, `test_retrieval_is_identical_across_policies`).
4. Run `make lint` and `make test` before declaring done.

## When suggesting a change

1. Identify which v5 frozen decision (if any) the change touches.
2. If it touches a frozen decision: do NOT silently apply. Surface the trade-off in chat.
3. If it doesn't touch a frozen decision: apply, note in commit message which v5 section the change implements.

## When the user asks "should I add X?"

Default answer: refer to v5 §24 (Anti-creep manifesto). The plan survived three rounds of review precisely because it stayed narrow. Convince yourself that "X" is essential for one of the locked hypotheses (H1-H5) before suggesting yes.

## Communication style

- The user is a master's researcher, communicates in Vietnamese, expects substantive synthesis.
- Technical content stays in English (code, schemas, paper terminology). Conversational replies can be Vietnamese.
- The user values directness and honest pushback. Do not perform agreement.
- When the user proposes scope expansion, evaluate against §24 first.

## Useful pointers

| Need | Read v5 §  |
|---|---|
| What the 6 policies actually do | §8 |
| Memory record schema | §5.2 |
| Logging schemas | §11 |
| YAML config | §13 |
| Metrics definitions | §14 |
| Statistical analysis | §15 |
| Feature importance (PR-AUC + VIF) | §16 |
| Week-by-week calendar | §21 |
| Risks and mitigations | §22 |
| Acceptance criteria | §23 |
| Code stubs and interfaces | §25 |

---

> **In one line:** Implement v5 faithfully. Do not redesign during implementation.
