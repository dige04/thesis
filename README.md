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

The experimental matrix is **6 policies × 8 official SWE-Bench-CL sequences × 3 seeds = 144 controlled runs** on GPT-5.4, with a 12-run multi-model validation on a smaller model.

Primary metric: **CL-F1** (harmonic mean of CL-Plasticity and CL-Stability) computed from the full `a_{i,j}` re-evaluation matrix. Primary analysis: Wilcoxon signed-rank on N=8 sequence-level means with Holm correction on 5 pre-registered contrasts. Effect sizes via rank-biserial r_rb with bootstrap BCa CIs.

The thesis hypothesizes that forgetting policies match or beat Full Memory on the Pareto frontier of CL-F1 versus operational cost.

## Documents

| File | Purpose |
|---|---|
| `THESIS_FINAL_v5.md` | **Single source of truth.** Complete spec + plan. Read this. |
| `CLAUDE.md` | Project memory for Claude Code. Frozen invariants, anti-patterns, command reference. |
| `README.md` | This file. |

## Repository layout

```
src/
  agents/         LangGraph coding agent
  memory/         MemoryRecord, store (SQLite + FAISS), retriever, policies
    policies/     6 policies, one file each
  benchmark/      SWE-Bench-CL loader, Docker eval_v3 wrapper, CL metrics
  metrics/        Correctness, CL, efficiency, retrieval quality, Pareto, behavioral
  analysis/       Statistical tests, GLMM, feature importance, plots
  configs/        YAML configs (base + per-policy)

runs/             Per-run artifacts (gitignored — see .gitignore)
results/          Aggregated results, plots, tables
tests/            pytest
```

## Quick start

```bash
# 1. Prerequisites: Docker, Python 3.11+, an x86_64 host with 32 GB RAM and 250 GB disk

# 2. Clone and install
git clone <this-repo>
cd <this-repo>
make setup

# 3. Configure API keys
cp .env.example .env
# edit .env: OPENAI_API_KEY, ANTHROPIC_API_KEY, WANDB_API_KEY

# 4. Verify environment
make verify-env

# 5. Spike Week — Day 1 smoke test (3 tasks, must pass >15%)
make smoke

# 6. Pilot — 2 sequences × 6 conditions
make pilot

# 7. Full matrix — 144 runs (long-running)
make run-all
```

## Compute environment

Tested target: **x86_64 VPS, 32 GB RAM, 250 GB disk, 8 cores**, Docker-native, monitored via `wandb` + `tmux`. ARM64 hosts are not supported (the upstream `eval_v3` harness has known issues on ARM64).

Docker concurrency starts at `max_workers=4` and ramps up with `iostat` monitoring. See `THESIS_FINAL_v5.md` §22 for failure modes.

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
