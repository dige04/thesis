# Design Document: Memory Pruning Research System

## Overview

This document specifies the technical design for a comprehensive research system that evaluates memory pruning and forgetting policies for AI coding agents. The system executes 144 controlled experimental runs (6 policies × 8 SWE-Bench-CL sequences × 3 seeds) to test whether proactive forgetting matches or beats full-memory accumulation on the Pareto frontier of continual learning F1-score versus operational cost.

### Core Principle

**The agent's codebase state resets per task; its external memory persists across tasks.**

```
Task 1: clean repo checkout → agent solves → memory updated → prune/consolidate
Task 2: clean repo checkout → SAME memory bank continues → solve → update → prune
Task 3: clean repo checkout → SAME memory bank continues → solve → update → prune
```

The thing that "continues learning" is neither the repository nor the model weights, but the **external semantic memory system**. This isolates the variable we study.

### Research Question

Do proactive forgetting and consolidation policies improve the sequential coding performance and operational efficiency of AI coding agents — including frontier models — compared with full-memory accumulation or no persistent memory?

### Hypotheses

- **H1:** Selective pruning policies achieve equal or better sequential performance compared to full-memory accumulation, while reducing operational cost
- **H2:** Semantically informed pruning (Type-Aware Decay) outperforms random pruning
- **H3:** CLS Consolidation provides similar performance to extractive pruning but at higher cost
- **H4:** Full-memory accumulation induces measurable analysis paralysis (increased tool calls, syntax errors)
- **H5:** Pruning can harm performance when it removes rare but critical repository-specific memories

### Frozen Decisions

All 26 frozen decisions from THESIS_FINAL_v5.md §0.1 are preserved in this design:

1. **Experimental platform:** SWE-Bench-CL from `github.com/thomasjoshi/agents-never-forget`
2. **Base model:** GPT-5.4
3. **Eval harness:** Standard SWE-Bench `eval_v3` Docker + custom CL-metric wrapper
4. **Compute environment:** x86_64 VPS, 32GB RAM, 250GB disk, 8 cores, Docker-native
5. **Sequences:** All 8 official SWE-Bench-CL sequences, no subsetting
6. **Core conditions:** 6 policies (No Memory, Full Memory, Random Prune, Recency Prune, Type-Aware Decay, CLS Consolidation)
7. **Seeds:** 3 seeds for ALL 6 conditions → 144 runs total
8. **Primary metric:** CL-F1 (harmonic mean of Plasticity and Stability)
9. **Primary statistical unit:** Sequence-level means (N=8 paired observations)
10. **Primary test:** Wilcoxon signed-rank + Holm correction on 5 pre-registered contrasts
11. **Effect size:** Rank-biserial r_rb + median paired difference ± bootstrap BCa 95% CI (5000 iterations)
12. **Task-level analysis:** GLMM with binomial/logit: `task_success ~ condition + difficulty + position + (1|seq/seed) + (1|task_id)`
13. **Memory-item labels:** "Associated with success/failure" — NOT causal
14. **Feature analysis:** PR-AUC + VIF check (target VIF < 5) + class weights for imbalance
15. **Memory type taxonomy:** 5 content types: `architectural`, `api_change`, `bug_fix`, `test_update`, `config` (NOT outcome-based)
16. **Classifier mechanism:** Structured Outputs / Tool Use, `temp=0`, cheapest model, 1-of-5 enum
17. **Embedding payload:** Preprocessed: `[Issue + Final Error + Final Diff]` only, verify < 7500 tokens
18. **Retrieval scoring:** Pure cosine similarity, identical across all 6 conditions
19. **Injection order:** Relevance-sorted, best item LAST (Lost-in-the-Middle fix)
20. **Execution limit:** Max 20 steps per task, hard force-fail if exceeded
21. **Docker concurrency:** Start `max_workers=4`, increase gradually
22. **Type-Aware Decay formula:** Multiplicative (Anderson & Schooler): `score = base_value(type) × age^{-d(type)} × (1+retrieval_count)^{0.5}`
23. **CLS consolidation schedule:** Fixed every k=5 tasks (not trigger-on-overflow)
24. **Bootstrap:** 5000 iterations, BCa method
25. **Same-repo retrieval:** Yes — main experiment only
26. **Temperature:** 0 for all LLM calls (reproducibility)

---

## Architecture

### High-Level Pipeline

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

### System Components

#### 1. Dataset Loader (`benchmark/swebenchcl_loader.py`)
- Loads all 8 official SWE-Bench-CL sequences from `SWE-Bench-CL-Curriculum.json`
- Preserves chronological ordering within each sequence
- Extracts: task_id, repo, base_commit, issue_text, test_patch, gold_patch, created_at, sequence_index, difficulty_label
- Validates minimum 15 tasks per sequence

#### 2. Sequence Runner (`benchmark/sequence_runner.py`)
- Orchestrates execution of all tasks in a sequence
- Maintains persistent memory store across task boundaries
- Ensures clean repository checkout per task
- Coordinates agent execution, evaluation, reflection, and policy maintenance
- Generates memory snapshots before/after each task

#### 3. Task Environment Manager (`benchmark/task_env.py`)
- Manages Docker container lifecycle for eval_v3
- Performs clean repository checkout per task
- Handles uncommitted changes and file system errors
- Provides repository metadata to agent

#### 4. Coding Agent (`agents/coding_agent.py`, `agents/langgraph_agent.py`)
- LangGraph-based agent with 12 explicit nodes
- Executes with temperature=0 for reproducibility
- Hard limits: 20 steps, 80 tool calls, 5 test runs, 20 minutes wall time
- Tools: read_file, write_file, edit_file, search_code, list_files, run_command, run_tests, get_patch

#### 5. Memory Store (`memory/store.py`)
- Two-layer storage: SQLite (metadata) + FAISS (vector index)
- Supports filtering by repository and archived status
- Tracks usage statistics: use_count, last_retrieved_at_step, success/failure after retrieval
- Maintains append-only logs and mutable metadata

#### 6. Memory Retriever (`memory/retriever.py`)
- Pure cosine similarity scoring (IDENTICAL across all 6 policies)
- Filters by same repository and non-archived status
- Returns top-k memories within token budget
- Drops lowest-scoring memories if budget exceeded
- No bonuses or penalties based on type, outcome, age, or retrieval count

#### 7. Type Classifier (`memory/classifier.py`)
- Structured Outputs / Tool Use with 1-of-5 enum
- Temperature=0, cheapest model (GPT-4o-mini or Claude Haiku)
- Classifies into: architectural, api_change, bug_fix, test_update, config
- Deterministic classification based on content only (NOT outcome)

#### 8. Reflection Step (`memory/reflection.py`)
- Post-task structured analysis generating memory records
- Extracts: issue_summary, patch_summary, failure_summary, test_summary
- Records: files_touched, functions_touched, commands_run, retrieved_memory_ids_used
- Invokes type classifier before passing to policy write method

#### 9. Memory Policies (`memory/policies/`)
Six policies inheriting from abstract `MemoryPolicy` base class:
- **No Memory:** Returns empty list for retrieval, discards all writes
- **Full Memory:** Stores everything, never prunes, uses shared retrieval
- **Random Prune:** Randomly archives memories when exceeding max_records
- **Recency Prune:** Archives oldest memories by sequence_index
- **Type-Aware Decay:** Scores using Anderson-Schooler power-law with type-specific parameters
- **CLS Consolidation:** Clusters and consolidates old memories every 5 tasks, falls back to Type-Aware Decay

#### 10. Evaluation Harness (`benchmark/evaluator.py`)
- Wraps standard SWE-Bench eval_v3 Docker containers
- Returns binary pass/fail per task
- Handles Docker failures gracefully
- Logs execution time and errors

#### 11. CL Metrics Calculator (`benchmark/cl_metrics.py`)
- Constructs accuracy matrix a_{i,j} (accuracy on task i after training through task j)
- Computes Plasticity: mean of diagonal elements
- Computes Stability: mean of lower-triangular elements
- Computes CL-F1: 2 × (Plasticity × Stability) / (Plasticity + Stability)
- Validates minimum learning occurred before computing metrics

#### 12. Logger (`src/logging/`)
- Writes task_results.jsonl (one row per task)
- Appends memory_events.jsonl (write, archive, consolidate events)
- Saves trajectory JSON files (action-observation pairs)
- Generates memory snapshots before_task_n.json and after_task_n.json
- All fields logged from Day 1 (cannot be recovered later)

#### 13. Statistical Analysis (`analysis/`)
- **statistical_tests.py:** Wilcoxon signed-rank + Holm correction + bootstrap BCa
- **glmm.py:** Task-level binomial GLMM with crossed random effects
- **feature_importance.py:** PR-AUC + VIF check for helpful/harmful prediction
- **pareto.py:** CL-F1 vs cost frontier analysis
- **plots.py:** Visualization generation

---

## Components and Interfaces

### MemoryRecord Dataclass

```python
@dataclass
class MemoryRecord:
    # Identity
    memory_id: str                     # UUID
    task_id: str
    repo: str
    sequence_index: int                # position in sequence
    
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
    retrieved_memory_ids_used: list[str]    # which memories were shown
    
    # Embedding
    embedding_text: str                # = "[Issue + Final Error + Final Diff]"
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

### MemoryPolicy Abstract Interface

```python
class MemoryPolicy(ABC):
    name: str
    
    @abstractmethod
    def retrieve(self, task, memory_store, top_k, token_budget) -> list[MemoryRecord]:
        """Retrieve relevant memories for task. MUST use shared_retrieve for all policies except No Memory."""
        pass
    
    @abstractmethod
    def write(self, memory_store, record: MemoryRecord) -> None:
        """Store a new memory record."""
        pass
    
    @abstractmethod
    def maintain(self, memory_store) -> None:
        """Perform pruning/consolidation after task completion."""
        pass
```

### MemoryStore Interface

```python
class MemoryStore:
    def __init__(self, run_id: str, policy_name: str):
        """Initialize SQLite + FAISS storage for a run."""
        
    def add(self, record: MemoryRecord) -> None:
        """Add a new memory record."""
        
    def filter(self, repo: str, is_archived: bool) -> list[MemoryRecord]:
        """Filter memories by repository and archived status."""
        
    def search(self, query_vector, top_k: int) -> list[tuple[float, MemoryRecord]]:
        """Cosine similarity search in FAISS."""
        
    def archive(self, memory_id: str, reason: str, replacement_id: str = None) -> None:
        """Archive a memory record."""
        
    def active_records(self) -> list[MemoryRecord]:
        """Return all non-archived records."""
        
    def count_active(self) -> int:
        """Count non-archived records."""
        
    def snapshot(self, step: int, boundary: str) -> dict:
        """Generate memory snapshot for logging."""
        
    def stats(self) -> dict:
        """Return memory store statistics."""
```

### Shared Retrieval Function

```python
def shared_retrieve(task, memory_store, top_k, token_budget) -> list[MemoryRecord]:
    """
    Pure cosine similarity retrieval - IDENTICAL across all 6 policies.
    
    1. Build query from task.repo + task.issue_text
    2. Embed query
    3. Filter candidates: same repo, not archived
    4. Score with pure cosine similarity (no bonuses/penalties)
    5. Sort descending, take top-k
    6. Drop lowest-scoring until within token_budget
    7. Return sorted ascending (best LAST for injection)
    """
    query_text = f"Repository: {task.repo}\nIssue: {task.issue_text}"
    query_vec = embed(query_text)
    
    candidates = memory_store.filter(repo=task.repo, is_archived=False)
    
    scored = []
    for record in candidates:
        sim = cosine_similarity(query_vec, record.embedding_vector)
        scored.append((sim, record))
    
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_k]
    
    # Token budget enforcement
    result = trim_to_token_budget(top, token_budget)
    
    # Sort ascending for injection (best LAST)
    result.sort(key=lambda x: x[0], reverse=False)
    
    return result
```

---

## Data Models

### Task Schema

```python
@dataclass
class Task:
    task_id: str                    # e.g., "django__django-12345"
    repo: str                       # e.g., "django/django"
    base_commit: str                # git commit hash
    issue_text: str                 # GitHub issue description
    test_patch: str                 # test file changes
    gold_patch: str                 # reference solution
    created_at: str                 # ISO timestamp
    sequence_index: int             # position in sequence (0-indexed)
    difficulty_label: str           # "easy" | "medium" | "hard"
```

### Sequence Schema

```python
@dataclass
class Sequence:
    sequence_name: str              # e.g., "django"
    repo: str                       # e.g., "django/django"
    tasks: list[Task]               # ordered chronologically
    task_count: int                 # must be >= 15
```

### Run Configuration Schema

```python
@dataclass
class RunConfig:
    run_id: str                     # unique identifier
    policy_name: str                # one of 6 policies
    sequence_name: str              # one of 8 sequences
    seed: int                       # 1, 2, or 3
    model: str                      # "gpt-5.4"
    temperature: float              # 0
    max_steps_per_task: int         # 20
    top_k: int                      # 5 (locked after Week 4)
    max_context_tokens: int         # 2000 (locked after Week 4)
    max_records: int                # 100
    max_storage_tokens: int         # 30000
```

### Logging Schemas

#### Task Result Log (task_results.jsonl)

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
  
  "retrieved_memory_ids": ["MEM-001", "MEM-007", "MEM-091"],
  "retrieved_memory_scores": [0.61, 0.68, 0.72],
  "retrieved_memory_types": ["test_update", "bug_fix", "api_change"],
  "retrieved_memory_ages": [12, 3, 7],
  
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

#### Memory Event Log (memory_events.jsonl)

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

#### Trajectory Log (trajectories/{task_id}.json)

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

#### Memory Snapshot (snapshots/before_task_n.json, after_task_n.json)

```json
{
  "step": 17,
  "boundary": "after_prune",
  "active_records": [
    {
      "memory_id": "MEM-001",
      "importance_score": 0.74,
      "memory_type": "architectural"
    }
  ],
  "archived_this_step": ["MEM-014", "MEM-019"]
}
```

---

## Error Handling

### Repository Checkout Failures
- **Trigger:** Uncommitted changes, file system errors, git failures
- **Action:** Fail entire sequence run immediately
- **Logging:** Record failure reason, task_id, sequence_index

### Docker Container Failures
- **Trigger:** eval_v3 container crashes, timeout, resource exhaustion
- **Action:** Log as evaluation error, mark task as failed
- **Retry:** No automatic retry (preserves experimental integrity)

### Type Classifier Failures
- **Trigger:** API error, timeout, invalid response
- **Action:** Fail reflection step entirely (do not proceed with untyped memory)
- **Logging:** Record classifier error, task_id, retry count

### Embedding Size Violations
- **Trigger:** embedding_text exceeds 7500 tokens
- **Action:** Truncate patch_summary from end until < 7500 tokens
- **Logging:** Record truncation event, original size, final size

### Memory Budget Violations
- **Trigger:** Retrieved memories exceed max_context_tokens
- **Action:** Drop lowest-scoring memories until within budget
- **Guarantee:** Final result MUST fit within budget (no partial items)

### Agent Timeout
- **Trigger:** Step count exceeds 20 or wall time exceeds 20 minutes
- **Action:** Force-fail task, log timeout=true
- **Memory:** Write memory record with outcome=unknown

### Configuration Validation Failures
- **Trigger:** Missing required keys, zero/negative values for critical parameters
- **Action:** Fail fast before starting run
- **Logging:** Record validation errors with parameter names

---

## Testing Strategy

This research system is NOT suitable for property-based testing because:

1. **Infrastructure as Code:** The system orchestrates Docker containers, file systems, and external APIs — these are configuration and integration concerns, not pure functions with universal properties
2. **Stochastic Experimental Design:** The system intentionally includes randomness (Random Prune policy, seeds) that is controlled through configuration, not testable as invariants
3. **External Dependencies:** Core functionality depends on SWE-Bench eval_v3 Docker harness, OpenAI/Anthropic APIs, and FAISS — these cannot be property-tested
4. **Statistical Analysis:** The system computes statistical tests (Wilcoxon, GLMM) on experimental data — these are one-shot analyses, not functions with universal properties

### Unit Testing Strategy

**Focus on specific examples, edge cases, and frozen invariants:**

#### 1. Frozen Invariant Tests
- **test_embedding_size_assert:** Verify embedding_text < 7500 tokens before embedding
- **test_retrieval_identical_across_policies:** Verify all policies use shared_retrieve with identical scoring
- **test_injection_order_best_last:** Verify highest-relevance memory injected last
- **test_max_steps_enforcement:** Verify agent force-fails at step 21
- **test_temperature_zero:** Verify all LLM calls use temperature=0
- **test_type_classifier_deterministic:** Verify classifier uses temperature=0
- **test_no_bonuses_in_retrieval:** Verify pure cosine scoring (no type/outcome/age bonuses)

#### 2. Data Loading Tests
- **test_load_all_8_sequences:** Verify all sequences loaded without subsetting
- **test_preserve_chronological_order:** Verify sequence_index ordering preserved
- **test_minimum_15_tasks_per_sequence:** Verify each sequence has >= 15 tasks
- **test_extract_all_required_fields:** Verify task_id, repo, base_commit, issue_text, etc. extracted

#### 3. Memory Store Tests
- **test_filter_by_repo_and_archived:** Verify filtering logic
- **test_archive_removes_from_active:** Verify archived records excluded from retrieval
- **test_snapshot_generation:** Verify before/after snapshots contain correct fields
- **test_usage_tracking_updates:** Verify use_count, last_retrieved_at_step updated correctly

#### 4. Policy Tests
- **test_no_memory_returns_empty:** Verify No Memory returns []
- **test_full_memory_never_prunes:** Verify Full Memory never archives
- **test_random_prune_seeded_reproducible:** Verify same seed produces same pruning sequence
- **test_recency_prune_oldest_first:** Verify oldest by sequence_index archived first
- **test_type_aware_decay_formula:** Verify Anderson-Schooler formula implementation
- **test_cls_consolidation_schedule:** Verify consolidation triggers every 5 tasks

#### 5. Retrieval Tests
- **test_pure_cosine_scoring:** Verify no bonuses/penalties applied
- **test_token_budget_enforcement:** Verify memories dropped when exceeding budget
- **test_no_partial_items:** Verify entire items dropped, not truncated
- **test_tie_break_most_recent:** Verify recency used as secondary sort

#### 6. Type Classifier Tests
- **test_classifier_5_types_only:** Verify output is one of 5 enum values
- **test_classifier_temperature_zero:** Verify temperature override to 0
- **test_classifier_not_outcome_based:** Verify classification independent of pass/fail

#### 7. Reflection Tests
- **test_reflection_extracts_required_fields:** Verify issue_summary, patch_summary, etc. extracted
- **test_reflection_records_retrieved_ids:** Verify retrieved_memory_ids_used populated
- **test_reflection_fails_without_type:** Verify reflection fails if classifier unavailable

#### 8. Logging Tests
- **test_task_results_schema_complete:** Verify all required fields present
- **test_memory_events_schema_complete:** Verify all event types logged correctly
- **test_trajectory_no_private_thoughts:** Verify only action summaries logged
- **test_snapshots_at_every_boundary:** Verify before/after snapshots generated

#### 9. Configuration Tests
- **test_config_validation_required_keys:** Verify missing keys cause failure
- **test_config_validation_positive_values:** Verify zero/negative values rejected
- **test_config_merge_policy_overrides:** Verify policy-specific configs merged correctly

#### 10. Statistical Analysis Tests
- **test_wilcoxon_on_sequence_means:** Verify N=8 paired observations
- **test_holm_correction_5_contrasts:** Verify correction applied to pre-registered contrasts
- **test_bootstrap_bca_5000_iterations:** Verify bootstrap configuration
- **test_glmm_crossed_random_effects:** Verify (1|seq/seed) + (1|task_id) structure
- **test_pr_auc_not_accuracy:** Verify PR-AUC used for imbalanced classes

### Integration Testing Strategy

**Test end-to-end workflows with mocked external dependencies:**

#### 1. Smoke Test (3 tasks)
- Load 3 tasks from one sequence
- Execute with No Memory policy
- Verify eval_v3 Docker invocation
- Verify logging schemas
- **Gate:** >15% pass rate = GO for full experiment

#### 2. Pilot Test (12 runs)
- 2 sequences × 6 policies × 1 seed
- Verify all policies execute without crashes
- Verify memory snapshots generated
- Verify cost tracking accurate
- **Gate:** Calibrate top_k and max_context_tokens

#### 3. Policy Comparison Test
- Run same sequence with all 6 policies
- Verify retrieval scoring identical across policies
- Verify memory counts differ as expected
- Verify Full Memory never prunes

#### 4. Seed Reproducibility Test
- Run same sequence with same policy, different seeds
- Verify Random Prune produces different results
- Verify Type-Aware Decay produces identical results (deterministic)

### Manual Testing Strategy

#### 1. Type Classifier Audit (Week 3)
- Sample 150 memory records stratified across 5 types and 8 repos
- Compute per-type precision/recall, confusion matrix, overall accuracy
- If accuracy < 80%, merge confusing pairs or collapse to 3 types

#### 2. Memory Snapshot Inspection
- Manually inspect before/after snapshots for 5 tasks
- Verify pruning decisions match policy logic
- Verify importance_score calculations correct

#### 3. Cost Monitoring
- Daily cost reports during full experiment
- Alert if daily spend exceeds budget
- Verify cost attribution (agent vs embedding vs consolidation)

### Test Coverage Goals

- **Frozen invariants:** 100% coverage (all 26 decisions tested)
- **Core logic:** 80% line coverage for memory/, agents/, benchmark/
- **Integration:** All 6 policies × 2 sequences smoke tested before full run
- **Statistical:** All analysis functions tested with synthetic data

---

## Policy Specifications

### Policy 0: No Memory

**Purpose:** Baseline to measure effect of memory versus no memory

**Behavior:**
- Returns empty list for all retrieval requests
- Discards all memory write requests (returns success for API compatibility)
- Performs no maintenance operations

**Pseudocode:**
```python
class NoMemoryPolicy(MemoryPolicy):
    name = "no_memory"
    
    def retrieve(self, task, memory_store, top_k, token_budget):
        return []
    
    def write(self, memory_store, record):
        return  # discard
    
    def maintain(self, memory_store):
        return  # no-op
```

### Policy 1: Full Memory

**Purpose:** Baseline to measure effect of unbounded memory accumulation

**Behavior:**
- Uses shared_retrieve (identical scoring to all other policies)
- Stores all memory records without limit
- Never prunes or archives
- Ignores max_records and max_storage_tokens limits

**Pseudocode:**
```python
class FullMemoryPolicy(MemoryPolicy):
    name = "full_memory"
    
    def retrieve(self, task, memory_store, top_k, token_budget):
        return shared_retrieve(task, memory_store, top_k, token_budget)
    
    def write(self, memory_store, record):
        memory_store.add(record)
    
    def maintain(self, memory_store):
        return  # never prune
```

**Note:** Full Memory means "store everything; retrieve top-k under same budget." It does NOT mean "append everything into prompt" (that would confound memory policy with context length).

### Policy 2: Random Prune

**Purpose:** Isolate volume effect (improvement from "less memory" alone, not "smarter memory")

**Behavior:**
- Uses shared_retrieve (identical scoring)
- Stores all incoming memory records
- When active count exceeds max_records, randomly selects victim and archives
- Uses seeded RNG for reproducibility
- Repeats until active count <= max_records

**Pseudocode:**
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

### Policy 3: Recency Prune

**Purpose:** Test whether recency alone is sufficient for effective memory management

**Behavior:**
- Uses shared_retrieve (identical scoring)
- Stores all incoming memory records
- When active count exceeds max_records, archives oldest memories by sequence_index
- Retains max_records most recent memories

**Pseudocode:**
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
            reverse=True  # newest first
        )
        for record in active[self.max_records:]:
            memory_store.archive(record.memory_id, reason="recency_prune")
```

### Policy 4: Type-Aware Decay

**Purpose:** Test whether semantic prioritization outperforms random pruning

**Behavior:**
- Uses shared_retrieve (identical scoring)
- Stores all incoming memory records
- When active count exceeds max_records, computes importance_score using Anderson-Schooler power-law with type-specific parameters
- Archives lowest-scoring memories until active count <= max_records

**Type Parameters (LOCKED):**
```python
TYPE_PARAMS = {
    #               base_value   decay_d   tier
    "architectural":   (1.0,       0.05,   "Sacred"),
    "api_change":      (0.8,       0.15,   "Critical"),
    "bug_fix":         (0.6,       0.25,   "Important"),
    "test_update":     (0.4,       0.35,   "Expendable"),
    "config":          (0.3,       0.40,   "Expendable"),
}
```

**Formula (LOCKED):**
```
importance_score = base_value(type) × age^{-decay_d(type)} × (1 + use_count)^{0.5}
```

Where:
- `age = current_step - sequence_index` (tasks since creation)
- `use_count = retrieval_count` (how many times retrieved)
- Exponent 0.5 for sub-linear frequency effect

**Rationale:**
1. Cognitive grounding: Anderson & Schooler (1991) showed P(need) ∝ t^{-d}
2. Calibration budget: Week-4 pilot can only calibrate 1-2 parameters per type
3. No causal contamination: Does NOT use success_after_retrieval_count (associated label, not causal)

**Pseudocode:**
```python
class TypeAwareDecayPolicy(MemoryPolicy):
    name = "type_aware_decay"
    FREQUENCY_EXPONENT = 0.5
    
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
            age = max(1, current_step - r.sequence_index)
            retrieval = r.use_count
            
            score = base * (age ** -decay) * ((1 + retrieval) ** self.FREQUENCY_EXPONENT)
            r.importance_score = score
            scored.append((score, r))
        
        scored.sort(key=lambda x: x[0])  # ascending: lowest first
        
        while memory_store.count_active() > self.max_records:
            _, victim = scored.pop(0)
            memory_store.archive(victim.memory_id, reason="type_aware_decay")
```

### Policy 5: CLS Consolidation

**Purpose:** Test whether abstractive compression improves performance-cost trade-off

**Behavior:**
- Uses shared_retrieve (identical scoring)
- Stores all incoming memory records
- Triggers consolidation every 5 tasks (fixed schedule, NOT on overflow)
- Selects candidates: >= 10 tasks old, not consolidated, not architectural
- Clusters by repo, files_touched, embedding similarity (min cluster size 3)
- Generates consolidated summary (max 350 tokens) for each cluster
- Archives source memories, stores consolidated record
- Falls back to Type-Aware Decay if still over budget

**Consolidation Parameters (LOCKED):**
- Interval: 5 tasks
- Min cluster size: 3
- Max summary tokens: 350
- Old memory threshold: 10 tasks
- Similarity threshold: 0.70
- Exclude type: architectural (Sacred tier)

**Consolidation Prompt:**
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

**Pseudocode:**
```python
class CLSConsolidationPolicy(MemoryPolicy):
    name = "cls_consolidation"
    CONSOLIDATION_INTERVAL = 5
    MIN_CLUSTER_SIZE = 3
    MAX_SUMMARY_TOKENS = 350
    OLD_MEMORY_THRESHOLD = 10
    
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
        
        current_step = max(r.sequence_index for r in memory_store.active_records())
        
        candidates = [
            r for r in memory_store.active_records()
            if (current_step - r.sequence_index) >= self.OLD_MEMORY_THRESHOLD
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
            log_consolidation_cost(summary_record.llm_cost)
            
            memory_store.add(summary_record)
            for r in cluster:
                memory_store.archive(
                    r.memory_id,
                    reason="cls_consolidated",
                    replacement_id=summary_record.memory_id,
                )
        
        # Fallback if still over budget
        if memory_store.count_active() > self.max_records:
            fallback = TypeAwareDecayPolicy(max_records=self.max_records)
            fallback.maintain(memory_store)
```

**Note:** Consolidated records carry `is_consolidated=True` and `source_memory_ids=[...]` for post-hoc tracing.

---

## Metrics and Evaluation

### Primary Metric: CL-F1

**Computation from accuracy matrix a_{i,j}:**

After completing a sequence, re-evaluate all previous tasks against final memory state to produce:
```
a_{i,j} = accuracy on task i when evaluated after task j was completed
```

From the matrix:
```python
# Plasticity (online accuracy)
CL_Plasticity = mean(a_{i,i})  # task i evaluated right when it arrived

# Forgetting per task
forgetting_i = max(a_{i, i..T}) - a_{i, T}

# Stability
CL_Stability = 1 - mean(forgetting_i)

# Primary metric
CL_F1 = 2 * CL_Plasticity * CL_Stability / (CL_Plasticity + CL_Stability)
```

**Validation:** System SHALL validate that minimum learning occurred before computing CL metrics (e.g., require CL_Plasticity > 0.1 or non-zero learning).

### Secondary Metrics

#### Correctness Metrics
- `resolved_rate = n_resolved / n_tasks` per (policy, sequence, seed)
- Per-repo resolved rate
- Sequence-window accuracy (rolling windows of 5 or 10 tasks)

#### Efficiency Metrics
- Total tokens (prompt + completion)
- Estimated cost USD
- Wall time seconds
- Tool calls per task
- Test runs per task
- Files read/modified per task
- Memory retrieval/write/pruning/consolidation latency

#### Derived Efficiency Metrics
- `cost_per_resolved_task = total_cost / max(n_resolved, 1)`
- `tokens_per_resolved_task = total_tokens / max(n_resolved, 1)`
- `tool_calls_per_resolved = total_tool_calls / max(n_resolved, 1)`
- `runtime_per_resolved = total_runtime / max(n_resolved, 1)`

#### Memory Growth Metrics
- Active memory count over time
- Active memory tokens over time
- Archived memory count
- Consolidated memory count
- `memory_growth_rate = active_memory_count_final / n_tasks`
- `pruning_ratio = archived / total_written`
- `consolidation_ratio = raw_archived_into_summaries / total_written`

#### Behavioral Metrics (H4 - Analysis Paralysis)
- Tool calls per task
- `syntax_error_rate = n_syntax_errors / n_tool_calls`
- Files read per task
- Test runs per task

**Hypothesis:** Under Full Memory, these rise as memory accumulates. Under forgetting policies, they stay bounded.

#### Retrieval Quality Metrics
For each retrieved memory:
- Same repo (bool)
- `file_overlap = |mem.files_touched ∩ task.files_touched| / |task.files_touched|`
- Same memory type (bool)
- Semantic similarity (float)
- Age (int)
- Outcome (enum)
- Retrieval rank (int)

Derived:
- `Relevant@k = (same_repo AND file_overlap > 0) / k`
- `Retrieval_noise@k = 1 - Relevant@k`
- `Stale_rate = (age > 20 AND file_overlap == 0 AND sim < 0.5) / k`

---

## Statistical Analysis

### Philosophy

With N=8 independent sequences, traditional NHST has limited power. We follow estimation-over-testing paradigm: **effect sizes + confidence intervals are primary evidence**; p-values supplement but do not gate conclusions.

### Primary Analysis: Sequence-Level

**Unit:** Sequence-level means (average across 3 seeds per sequence)
**N:** 8 paired observations per condition pair

**Effect Size (Primary Evidence):**
- Rank-biserial r_rb
- Median paired difference ± bootstrap BCa 95% CI (5000 iterations)

**Interpretation:** |r_rb| ≈ 0.1 small, ≈ 0.3 medium, ≈ 0.5 large

**Planned Contrasts (Pre-Registered):**
Five contrasts, each pruning policy vs Full Memory:
1. Random Prune vs Full Memory (volume effect)
2. Recency Prune vs Full Memory (temporal heuristic)
3. Type-Aware Decay vs Full Memory (semantic pruning)
4. CLS Consolidation vs Full Memory (abstractive compression)
5. No Memory vs Full Memory (memory value at all)

**Test:** Paired Wilcoxon signed-rank on N=8 sequence means
**Correction:** Holm on 5 planned contrasts
**Remaining 10 pairwise comparisons:** Reported as exploratory with uncorrected p-values

### Task-Level Analysis: GLMM (Exploratory)

```
task_success ~ condition + task_difficulty + sequence_position + (1|repo_sequence/seed) + (1|task_id)
```

- **Family:** Binomial, **Link:** logit
- **Python:** `statsmodels.BinomialBayesMixedGLM`
- **R:** `lme4::glmer(family=binomial)`
- `(1|task_id)` accounts for inherent task difficulty variation (crossed random effect)
- `task_difficulty` sourced from SWE-Bench metadata (NOT derived from outcomes)

**Sensitivity Check:** Run with and without `(1|task_id)` if convergence issues

### Efficiency Comparisons

For non-normal metrics (tokens, runtime, tool calls):
- Wilcoxon signed-rank on sequence-level means
- Rank-biserial r_rb effect size
- 95% bootstrap BCa CI for median paired difference
- Report absolute + relative changes

### Reporting Template

```
Type-Aware Decay vs Full Memory:
  CL-F1:        Δ = +0.018  (r_rb = 0.43, 95% BCa CI [-0.005, +0.038], Holm-p = 0.078)
  Total tokens: Δ = -31%    (r_rb = -0.72, 95% BCa CI [-38%, -23%],   Holm-p = 0.012)
  Tool calls:   Δ = -18%    (r_rb = -0.51, 95% BCa CI [-26%, -9%],    Holm-p = 0.039)
  
  Conclusion: Type-Aware Decay matches Full Memory on correctness (CI includes zero)
  while substantially reducing token cost. Pareto-favorable.
```

---

## Helpful/Harmful Memory Prediction

### Unit of Analysis

```
(task, retrieved_memory)
```

Each row contains:
- Task identifiers: task_id, policy, seed, sequence
- Memory features: semantic_similarity, retrieval_rank, memory_age, memory_type, memory_outcome, same_repo, file_overlap, token_length, use_count, is_consolidated
- Task outcome: task_resolved
- Label: helpful | harmful | neutral

### Labeling Strategy

**Tier 1: Automatic Weak Labels (All Rows)**
```
helpful  if  task_resolved == 1  AND  file_overlap > 0  AND  memory_outcome == "pass"
harmful  if  task_resolved == 0  AND  semantic_similarity > 0.7  AND  memory_outcome == "fail"
neutral  otherwise
```

**Tier 2: Manual Labels (100-200 Stratified Sample)**
Sample stratified across policies, memory types, and weak-label categories. Two annotators if possible.

```
helpful: memory directly points to useful file/function/test/strategy that agent used
harmful: memory encourages wrong file, wrong assumption, stale patch, or failed strategy
neutral: memory was not obviously used or relevant
```

Inter-annotator agreement: Cohen's kappa

**Tier 3: Matched-Contrast Case Studies**
Pick task pairs where memory X was helpful in task A but harmful in task B. These support causal claims.

### Derived Feature (VIF Mitigation)

```
retrieval_rate = use_count / (memory_age + 1)
```

Pre-flight VIF check: if `VIF(age) > 5` OR `VIF(use_count) > 5`, drop both raw features and keep only `retrieval_rate`.

### Model

- Logistic regression (interpretable)
- Gradient Boosted Machine (nonlinear)

Both models trained. Compare feature importance rankings.

### Evaluation

**5-fold cross-validation, stratified by sequence**

**Metric:** PR-AUC (Precision-Recall Area Under Curve)
- NOT accuracy (class imbalance ~20% positive)
- NOT ROC-AUC (optimistic for imbalanced classes)

**Class Weights:** Applied to handle imbalanced positive class

**Feature Importance:** Report top features from both models

---

## Pareto Frontier Analysis

### Objective

Plot policies on CL-F1 versus cost Pareto frontier to identify which policies achieve best performance-cost trade-off.

### Cost Computation

```
total_cost = agent_llm_cost + embedding_cost + consolidation_cost
```

Per (policy, sequence, seed) run.

### Pareto Frontier Definition

Set of policies where no other policy achieves both:
- Higher CL-F1 AND
- Lower cost

### Visualization

- X-axis: Total cost (USD)
- Y-axis: CL-F1
- Each point: One (policy, sequence, seed) run
- Annotate each policy with name and confidence ellipse
- Highlight Pareto frontier

### Expected Outcomes

**H1 (Win-Win):** If Full Memory doesn't degrade → forgetting validated as zero-cost optimization
**H1 (Performance):** If Full Memory degrades → forgetting validated as performance improvement
**H3 (CLS Cost):** CLS Consolidation provides similar performance but higher cost → fails Pareto efficiency test

---

## Failure Analysis Protocol

### Failure Categories

When a task fails, log failure category:
- `timeout`: Step count exceeded 20 or wall time exceeded 20 minutes
- `test_failure`: Patch generated but tests failed
- `syntax_error`: Patch contains syntax errors
- `tool_error`: Tool execution failed (file not found, command error, etc.)
- `unknown`: Other failures

### Logging Requirements

When both error message and stack trace available:
- Log final error message
- Log stack trace

### Analysis Metrics

- Per-policy failure rates by category
- Identify tasks where Full Memory fails but pruning policy succeeds (boundary condition for H5)
- Compute failure rate trends over sequence position

### Boundary Condition Analysis (H5)

**Hypothesis:** Pruning can harm performance when it removes rare but critical repository-specific memories.

**Test:** Identify tasks where:
- Full Memory succeeds
- At least one pruning policy fails
- Pruning policy archived a memory that Full Memory used

**Analysis:** Manual inspection of these cases to understand when forgetting is unsafe.

---

## Configuration Management

### Base Configuration (base.yaml)

Located at: `configs/base.yaml`

Contains:
- Experiment metadata (name, benchmark, sequence_mode)
- Agent configuration (models, temperature, execution limits)
- Memory configuration (top_k, max_context_tokens, max_records, embedding limits)
- Retrieval configuration (scoring, tie_break, overflow handling)
- Execution configuration (Docker workers, VPS specs)
- Logging configuration (what to save)
- Evaluation configuration (harness, metrics, bootstrap settings)
- Statistical configuration (tests, contrasts, effect sizes)

### Policy-Specific Overrides

Located at: `configs/policies/{policy_name}.yaml`

Each policy can override:
- `max_records`
- `seeds` (for Random Prune)
- Type-specific parameters (for Type-Aware Decay)
- Consolidation parameters (for CLS Consolidation)

### Configuration Loading

```python
def load_config(policy_name: str) -> RunConfig:
    base = yaml.load("configs/base.yaml")
    policy_override = yaml.load(f"configs/policies/{policy_name}.yaml")
    merged = deep_merge(base, policy_override)
    validate_config(merged)
    return RunConfig(**merged)
```

### Configuration Validation

**Required Keys:** All keys in base.yaml must be present
**Positive Values:** max_context_tokens, max_records, max_steps_per_task must be > 0
**Enum Values:** policy names, memory types, event types must match allowed values
**Seed Values:** Must be integers >= 0

**Failure Mode:** Fail fast before starting run if validation fails

### Calibration Windows

**Two parameters are TBD until calibration:**

1. **top_k and max_context_tokens** — Confirmed at end of Spike Week (Friday gate)
   - Defaults: top_k=5, max_context_tokens=2000
   - If pilot shows different optima, change once, then lock

2. **Type-Aware Decay decay_d per type** — Confirmed at end of Week 4 pilot
   - Initial values in TYPE_PARAMS
   - One-parameter-per-type calibration only (no grid search)

**After Week 4:** All hyperparameters frozen for full 144 runs. Any later change requires re-running everything.

---

## Cost Monitoring

### Per-Task Cost Tracking

Log for each task:
- `prompt_tokens`: Tokens in prompt
- `completion_tokens`: Tokens in completion
- `total_tokens`: Sum of prompt + completion
- `estimated_cost_usd`: Estimated cost based on model pricing
- `task_api_cost`: Total API cost for task (agent + reflection + classifier)
- `consolidation_llm_cost`: Cost of consolidation LLM calls (CLS policy only)

### Cost Attribution

- **Agent cost:** Main agent LLM calls during task solving
- **Embedding cost:** Embedding API calls for memory records
- **Consolidation cost:** LLM calls for CLS consolidation summaries
- **Classifier cost:** Type classifier LLM calls

### Cost Aggregation

Per run:
```python
total_cost = sum(task_api_cost) + sum(embedding_cost) + sum(consolidation_cost)
```

Write to: `runs/{run_id}/cost_summary.json`

### Daily Cost Reports

Generate daily cost report across all active runs:
```python
def generate_daily_cost_report(date: str) -> dict:
    runs = get_runs_active_on_date(date)
    return {
        "date": date,
        "total_cost_usd": sum(r.total_cost for r in runs),
        "by_policy": group_by_policy(runs),
        "by_sequence": group_by_sequence(runs),
        "cumulative_cost_usd": get_cumulative_cost_to_date(date),
    }
```

### Budget Alerts

- Alert if daily spend exceeds budget threshold
- Alert if projected total cost exceeds experiment budget
- Alert if any single run exceeds expected cost by >50%

---

## Experiment Execution Plan

### Experiment Matrix (LOCKED - 144 Runs)

```
6 policies × 8 sequences × 3 seeds = 144 runs
```

| Component | Value |
|---|---|
| Policies | No Memory, Full Memory, Random Prune, Recency Prune, Type-Aware Decay, CLS Consolidation |
| Sequences | All 8 official SWE-Bench-CL sequences |
| Seeds | 1, 2, 3 (for ALL 6 conditions) |
| Model | GPT-5.4 |
| Temperature | 0 |

### Execution Phases

**Phase 1: Spike Week (Week 1)**
- Day 1: Smoke test (3 tasks, >15% pass = GO)
- Days 2-4: Pilot (2 sequences × 6 policies × 1 seed = 12 runs)
- Day 5: Calibrate top_k and max_context_tokens, lock for main experiment

**Phase 2: Type Classifier Audit (Week 3)**
- Sample 150 memory records stratified across 5 types and 8 repos
- Compute per-type precision/recall, confusion matrix, overall accuracy
- If accuracy < 80%, merge confusing pairs or collapse to 3 types

**Phase 3: Week 4 Pilot**
- Run 12 runs to calibrate Type-Aware Decay decay_d parameters
- Lock decay_d values for main experiment

**Phase 4: Main Experiment (Weeks 5-6)**
- Execute all 144 runs
- Monitor via wandb + tmux
- Daily cost reports
- Pause if budget exceeded

**Phase 5: Multi-Model Validation (Week 7)**
- Top-3 conditions × 4 sequences × 1 seed = 12 runs
- Model: Claude Haiku or GPT-4o-mini
- Tests whether forgetting helps weaker models MORE than frontier model

### Docker Concurrency Management

**Initial Setting:** `max_workers=4`
**Monitoring:** `iostat` for disk I/O saturation
**Scaling:** Increase gradually if resources allow
**Constraint:** x86_64 VPS with 32GB RAM, 250GB disk, 8 cores

### Run Monitoring

- **wandb:** Track metrics, costs, progress
- **tmux:** Persistent sessions for long-running experiments
- **Logging:** All runs write to `runs/{run_id}/` with structured logs
- **Snapshots:** Memory snapshots at every task boundary for post-hoc analysis

---

## Implementation Priorities

### Must-Have (Week 1-2)

1. Dataset loader with all 8 sequences
2. Memory store (SQLite + FAISS)
3. Shared retrieval function (pure cosine)
4. All 6 policies implemented
5. Type classifier (Structured Outputs, temp=0)
6. Reflection step
7. Agent execution loop with 20-step limit
8. Logging schemas (task_results, memory_events, trajectories, snapshots)
9. eval_v3 Docker wrapper
10. Smoke test (3 tasks)

### Should-Have (Week 3-4)

1. Type classifier audit protocol
2. CL metrics calculator (a_{i,j} matrix)
3. Configuration management (base + policy overrides)
4. Cost tracking and daily reports
5. Pilot execution (12 runs)
6. Calibration of top_k, max_context_tokens, decay_d

### Nice-to-Have (Week 5+)

1. Statistical analysis scripts (Wilcoxon, Holm, bootstrap)
2. GLMM task-level analysis
3. Helpful/harmful prediction (PR-AUC + VIF)
4. Pareto frontier visualization
5. Failure analysis reports
6. Multi-model validation runs

### Out of Scope (Cut if Time/Budget Constrained)

1. Cross-repo retrieval (optional ablation)
2. Memory budget ablations (max_records ∈ {25, 50, 100})
3. Top-k ablations (∈ {1, 3, 5})
4. Success-only memory ablation
5. Append-all stress test
6. SWE-ContextBench integration
7. MEMTRACK cross-validation

---

## Risk Mitigation

### Risk 1: Docker Eval Harness Instability

**Mitigation:**
- Smoke test on Day 1 (>15% pass = GO)
- Monitor Docker container failures
- Graceful error handling and logging
- No automatic retries (preserves experimental integrity)

### Risk 2: Type Classifier Low Accuracy

**Mitigation:**
- Manual audit in Week 3 (150 samples)
- Decision rules: ≥80% proceed, 70-79% note limitation, <70% collapse to 3 types, <50% abandon type-aware policy
- Audit BEFORE full 144 runs

### Risk 3: Budget Overrun

**Mitigation:**
- Daily cost reports
- Budget alerts
- Pilot runs to estimate costs
- Prioritize core 144 runs over optional ablations

### Risk 4: Insufficient Statistical Power

**Mitigation:**
- Effect sizes + confidence intervals as primary evidence (not p-values)
- Pre-registered contrasts (5 planned, 10 exploratory)
- Honest reporting of power limitations
- Estimation-over-testing paradigm

### Risk 5: Memory Store Corruption

**Mitigation:**
- Append-only logs (records.jsonl, archive.jsonl)
- Memory snapshots at every task boundary
- Separate SQLite + FAISS files per run
- No shared state across runs

### Risk 6: Embedding Truncation

**Mitigation:**
- Pre-flight check: assert embedding_text < 7500 tokens
- Truncate patch_summary from end if exceeded
- Log truncation events
- Never embed raw trajectories (would silently truncate)

### Risk 7: Repository Checkout Failures

**Mitigation:**
- Fail entire sequence run immediately (don't continue with corrupted state)
- Log failure reason, task_id, sequence_index
- Clean checkout per task (no state leakage)

### Risk 8: Configuration Drift

**Mitigation:**
- Validate configuration before starting run
- Log full merged configuration at run start
- Lock hyperparameters after Week 4 calibration
- Any change requires re-running everything

---

## Acceptance Criteria Summary

This design satisfies all 30 requirements from the requirements document:

**Req 1-5:** Benchmark data loading, memory persistence, record structure, embedding payload, type classification
**Req 6-7:** Identical retrieval across policies, lost-in-the-middle mitigation
**Req 8-13:** Six memory policies (No Memory, Full Memory, Random Prune, Recency Prune, Type-Aware Decay, CLS Consolidation)
**Req 14-15:** Agent execution limits, reflection and memory writing
**Req 16-18:** Experiment matrix (144 runs), evaluation harness, logging schema compliance
**Req 19-22:** CL metrics, sequence-level statistics, bootstrap CIs, task-level GLMM
**Req 23-24:** Helpful/harmful prediction, Pareto frontier analysis
**Req 25-27:** Memory snapshots, configuration management, cost monitoring
**Req 28-29:** Failure analysis, behavioral metrics
**Req 30:** Calibration window support

All 26 frozen decisions from THESIS_FINAL_v5.md §0.1 are preserved.

---

## Appendix: Key Formulas

### Type-Aware Decay Importance Score

```
importance_score = base_value(type) × age^{-decay_d(type)} × (1 + use_count)^{0.5}
```

Where:
- `age = current_step - sequence_index` (tasks since creation)
- `use_count = retrieval_count` (how many times retrieved)
- Type parameters (LOCKED):
  - architectural: base=1.0, decay=0.05
  - api_change: base=0.8, decay=0.15
  - bug_fix: base=0.6, decay=0.25
  - test_update: base=0.4, decay=0.35
  - config: base=0.3, decay=0.40

### CL-F1 Computation

```python
# Plasticity (online accuracy)
CL_Plasticity = mean(a_{i,i})

# Forgetting per task
forgetting_i = max(a_{i, i..T}) - a_{i, T}

# Stability
CL_Stability = 1 - mean(forgetting_i)

# CL-F1
CL_F1 = 2 * CL_Plasticity * CL_Stability / (CL_Plasticity + CL_Stability)
```

### Rank-Biserial Effect Size

```python
r_rb = (2 * W) / (n * (n + 1)) - 1
```

Where W is the Wilcoxon signed-rank statistic, n is the number of pairs.

Interpretation: |r_rb| ≈ 0.1 small, ≈ 0.3 medium, ≈ 0.5 large

### Embedding Payload Construction

```python
embedding_text = f"""
Issue: {issue_summary}
Final Error: {failure_summary or '(none — task succeeded)'}
Final Diff: {patch_summary}
""".strip()

assert count_tokens(embedding_text) < 7500, "Embedding too large"
```

### Retrieval Token Budget Enforcement

```python
def trim_to_token_budget(scored_memories, token_budget):
    result = []
    total_tokens = 0
    for score, memory in scored_memories:
        if total_tokens + memory.token_length <= token_budget:
            result.append((score, memory))
            total_tokens += memory.token_length
        else:
            break  # drop remaining (lowest-scoring)
    return result
```

---

## Appendix: Directory Structure

```
/Users/hieudinh/Documents/02-Areas/subject/Internship/
├── src/
│   ├── agents/
│   │   ├── coding_agent.py
│   │   ├── langgraph_agent.py
│   │   ├── prompts.py
│   │   └── tools.py
│   ├── memory/
│   │   ├── record.py
│   │   ├── store.py
│   │   ├── retriever.py
│   │   ├── reflection.py
│   │   ├── classifier.py
│   │   ├── summarizer.py
│   │   ├── consolidation.py
│   │   └── policies/
│   │       ├── base.py
│   │       ├── no_memory.py
│   │       ├── full_memory.py
│   │       ├── random_prune.py
│   │       ├── recency_prune.py
│   │       ├── type_aware_decay.py
│   │       └── cls_consolidation.py
│   ├── benchmark/
│   │   ├── swebenchcl_loader.py
│   │   ├── task_env.py
│   │   ├── evaluator.py
│   │   ├── sequence_runner.py
│   │   └── cl_metrics.py
│   ├── metrics/
│   │   ├── correctness.py
│   │   ├── continual_learning.py
│   │   ├── efficiency.py
│   │   ├── retrieval_quality.py
│   │   ├── pareto.py
│   │   └── behavioral.py
│   └── analysis/
│       ├── aggregate_results.py
│       ├── statistical_tests.py
│       ├── glmm.py
│       ├── feature_importance.py
│       └── plots.py
├── configs/
│   ├── base.yaml
│   └── policies/
│       ├── no_memory.yaml
│       ├── full_memory.yaml
│       ├── random_prune.yaml
│       ├── recency_prune.yaml
│       ├── type_aware_decay.yaml
│       └── cls_consolidation.yaml
├── runs/  (gitignored)
│   └── {run_id}/
│       ├── task_results.jsonl
│       ├── memory_events.jsonl
│       ├── trajectories/
│       │   └── {task_id}.json
│       └── memory/
│           ├── records.jsonl
│           ├── metadata.sqlite
│           ├── faiss.index
│           ├── archive.jsonl
│           └── snapshots/
│               ├── before_task_{n}.json
│               └── after_task_{n}.json
├── results/
│   ├── raw/
│   ├── aggregated/
│   ├── plots/
│   └── tables/
├── logs/  (gitignored)
├── tests/
└── .kiro/
    └── specs/
        └── memory-pruning-research-system/
            ├── .config.kiro
            ├── requirements.md
            └── design.md  (this document)
```

---

**End of Design Document**
