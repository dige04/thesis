# AGENTS.md — Contract & Runbook for Agentic Tools

> For any coding agent (Claude Code, Codex, Cursor, aider, Gemini, …) working in this repo.
> **`CLAUDE.md` is the primary contract and `THESIS_FINAL_v5.md` is the design source of truth.** This file mirrors the rules and adds the operational runbook for running on OpenCode Zen go. When this file and CLAUDE.md disagree, CLAUDE.md wins.

## What this repository is

Research code for a master's thesis: **Memory Pruning and Forgetting Policies for AI Coding Agents**. Six memory policies × 8 SWE-Bench-CL sequences × 3 seeds = **144 controlled runs**, evaluated with `eval_v3`, analyzed with sequence-level non-parametric statistics + task-level GLMM.

## Golden rules (do not violate without asking the user)

1. **Do not redesign during implementation.** Implement v5 faithfully. v5 §0.1 lists frozen decisions; §24 is the anti-creep manifesto.
2. **Six conditions, locked.** No conditions 7/8/9.
3. **Frozen invariants** (full table in CLAUDE.md): 8 official sequences with no re-ordering; 3 seeds × 6 conditions = 144; max 20 steps/task hard-fail; embedding payload `[Issue + Final Error + Final Diff]` < 7500 tokens; **pure cosine retrieval identical across all conditions**; best-item-**LAST** injection; 5-type taxonomy (`architectural, api_change, bug_fix, test_update, config`); Type-Aware Decay = `base × age^{-d} × (1+retrieval_count)^{0.5}`; CLS every k=5 tasks; Wilcoxon on N=8 sequence means + Holm; rank-biserial `r_rb` (NOT Cliff's delta); PR-AUC + VIF; GLMM binomial/logit; 5000-iter BCa; same-repo retrieval only.
4. **Do not** embed raw trajectories, write chain-of-thought to logs, use accuracy for the helpful/harmful prediction, collapse `outcome` into `memory_type`, or check in `runs/`, `results/raw/`, `*.faiss`, `*.sqlite`, the dataset JSON, or wandb cache.
5. **Log everything from Day 1** (v5 §11): `task_results.jsonl`, `memory_events.jsonl`, per-task trajectory files, before/after memory snapshots. Missing fields cannot be recovered.
6. **TDD.** New file → read the relevant v5 section → write the file → write a pytest (at minimum assert frozen invariants hold) → `make lint` + `make test`.

## Runtime deviations from pre-registration (OpenCode Zen go)

The experiment runs on **OpenCode Zen "go"** (OpenAI-compatible), not GPT-5.4 (user-authorized; provider switched from Ollama Cloud → OpenCode Zen go on 2026-06-08 — both OpenAI-compatible, config-only switch). See the deviation table **D1–D5 in CLAUDE.md** (model, embedder, cost metric, classifier structured-output, host/architecture). All must be disclosed in the thesis Methods. The model is held constant across all conditions/seeds, so between-policy comparisons remain valid; absolute numbers are not comparable to GPT-5.4 baselines.

---

## ⚡ CURRENT STATE — D7 (2026-06-18): Kimi k2.7-code agent + DeepSeek aux, sustained fleet run
> READ FIRST. This supersedes the OpenCode-go / MiniMax-M3 (D6) text below. Full disclosure = **AMENDMENTS.md D7**.

**Models (per-role split):**
- **Agent** = `kimi-k2.7-code` — Kimi "For Coding" subscription via a local **CLIProxyAPI** (`localhost:8317`); the sfo workers reach it through an **nyc1-anchored SSH tunnel**. OpenCode go also serves the same id (bonus capacity).
- **Aux (5-type classifier + reflection + CLS summary)** = `deepseek-v4-flash` on **OpenCode go**, routed via a **per-role aux client**: `src.config.llm_factory.get_aux_client()` + env `AUX_LLM_CHAT_BASE_URL/_API_KEY/_API_KEYS` (falls back to the chat client when unset → backward-compatible). Pin `LLM_MAIN_MODEL=kimi-k2.7-code`, `LLM_CLASSIFIER_MODEL=LLM_SUMMARY_MODEL=deepseek-v4-flash`, and base.yaml `reflection.model=deepseek-v4-flash`.
- Embeddings unchanged: local Ollama `nomic-embed-text-v2-moe` (768-d).
- *Why:* agent on k2.7-code = the science (reasoning); aux on DeepSeek = ~27× cheaper, method-neutral (aux only sets the type label + record metadata; the retrieval payload is raw `[Issue+Err+Diff]`+nomic, untouched). Calibrated 0% JSON-failure, accurate 5-type.

**Matrix composition:** 132 fresh k2.7-code units (`runs_k27/`, sfo fleet) + **12 KEPT gate-3 units** (`runs/` on nyc1, agent `k2.6`/aux `k2.5`, django+pytest seed1 × 6 policies — NOT re-run). Within every (seq×seed) cell all 6 policies use identical models ⇒ no policy confound; report a **drop-gate-3-cells sensitivity check**. Provenance: `MODEL_PROVENANCE.json` per dataset dir + dir separation + committed `base.yaml` (k2.6 pre-`b495e6e`, k2.7-code after).

**Fleet & sustained running:** 5 sfo3 droplets + nyc1 (prod + CLIProxy + the 12 k2.6 units). Each sfo runs **systemd** units (boot-persistent, `Restart=always`):
- `thesis-tunnel.service` — `ssh -L 8317` → nyc1 cli-proxy (scoped forward-only key `/root/.ssh/thesis_tunnel_key`, authorized on nyc1 with `permitopen=127.0.0.1:8317`).
- `thesis-matrix@<shard>.service` — `run_matrix_shard.sh <shard> 5 2` (shard `i%5`, CONC 2, `RUNS_ROOT=runs_k27`).
- `thesis-doctor@<shard>.service` — `scripts/doctor.sh`: auto-heals disk(docker-image leak)/ollama/tunnel/process + `doctor_status.json` heartbeat; fail-closed on go-cap, **never switches aux model mid-run**.
- Files: `scripts/doctor.sh`, `scripts/systemd/{thesis-tunnel,thesis-matrix@,thesis-doctor@}.service`, `scripts/fleet_setup.sh`. Set up one droplet: `bash scripts/fleet_setup.sh <shard>`.

**Operate** (IPs 0=209.38.73.215 1=164.92.103.21 2=209.38.66.73 3=146.190.38.23 4=143.198.230.28; nyc1=157.230.177.56; key `~/.ssh/id_ed25519`):
- **STOP/pause:** per droplet `systemctl stop thesis-doctor@N` (FIRST — else it resurrects the matrix) → `systemctl stop thesis-matrix@N` → `docker ps -q|xargs -r docker kill` → `systemctl disable thesis-matrix@N thesis-doctor@N`. Leave the tunnel.
- **RESUME:** `systemctl enable --now thesis-matrix@N thesis-doctor@N` on each.
- **MONITOR:** `ssh root@<ip> cat /root/thesis/doctor_status.json`.

**Run state (2026-06-18):** fleet **STOPPED** by the user — quota concern: ~5% of the monthly sub quota burned for ~109 partial tasks with **0 full units** (the sub's monthly quota can't carry all 132 at this concurrency). The 10 partial units are **not cleanly resumable** (no mid-unit resume; the shard partial-clears; + the store path bug below) → they re-run from scratch. One review unit (`recency_prune·pytest·seed2`) is finishing on sfo-0 for the user to inspect. **OPEN DECISION (user): full-run capacity** — Moonshot pay-per-token k2.7-code (uncapped, ~$200–300) vs reduce scope (touches A7). **Mid-unit resume code = SKIPPED** (user's call).

**Pitfalls (each cost real time):**
- `rsync src/ configs/ scripts/ DEST/` (trailing slashes) **flattens** contents into DEST → stray `/root/thesis/logging/` shadows stdlib `logging` → every unit `EXIT=1`. Use `rsync src configs scripts DEST/` (NO trailing slash).
- `pkill -f run_matrix_shard` **self-matches the ssh command** → kills its own session (exit 255). Use `pkill -f 'run_matrix[_]shard'`.
- Background/detached ssh **fails the Keychain passphrase** → **foreground ssh only**; run heavy/long remote work via remote `nohup`/systemd, not a bg ssh from the Mac.
- **Pre-existing bug:** `MemoryStore.run_dir` hardcodes `Path("runs")` (`store.py:99`) not `RUNS_ROOT` → `memory.db`/`memory.faiss` land in `runs/`, split from task data in `runs_k27/` (rsync of `runs_k27/` misses them; also blocks clean mid-unit resume). Fix before relying on resume or collecting memory.db.

---

## Running on OpenCode Zen go

### Provider architecture
- **Chat / agent / summary / classifier** → **OpenCode Zen go**, OpenAI-compatible at `https://opencode.ai/zen/go/v1` (needs an API key). List models: `curl -H "Authorization: Bearer $KEY" https://opencode.ai/zen/go/v1/models`. **Qwen models on this tier are Anthropic-endpoint-only (not oa-compat)** — use the `kimi`/`glm`/`deepseek`/`minimax`/`mimo` families.
- **Embeddings** → local Ollama daemon at `http://localhost:11434/v1` (OpenCode Zen serves **no** embedding model).
- Both clients are built by **`src/config/llm_factory.py`** from `.env`. **Never set a global `OPENAI_BASE_URL`** — it would redirect embeddings to a cloud endpoint that has no embedder and break retrieval.

### One-time setup
```bash
# 1. Python env + deps
python -m venv .venv && .venv/bin/python -m pip install -e ".[dev]"

# 2. Dataset (already fetched by scripts/build_curriculum.py → data/SWE-Bench-CL-Curriculum.json)
#    Re-fetch/rebuild if needed:
.venv/bin/python scripts/build_curriculum.py        # downloads from thomasjoshi/agents-never-forget

# 3. OpenCode Zen auth (generative models)
#    create an API key in the OpenCode Zen console at https://opencode.ai
#    then put it in .env as LLM_CHAT_API_KEY (no CLI signin needed)

# 4. Local Ollama embedder (embeddings)
ollama serve &                                      # if not already running
ollama pull nomic-embed-text-v2-moe                 # 768-dim; or qwen3-embedding:0.6b (1024-dim)

# 5. Configure
cp .env.example .env                                # then fill LLM_CHAT_API_KEY
```

### `.env` (template in `.env.example`)
| Var | Default | Purpose |
|---|---|---|
| `LLM_CHAT_BASE_URL` | `https://opencode.ai/zen/go/v1` | chat endpoint (OpenAI-compat) |
| `LLM_CHAT_API_KEY` | *(required)* | OpenCode Zen key |
| `LLM_MAIN_MODEL` | `kimi-k2.6` | coding agent (oa-compat, non-reasoning) |
| `LLM_SUMMARY_MODEL` | `kimi-k2.5` | reflection + CLS summary |
| `LLM_CLASSIFIER_MODEL` | `kimi-k2.5` | 5-type classifier (JSON-mode verified) |
| `EMBEDDING_BASE_URL` | `http://localhost:11434/v1` | local embedder |
| `EMBEDDING_API_KEY` | `ollama` | ignored locally but required |
| `EMBEDDING_MODEL` | `nomic-embed-text-v2-moe` | embedder |
| `EMBEDDING_DIM` | `768` | **must** match embedder; rebuild FAISS if changed |
| `COST_METRIC_MODE` | `tokens` | `usd` \| `tokens` \| `walltime` |

Env vars override `configs/base.yaml`. The repo stays runnable on OpenAI/GPT-5.4 by editing `.env` only.

### Quotas / rate limits (verify live in the OpenCode Zen console)
OpenCode Zen is credit/subscription-based; confirm the current rate limits and balance in the console. 144 runs × up to 20 steps/task is heavy — run sequentially, checkpoint/resume, and watch the balance. The token-count proxy (D3, `COST_METRIC_MODE=tokens`) is the Pareto cost axis regardless of provider billing.

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
- **Per task:** one live container started from the swebench **arm64 instance image** (repo @ `base_commit` + deps installed). The ReAct agent's tools act *inside* it via `docker exec` (writes via `docker cp`/stdin); `get_patch` = in-container `git diff`. The ReAct loop + LLM stay on the host → OpenCode Zen go; only tool *effects* relocate.
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

## Repository map (per-directory AGENTS.md)

This file is the **root** of a hierarchical AGENTS.md tree (generated 2026-06-02). Each directory has its own `AGENTS.md` with file-level detail, v5 cross-references, and per-area invariants. Navigate down for specifics:

| Directory | What's documented |
|---|---|
| `src/AGENTS.md` | Source overview + cross-cutting rules |
| `src/agents/AGENTS.md` | LangGraph ReAct agent, tools, prompts, hard limits (v5 §4) |
| `src/memory/AGENTS.md` | Record, store (SQLite+FAISS), shared retriever, reflection, classifier (v5 §5–10) |
| `src/memory/policies/AGENTS.md` | The 6 locked policies (v5 §8) |
| `src/benchmark/AGENTS.md` | Loader, task env, eval_v3, runners, CL metrics (v5 §2,3,11,14) |
| `src/metrics/AGENTS.md` | Cost (tokens/D3), retrieval quality, behavioral (v5 §14) |
| `src/analysis/AGENTS.md` | Wilcoxon/BCa/r_rb, GLMM, PR-AUC, Pareto, plots (v5 §15–18) |
| `src/config/AGENTS.md` | YAML loader, LLM factory, calibration (v5 §13; D1–D5) |
| `src/logging/AGENTS.md` | The 4 mandatory log artifacts (v5 §11) |
| `tests/AGENTS.md` | Invariant-asserting pytest suite |
| `configs/AGENTS.md`, `configs/policies/AGENTS.md` | Locked YAML config (v5 §13) |
| `data/AGENTS.md` | SWE-Bench-CL curriculum |
| `examples/AGENTS.md`, `scripts/AGENTS.md`, `docs/AGENTS.md`, `.kiro/specs/.../AGENTS.md` | Usage scripts, dataset build, plans, Kiro specs |

Regenerate with `/oh-my-claudecode:deepinit`. Manual notes under each file's `<!-- MANUAL -->` marker are preserved.

---
> **In one line:** Implement v5 faithfully on OpenCode Zen go; the five deviations (D1–D5 in CLAUDE.md) are declared and disclosed, nothing else changes.
