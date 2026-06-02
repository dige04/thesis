# Memory Pruning and Forgetting Policies for AI Coding Agents

Research code for a master's thesis investigating whether **proactive forgetting** improves long-horizon performance of AI coding agents on sequential software-engineering tasks.

> Status: alpha / research artifact. Not production. The code exists to produce thesis results, not for general reuse.

## What this is

We evaluate six external-memory policies on the **SWE-Bench-CL** benchmark (chronological sequences of GitHub issues per repository):

| Policy | What it does |
|---|---|
| No Memory | Control — agent solves each task with no persistent memory |
| Full Memory | Store every experience, retrieve top-k, never prune |
| Random Prune | Reduce memory to budget by random deletion (volume baseline) |
| Recency Prune | FIFO — keep the newest N records |
| Type-Aware Decay | Failure-mode-tiered power-law decay (Anderson-Schooler) |
| CLS Consolidation | LLM-driven episodic→semantic compression every 5 tasks |

The experimental matrix is **6 policies × 8 official SWE-Bench-CL sequences × 3 seeds = 144 controlled runs** on a single frozen LLM, with a 12-run multi-model validation on a smaller model.

> **Runtime deviations (D1–D5, authorized 2026-06-01/02).** The experiment now runs on **Ollama Cloud** (`qwen3-coder:480b-cloud` agent, `gpt-oss:20b-cloud` summary/classifier) on a local **arm64 macOS** host with **swebench arm64** instance images — NOT the pre-registered GPT-5.4 / x86_64 VPS. The model + architecture are held constant across all 6×3, so between-policy inference is unaffected, but **absolute resolve rates are not comparable** to GPT-5.4 / SWE-Bench leaderboards. See the D1–D5 table in `CLAUDE.md` and the runbook in `AGENTS.md`.

Primary metric: **CL-F1** (harmonic mean of CL-Plasticity and CL-Stability) computed from anchor-probe `a_{i,j}` entries (§14.2; the full matrix is supplementary, §14.3). Primary analysis: Wilcoxon signed-rank on N=8 sequence-level means with Holm correction on 5 pre-registered contrasts. Effect sizes via rank-biserial r_rb with bootstrap BCa CIs.

The thesis hypothesizes that forgetting policies match or beat Full Memory on the Pareto frontier of CL-F1 versus operational cost.

## Documents

| File | Purpose |
|---|---|
| `THESIS_FINAL_v5.md` | **Single source of truth.** Complete spec + plan. Read this. |
| `CLAUDE.md` | Project memory for Claude Code. Frozen invariants, anti-patterns, deviation table (D1–D5), command reference. |
| `AGENTS.md` | **Operational runbook** — how to run on Ollama Cloud / arm64. Read this before running. |
| `README.md` | This file. |

## Repository layout

```
src/
  agents/         LangGraph coding agent
  memory/         MemoryRecord, store (SQLite + FAISS), retriever, policies
    policies/     6 policies, one file each
  benchmark/      SWE-Bench-CL loader, swebench eval harness (arm64) + build-probe, CL metrics
  metrics/        Correctness, CL, efficiency, retrieval quality, Pareto, behavioral
  analysis/       Statistical tests, GLMM, feature importance, plots
  configs/        YAML configs (base + per-policy)

runs/             Per-run artifacts (gitignored — see .gitignore)
results/          Aggregated results, plots, tables
tests/            pytest
```

## Quick start

**Prerequisites** (arm64 macOS): Docker Desktop running, Python 3.11+, a local
**Ollama** install (`ollama serve` + the embedder model — Ollama Cloud serves no
embedder), ~60 GB free disk (swebench instance images), and network access.
`make setup` automates what it can; `make verify-env` reports the rest.

```bash
# 1. Clone + bootstrap (venv, deps incl. swebench, .env, curriculum, embedder pull)
git clone <this-repo> && cd <this-repo>
make setup

# 2. The ONLY required manual input: your Ollama Cloud API key
#    Edit .env and set LLM_CHAT_API_KEY  (create one at https://ollama.com/settings/keys)
#    (Embeddings use a LOCAL daemon: `ollama serve` + `ollama pull nomic-embed-text-v2-moe`)

# 3. Verify (FAILs on missing hard prereqs; WARNs on Docker/Ollama daemon/swebench)
make verify-env

# 4. Spike-Week build-probe GATE: arm64 buildability + Verified coverage over all 273
make build-probe

# 5. Smoke (real django easy tasks, NoMemory; plumbing-first)
make smoke

# 6. Pilot — django + pytest × 6 policies × 1 seed = 12 runs
make pilot

# 7. Full matrix — 8 × 6 × 3 = 144 runs (sequential, long-running)
make run-all
```

See **`AGENTS.md`** for the authoritative Ollama Cloud / arm64 runbook (provider
architecture, quotas, the per-task container model).

## Compute environment

**Current host (deviation D5):** local **arm64 macOS** with Docker `linux/arm64`. The swebench eval harness builds **arm64 instance images locally** (`namespace=""`); the Phase 5.0 build-probe (`make build-probe`) flags any arm64-unbuildable tasks and excludes them identically across all conditions (escalate to an x86_64 host if >15% of any sequence is unbuildable). Keep ~60 GB free; images build on demand and are pruned between tasks.

> The originally pre-registered target was an x86_64 VPS (32 GB / 250 GB / 8 cores). That is recorded in `THESIS_FINAL_v5.md` §0.1 #4/#5 and overridden for execution by D5 — see the dated override note in v5 §0.1 and the D5 row in `CLAUDE.md`. Execution is sequential-first; bounded parallelism (≤3, the Ollama Pro cap) is a post-pilot switch. See `THESIS_FINAL_v5.md` §22 for failure modes.

## Reproducibility

- Master seed: 42
- All policies use 3 seeds (1, 2, 3) for variance estimation
- Temperature 0 throughout
- Memory snapshots taken at every task boundary (before + after pruning)
- Full per-task logs in `runs/{run_id}/task_results.jsonl`

## What this repo does NOT do

- It does not propose a new agent architecture. The agent is a standard LangGraph coding agent from SWE-Bench-CL.
- It does not benchmark code-search tools (WarpGrep, AFT, srcwalk, etc.) — those are a parallel research direction discussed in the thesis Related Work but not experimentally varied here.
- It does not optimize hyperparameters via grid search. Parameters are calibrated once during Week 4 and then frozen.
- It does not generalize beyond SWE-Bench-CL. Multi-model validation tests one axis of generalization (model size); cross-benchmark validation is future work.

## License

TBD (pending thesis submission). For inquiries: contact the author.

## Citation

```bibtex
@mastersthesis{triadmakers2026forgetting,
  title  = {Memory Pruning and Forgetting Policies for AI Coding Agents:
            Impact on Performance Across Sequential Tasks},
  author = {Triad-makers},
  school = {TBD},
  year   = {2026}
}
```
