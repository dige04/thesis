# THESIS — FINAL UNIFIED SPEC + PLAN (v5)

## Memory Pruning and Forgetting Policies for AI Coding Agents

> **Version:** v5 — Final unified document. Supersedes both `THESIS_MASTER_PLAN-final.md` (v4) and the standalone `FULL IMPLEMENTATION SPEC`.
> **Status:** Implementation-ready. Begin Spike Week.
> **Last updated:** May 2026
> **Reconciliation principle:** v4 locks win every conflict; useful additions from the impl spec are merged; methodological errors in the impl spec are corrected; remaining gaps are filled.

---

## Table of Contents

0. Core principle & frozen decisions
1. Research question, sub-questions, hypotheses
2. Benchmark, sequences, scope lock
3. System architecture & directory layout
4. Agent specification
5. Memory representation
6. Memory store backend
7. Retrieval specification
8. Six memory policies (full pseudocode)
9. Memory writing & reflection step
10. Type classifier — design, audit, decision rules
11. Logging specification (per-task, per-event, per-trajectory)
12. Experiment matrix
13. Default configuration (complete YAML)
14. Metrics
15. Statistical analysis plan
16. Helpful/harmful memory prediction
17. Pareto analysis
18. Failure analysis protocol
19. Result interpretation rules
20. Threats to validity
21. Week-by-week execution
22. Risk registry
23. Acceptance criteria
24. Anti-creep manifesto
25. Code stubs & base interfaces
26. References

---

# 0. Core principle & frozen decisions

> **The agent's codebase state resets per task; its external memory persists across tasks.**

```
Task 1: clean repo checkout → agent solves → memory updated → prune/consolidate
Task 2: clean repo checkout → SAME memory bank continues → solve → update → prune
Task 3: clean repo checkout → SAME memory bank continues → solve → update → prune
...
```

The thing that "continues learning" is neither the repository nor the model weights, but the **external semantic memory system**. This isolates the variable we study.

## 0.1 Frozen decisions

These are NOT debatable during implementation. Any deviation must be justified in writing and added to the risk registry.

| # | Decision | Value |
|---|---|---|
| 1 | Experimental platform | SWE-Bench-CL `github.com/thomasjoshi/agents-never-forget` |
| 2 | Base model | GPT-5.4 |
| 3 | Multi-model exploratory probe (D-0.4) | Claude Haiku or GPT-4o-mini, top-3 conditions × 4 sequences × 1 seed = 12 extra runs; framed as exploratory, not a generalization/validation claim |
| 4 | Eval harness | Standard SWE-Bench `eval_v3` on x86_64 VPS + custom CL-metric wrapper (~100 LOC) |
| 5 | Compute environment | x86_64 VPS, 32GB RAM, 250GB disk, 8 cores, Docker-native |
| 6 | Sequences | **All 8 official SWE-Bench-CL sequences**, no self-generated, no subsetting unless documented as compute trade-off |
| 7 | Core conditions | 6: No Memory, Full Memory, Random Prune, Recency Prune, Type-Aware Decay, CLS Consolidation |
| 8 | Seeds | **3 seeds for ALL 6 conditions** → 6 × 8 × 3 = **144 runs** |
| 9 | Primary metric | CL-F1 (harmonic mean of Plasticity and Stability), computed from anchor-probe `a_{i,j}` entries per §14.2; full matrix is supplementary (§14.3) |
| 10 | Primary statistical unit | Sequence-level means (N=8 paired observations) |
| 11 | Primary test | Wilcoxon signed-rank on N=8 sequence means + Holm correction on 5 pre-registered contrasts |
| 12 | Effect size | Rank-biserial r_rb + median paired difference ± bootstrap BCa 95% CI (5000 iterations) |
| 13 | Task-level (exploratory) | GLMM with binomial/logit: `task_success ~ condition + difficulty + position + (1\|seq/seed) + (1\|task_id)` |
| 14 | Memory-item labels | "Associated with success/failure" — NOT causal. Causal claims only in matched-contrast case studies |
| 15 | Feature analysis | PR-AUC + VIF check (target VIF < 5) + class weights for imbalance |
| 16 | Memory type taxonomy | **5 content types**: `architectural`, `api_change`, `bug_fix`, `test_update`, `config` (NOT outcome-based) |
| 17 | Classifier mechanism | Structured Outputs / Tool Use, `temp=0`, cheapest model, 1-of-5 enum |
| 18 | Embedding payload | **Preprocessed: `[Issue + Final Error + Final Diff]` only**. Never raw trajectory. Verify < 8K tokens |
| 19 | Retrieval scoring | **Pure cosine similarity, identical across all 6 conditions**. Policies affect STORE only, never retrieval |
| 20 | Injection order | Relevance-sorted, **best item LAST** (closest to task prompt) — fixes Lost-in-the-Middle |
| 21 | Execution limit | **Max 20 steps per task**, hard force-fail if exceeded |
| 22 | Docker concurrency | Start `max_workers=4`, increase gradually, monitor `iostat` |
| 23 | Type-Aware Decay formula | **Multiplicative** (Anderson & Schooler): `score = base_value(type) × age^{-d(type)} × retrieval_count^{0.5}` |
| 24 | CLS consolidation schedule | Fixed: every k=5 tasks (not trigger-on-overflow) |
| 25 | Bootstrap | 5000 iterations, BCa method |
| 26 | Same-repo retrieval | Yes — main experiment. Cross-repo as optional ablation only |
| 27 | SESOI for H1a TOST | ±0.03 CL-F1 (sequence-level median paired Δ); pre-registered before Spike Week |
| 28 | Jaccard overlap probe (§11.5, §20.11) | Median ≤ 0.5 = well-identified; > 0.9 = §19.7 fires |
| 29 | Primary CL-Stability estimator | Anchor probe (§14.2): k=5 anchors per sequence, 4 probe points; full `a_{i,j}` matrix demoted to supplementary (§14.3) |
| 30 | H1 rejection rule (D-0.1) | α-strict: H1 rejected for policy P iff H1a outcome is C (P degraded). H1b is reported as an independent secondary claim, not part of the rejection rule. |

---

# 1. Research question, sub-questions, hypotheses

## 1.1 Central question

**Under controlled retrieval, do proactive forgetting and consolidation policies achieve performance non-inferior to full-memory accumulation on sequential coding tasks while materially reducing operational cost — and which content-aware structure of forgetting matters most?**

## 1.2 Sub-questions

- **SQ1.** Which memory policies optimize the trade-off between sequential coding performance and operational cost?
- **SQ2.** Are gains explained mainly by reducing memory volume (Random), selectively retaining useful memory (Type-Aware), or abstractive compression (CLS)?
- **SQ3.** Which memory-item characteristics predict whether stored experience will help or harm future tasks?
- **SQ4.** How does agent performance change as persistent memory grows over time?
- **SQ5 (Behavioral).** Does memory accumulation induce behavioral changes (tool-call frequency, syntax-error rates) that forgetting policies mitigate?

## 1.3 Falsifiable hypotheses

- **H1.** Selective pruning policies achieve **at least one** of: (H1a) non-inferior sequential performance vs. Full Memory, AND/OR (H1b) materially lower operational cost.
  - **H1a (performance non-inferiority).** For each pruning policy P ∈ {Random, Recency, Type-Aware, CLS}, the paired difference (P − Full Memory) in CL-F1 across the N=8 SWE-Bench-CL sequences lies within the equivalence margin **SESOI = ±0.03 CL-F1**, evaluated by a **two one-sided tests (TOST) procedure** with 95% BCa bootstrap CI (5000 iterations) on the sequence-level median paired difference.
    - *Outcome A (equivalence):* both one-sided tests reject; CI of median paired Δ ⊂ (−0.03, +0.03) → H1a confirmed for P.
    - *Outcome B (P superior):* one-sided test for "P ≤ Full Memory" rejects AND median Δ > 0 → H1a strictly satisfied for P.
    - *Outcome C (P degraded):* CI escapes the lower bound (median Δ < −0.03 with CI not crossing −0.03) → H1a rejected for P.
    - *Outcome D (inconclusive):* CI overlaps an SESOI bound → H1a inconclusive at N=8.
  - **H1b (cost reduction).** For each pruning policy P, the median paired Δ(total task API cost USD) vs. Full Memory satisfies median Δ ≤ **−20%** with 95% BCa CI upper bound below 0.
  - **H1 rejection rule (α-strict, pre-registered per D-0.1).** H1 is rejected for policy P iff H1a outcome is C (P degraded) — regardless of H1b. Rationale: H1a is the load-bearing performance claim; a pruning policy that costs less but degrades CL-F1 beyond SESOI fails the contribution test, since cost reduction without performance non-inferiority does not establish that proactive forgetting "matches or beats" full memory. H1b stands alongside as an *independent secondary claim* and is reported separately under §19 (see §0.1 #30 for the lock; §0.1 #27 for SESOI lock).
  - **SESOI rationale.** ±0.03 in CL-F1 corresponds to ≈1 task out of 30 changing outcome per sequence on average — the smallest practitioner-meaningful difference at SWE-Bench-CL's typical sequence length. The threshold is pre-registered before Spike Week and locked.
- **H2.** Semantically informed pruning (Type-Aware Decay) outperforms random pruning, indicating that WHAT is forgotten matters beyond simply reducing volume.
- **H3.** CLS Consolidation provides similar or marginally better raw performance than extractive pruning, but at higher cost — failing the Pareto efficiency test against simpler policies.
- **H4 (Behavioral).** Full-memory accumulation induces measurable analysis paralysis — increased tool calls and syntax errors — which forgetting policies mitigate.
- **H5 (Boundary).** Pruning can harm performance when it removes rare but critical repository-specific memories. (Identifies conditions under which forgetting is unsafe.)

## 1.4 Positioning vs. prior work

The six policies tested here overlap in name with prior work, but the *contribution claim is methodological*, not policy-set novelty. We use the standard SWE-Bench-CL benchmark (Joshi et al. 2025), hold retrieval scoring identical across all six conditions (locked invariant #19), include both No-Memory and Full-Memory boundary baselines, and pre-register the analysis (estimation-over-NHST per Cumming 2014; Wasserstein et al. 2019). The closest prior work in name — Alqithami (2025), six forgetting policies on a custom *FiFA* benchmark for privacy-aware generative agents — does not share the domain, benchmark, baselines, retrieval control, or statistical framework.

| Axis | Xiong 2025 (#5) | Alqithami 2025 (#13) | Lindenbauer 2025 (#6) | Joshi 2025 SWE-Bench-CL (#8) | **This work** |
|---|---|---|---|---|---|
| Domain | LLM agents, general | Privacy-aware generative agents | Coding agents (in-task) | Coding agents (sequential) | Coding agents (sequential) |
| Benchmark | mixed | FiFA (custom) | mixed | SWE-Bench-CL (standard) | **SWE-Bench-CL (standard)** |
| # forgetting policies | 1 (add-all) vs. 1 (none) | 6 | 1 (observation masking) | 1 (FAISS top-k) | **6** |
| Retrieval held constant across policies? | n/a (single policy) | not stated | n/a (different layer) | n/a (single policy) | **Yes — pure cosine, identical** |
| No-Memory / Full-Memory boundary baselines | partial | absent | absent | absent | **both included** |
| Primary metric | task success | composite (narrative + privacy + cost) | task success | CL-Plasticity / CL-Stability / CL-F1 | **CL-F1** |
| Statistical unit | per-task | per-run | per-task | per-sequence | **per-sequence (N=8)** |
| Pre-registered analysis / interpretation rules | no | no | no | no | **yes (§19)** |
| Effect-size + bootstrap CI as primary evidence | no | no | no | no | **yes (§15.1, §15.2)** |
| Scale | varies | 300 runs (custom benchmark) | varies | varies | **144 runs + 12-run exploratory cross-model probe** |

**Delta contribution.** Combining (a) the SWE-Bench-CL benchmark with full a_{i,j} or anchor-probe CL-Stability estimation, (b) identical retrieval as confound control isolating *storage* policy from *retrieval* policy, (c) the No-Memory ↔ Full-Memory bracketing, and (d) pre-committed effect-size-gated interpretation framings, this thesis produces the first Pareto map of forgetting policies for coding agents on a standard CL benchmark, with the experimental contrast cleanly attributable to storage-side decisions. The price of this discipline is narrowness: we operate at fixed `top_k`, fixed retrieval scoring, same-repo retrieval, and a single base model in the primary experiment. We do not claim novelty of policy invention; we claim novelty of controlled measurement.

---

# 2. Benchmark, sequences, scope lock

## 2.1 Primary benchmark

**SWE-Bench-CL** from `github.com/thomasjoshi/agents-never-forget`:

| Property | Detail |
|---|---|
| Repo + data | MIT-licensed, available |
| Structure | 8 repo sequences, 15–80+ tasks each, chronological |
| Memory module | FAISS-backed semantic memory + LangGraph agent |
| CL metrics | Plasticity, Stability, CL-F1, Forward/Backward Transfer |
| Eval harness | `eval_v3` Docker containers (standard SWE-Bench) |
| Dataset | `SWE-Bench-CL-Curriculum.json` (tasks ordered by creation date + difficulty) |

## 2.2 Sequence schema

Each task instance:

```json
{
  "task_id": "django__django-12345",
  "repo": "django/django",
  "base_commit": "abc123...",
  "issue_text": "...",
  "test_patch": "...",
  "gold_patch": "...",
  "created_at": "2018-03-15T10:23:00Z",
  "sequence_index": 17,
  "difficulty_label": "medium"   // from SWE-Bench metadata
}
```

## 2.3 Scope lock

- **Use all 8 official SWE-Bench-CL sequences.** No self-generated sequences. No re-ordering. No subsetting unless explicitly documented as a compute trade-off in the Limitations section.
- **Same-repo retrieval only** in the main experiment. Cross-repo retrieval is an optional ablation (priority 10 in cut order).
- **Benchmark integrity** preserved: do not modify task curation, ordering, or evaluation harness.

## 2.4 Benchmark availability matrix

| Benchmark | Code | Data | Role |
|---|---|---|---|
| SWE-Bench-CL | ✅ | ✅ | PRIMARY — all core experiments |
| SWE-Bench Verified | ✅ | ✅ | Foundation infrastructure |
| SWE-ContextBench | ❌ | ❌ | OPTIONAL — email authors, don't depend |
| MEMTRACK | ✅ | ✅ | OPTIONAL — cross-validation if time |

---

# 3. System architecture & directory layout

## 3.1 High-level pipeline

```
Dataset Loader
    │
    ▼
Sequence Runner ─── per-sequence loop ─── Memory Store (persists across tasks)
    │
    ▼
Per-task: Task Environment Manager (clean repo checkout)
    │
    ▼
Coding Agent
    ├── Memory Retriever (pure cosine, identical across conditions)
    ├── Context Builder (best item LAST)
    ├── Tool Executor
    ├── Patch Generator
    └── Test Runner
    │
    ▼
Evaluation Harness (eval_v3 Docker)
    │
    ▼
Reflection Step → Memory Writer
    │
    ▼
Policy Maintain (prune / consolidate)
    │
    ▼
Logger (per-task, per-event, trajectory, snapshots)
```

## 3.2 Project layout

```
src/
  agents/
    coding_agent.py
    langgraph_agent.py
    prompts.py
    tools.py

  memory/
    record.py             # MemoryRecord dataclass
    store.py              # MemoryStore (SQLite + FAISS)
    retriever.py          # pure cosine similarity
    reflection.py         # post-task structured reflection
    classifier.py         # 5-type Structured-Outputs classifier
    summarizer.py         # CLS consolidation prompt
    consolidation.py      # cluster + consolidate
    policies/
      base.py             # MemoryPolicy abstract
      no_memory.py
      full_memory.py
      random_prune.py
      recency_prune.py
      type_aware_decay.py
      cls_consolidation.py

  benchmark/
    swebenchcl_loader.py
    task_env.py           # Docker container management
    evaluator.py          # eval_v3 wrapper
    sequence_runner.py
    cl_metrics.py         # custom a_{i,j} matrix → CL-P, CL-S, CL-F1

  metrics/
    correctness.py
    continual_learning.py
    efficiency.py
    retrieval_quality.py
    pareto.py
    behavioral.py         # tool-call counts, syntax-error rates

  analysis/
    aggregate_results.py
    statistical_tests.py  # Wilcoxon + Holm + bootstrap BCa
    glmm.py               # task-level mixed model
    feature_importance.py # PR-AUC + VIF
    plots.py

  configs/
    base.yaml
    policies/
      no_memory.yaml
      full_memory.yaml
      random_prune.yaml
      recency_prune.yaml
      type_aware_decay.yaml
      cls_consolidation.yaml

runs/
  {run_id}/
    task_results.jsonl
    memory_events.jsonl
    trajectories/
      {task_id}.json
    memory/
      records.jsonl
      metadata.sqlite
      faiss.index
      archive.jsonl
      snapshots/
        before_task_{n}.json
        after_task_{n}.json

results/
  raw/
  aggregated/
  plots/
  tables/

logs/
tests/
```

---

# 4. Agent specification

## 4.1 Agent type

LangGraph-style coding agent with explicit nodes:

```
Node 1:  task_setup
Node 2:  memory_retrieval
Node 3:  context_construction  (best item LAST)
Node 4:  planning
Node 5:  code_search
Node 6:  file_editing
Node 7:  test_execution
Node 8:  repair_loop
Node 9:  final_patch_generation
Node 10: reflection            (structured output → memory record candidates)
Node 11: memory_write
Node 12: memory_prune_or_consolidate
```

## 4.2 Execution limits (LOCKED)

| Parameter | Value | Rationale |
|---|---|---|
| `max_steps_per_task` | **20** | Prevents infinite loops, caps API burn |
| `max_tool_calls_per_task` | 80 | Secondary cap |
| `max_test_runs_per_task` | 5 | Test invocations are expensive |
| `max_wall_time_minutes` | 20 | Hard timeout |
| `temperature` | 0 | Reproducibility |

If `max_steps_per_task` is exceeded → force-fail task, log `timeout=true`, write memory record with `outcome=unknown`.

## 4.3 Agent tools

```
read_file(path)
write_file(path, content)
edit_file(path, diff)
search_code(query)
list_files(path)
run_command(command)
run_tests(test_command)
get_patch()
```

## 4.4 Agent loop (pseudocode)

```python
def solve_task(task, memory_store, policy, config):
    env = TaskEnvironment(task)
    env.checkout_clean_repo()  # fresh repo state every task

    # 1. Retrieve (pure cosine, identical across conditions)
    retrieved = policy.retrieve(
        task=task,
        memory_store=memory_store,
        top_k=config.memory.top_k,
        token_budget=config.memory.max_context_tokens,
    )

    # 2. Inject — best item LAST
    retrieved_sorted = sorted(retrieved, key=lambda r: r.score, reverse=False)
    # ascending sort: lowest-relevance first in the prompt,
    # highest-relevance immediately before the task body

    context = build_prompt_context(
        task=task,
        retrieved_memories=retrieved_sorted,
        repo_snapshot=env.repo_metadata(),
    )

    trajectory = []
    state = AgentState(context=context)

    for step in range(config.agent.max_steps):
        action = agent.next_action(state)
        observation = env.execute(action)
        trajectory.append((action, observation))
        state.update(action, observation)
        if agent.finished(state):
            break
    else:
        # force-fail on timeout
        trajectory.append(("__TIMEOUT__", None))

    patch = env.get_patch()
    eval_result = evaluate_patch(task, patch)  # eval_v3 Docker

    # 3. Reflection → structured record
    record = reflection_step(
        task=task,
        trajectory=trajectory,
        patch=patch,
        eval_result=eval_result,
        retrieved_memories=retrieved_sorted,
    )

    # 4. Type classifier (Structured Outputs)
    record.memory_type = classify_type(record)  # 1 of 5 enum values

    # 5. Write + maintain
    policy.write(memory_store, record)
    policy.maintain(memory_store)  # prune / consolidate per policy

    log_task_result(task, policy, retrieved_sorted, trajectory, eval_result, memory_store.stats())

    return eval_result
```

## 4.5 Prompt structure (identical across conditions)

```
SYSTEM:
You are an autonomous software-engineering agent. Solve the GitHub issue by editing the repository.
Retrieved memories may be stale or wrong. Prefer direct evidence from the current repository.
Produce a minimal patch.

TASK:
Repository: {repo}
Base commit: {base_commit}
Issue:
{issue_text}

RETRIEVED MEMORY:
{memory_block}            # lowest-relevance first, best LAST

RULES:
- Use retrieved memories only when relevant.
- Do not blindly copy old solutions.
- Run tests before declaring done.
- Stop within {max_steps} steps.

WORKSPACE:
{repo_metadata}
```

Each retrieved memory in `memory_block` is tagged with its `memory_id` for downstream tracing:

```
[MEM-0042] (rank=5, sim=0.61, age=12, type=test_update)
[MEM-0091] (rank=4, sim=0.68, age=3,  type=bug_fix)
[MEM-0188] (rank=3, sim=0.72, age=7,  type=api_change)
[MEM-0211] (rank=2, sim=0.78, age=1,  type=bug_fix)
[MEM-0303] (rank=1, sim=0.84, age=2,  type=architectural)   ← LAST = highest relevance
```

---

# 5. Memory representation

## 5.1 Memory type taxonomy (LOCKED — 5 content types)

| Type | Failure tier | Definition |
|---|---|---|
| `architectural` | Sacred | Module structure, design invariants, cross-component contracts |
| `api_change` | Critical | Function/class signature, public API, breaking changes |
| `bug_fix` | Important | Specific bug + fix pattern, root-cause analysis |
| `test_update` | Expendable | Test additions/modifications, test infrastructure |
| `config` | Expendable | Configuration, environment, dependencies, build setup |

**Outcome is a SEPARATE field**, not a type. Do not collapse `successful_patch` / `failed_attempt` into the type axis — that would mix two orthogonal dimensions.

Our taxonomy is *static and content-based*, unlike A-MEM (Xu et al. 2025, #29), whose memories form dynamic links at write time; we adopt the static form to keep the *storage* policy cleanly separable from the *retrieval* policy (locked invariant #19).

## 5.2 MemoryRecord dataclass

```python
@dataclass
class MemoryRecord:
    # Identity
    memory_id: str                     # UUID
    task_id: str
    repo: str
    sequence_index: int                # position in sequence (= created_at_task)

    # Type & outcome (orthogonal axes)
    memory_type: str                   # one of 5 content types
    outcome: str                       # pass | fail | partial | unknown

    # Content (preprocessed for embedding)
    issue_summary: str
    patch_summary: str
    failure_summary: str | None
    test_summary: str | None

    # Structural metadata
    files_touched: list[str]
    functions_touched: list[str]
    commands_run: list[str]

    # Retrieval provenance
    retrieved_memory_ids_used: list[str]    # which memories were shown when this task was solved

    # Embedding
    embedding_text: str                # = "[Issue + Final Error + Final Diff]" — verify < 8K tokens
    embedding_vector_id: str           # FAISS index pointer

    # Size & raw
    token_length: int
    raw_trace_ref: str | None          # path to full trajectory JSON

    # Usage tracking (updated over time)
    use_count: int                     # = retrieval_count
    last_retrieved_at_step: int | None
    success_after_retrieval_count: int # ASSOCIATED, not causal
    failure_after_retrieval_count: int # ASSOCIATED, not causal

    # Scoring / lifecycle
    importance_score: float            # set by Type-Aware Decay
    is_consolidated: bool
    source_memory_ids: list[str] | None # for consolidated summaries
    is_archived: bool
    archived_reason: str | None
    archived_at_step: int | None
```

## 5.3 Embedding payload (CRITICAL — 8K cap)

```
embedding_text = f"""
Issue: {issue_summary}
Final Error: {failure_summary or '(none — task succeeded)'}
Final Diff: {patch_summary}
""".strip()
```

**Do not add files_touched, memory_type, outcome, or anything else into the embedding string.** That metadata lives in the retrieval filter (same_repo), the scoring (pure cosine), and the prompt rendering — not the embedding.

Pre-flight check: assert `count_tokens(embedding_text) < 7500` before sending to the embedder. If exceeded, truncate `patch_summary` from the end.

---

# 6. Memory store backend

## 6.1 Two-layer storage

```
SQLite                                FAISS
  metadata, summaries, outcomes         vector index
  use_count, last_retrieved             cosine similarity search
  archived flag, snapshot history       L2-normalized vectors
```

## 6.2 File layout per run

```
runs/{run_id}/memory/
  records.jsonl       # append-only log of all writes
  metadata.sqlite     # mutable metadata + use_count + archived
  faiss.index         # vector index (rebuilt on archive)
  archive.jsonl       # archived records (for post-hoc analysis)
  snapshots/
    before_task_{n}.json
    after_task_{n}.json
```

Snapshot at every task boundary (before + after pruning). Snapshots are JSON: list of active `memory_ids` + their `importance_score`. Enables post-hoc analysis without re-running.

## 6.3 Memory budget (LOCKED after Week 4 calibration)

```yaml
memory:
  top_k: 5                   # tentative — confirm in spike
  max_context_tokens: 2000   # tentative — confirm in spike
  max_records: 100           # active record cap
  max_storage_tokens: 30000  # total storage cap
```

**Calibration window:** Week 4 pilot adjusts `top_k` and `max_context_tokens` based on observed retrieval quality and prompt length. After Week 4, these are frozen for all 144 runs.

**Important:** Full Memory ignores `max_records` and `max_storage_tokens`. All memory-enabled policies obey the same `top_k` and `max_context_tokens` for the retrieval-time budget.

---

# 7. Retrieval specification

## 7.1 Retrieval mechanism (IDENTICAL across all 6 conditions)

```python
def retrieve(task, memory_store, top_k, token_budget):
    query_text = build_query(task)
    query_vec = embed(query_text)

    # Filter
    candidates = memory_store.filter(
        repo=task.repo,           # main experiment: same-repo only
        is_archived=False,
    )

    # Score — PURE COSINE, no bonuses
    scored = []
    for record in candidates:
        sim = cosine_similarity(query_vec, record.embedding_vector)
        scored.append((sim, record))

    # Top-k
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_k]

    # Token budget — drop lowest-similarity until ≤ budget
    return trim_to_token_budget(top, token_budget)
```

**No same-repo bonus, no success bonus, no consolidated bonus, no failure penalty, no staleness penalty.** All policies use this identical retrieval. Differences live in STORE contents (what's available to retrieve), never in RETRIEVAL scoring.

## 7.2 Query construction

```
query_text = f"""
Repository: {task.repo}
Issue: {task.issue_text}
""".strip()
```

(Single retrieval at task start. Initial file hints and stack traces are unknown at this point.)

## 7.3 Budget enforcement

| Parameter | Value | Rule |
|---|---|---|
| `top_k` | 5 (locked Week 4) | Items per task |
| `memory_token_cap B` | 2000 (locked Week 4) | Total token budget for memory block |
| `overflow_rule` | Drop lowest-similarity until ≤ B | If top-k exceeds cap |
| `item_truncation` | NO truncation — drop entire item | Partial items mislead |
| `tie_break` | Most recent wins at equal similarity | Recency as secondary sort |

## 7.4 Injection order

**Best item LAST** (closest to the task body, farthest from system prompt). Mitigates Lost-in-the-Middle (Liu et al. 2024).

Render order: rank 5 → rank 4 → rank 3 → rank 2 → rank 1 → `TASK:` body.

---

# 8. Six memory policies (full pseudocode)

## P0. No Memory

```python
class NoMemoryPolicy(MemoryPolicy):
    name = "no_memory"

    def retrieve(self, task, memory_store, top_k, token_budget):
        return []

    def write(self, memory_store, record):
        return                  # store nothing

    def maintain(self, memory_store):
        return
```

## P1. Full Memory (Add-All)

```python
class FullMemoryPolicy(MemoryPolicy):
    name = "full_memory"

    def retrieve(self, task, memory_store, top_k, token_budget):
        return shared_retrieve(task, memory_store, top_k, token_budget)
        # IDENTICAL to all other policies

    def write(self, memory_store, record):
        memory_store.add(record)

    def maintain(self, memory_store):
        return                  # never prune
```

> **Note on definition:** Full Memory means "store everything; retrieve top-k under the same budget." It does NOT mean "append everything into the prompt." Appending all memories into the prompt would confound memory-bank policy with context length and is reserved as an optional **append-all stress test** (Ablation E, priority 10 in cut order).

## P2. Random Prune

```python
class RandomPrunePolicy(MemoryPolicy):
    name = "random_prune"

    def __init__(self, seed: int, max_records: int):
        self.rng = random.Random(seed)
        self.max_records = max_records

    def retrieve(self, task, memory_store, top_k, token_budget):
        return shared_retrieve(task, memory_store, top_k, token_budget)

    def write(self, memory_store, record):
        memory_store.add(record)

    def maintain(self, memory_store):
        while memory_store.count_active() > self.max_records:
            victim = self.rng.choice(memory_store.active_records())
            memory_store.archive(victim.memory_id, reason="random_prune")
```

Random Prune isolates the **volume** effect: any improvement here is from "less memory" alone, not "smarter memory."

## P3. Recency Prune

```python
class RecencyPrunePolicy(MemoryPolicy):
    name = "recency_prune"

    def __init__(self, max_records: int):
        self.max_records = max_records

    def retrieve(self, task, memory_store, top_k, token_budget):
        return shared_retrieve(task, memory_store, top_k, token_budget)

    def write(self, memory_store, record):
        memory_store.add(record)

    def maintain(self, memory_store):
        active = sorted(
            memory_store.active_records(),
            key=lambda r: r.sequence_index,
            reverse=True,
        )
        for record in active[self.max_records:]:
            memory_store.archive(record.memory_id, reason="recency_prune")
```

## P4. Type-Aware Decay (LOCKED FORMULA)

P4's power-law shape is also used in MemoryBank (Zhong et al. 2024, #28) under an Ebbinghaus framing; we differ by parameterizing decay *per memory type* rather than globally per item, motivated by failure-tier semantics (#21).

```python
# Failure-tier-based weights (Anderson & Schooler + Fastpaca)
TYPE_PARAMS = {
    #               base_value   decay_d   tier
    "architectural":   (1.0,       0.05,   "Sacred"),
    "api_change":      (0.8,       0.15,   "Critical"),
    "bug_fix":         (0.6,       0.25,   "Important"),
    "test_update":     (0.4,       0.35,   "Expendable"),
    "config":          (0.3,       0.40,   "Expendable"),
}

class TypeAwareDecayPolicy(MemoryPolicy):
    name = "type_aware_decay"
    FREQUENCY_EXPONENT = 0.5   # sub-linear: doubling retrievals ≠ doubling value

    def __init__(self, max_records: int):
        self.max_records = max_records

    def retrieve(self, task, memory_store, top_k, token_budget):
        return shared_retrieve(task, memory_store, top_k, token_budget)

    def write(self, memory_store, record):
        memory_store.add(record)

    def maintain(self, memory_store):
        active = memory_store.active_records()
        if len(active) <= self.max_records:
            return

        current_step = max(r.sequence_index for r in active)

        scored = []
        for r in active:
            base, decay, _ = TYPE_PARAMS.get(r.memory_type, (0.3, 0.40, "Expendable"))
            age = max(1, current_step - r.sequence_index)   # tasks-since-creation
            retrieval = r.use_count                          # retrieval_count

            # Anderson & Schooler power-law form
            score = base * (age ** -decay) * ((1 + retrieval) ** self.FREQUENCY_EXPONENT)
            r.importance_score = score
            scored.append((score, r))

        scored.sort(key=lambda x: x[0])   # ascending: lowest score first

        while memory_store.count_active() > self.max_records:
            _, victim = scored.pop(0)
            memory_store.archive(victim.memory_id, reason="type_aware_decay")
```

**Why this formula, not a linear combination of 7 weighted features:**
1. Cognitive grounding — Anderson & Schooler (1991) showed `P(need) ∝ t^{-d}`. Power-law decay is the optimal forgetting curve, not an arbitrary linear sum.
2. Calibration budget — Week-4 pilot (12 runs) can only calibrate 1–2 parameters. The locked formula has 1 free knob per type (decay `d`) + 1 global exponent. A linear-sum formula with 7 weights cannot be calibrated from this budget.
3. No causal contamination — does NOT include `success_after_retrieval_count` / `failure_after_retrieval_count`. Those are downstream associated labels (locked decision #14), and using them in the scoring formula would smuggle causal claims into the policy.

**Calibration stance (locked per D-0.3).** The per-type `decay_d` values above are *theoretical*, derived from the Anderson & Schooler power-law form combined with Fastpaca's failure-tier taxonomy (#21). The Week-4 pilot (12 runs) is treated as a *sanity check*, not a calibration step: `decay_d` is not re-tuned after the pilot. Rationale: one-knob-per-type fit on 2 sequences would overfit and require re-piloting, breaking the pre-registration. If the pilot shows Type-Aware underperforming Random Prune on the 2 pilot sequences, that is a real signal carried into the main run, not a calibration trigger.

## P5. CLS-style Consolidation

```python
class CLSConsolidationPolicy(MemoryPolicy):
    name = "cls_consolidation"

    CONSOLIDATION_INTERVAL = 5     # every k=5 tasks (fixed schedule)
    MIN_CLUSTER_SIZE = 3
    MAX_SUMMARY_TOKENS = 350
    OLD_MEMORY_THRESHOLD = 10      # only consolidate records older than 10 tasks

    def __init__(self, max_records: int):
        self.max_records = max_records
        self._tasks_since_last_consolidation = 0

    def retrieve(self, task, memory_store, top_k, token_budget):
        return shared_retrieve(task, memory_store, top_k, token_budget)

    def write(self, memory_store, record):
        memory_store.add(record)

    def maintain(self, memory_store):
        self._tasks_since_last_consolidation += 1
        if self._tasks_since_last_consolidation < self.CONSOLIDATION_INTERVAL:
            return
        self._tasks_since_last_consolidation = 0

        # Pick candidates: old enough, same repo, not already consolidated,
        # not Sacred (architectural)
        candidates = [
            r for r in memory_store.active_records()
            if (current_step(memory_store) - r.sequence_index) >= self.OLD_MEMORY_THRESHOLD
            and not r.is_consolidated
            and r.memory_type != "architectural"
        ]

        clusters = cluster_by_repo_files_and_similarity(
            candidates,
            min_cluster_size=self.MIN_CLUSTER_SIZE,
            similarity_threshold=0.70,
        )

        for cluster in clusters:
            summary_record = consolidate_cluster(
                cluster,
                max_tokens=self.MAX_SUMMARY_TOKENS,
                llm_model=config.summary_model,
            )
            # Track cost for Pareto analysis
            log_consolidation_cost(summary_record.llm_cost)

            memory_store.add(summary_record)
            for r in cluster:
                memory_store.archive(
                    r.memory_id,
                    reason="cls_consolidated",
                    replacement_id=summary_record.memory_id,
                )

        # Fallback: if still over budget, fall through to Type-Aware Decay
        if memory_store.count_active() > self.max_records:
            fallback = TypeAwareDecayPolicy(max_records=self.max_records)
            fallback.maintain(memory_store)
```

Consolidation prompt:

```
You are compressing coding-agent memories from a single repository.

Given several past task memories, produce one compact reusable memory.

Keep: repository conventions, recurring files/functions, successful fix strategies,
test commands, failure traps, assumptions proven wrong.

Remove: duplicate details, irrelevant logs, one-off stack traces, exact patches
unless the pattern is reusable.

Output JSON:
{
  "memory_type": "consolidated_summary",
  "summary": "...",
  "common_files": [...],
  "recurring_pattern": "...",
  "successful_strategy": "...",
  "failure_traps": "...",
  "test_commands": [...]
}
```

Consolidated records carry `is_consolidated=True` and `source_memory_ids=[...]` so post-hoc analysis can trace what was compressed.

---

# 9. Memory writing & reflection step

## 9.1 Reflection input

The reflection step is methodologically inspired by Reflexion (Shinn et al. 2023, #30), adapted to emit *typed* memory records (§5.1) rather than free-text traces, so downstream storage policies can operate on a fixed schema.

After the agent finishes a task:

```
issue_text
files inspected (from agent trace)
files modified (from patch)
patch diff
commands run
test output
final resolved/not-resolved result
retrieved memories shown to the agent (memory_ids)
```

## 9.2 Reflection output (Structured Output)

```json
{
  "issue_summary": "QuerySet .filter() chained with .exclude() returns wrong rows when ...",
  "patch_summary": "Modified Q-object combination in query.py:847 to short-circuit ...",
  "failure_summary": null,
  "test_summary": "Added tests/test_query.py::test_exclude_chain; all pass.",
  "files_touched": ["django/db/models/query.py", "tests/queries/test_query.py"],
  "functions_touched": ["QuerySet.exclude", "_filter_or_exclude_inplace"],
  "outcome": "pass"
}
```

The reflection step is itself an LLM call (counted in `task_api_cost`).

## 9.3 Type classifier (separate Structured-Outputs call)

```
SYSTEM:
Classify this coding-agent memory into exactly one of 5 content types:
  architectural | api_change | bug_fix | test_update | config

architectural: module structure, design invariants, cross-component contracts
api_change:    function/class signature, public API, breaking changes
bug_fix:       specific bug + fix pattern, root-cause analysis
test_update:   test additions/modifications, test infrastructure
config:        configuration, environment, dependencies, build setup

Examples:
  [issue=Add new optional kwarg to BaseModel.save] → api_change
  [issue=NullPointer when iterating empty QuerySet] → bug_fix
  [issue=Migrate test runner from nose to pytest]  → test_update
  ...

OUTPUT: JSON {"memory_type": "<one of 5>"}
```

`temp=0`, cheapest model (Haiku / 4o-mini), Structured Outputs / Tool Use enforcing the enum. See Section 10 for audit protocol.

## 9.4 One main record per task

For bachelor scope: **one main memory record per task** (the patch attempt). Test observations, repo conventions, etc. are folded into the main record's `test_summary` / metadata fields rather than spawning extra records. This keeps the per-task memory growth predictable (~1 record/task) for budget analysis.

---

# 10. Type classifier — design, audit, decision rules

## 10.1 Design

- Structured Outputs / Tool Use with JSON Schema enforcing the 5-enum.
- `temp=0`, cheapest model.
- Prompt = definitions + 2 examples per type.

## 10.2 Manual audit (Week 3)

- Sample **150 memory records**, stratified across 5 types and 8 repos.
- Per-type precision / recall, confusion matrix, overall accuracy.
- If possible: 2nd annotator → Cohen's kappa.

## 10.3 Decision rules

| Accuracy | Action |
|---|---|
| ≥ 80% | Proceed with 5 types |
| 70–79% | Proceed, note as limitation. Merge confusing pairs if pattern is clear |
| < 70% | Collapse to 3 types: `architectural`, `bug_fix`, `other`. Re-audit |
| < 50% | Abandon type-aware policy. Replace with similarity-based pruning |

## 10.4 Timing

Audit happens **Weeks 3–4**, BEFORE the full 144 runs. Don't discover bad labels at Week 8.

---

# 11. Logging specification

> If a field is missing from logs at run time, it CANNOT be recovered. Log everything from Day 1.

## 11.1 Per-task result log → `runs/{run_id}/task_results.jsonl`

```json
{
  "run_id": "gpt54_typeaware_seed2_seq3",
  "policy": "type_aware_decay",
  "seed": 2,
  "repo": "django/django",
  "task_id": "django__django-12345",
  "sequence_index": 17,

  "resolved": 1,
  "patch_generated": true,
  "patch_applied": true,
  "syntax_error": false,
  "timeout": false,

  "prompt_tokens": 12345,
  "completion_tokens": 2048,
  "total_tokens": 14393,
  "estimated_cost_usd": 0.31,
  "task_api_cost": 0.31,
  "consolidation_llm_cost": 0.0,

  "wall_time_seconds": 944,
  "tool_calls": 52,
  "test_runs": 3,
  "files_read": 18,
  "files_modified": 2,
  "syntax_error_rate": 0.038,

  "retrieved_memory_ids": ["MEM-001", "MEM-007", "MEM-091", "MEM-188", "MEM-303"],
  "retrieved_memory_scores": [0.61, 0.68, 0.72, 0.78, 0.84],
  "retrieved_memory_types": ["test_update","bug_fix","api_change","bug_fix","architectural"],
  "retrieved_memory_ages":  [12, 3, 7, 1, 2],

  "memory_count_before": 89,
  "memory_count_after": 90,
  "memory_tokens_before": 26500,
  "memory_tokens_after": 26900,

  "pruned_memory_ids": [],
  "consolidated_memory_ids": [],

  "task_difficulty": "medium",
  "error_message": null
}
```

## 11.2 Per-memory event log → `runs/{run_id}/memory_events.jsonl`

```json
{
  "event_id": "evt_00342",
  "step": 17,
  "policy": "cls_consolidation",
  "event_type": "consolidate",
  "memory_id": "MEM-042",
  "replacement_id": "MEM-CONS-007",
  "task_id": "django__django-12345",
  "repo": "django/django",
  "reason": "cls_consolidated",
  "metadata": {"source_count": 4, "summary_tokens": 312}
}
```

Event types: `write | retrieve | archive | consolidate | update_score | snapshot`.

## 11.3 Trajectory log → `runs/{run_id}/trajectories/{task_id}.json`

```json
{
  "task_id": "django__django-12345",
  "policy": "type_aware_decay",
  "seed": 2,
  "steps": [
    {
      "step": 1,
      "action": "search_code",
      "action_input": "QuerySet.exclude",
      "observation_summary": "Found in django/db/models/query.py:823",
      "timestamp": "2026-05-17T10:23:01Z"
    }
  ]
}
```

**Do not store private model chain-of-thought.** Only action summaries and observations.

## 11.4 Memory snapshots

At every task boundary (before + after pruning):

```json
{
  "step": 17,
  "boundary": "after_prune",
  "active_records": [
    {"memory_id": "MEM-001", "importance_score": 0.74, "memory_type": "architectural"},
    ...
  ],
  "archived_this_step": ["MEM-014", "MEM-019"]
}
```

## 11.5 Cross-condition retrieval comparison → `runs/{run_id}/retrieval_overlap.jsonl`

For each (task_id, condition-pair) where both conditions ran the same task with the same seed, compute and log:

```json
{
  "task_id": "django__django-12345",
  "seed": 2,
  "condition_a": "full_memory",
  "condition_b": "type_aware_decay",
  "retrieved_ids_a": ["MEM-001","MEM-007","MEM-091","MEM-188","MEM-303"],
  "retrieved_ids_b": ["MEM-001","MEM-007","MEM-091","MEM-188","MEM-303"],
  "jaccard_overlap": 1.0,
  "rank_correlation_spearman": 1.0
}
```

`jaccard_overlap = |A ∩ B| / |A ∪ B|`. Computed offline from existing `retrieved_memory_ids` fields in `task_results.jsonl`; no extra agent runs required.

**Pre-registered sanity check (§20.11):** if median Jaccard overlap across (task, condition-pair, seed) > 0.9 for the four pruning-vs-Full-Memory pairs, the storage-side contrast at the prompt is empirically small; §19.7 framing fires and the contribution claim restricts to "characterization of storage policies under fixed retrieval, in a regime where the retrieval bottleneck dominates."

---

# 12. Experiment matrix

## 12.1 Main experiment (LOCKED — 144 runs)

```
6 conditions × 8 SWE-Bench-CL sequences × 3 seeds = 144 task sequences
```

| Component | Value |
|---|---|
| Policies | No Memory, Full Memory, Random Prune, Recency Prune, Type-Aware Decay, CLS Consolidation |
| Sequences | All 8 official SWE-Bench-CL sequences |
| Seeds | 3 seeds for ALL 6 conditions (1, 2, 3) |
| Model | GPT-5.4 |
| Temperature | 0 |

## 12.2 Multi-model exploratory probe (12 extra runs, Week 7)

```
Top-3 conditions (decided after Week 6) × 4 sequences × 1 seed = 12 runs
```

Model: Claude Haiku or GPT-4o-mini. **Framing (per D-0.4):** this is an exploratory probe of cross-model transfer, not a validation arm. With 1 seed and 4 of 8 sequences it is underpowered for inferential claims. Reported descriptively (point estimates, BCa CIs from sequence means) alongside an explicit non-generalization disclaimer. The main-experiment GPT-5.4 results stand on their own; the probe sets future-work direction.

## 12.3 Optional ablations (priority order, run only if compute allows)

| # | Ablation | What it tests |
|---|---|---|
| A | Memory budget (`max_records` ∈ {25, 50, 100}) | Sensitivity of conclusions to budget |
| B | Top-k (∈ {1, 3, 5}) | Retrieval budget sensitivity |
| C | Success-only memory | Does failure memory help or hurt? |
| D | Cross-repo retrieval | Knowledge transfer across repos |
| E | Append-all stress test | Confound check for Full Memory |

Ablations are NOT in the locked 144 runs. They sit in the cut order (Section 13 — Scope Control).

---

# 13. Default configuration (complete YAML)

```yaml
experiment:
  name: "memory_pruning_coding_agents"
  benchmark: "swebench_cl"
  sequence_mode: "chronological_by_repo"
  same_repo_retrieval_only: true
  master_seed: 42

agent:
  type: "langgraph_coding_agent"
  main_model: "gpt-5.4"
  summary_model: "gpt-4o-mini"        # for reflection + consolidation
  classifier_model: "gpt-4o-mini"     # for type classification
  embedding_model: "text-embedding-3-small"
  temperature: 0
  max_steps_per_task: 20              # LOCKED
  max_tool_calls_per_task: 80
  max_test_runs_per_task: 5
  max_wall_time_minutes: 20

memory:
  backend: "sqlite_faiss"
  top_k: 5                            # confirm in spike
  max_context_tokens: 2000            # confirm in spike
  max_records: 100
  max_storage_tokens: 30000
  retrieve_same_repo_only: true
  embedding_max_tokens: 7500          # hard cap before truncation
  injection_order: "best_last"

retrieval:
  scoring: "pure_cosine"              # IDENTICAL across all conditions
  tie_break: "most_recent"
  overflow: "drop_lowest_similarity"
  item_truncation: false              # drop whole item if over budget

policies:
  no_memory:
    enabled: true

  full_memory:
    enabled: true
    obey_retrieval_budget: true
    delete_records: false

  random_prune:
    enabled: true
    max_records: 100
    seeds: [1, 2, 3]

  recency_prune:
    enabled: true
    max_records: 100

  type_aware_decay:
    enabled: true
    max_records: 100
    frequency_exponent: 0.5
    type_params:
      architectural: { base: 1.0, decay: 0.05 }
      api_change:    { base: 0.8, decay: 0.15 }
      bug_fix:       { base: 0.6, decay: 0.25 }
      test_update:   { base: 0.4, decay: 0.35 }
      config:        { base: 0.3, decay: 0.40 }

  cls_consolidation:
    enabled: true
    max_records: 100
    interval_tasks: 5                 # fixed schedule
    min_cluster_size: 3
    max_summary_tokens: 350
    old_memory_threshold: 10
    similarity_threshold: 0.70
    fallback_prune: "type_aware_decay"

execution:
  docker_max_workers: 4               # increase gradually, monitor iostat
  vps_arch: "x86_64"
  vps_ram_gb: 32
  vps_disk_gb: 250
  vps_cores: 8

logging:
  save_raw_trajectory: true
  save_patches: true
  save_test_output: true
  save_retrieved_memories: true
  save_prompt_tokens: true
  save_completion_tokens: true
  save_memory_snapshots: true
  snapshot_at_every_task_boundary: true

evaluation:
  harness: "eval_v3"
  cl_metric_wrapper: "custom"         # ~100 LOC computing a_{i,j} matrix
  primary_metric: "CL_F1"
  bootstrap_iterations: 5000
  bootstrap_method: "BCa"
  confidence_level: 0.95
  effect_size: "rank_biserial"
  multiple_comparison_correction: "holm"

statistical:
  primary_test: "wilcoxon_signed_rank"
  primary_unit: "sequence_level_means"
  primary_n: 8
  planned_contrasts:
    - ["full_memory", "no_memory"]
    - ["full_memory", "random_prune"]
    - ["full_memory", "recency_prune"]
    - ["full_memory", "type_aware_decay"]
    - ["full_memory", "cls_consolidation"]
  task_level_model: "glmm_binomial_logit"
  feature_analysis_metric: "PR_AUC"
  vif_threshold: 5.0
```

---

# 14. Metrics

## 14.1 Correctness

| Metric | Definition |
|---|---|
| `resolved_rate` | `n_resolved / n_tasks` per (policy, sequence, seed) |
| Per-repo resolved rate | Same, per sequence |
| Sequence-window accuracy | Resolved rate over rolling windows of 5 or 10 tasks (for trajectory plots) |

## 14.2 Continual-learning — Stability (PRIMARY: anchor-probe schedule)

Computing the full `a_{i,j}` matrix (Section 14.3) requires T(T−1)/2 re-evaluations per (sequence, condition, seed), which at 8 sequences × 6 conditions × 3 seeds and typical T ≈ 30–80 produces O(10⁴) extra agent runs. Under the §22.1 budget projection this is infeasible. We therefore make the **anchor-probe schedule** primary and the full matrix supplementary.

**Anchor-probe schedule.** For each sequence of length T, fix a deterministic anchor index set A with **k=5 anchors** at positions {⌈T/10⌉, ⌈3T/10⌉, ⌈5T/10⌉, ⌈7T/10⌉, ⌈9T/10⌉} (locked before Spike Week). At four probe points p ∈ {⌈T/4⌉, ⌈T/2⌉, ⌈3T/4⌉, T}, re-evaluate every anchor `a ∈ A with a ≤ p` against the memory snapshot taken after task `p`. Total re-evaluations per (sequence, condition, seed) is bounded above by 4·5 = 20, vs. ~T(T−1)/2 ≈ 435 for the full matrix at T=30.

**`a_{i,j}` entries collected:** for i ∈ A, j ∈ {⌈T/4⌉, ⌈T/2⌉, ⌈3T/4⌉, T}. The diagonal `a_{i,i}` for non-anchor i is read from per-task online results (always collected). Probed-stability is the only off-diagonal information collected in the primary protocol.

**CL metrics from the anchor probe:**

```python
# Online accuracy (Plasticity) — uses ALL tasks (diagonal)
CL_Plasticity = mean(a_{i,i} for i in range(T))

# End-of-sequence accuracy on anchors only
end_acc = mean(a_{i, T} for i in A)

# Anchor forgetting
forgetting_i = max(a_{i, p} for p in PROBES with p >= i) - a_{i, T}
CL_Stability_anchor = 1 - mean(forgetting_i for i in A)

# Primary metric
CL_F1 = 2 * CL_Plasticity * CL_Stability_anchor / max(CL_Plasticity + CL_Stability_anchor, 1e-8)
```

This is a deliberate departure from the SWE-Bench-CL full-matrix standard, justified by §22.1 budget reality. Stability is therefore estimated on 5 anchor tasks rather than all T tasks; the resulting estimator has higher variance but is computationally tractable. We report the anchor-probe Stability with explicit acknowledgment that it lower-bounds the full-matrix Stability (anchors are a random subset of tasks; missed forgetting events outside the anchor set inflate the estimator).

**Stochasticity handling.** `re_evaluate(task_i, snapshot_after_j)` re-runs the *agent* (not just re-scores a fixed patch) with the historical memory state from after task j and a clean repo checkout. At temperature 0 the agent is approximately deterministic but not guaranteed (provider-side load, tool-call tie-breaking). The primary protocol pre-registers **n=1 re-evaluation per (i, j) cell with the resulting variance treated as part of within-sequence noise**, mitigated by reporting Stability with 3-seed pooling. If a future budget supplement allows, the protocol upgrades to n=3 majority vote.

## 14.3 Continual-learning — full `a_{i,j}` matrix (SUPPLEMENTARY)

If the §22.1 budget permits at Week 7, the full off-diagonal `a_{i,j}` reconstruction (per Section 25.6) is run for **2 sequences × top-2 conditions × 1 seed = 4 cells**, providing a comparison between anchor-probed and densely-probed Stability estimates. This is sensitivity, not primary. If the anchor-probed and full-matrix Stability estimates disagree by more than ±0.05 on these 4 cells, the Limitations section qualifies all Stability-based claims accordingly.

## 14.4 Efficiency

```
prompt_tokens, completion_tokens, total_tokens
estimated_cost_usd
wall_time_seconds
tool_calls
test_runs
files_read, files_modified
memory_retrieval_latency
memory_write_latency
pruning_latency
consolidation_latency
```

Derived:

```
cost_per_resolved_task    = total_cost  / max(n_resolved, 1)
tokens_per_resolved_task  = total_tokens / max(n_resolved, 1)
tool_calls_per_resolved   = total_tool_calls / max(n_resolved, 1)
runtime_per_resolved      = total_runtime / max(n_resolved, 1)
```

## 14.5 Memory growth

```
active_memory_count_t, active_memory_tokens_t
archived_memory_count_t, consolidated_memory_count_t
memory_growth_rate   = active_memory_count_final / n_tasks
pruning_ratio        = archived / total_written
consolidation_ratio  = raw_archived_into_summaries / total_written
```

## 14.6 Behavioral (H4 — analysis paralysis)

```
tool_calls_per_task
syntax_error_rate          = n_syntax_errors / n_tool_calls
files_read_per_task
test_runs_per_task
```

Hypothesis: under Full Memory, these rise as memory accumulates. Under forgetting policies, they stay bounded.

## 14.7 Retrieval quality

For each retrieved memory at each task:

```
same_repo (bool)
file_overlap = |mem.files_touched ∩ task.files_touched| / |task.files_touched|
same_memory_type (bool)
semantic_similarity (float)
age (int)
outcome (enum)
retrieval_rank (int)
```

Derived:

```
Relevant@k        = (same_repo AND file_overlap > 0) / k
Retrieval_noise@k = 1 - Relevant@k
Stale_rate        = (age > 20 AND file_overlap == 0 AND sim < 0.5) / k
```

`file_overlap` is computed offline (current task's actual files are only known after solving).

---

# 15. Statistical analysis plan

## 15.1 Philosophy

With N=8 independent sequences, traditional NHST has very limited power. We follow the estimation-over-testing paradigm (Cumming 2014; Wasserstein et al. 2019): **effect sizes + confidence intervals are primary evidence**; p-values supplement but do not gate conclusions.

## 15.2 Primary analysis — sequence-level

**Unit:** Sequence-level means (average across 3 seeds per sequence).
**N:** 8 paired observations per condition pair.

**Effect size (primary evidence):**

```
For each of 15 condition pairs:
  - Rank-biserial r_rb
  - Median paired difference ± bootstrap BCa 95% CI (5000 iterations)
```

Interpretation: `|r_rb| ≈ 0.1` small, `≈ 0.3` medium, `≈ 0.5` large.

**Planned contrasts (significance testing — pre-registered):**

Five contrasts, each pruning policy vs Full Memory (the natural baseline):

```
1. Random Prune        vs Full Memory   (volume effect)
2. Recency Prune       vs Full Memory   (temporal heuristic)
3. Type-Aware Decay    vs Full Memory   (semantic pruning)
4. CLS Consolidation   vs Full Memory   (abstractive compression)
5. No Memory           vs Full Memory   (memory value at all)
```

Test: paired Wilcoxon signed-rank on N=8 sequence means.
Correction: Holm on 5 planned contrasts.
Remaining 10 pairwise comparisons: reported as exploratory with uncorrected p-values.

**Per-seed supplementary:** Report within-sequence variance across 3 seeds for each (condition, sequence) cell.

**Honest power limitation:** Wilcoxon at N=8 with Holm-corrected α reaches significance only for very large effects (near-unanimous agreement across all 8 sequences). Effect sizes are primary; p-values supplement.

## 15.3 Task-level analysis — GLMM (exploratory)

```
task_success ~ condition
             + task_difficulty
             + sequence_position
             + (1 | repo_sequence/seed)
             + (1 | task_id)
```

- **Family:** Binomial, **link:** logit
- **Python:** `statsmodels.BinomialBayesMixedGLM`
- **R:** `lme4::glmer(family=binomial)`
- `(1|task_id)` accounts for inherent task difficulty variation (crossed random effect)
- **Sensitivity check:** run with and without `(1|task_id)` if convergence issues
- `task_difficulty` sourced from SWE-Bench metadata (NOT derived from outcomes)

## 15.4 Efficiency comparisons

For non-normal metrics (tokens, runtime, tool calls):

- Wilcoxon signed-rank on sequence-level means
- Rank-biserial r_rb effect size
- 95% bootstrap BCa CI for median paired difference
- Report absolute + relative changes

## 15.5 Reporting template

```
Type-Aware Decay vs Full Memory:
  CL-F1:        Δ = +0.018  (r_rb = 0.43, 95% BCa CI [-0.005, +0.038], Holm-p = 0.078)
  Total tokens: Δ = -31%    (r_rb = -0.72, 95% BCa CI [-38%, -23%],   Holm-p = 0.012)
  Tool calls:   Δ = -18%    (r_rb = -0.51, 95% BCa CI [-26%, -9%],    Holm-p = 0.039)

  TOST (H1a, SESOI=0.03): equivalence rejected for the lower bound (p_TOST_lower = 0.012)
                          equivalence rejected for the upper bound (p_TOST_upper = 0.008)
                          ⇒ Type-Aware Decay is statistically equivalent to Full Memory on CL-F1.

  Conclusion: Type-Aware Decay achieves H1a equivalence with Full Memory on correctness
  AND substantially reduces token cost (H1b satisfied). Pareto-favorable.
```

---

# 16. Helpful/harmful memory prediction

## 16.1 Unit of analysis

```
(task, retrieved_memory)
```

Each row:

```json
{
  "task_id": "django__django-12345",
  "memory_id": "MEM-009",
  "policy": "full_memory",
  "seed": 2,
  "sequence": "django",

  "semantic_similarity": 0.82,
  "retrieval_rank": 1,
  "memory_age": 13,
  "memory_type": "bug_fix",
  "memory_outcome": "pass",
  "same_repo": true,
  "file_overlap": 0.5,
  "token_length": 220,
  "use_count": 3,
  "is_consolidated": false,

  "task_resolved": 1,
  "label": "helpful"
}
```

## 16.2 Labeling — three tiers

### Tier 1: automatic weak labels (all rows)

```
helpful  if  task_resolved == 1  AND  file_overlap > 0  AND  memory_outcome == "pass"
harmful  if  task_resolved == 0  AND  semantic_similarity > 0.7  AND  memory_outcome == "fail"
neutral  otherwise
```

### Tier 2: manual labels (100–200 stratified sample)

Sample stratified across policies, memory types, and weak-label categories. Two annotators if possible.

```
helpful: memory directly points to useful file/function/test/strategy that the agent used
harmful: memory encourages wrong file, wrong assumption, stale patch, or failed strategy
neutral: memory was not obviously used or relevant
```

Inter-annotator agreement (Cohen's kappa). Manual labels are the gold standard for the prediction model's evaluation set.

### Tier 3: matched-contrast case studies

For Discussion chapter: pick task pairs where memory X was helpful in task A but harmful in task B. These support causal claims that the policy framework cannot make from associated labels alone.

## 16.3 Derived feature (CRITICAL — VIF mitigation)

```
retrieval_rate = use_count / (memory_age + 1)
```

Pre-flight VIF check: if `VIF(age) > 5` OR `VIF(use_count) > 5`, drop both raw features and keep only `retrieval_rate`.

## 16.4 Model

```
Logistic regression  (interpretable)
Gradient Boosted Machine  (nonlinear)
```

Both. Compare feature importance rankings.

## 16.5 Evaluation

**5-fold cross-validation, stratified by sequence.**

```
Primary metric: PR-AUC          (not ROC-AUC — class is ~20% positive)
Secondary:      precision, recall, F1 at threshold = 0.5
Class weights:  inverse frequency
Calibration:    reliability curve
```

Report feature importance from both models. Bootstrapped CIs on PR-AUC.

---

# 17. Pareto analysis

**Cost-axis definition (lock).** The Pareto X-axis "total system API cost (USD)" includes only the operational cost the agent would pay in deployment: per-task LLM calls (main model + reflection model + classifier model) + consolidation LLM calls. It **excludes** the methodological cost of the `a_{i,j}` / anchor-probe re-evaluation (§14.2), which is measurement overhead not borne by a production system using the same policy.

For each of 6 conditions, plot:

```
X-axis: total system API cost (USD), including consolidation LLM cost
Y-axis: CL-F1
```

Add per-sequence error bars (3 seeds → SEM).

**Pareto-optimal conditions** are not dominated on both axes. These become the practical recommendations.

Also produce:

- Pareto: resolved rate vs total cost
- Pareto: resolved rate vs final memory size (token count)
- Pareto: CL-F1 vs total tool calls (efficiency)

For CLS Consolidation specifically, report **cost-normalized CL-F1**:

```
CL_F1_per_dollar = CL_F1 / total_cost_usd
```

If CLS's raw CL-F1 matches Type-Aware Decay but its cost is 3× higher, CLS fails the Pareto test.

---

# 18. Failure analysis protocol

For each of 6 policies, hand-inspect:

```
5 successful cases where memory helped
5 failed cases where memory was irrelevant
5 failed cases where memory was harmful
5 cases where pruning removed a useful memory  (skip for No Memory, Full Memory)
5 cases where consolidation lost useful details (CLS only)
```

Template per case:

```
Task ID:
Policy:
Sequence position:
Retrieved memories (IDs + types + scores):
What the memory suggested:
What the agent actually did:
Final result:
Why it helped/hurt:
Could another policy have avoided this? (counterfactual)
```

These case studies feed Chapter 4 (Results) and Chapter 5 (Discussion).

---

# 19. Result interpretation rules (triggered framings)

Each interpretation framing is gated on a pre-specified effect-size trigger. Triggers are evaluated against the primary CL-F1 sequence-level Wilcoxon + r_rb + BCa CI for the 5 planned contrasts, plus the Pareto frontier on (CL-F1, total cost). Only the framing whose trigger fires is invoked in the Discussion. Multiple triggers may fire (e.g., 19.2 and 19.5 simultaneously); silently re-purposing a non-triggered framing post-hoc is prohibited.

## 19.1 If Full Memory wins

**Trigger.** For at least 3 of 4 pruning policies P ∈ {Random, Recency, Type-Aware, CLS}: median paired Δ CL-F1 (P − Full Memory) < −0.03 with 95% BCa CI excluding 0 (i.e., H1a outcome C), AND Full Memory is non-dominated on the Pareto (CL-F1, cost) frontier.

**Framing.** "Full memory accumulation may be beneficial when prior tasks contain reusable repository-specific knowledge. Within the SWE-Bench-CL same-repo regime tested here, pruning policies removed memories whose marginal value exceeded the noise they introduced. The value of forgetting is conditional, not universal." Strong contribution: identifies conditions where pruning is unsafe — feeds §18 failure-analysis case studies on which records pruning removed.

## 19.2 If Type-Aware Decay wins

**Trigger.** Type-Aware vs. Full Memory: H1a outcome A or B AND r_rb ≥ 0.3 AND Type-Aware strictly dominates Full Memory on the Pareto (CL-F1, cost) frontier. Additionally, Type-Aware vs. Random Prune: median paired Δ CL-F1 ≥ +0.02 with CI excluding 0.

**Framing.** "Memory quality matters more than memory quantity. Structured pruning by content type can preserve useful memories while reducing noise and cost. The failure-mode tier framework operationalizes this distinction." Gated analyses: §16 feature-importance trained on the data; §18 case studies on Type-Aware's correctly-retained `architectural` / `api_change` records.

## 19.3 If Random Prune matches Type-Aware Decay

**Trigger.** Type-Aware vs. Random Prune: |median paired Δ CL-F1| < 0.02 AND 95% BCa CI ⊂ (−0.03, +0.03) (TOST equivalence). AND both beat Full Memory on Pareto.

**Framing.** "Volume reduction may be the main benefit; the type/relevance heuristics tested here did not dominate naive sampling at N=8. The classifier-as-policy confound (§20.12) limits causal attribution. Future work: stronger content signals, classifier accuracy floor higher than the §10.3 threshold." Gated analyses: re-analysis with classifier-confidence covariate; an Anti-Type baseline is essential for any causal claim that "type matters."

## 19.4 If Recency Prune wins

**Trigger.** Recency vs. Full Memory: H1a outcome A or B AND Recency dominates Full Memory on Pareto AND Recency vs. Type-Aware: median paired Δ CL-F1 ≥ +0.02 with CI excluding 0.

**Framing.** "Recent experiences are most predictive on SWE-Bench-CL. Chronological locality dominates content-type signals at this sequence scale; the Anderson-Schooler power-law form is functionally indistinguishable from a recency cutoff for the d-values tested. Type-aware structure may pay off at longer sequence horizons or in domains with stronger content recurrence patterns."

## 19.5 If CLS Consolidation loses on Pareto

**Trigger.** CLS vs. Type-Aware (or whichever extractive policy ranks highest): median paired Δ CL-F1 within ±0.03 (statistically tied) AND median paired Δ(total cost) ≥ +20% (CLS more expensive) AND CLS is strictly dominated by Type-Aware on the Pareto frontier.

**Framing.** "Abstractive summarization paid the LLM-on-write tax without recovering a CL-F1 advantage at this sequence length. The dual-store CLS analogy (McClelland et al. 1995) is not realized by single-store cluster-summarize; we use 'Periodic Abstractive Consolidation' descriptively. CLS may be advantaged at sequence lengths beyond SWE-Bench-CL's 15–80-task range, or under harder context-budget constraints." Gated analyses: report CLS firing rate — if firing rate is < 30%, the result is uninformative.

## 19.6 If No Memory is competitive

**Trigger.** No Memory vs. Full Memory: H1a outcome A (equivalence) — CI of median paired Δ CL-F1 ⊂ (−0.03, +0.03). AND No Memory non-dominated on Pareto.

**Framing.** "The task sequence may have weak inter-task dependency. The retrieval system may not surface useful memories. The base model may already encode enough general coding knowledge to make episodic memory marginal at SWE-Bench-CL's task complexity. This is a strong publishable negative result; the implication for production memory systems is that vector-DB infrastructure should be evaluated against the No-Memory baseline directly." Gated analyses: §16 feature-importance becomes purely descriptive (memory had no average effect to explain).

## 19.7 If the retrieval Jaccard probe shows no contrast between storage policies

**Trigger.** Median across (task, condition-pair) of Jaccard overlap of retrieved memory-ID sets > 0.9 for most pruning-vs-Full-Memory pairs (see §11.5 and §20.11).

**Framing.** "At the locked retrieval budget (top_k=5, max_context_tokens=2000), storage-side pruning policies feed nearly identical prompts to the agent on most tasks; the experimental contrast on CL-F1 measures small-tail effects. This is itself a finding: in the frontier-model + top-k regime, the storage policy is dominated by the retrieval policy. Future work must vary the retrieval layer to isolate storage effects." This framing co-fires with whichever of 19.1–19.6 applies and modifies the causal claim attached to it.

## 19.8 Multi-framing combination rule

If multiple triggers fire, report each in order, and explicitly mark which framings are *primary* (based on the planned 5 contrasts) vs. *secondary* (based on derived metrics). HARKing — narrating a finding under a non-triggered framing — is prohibited.

---

# 20. Threats to validity

## 20.1 Model stochasticity

Even at temp=0, agent behavior can vary (tool selection, retry order).
**Mitigation:** 3 seeds per condition. Within-sequence variance reported.

## 20.2 Benchmark cost

SWE-style tasks are expensive (Docker, test runs, multi-step agent loops).
**Mitigation:** Hard 20-step timeout; Docker `max_workers` monitoring; daily cost tracking; spike-week budget check before committing to 144 runs.

## 20.3 Retrieval confound

A policy may appear bad because retrieval is weak, not because the policy is bad.
**Mitigation:** Identical retrieval scoring across all conditions (pure cosine). Retrieval-quality logged per task. Relevant@k analysis disentangles retrieval from policy.

## 20.4 Full Memory definition

Appending all memories to the prompt would confound memory policy with context length.
**Mitigation:** Full Memory is Add-All storage + top-k retrieval under the same budget. Append-all is a separate stress-test ablation.

## 20.5 Summary loss in CLS

Consolidation may lose code-level details.
**Mitigation:** Store `source_memory_ids` for every consolidated record. Log consolidated summaries. Manual inspection in failure analysis. Ablation D compares summary vs raw.

## 20.6 Embedding truncation

Raw trajectories are too long for the embedder (8K cap).
**Mitigation:** Preprocessed `[Issue + Final Error + Final Diff]` payload. Pre-flight assert < 7500 tokens.

## 20.7 Classifier accuracy

Type-aware policy depends on the 5-type classifier.
**Mitigation:** Week-3 audit on 150 stratified items + decision rules (Section 10.3). If accuracy < 70%, collapse types.

## 20.8 Type-Aware parameter calibration

Initial type weights are theoretical (Anderson & Schooler power-law form × Fastpaca tiers), not empirically calibrated.
**Mitigation (locked per D-0.3):** Week-4 pilot is a *sanity check*, not a calibration step — `decay_d` values are not re-tuned after the pilot. The theoretical-vs-empirical gap is a documented limitation; pilot performance is part of the result set, not a tuning input.

## 20.9 Single benchmark

All results from SWE-Bench-CL.
**Mitigation:** Multi-model *exploratory probe* (Week 7, 12 runs) provides descriptive evidence on cross-model transfer but is not powered for inferential generalization (per D-0.4). Optional MEMTRACK cross-validation noted as future work.

## 20.10 Causal interpretation

Memory-item labels are "associated with success/failure," not causal.
**Mitigation:** Causal claims confined to Tier-3 matched-contrast case studies. Prediction model uses associated labels and is framed as feature analysis, not causal estimation.

## 20.11 Retrieval-bottleneck confound (and how we detect it)

By locked invariant #19, retrieval is identical (pure cosine top-k) across all six conditions. By locked configuration `top_k=5` and `max_context_tokens=2000`, the *prompt* receives at most ~5 memories regardless of how many records the storage policy keeps. If pruning policies and Full Memory return overlapping top-5 sets on most tasks (e.g., because the highest-cosine records survive pruning by all policies), the experimental contrast on CL-F1 measures a small-tail effect, not the headline "memory policy matters" claim.

This is empirically testable via the Jaccard overlap probe (§11.5). Pre-registered decision rule:

- **Median Jaccard ≤ 0.5** across the four pruning-vs-Full-Memory pairs: contrast is well-identified at the prompt; storage policies drive observable retrieval differences.
- **Median Jaccard ∈ (0.5, 0.9):** moderate; storage policies differ on a substantial minority of tasks; standard interpretation applies but the overlap distribution is reported alongside.
- **Median Jaccard > 0.9:** §19.7 fires; contribution claim restricts to "storage-side policy characterization under fixed retrieval, in a regime where retrieval dominates"; §1.4 contribution paragraph is qualified accordingly in the Discussion.

Reporting: §20 includes the Jaccard distribution histogram per condition-pair. Acceptance criterion #18 (§23): the probe must be reported regardless of outcome.

## 20.12 Classifier-as-policy confound

The Type-Aware Decay policy depends on the 5-type classifier (§10). If classifier accuracy is, say, 75% (within §10.3's "proceed, note as limitation" band), then 25% of memory records carry an incorrect type label, and Type-Aware Decay is operationally ~75% type-aware + ~25% near-random for those misclassified records. Random Prune and Recency Prune do not depend on the classifier; their performance is a clean reference.

**Mitigation:** Pre-registered sensitivity analysis: re-run the Type-Aware Decay maintain() step offline using the 150 manually-audited gold labels (§10.2) in place of classifier labels, on the audited records only. Compare the resulting archived-set Jaccard to the original. Report classifier confidence as a covariate in any GLMM specification on Type-Aware-relevant cells. Without this, any "Type-Aware beats Random" finding cannot be attributed to type-awareness vs. classifier quality.

---

# 21. Week-by-week execution

## Week 1 — Spike

| Day | Task | Gate |
|---|---|---|
| Mon | Clone repo. Read `eval_v3`. Setup GPT-5.4 API + cost monitoring. | Codebase navigable? |
| Tue | Implement: embedding fix, hard timeout, injection order. | Technical fixes verified? |
| Wed | Run 1 sequence: No Memory. Verify CL metrics. Monitor `iostat`. | CL-F1 output? |
| Thu | Run same sequence: Full Memory. Compare. Measure cost/runtime. | Different output? Cost reasonable? |
| Fri | Choose `top_k`, budget B, `max_workers`. Document. | **GO / NO-GO gate** |

Backup plan if `eval_v3` harness fails: SWE-agent + custom FAISS on SWE-Bench Verified.

## Week 2 — Infrastructure + simple policies

- Full logging schema (per-task, per-event, trajectories, snapshots)
- Type classifier (Structured Outputs); test on 20 items
- Random Prune + Recency Prune policies
- Verify 4 conditions (No Memory, Full, Random, Recency) on 1 sequence

## Week 3 — Complex policies + classifier audit

- Type-Aware Decay (with cost tracking)
- CLS Consolidation (with cost tracking)
- Classifier audit: 150 stratified items, apply decision rules
- Pilot: all 6 conditions on 2 sequences (1 seed)

## Week 4 — Calibrate + lock

- Analyze pilot. Adjust `decay_d` per type if needed.
- Lock `top_k`, budget B, all hyperparameters.
- **FREEZE parameters.** Begin Methodology chapter.

## Weeks 5–6 — Full matrix

- All 6 conditions × 8 sequences × 3 seeds = 144 runs on GPT-5.4
- Monitor cost daily. Re-evaluate weekly. Adjust Docker `max_workers` if needed.

## Week 7 — Multi-model exploratory probe

- Top-3 conditions (decided after Week 6) × 4 sequences × 1 seed = 12 runs on Haiku / 4o-mini
- Framed as exploratory cross-model probe, not a validation/generalization arm (D-0.4)

## Weeks 8–9 — Analysis (strict order)

1. Sequence-level ranking (Wilcoxon + r_rb + bootstrap)
2. Pareto frontier (CL-F1 vs cost)
3. Trajectory plots (resolved-rate / memory-size / tokens over sequence)
4. Behavioral analysis (tool calls, syntax errors — H4)
5. Feature importance (LogReg + GBM, PR-AUC + VIF)
6. GLMM task-level analysis
7. Failure analysis (case studies)
8. Survival analysis per memory type (if data supports)
9. Dose-response (CL-F1 vs memory size)

## Week 10 — OpenMem module (packaging)

Translate validated policies into the OpenMem codebase. Design spec in thesis even if implementation slips.

## Week 11 — Write Chapters 1–5

## Week 12 — Finish + submit

---

# 22. Budget, risks, and stop-loss

## 22.1 Budget projection and stop-loss

**Per-task cost model (rounded estimates, GPT-5.4 at assumed $0.005/1K input + $0.015/1K output tokens; refine after Spike Day 2 cost telemetry):**

| Component | Per-task tokens (typ.) | Per-task USD (typ.) |
|---|---|---|
| Main model (20 steps × ~3000 in + ~500 out / step) | ~70K | ~$0.40 |
| Reflection (§9.2, gpt-4o-mini) | ~5K | ~$0.005 |
| Classifier (§9.3, gpt-4o-mini) | ~1K | ~$0.001 |
| **Total per online task** | **~76K** | **~$0.41** |

**Forward run projection (144 runs × average 30 tasks/sequence):**

- 4320 online tasks × $0.41 ≈ **$1,770** primary forward cost.

**Anchor-probe re-evaluation projection (§14.2):**

- Per (sequence, condition, seed): up to 20 re-evaluations × $0.41 ≈ $8.20.
- Across 144 cells: 144 × $8.20 ≈ **$1,180** anchor-probe cost.

**Consolidation LLM cost (CLS only, §8 P5):**

- ~6 consolidation rounds per sequence × ~5 records summarized × 350 output tokens ≈ ~15K tokens per round → ~$0.05/round.
- Across CLS cells (24 cells × 6 rounds) ≈ **$8** consolidation cost.

**Multi-model validation (12 runs, Haiku/4o-mini at lower per-token cost):**

- 12 runs × 30 tasks × ~$0.10 ≈ **$36**.

**Total expected cost: ~$3,000** (forward + anchor probe + consolidation + multi-model). Spike Week pilot adds ~$50. `eval_v3` Docker compute is paid by the VPS (sunk).

**Stop-loss triggers and decision tree:**

| Trigger | Threshold | Action |
|---|---|---|
| Week-1 spike actual > 1.5× projected | > $75 for 3 smoke tasks | Recompute per-task cost; abort if real per-task > $1.50 |
| Week-3 pilot actual > 1.5× projected | > $300 for 12 pilot runs | Reduce `max_steps_per_task` from 20 → 15 (re-document as a tighter limit, locked) |
| Week-5 projected total > $5,000 | Linear extrapolation | Invoke §23 fallback (2): drop 1 seed → 96 runs |
| Week-6 projected total > $7,000 | Linear extrapolation | Invoke §23 fallback (3): drop 2 hardest sequences → 72 runs |
| Week-6 projected total > $10,000 | Linear extrapolation | Invoke §23 fallback (4): drop CLS Consolidation → 120 runs |
| Any single day burn > $400 | Daily cost telemetry | Pause runs; investigate; do not auto-restart |

**Pre-registered:** the actual cost numbers (per-task, per-sequence, total) are reported in the thesis Limitations section regardless of outcome, alongside the realized scope after any fallback. Cost-realization data are captured in acceptance criterion #19 (§23).

**Note on `a_{i,j}` supplementary (§14.3).** The supplementary full-matrix sensitivity (4 cells × ~T²/2 re-evaluations ≈ 1800 extra re-evaluations × $0.41 ≈ $740) is only invoked if Week-7 cumulative cost is < $3,000 and remaining budget ≥ $1,000.

## 22.2 Risk registry

| Risk | Prob | Impact | Mitigation | Detection |
|---|---|---|---|---|
| Harness buggy | Med | 2-wk delay | Spike-week 3-task smoke run; backup SWE-agent. | Spike Day 3 fails. |
| GPT-5.4 robust to memory noise | Med | Narrative pivot | H1 covers both outcomes (cost story works either way). | Pilot Week 3–4. |
| Small effect (< 3%) | Med | Weak stats | Multi-metric reporting. Pareto finding independent of significance. | Pilot. |
| No inverted-U / no degradation | Med-Hi | Lose one outcome | Stretch layer (dose-response) is optional. Descriptive stats still informative. | Trajectory Week 8. |
| Classifier < 70% accuracy | Med | Type-aware weakened | Collapse to 3 types (Section 10.3). | Audit Week 3. |
| Infinite loop burns budget | High | Cost spike | Hard 20-step timeout. Daily cost monitoring. | Cost spikes in logs. |
| Docker I/O crash at high concurrency | Med | False task failures | Start `max_workers=4`, monitor `iostat`, ramp gradually. | Timeouts cluster at high concurrency. |
| Embedding truncation | High if unfixed | FAISS garbage | Preprocessed payload, < 7500 token assert. | Verify in spike. |
| Full Memory doesn't hurt | Low | Premise undermined | Negative result publishable. Cost story remains. | Pilot Week 3–4. |
| Multi-model run blows budget | Med | Lose Week-7 validation | Already restricted to 12 runs. Skip if needed. | Week-6 cost projection. |
| SWE-ContextBench unavailable | High | Lose validation | Plan doesn't depend on it. | No reply by Week 4. |

---

# 23. Acceptance criteria

The implementation is thesis-ready when the following are produced:

1. ✅ A complete run for all 8 SWE-Bench-CL sequences
2. ✅ Results for all 6 memory policies on all sequences
3. ✅ 3 seeds for each (condition, sequence) cell → 144 task sequences
4. ✅ Per-task `resolved` logs + token / runtime / tool-call metrics
5. ✅ Memory event logs (write / retrieve / archive / consolidate)
6. ✅ Retrieved-memory logs (with IDs, scores, ages, types)
7. ✅ Memory snapshots at every task boundary
8. ✅ Per-sequence anchor-probe `a_{i,j}` entries (§14.2: k=5 anchors × 4 probe points) → CL-Plasticity, CL-Stability, CL-F1
9. ✅ Sequence-level Wilcoxon + Holm + r_rb + bootstrap BCa CI for 5 planned contrasts
10. ✅ Task-level GLMM (exploratory)
11. ✅ Pareto frontier plot (CL-F1 vs cost)
12. ✅ Memory-size and tool-call trajectory plots
13. ✅ Behavioral analysis (H4): tool calls + syntax errors over sequence
14. ✅ Feature importance for helpful/harmful prediction (PR-AUC + VIF)
15. ✅ At least one failure-analysis section with 5+ cases per policy
16. ✅ At least one skeptical / negative result (case where pruning harms or Full Memory helps)
17. ✅ Multi-model validation results (12 runs, top-3 conditions)
18. ✅ Cross-condition retrieval Jaccard-overlap report (§11.5, §20.11) for the four pruning-vs-Full-Memory pairs across all 8 sequences and 3 seeds (reported regardless of outcome)
19. ✅ Budget realization table (§22.1): planned vs. actual cost per phase, fallback ladder invocations if any

**Minimum-acceptable scope** (if compute tight at Week 6, listed by priority of fallback):

1. **Anchor-probe Stability only** (§14.2) with no §14.3 supplementary full matrix. Default and primary; no scope reduction needed.
2. **Drop 1 seed** if total cost projection at Week 6 ≥ stop-loss threshold (§22.1): 8 sequences × 6 conditions × 2 seeds = 96 runs. Document in Limitations.
3. **Drop 2 hardest sequences** if (2) is also exceeded: 6 sequences × 6 conditions × 3 seeds = 108 runs. Document in Limitations.
4. **Drop CLS Consolidation** if (3) is also exceeded: 8 sequences × 5 conditions × 3 seeds = 120 runs. CLS is the most expensive policy due to LLM-on-write tax; dropping it preserves the H1a/H1b core contrasts.

Document any invocation of (2)–(4) explicitly in the Limitations chapter with the cost projection that triggered it.

---

# 24. Anti-creep manifesto

| Rejected | Why |
|---|---|
| 20+ self-generated sequences | Changes benchmark; weeks to validate. |
| Conditions 7, 8, 9 | 6 is the sweet spot. Bonferroni penalty + compute cost. |
| Hyperparameter grid search | Overfitting risk. Calibrate once at Week 4, then lock. |
| Bayesian hierarchical model | Unnecessary. GLMM + Wilcoxon sufficient. |
| Network analysis / topic modeling on trajectories | Post-thesis. |
| Cross-repo retrieval as main experiment | Confound with general transfer; same-repo is the clean condition. |
| In-task code-search tools (WarpGrep, AFT, srcwalk) | Different layer; cite in Related Work as parallel direction, not as experimental variable. |
| Adding outcome to the embedding payload | Would mix policy signal into retrieval. |
| Compound retrieval score with bonuses | Would confound policy with retrieval scoring; locked invariant #19. |
| Calibrating all 11 Type-Aware knobs from the 12-run pilot | Statistically infeasible; pilot is sanity-check only (§20.8). |

---

# 25. Code stubs & base interfaces

## 25.1 MemoryPolicy ABC

```python
from abc import ABC, abstractmethod

class MemoryPolicy(ABC):
    name: str

    @abstractmethod
    def retrieve(
        self,
        task: Task,
        memory_store: "MemoryStore",
        top_k: int,
        token_budget: int,
    ) -> list[MemoryRecord]:
        ...

    @abstractmethod
    def write(self, memory_store: "MemoryStore", record: MemoryRecord) -> None:
        ...

    @abstractmethod
    def maintain(self, memory_store: "MemoryStore") -> None:
        """Called after every task; prune / consolidate as needed."""
        ...
```

## 25.2 MemoryStore interface

```python
class MemoryStore:
    def __init__(self, config: MemoryConfig):
        self.sqlite = SQLiteBackend(config.sqlite_path)
        self.faiss = FAISSBackend(config.faiss_path, dim=config.embedding_dim)
        self._snapshots = SnapshotLog(config.snapshot_dir)

    def add(self, record: MemoryRecord) -> None:
        self._verify_embedding_size(record.embedding_text)
        vec = embed(record.embedding_text)
        record.embedding_vector_id = self.faiss.add(vec)
        self.sqlite.insert(record)

    def search(
        self,
        query: str,
        repo: str,
        top_k: int,
        same_repo_only: bool = True,
    ) -> list[tuple[float, MemoryRecord]]:
        """Pure cosine similarity, no bonuses."""
        query_vec = embed(query)
        candidate_ids = self.sqlite.filter(repo=repo if same_repo_only else None,
                                           is_archived=False)
        scored = self.faiss.search(query_vec, candidate_ids, k=top_k)
        return [(score, self.sqlite.get(id_)) for id_, score in scored]

    def active_records(self) -> list[MemoryRecord]:
        return self.sqlite.filter(is_archived=False)

    def archive(
        self,
        memory_id: str,
        reason: str,
        replacement_id: str | None = None,
    ) -> None:
        self.sqlite.update(memory_id, is_archived=True,
                           archived_reason=reason,
                           archived_at_step=current_step())
        log_memory_event("archive", memory_id, reason=reason,
                         replacement_id=replacement_id)

    def count_active(self) -> int:
        return self.sqlite.count(is_archived=False)

    def stats(self) -> dict:
        return {
            "active_count": self.count_active(),
            "archived_count": self.sqlite.count(is_archived=True),
            "total_tokens": self.sqlite.sum_tokens(is_archived=False),
        }

    def snapshot(self, boundary: str) -> None:
        self._snapshots.write(
            step=current_step(),
            boundary=boundary,
            active=self.active_records(),
        )

    def _verify_embedding_size(self, text: str) -> None:
        n_tokens = count_tokens(text)
        assert n_tokens < 7500, \
            f"Embedding payload {n_tokens} tokens exceeds 7500 cap"
```

## 25.3 Sequence runner

```python
def run_sequence(
    sequence: list[Task],
    policy: MemoryPolicy,
    config: ExperimentConfig,
    seed: int,
) -> SequenceResults:
    set_seed(seed)
    memory_store = MemoryStore(config.memory)

    results = []
    for task in sequence:
        memory_store.snapshot("before_task")

        result = solve_task(task, memory_store, policy, config)
        results.append(result)

        memory_store.snapshot("after_task_before_prune")
        # write + maintain happen inside solve_task

        memory_store.snapshot("after_prune")

    # End-of-sequence: compute a_{i,j} matrix
    matrix = build_aij_matrix(sequence, memory_store, config)
    cl_metrics = compute_cl_metrics(matrix)

    return SequenceResults(
        per_task=results,
        cl_metrics=cl_metrics,
        memory_final_state=memory_store.stats(),
    )
```

## 25.4 Experiment runner

```python
def run_experiment(config: ExperimentConfig) -> None:
    sequences = load_swebench_cl()  # all 8 sequences
    assert len(sequences) == 8, "Expected 8 official SWE-Bench-CL sequences"

    for sequence in sequences:
        for policy_name in config.policies:
            for seed in config.seeds[policy_name]:   # always [1,2,3] for all policies
                run_id = f"{config.model}_{policy_name}_seq{sequence.id}_seed{seed}"
                if results_exist(run_id):
                    continue   # resume support

                policy = build_policy(policy_name, seed, config)

                results = run_sequence(sequence, policy, config, seed)
                save_results(run_id, results)
```

## 25.5 Retrieval helper (shared across all policies)

```python
def shared_retrieve(
    task: Task,
    memory_store: MemoryStore,
    top_k: int,
    token_budget: int,
) -> list[MemoryRecord]:
    """IDENTICAL retrieval used by all memory-enabled policies."""
    query = build_query(task)
    scored = memory_store.search(
        query=query,
        repo=task.repo,
        top_k=top_k,
        same_repo_only=True,
    )
    return trim_to_token_budget(scored, token_budget)

def build_query(task: Task) -> str:
    return f"Repository: {task.repo}\nIssue: {task.issue_text}".strip()

def trim_to_token_budget(
    scored: list[tuple[float, MemoryRecord]],
    token_budget: int,
) -> list[MemoryRecord]:
    """Drop lowest-similarity until total tokens <= budget. Never partial."""
    sorted_desc = sorted(scored, key=lambda x: x[0], reverse=True)
    out = []
    total = 0
    for score, rec in sorted_desc:
        if total + rec.token_length > token_budget:
            continue
        out.append(rec)
        total += rec.token_length
    return out
```

## 25.6 CL metrics wrapper (~100 LOC target)

```python
def build_aij_matrix(
    sequence: list[Task],
    memory_store: MemoryStore,
    config: ExperimentConfig,
) -> np.ndarray:
    """a_{i,j} = score of task i when re-evaluated after task j was completed.
       For SWE-Bench-CL, the memory state after task j is what matters."""
    T = len(sequence)
    matrix = np.zeros((T, T))

    # Diagonal: online performance — read from per-task results
    for i, task in enumerate(sequence):
        matrix[i, i] = task.result.resolved

    # Off-diagonal: re-evaluate task i with memory state after task j (j > i)
    # In practice, save memory snapshots; re-run task i against each later snapshot
    for j in range(T):
        snapshot = load_snapshot(after_task=j)
        for i in range(j):
            matrix[i, j] = re_evaluate(sequence[i], snapshot, config)

    return matrix


def compute_cl_metrics(matrix: np.ndarray) -> dict:
    T = matrix.shape[0]
    plasticity = matrix.diagonal().mean()
    # Forgetting = max past score - current score, averaged
    forgetting = np.mean([
        max(matrix[i, i:T]) - matrix[i, T-1]
        for i in range(T-1)
    ])
    stability = 1.0 - forgetting
    cl_f1 = 2 * plasticity * stability / max(plasticity + stability, 1e-8)
    return {
        "plasticity": plasticity,
        "stability": stability,
        "forgetting": forgetting,
        "cl_f1": cl_f1,
    }
```

## 25.7 Statistical analysis

```python
def primary_analysis(
    results: dict[str, dict[str, list[float]]],   # results[policy][sequence] = [seed1, seed2, seed3]
    metric: str = "cl_f1",
) -> dict:
    """Sequence-level Wilcoxon + r_rb + bootstrap BCa for 5 planned contrasts."""
    PLANNED = [
        ("full_memory", "no_memory"),
        ("full_memory", "random_prune"),
        ("full_memory", "recency_prune"),
        ("full_memory", "type_aware_decay"),
        ("full_memory", "cls_consolidation"),
    ]

    # Aggregate to sequence-level means
    seq_means = {}
    for policy, by_seq in results.items():
        seq_means[policy] = {seq: np.mean(seeds) for seq, seeds in by_seq.items()}

    contrasts = []
    for a, b in PLANNED:
        diffs = [seq_means[a][s] - seq_means[b][s] for s in seq_means[a]]
        stat, p = scipy.stats.wilcoxon(diffs)
        r_rb = rank_biserial(diffs)
        ci_low, ci_high = bootstrap_bca_ci(diffs, n_iter=5000, conf=0.95)
        contrasts.append({
            "pair": (a, b),
            "median_diff": np.median(diffs),
            "r_rb": r_rb,
            "ci_95": (ci_low, ci_high),
            "p_raw": p,
        })

    # Holm correction
    p_raw = [c["p_raw"] for c in contrasts]
    p_holm = holm_correction(p_raw)
    for c, p in zip(contrasts, p_holm):
        c["p_holm"] = p

    return {"planned_contrasts": contrasts}


def feature_importance_analysis(rows: pd.DataFrame) -> dict:
    """LogReg + GBM with PR-AUC + VIF check."""
    # VIF check
    vifs = compute_vif(rows[FEATURE_COLS])
    if vifs.get("memory_age", 0) > 5 or vifs.get("use_count", 0) > 5:
        # Use derived feature
        rows["retrieval_rate"] = rows["use_count"] / (rows["memory_age"] + 1)
        feature_cols = [c for c in FEATURE_COLS if c not in ("memory_age", "use_count")] + ["retrieval_rate"]
    else:
        feature_cols = FEATURE_COLS

    X, y = rows[feature_cols], rows["label_helpful"]
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    lr_scores = cross_val_score(
        LogisticRegression(class_weight="balanced", max_iter=1000),
        X, y, cv=cv, scoring="average_precision",   # PR-AUC
    )
    gbm_scores = cross_val_score(
        GradientBoostingClassifier(),
        X, y, cv=cv, scoring="average_precision",
    )

    return {
        "vif": vifs,
        "features_used": feature_cols,
        "logreg_pr_auc": (lr_scores.mean(), lr_scores.std()),
        "gbm_pr_auc": (gbm_scores.mean(), gbm_scores.std()),
    }
```

---

# 26. References

| # | Reference | Role |
|---|---|---|
| 1 | Anderson & Schooler (1991) | Power-law decay — formula grounding |
| 2 | Richards & Frankland (2017). *Neuron*. | Forgetting as regularization |
| 3 | McClelland et al. (1995). *Psych Review*. | CLS theory |
| 4 | Davis & Zhong (2017). *Neuron*. | Active forgetting |
| 5 | Xiong et al. (2025). arXiv:2505.16067. | Add-all worse than no memory |
| 6 | Lindenbauer et al. (2025). NeurIPS DL4C. arXiv:2508.21433. | Observation masking |
| 7 | Zhu et al. (2026). arXiv:2602.08316. | SWE-ContextBench |
| 8 | Joshi et al. (2025). arXiv:2507.00014. | **SWE-Bench-CL (primary)** |
| 9 | Deshpande et al. (2025). NeurIPS. arXiv:2510.01353. | MEMTRACK |
| 10 | Du et al. (2025). EMNLP. arXiv:2510.05381. | Context length hurts |
| 11 | Liu et al. (2024). TACL. | **Lost in the Middle — injection order** |
| 12 | Cuconasu et al. (2024). SIGIR. arXiv:2401.14887. | Power of Noise |
| 13 | Alqithami (2025). *Forgetful but Faithful: A Cognitive Memory Architecture and Benchmark for Privacy-Aware Generative Agents.* arXiv:2512.12856. | 6 forgetting policies on FiFA benchmark — closest by name, different domain (privacy-aware generative agents); see §1.4 for differentiation |
| 14 | Shen et al. (2026). arXiv:2602.21611. | Subtask-level memory |
| 15 | Sun et al. (2022). ICLR 2023. | Info-theoretic selection |
| 16 | Pink et al. (2025). arXiv:2502.06975. | Episodic memory position |
| 17 | Letta (2025). Blog. | Filesystem beats memory |
| 18 | Wong et al. (2025). arXiv:2512.10398. | Confucius Code Agent |
| 19 | Fastpaca (2025). Blog. | Mem0/Zep cost explosion |
| 20 | Fastpaca (2026). Blog. | Memory taxonomy |
| 21 | Fastpaca (2025). Blog. | **Failure-mode design — type weights** |
| 22 | MemBench (2025). arXiv:2506.21605. | Cost benchmark |
| 23 | Packer et al. (2024). ICLR. | MemGPT |
| 24 | Park et al. (2023). UIST. | Generative Agents |
| 25 | Zheng et al. (2025). IEEE TPAMI. | Lifelong learning roadmap |
| 26 | Cumming (2014). *Psychological Science*. | **Estimation-based inference** |
| 27 | Wasserstein et al. (2019). *The American Statistician*. | **ASA statement on p-values** |
| 28 | Zhong, Guo, Gao, Ye & Wang (2024). MemoryBank: Enhancing Large Language Models with Long-Term Memory. AAAI 2024. | Ebbinghaus forgetting-curve memory — closest cognitive-decay analog to P4 |
| 29 | Xu, Liang, Yan, Li, Liu, Yan, Jin & Wen (2025). A-MEM: Agentic Memory for LLM Agents. arXiv:2502.12110. | Dynamic linked memory organization — contrast with our static content taxonomy (§5.1) |
| 30 | Shinn, Cassano, Berman, Gopinath, Narasimhan & Yao (2023). Reflexion: Language Agents with Verbal Reinforcement Learning. NeurIPS 2023. | Reflection-as-memory — methodological precedent for §9 reflection step |

---

# Appendix A — Pre-spike checklist

- [ ] Clone `github.com/thomasjoshi/agents-never-forget`
- [ ] Read `eval_v3_agent/` code; understand sequence loading
- [ ] Setup GPT-5.4 API + cost monitoring (wandb dashboard)
- [ ] Setup backup model API (Haiku / 4o-mini)
- [ ] Provision x86_64 VPS: Docker, 250 GB disk, 32 GB RAM, 8 cores
- [ ] Configure tmux + wandb on VPS
- [ ] Create experiment Git repo with directory layout from Section 3.2
- [ ] Implement `cl_metrics.py` wrapper (≈100 LOC)
- [ ] Implement embedding-size assert (Section 6.3)
- [ ] Implement injection-order (best-LAST) helper
- [ ] **Spike Day 1:** 3-task smoke run on `eval_v3` → confirm > 15% pass rate
- [ ] Email SWE-ContextBench authors (Jared Zhu, Oxford)
- [ ] Read Xiong et al. (2505.16067), Alqithami (2512.12856), Lindenbauer et al. (2508.21433)
- [ ] Read Fastpaca blog series (3 articles)

---

# Appendix B — What this document replaces and why

This document supersedes:

1. `THESIS_MASTER_PLAN-final.md` (v4) — the research plan with locked decisions after 3 rounds of multi-LLM review
2. `FULL IMPLEMENTATION SPEC` — the engineering implementation draft

Reconciliation decisions:

| Source | Status |
|---|---|
| All 26 v4 frozen decisions | **Preserved** as Section 0.1 |
| Spec's reflection-step structured output | **Merged** into Section 9 |
| Spec's manual-labeling protocol for 100–200 pairs | **Merged** into Section 16.2 (Tier 2) |
| Spec's failure-analysis template | **Merged** into Section 18 |
| Spec's interpretation rules | **Merged** into Section 19 |
| Spec's anchor probe | **Demoted** to supplementary (Section 14.3); `a_{i,j}` matrix remains primary |
| Spec's append-all stress test | **Demoted** to optional ablation (Section 12.3 E) |
| Spec's 7-type taxonomy | **Replaced** by v4's 5-type taxonomy (locked) |
| Spec's linear-sum Type-Aware Decay formula | **Replaced** by v4's Anderson-Schooler multiplicative formula |
| Spec's McNemar test | **Replaced** by Wilcoxon on sequence means |
| Spec's Cliff's delta | **Replaced** by rank-biserial r_rb |
| Spec's accuracy-based feature analysis | **Replaced** by PR-AUC + VIF |
| Spec's "1 seed for deterministic policies" | **Replaced** by 3 seeds for all conditions |
| Spec's 3–5 self-chosen repos | **Replaced** by all 8 official SWE-Bench-CL sequences |
| Spec's 30-step task limit | **Replaced** by v4's 20-step hard timeout |
| Spec's compound retrieval score | **Replaced** by pure cosine, identical across conditions |
| Spec's outcome-laden embedding payload | **Replaced** by v4's `[Issue + Error + Diff]` only |
| Spec's trigger-on-overflow CLS schedule | **Replaced** by v4's fixed every-5-tasks schedule |

This is the single source of truth. Begin Spike Week.
