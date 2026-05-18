# Implementation Plan: Memory Pruning Research System

## Overview

This implementation plan breaks down the comprehensive memory pruning research system into discrete, testable tasks. The system evaluates 6 memory policies across 8 SWE-Bench-CL sequences with 3 seeds each (144 total runs), measuring continual learning performance versus operational cost.

**Core Principle:** The agent's codebase state resets per task; its external memory persists across tasks.

**Implementation Language:** Python 3.11+

**Key Constraints:**
- All 26 frozen decisions from THESIS_FINAL_v5.md must be preserved
- Pure cosine similarity retrieval (identical across all 6 policies)
- Max 20 steps per task with hard force-fail
- Embedding payload < 7500 tokens (Issue + Error + Diff only)
- Best memory item injected LAST (Lost-in-the-Middle mitigation)
- Temperature=0 for all LLM calls (reproducibility)

---

## Tasks

### 1. Project Setup and Infrastructure

- [x] 1.1 Initialize project structure and dependencies
  - Create directory structure: `src/`, `tests/`, `configs/`, `runs/`, `results/`, `logs/`
  - Set up Python 3.11+ virtual environment
  - Create `pyproject.toml` with dependencies: LangGraph, FAISS, SQLite, OpenAI SDK, pytest, ruff, mypy
  - Create `.gitignore` for `runs/`, `results/raw/`, `*.faiss`, `*.sqlite`, wandb cache
  - Create `Makefile` with placeholder commands: `setup`, `verify-env`, `smoke`, `pilot`, `run-all`, `lint`, `test`
  - _Requirements: 26_

- [x] 1.2 Create base configuration system
  - Implement `configs/base.yaml` with all required parameters from THESIS_FINAL_v5.md §13
  - Create configuration loader that merges base + policy-specific overrides
  - Add validation for required keys and positive value constraints
  - Implement configuration freezing after calibration window
  - _Requirements: 26_

- [ ]* 1.3 Write unit tests for configuration system
  - Test required key validation (test_config_validation_required_keys)
  - Test positive value constraints (test_config_validation_positive_values)
  - Test policy override merging (test_config_merge_policy_overrides)
  - _Requirements: 26_


### 2. Data Models and Core Interfaces

- [x] 2.1 Implement MemoryRecord dataclass
  - Create `src/memory/record.py` with complete MemoryRecord dataclass
  - Include all fields: identity, type/outcome, content, metadata, embedding, usage tracking, lifecycle
  - Add validation for orthogonal type/outcome axes
  - Implement serialization/deserialization methods
  - _Requirements: 3, 5_

- [x] 2.2 Implement Task and Sequence dataclasses
  - Create `src/benchmark/models.py` with Task and Sequence dataclasses
  - Include all required fields: task_id, repo, base_commit, issue_text, test_patch, gold_patch, created_at, sequence_index, difficulty_label
  - Add validation for minimum 15 tasks per sequence
  - _Requirements: 1_

- [x] 2.3 Define MemoryPolicy abstract base class
  - Create `src/memory/policies/base.py` with abstract MemoryPolicy interface
  - Define abstract methods: retrieve(), write(), maintain()
  - Add policy name attribute
  - Document that retrieve() MUST use shared_retrieve for all policies except No Memory
  - _Requirements: 8, 9, 10, 11, 12, 13_

- [x] 2.4 Define MemoryStore interface
  - Create `src/memory/store.py` with MemoryStore class skeleton
  - Define methods: add(), filter(), search(), archive(), active_records(), count_active(), snapshot(), stats()
  - Document two-layer storage: SQLite (metadata) + FAISS (vectors)
  - _Requirements: 2_


### 3. Benchmark Data Loading

- [x] 3.1 Implement SWE-Bench-CL dataset loader
  - Create `src/benchmark/swebenchcl_loader.py`
  - Load all 8 official sequences from `SWE-Bench-CL-Curriculum.json`
  - Preserve chronological ordering within each sequence
  - Extract all required task fields
  - Validate minimum 15 tasks per sequence
  - _Requirements: 1_

- [ ]* 3.2 Write unit tests for dataset loader
  - Test all 8 sequences loaded (test_load_all_8_sequences)
  - Test chronological order preserved (test_preserve_chronological_order)
  - Test minimum 15 tasks validation (test_minimum_15_tasks_per_sequence)
  - Test all required fields extracted (test_extract_all_required_fields)
  - _Requirements: 1_


### 4. Memory Store Implementation

- [x] 4.1 Implement SQLite metadata storage
  - Create SQLite schema for memory records with all fields from MemoryRecord
  - Implement add(), filter(), archive() methods for metadata
  - Add usage tracking updates: use_count, last_retrieved_at_step, success/failure counts
  - Implement snapshot generation for before/after task boundaries
  - _Requirements: 2, 3, 25_

- [x] 4.2 Implement FAISS vector index
  - Initialize FAISS index with L2-normalized vectors
  - Implement embedding storage and cosine similarity search
  - Add index rebuilding on archive operations
  - Handle embedding vector ID mapping to memory records
  - _Requirements: 2, 6_

- [x] 4.3 Implement embedding payload construction
  - Create embedding_text from Issue + Final Error + Final Diff only
  - Add token counting and 7500 token limit validation
  - Implement patch_summary truncation from end if limit exceeded
  - Log truncation events with original and final sizes
  - _Requirements: 4_

- [ ]* 4.4 Write unit tests for memory store
  - Test filter by repo and archived status (test_filter_by_repo_and_archived)
  - Test archive removes from active (test_archive_removes_from_active)
  - Test snapshot generation (test_snapshot_generation)
  - Test usage tracking updates (test_usage_tracking_updates)
  - Test embedding size assertion (test_embedding_size_assert)
  - _Requirements: 2, 3, 4, 25_


### 5. Memory Retrieval System

- [x] 5.1 Implement shared retrieval function
  - Create `src/memory/retriever.py` with shared_retrieve() function
  - Build query from task.repo + task.issue_text
  - Embed query and perform FAISS cosine similarity search
  - Filter candidates by same repo and non-archived status
  - Apply pure cosine scoring with NO bonuses or penalties
  - Return top-k memories sorted ascending (best LAST for injection)
  - _Requirements: 6, 7_

- [x] 5.2 Implement token budget enforcement
  - Drop lowest-scoring memories until within max_context_tokens budget
  - Guarantee final result fits within budget (no partial items)
  - Use recency as tie-breaker for equal similarity scores
  - _Requirements: 6, 7_

- [ ]* 5.3 Write unit tests for retrieval
  - Test pure cosine scoring with no bonuses (test_pure_cosine_scoring, test_no_bonuses_in_retrieval)
  - Test token budget enforcement (test_token_budget_enforcement)
  - Test no partial items (test_no_partial_items)
  - Test tie-break by recency (test_tie_break_most_recent)
  - Test injection order best last (test_injection_order_best_last)
  - _Requirements: 6, 7_


### 6. Type Classification System

- [x] 6.1 Implement 5-type memory classifier
  - Create `src/memory/classifier.py` with type classification function
  - Use Structured Outputs or Tool Use with 1-of-5 enum
  - Enforce temperature=0 for deterministic classification
  - Classify into: architectural, api_change, bug_fix, test_update, config
  - Base classification on content only (NOT outcome)
  - _Requirements: 5_

- [x] 6.2 Add classifier error handling
  - Fail reflection step entirely if classifier unavailable or fails
  - Log classifier errors with task_id and retry count
  - Do not proceed with untyped memory records
  - _Requirements: 5, 15_

- [ ]* 6.3 Write unit tests for type classifier
  - Test 5 types only output (test_classifier_5_types_only)
  - Test temperature zero enforcement (test_classifier_temperature_zero, test_type_classifier_deterministic)
  - Test classification not outcome-based (test_classifier_not_outcome_based)
  - _Requirements: 5_


### 7. Memory Policies Implementation

- [x] 7.1 Implement No Memory policy
  - Create `src/memory/policies/no_memory.py`
  - Return empty list for all retrieval requests
  - Discard all write requests (return success for API compatibility)
  - No maintenance operations
  - _Requirements: 8_

- [ ] 7.2 Implement Full Memory policy
  - Create `src/memory/policies/full_memory.py`
  - Use shared_retrieve with identical scoring
  - Store all records without limit
  - Never prune or archive (ignore max_records and max_storage_tokens)
  - _Requirements: 9_

- [ ] 7.3 Implement Random Prune policy
  - Create `src/memory/policies/random_prune.py`
  - Use shared_retrieve with identical scoring
  - Store all incoming records
  - Randomly select and archive victims when exceeding max_records
  - Use seeded RNG for reproducibility
  - _Requirements: 10_

- [ ] 7.4 Implement Recency Prune policy
  - Create `src/memory/policies/recency_prune.py`
  - Use shared_retrieve with identical scoring
  - Store all incoming records
  - Archive oldest memories by sequence_index when exceeding max_records
  - _Requirements: 11_

- [ ] 7.5 Implement Type-Aware Decay policy
  - Create `src/memory/policies/type_aware_decay.py`
  - Use shared_retrieve with identical scoring
  - Implement Anderson-Schooler power-law formula: `base_value(type) × age^(-decay_d(type)) × (1+use_count)^0.5`
  - Use locked type-specific parameters from THESIS_FINAL_v5.md
  - Archive lowest-scoring memories when exceeding max_records
  - _Requirements: 12_

- [ ] 7.6 Implement CLS Consolidation policy
  - Create `src/memory/policies/cls_consolidation.py`
  - Use shared_retrieve with identical scoring
  - Trigger consolidation every 5 tasks on fixed schedule
  - Select candidates: ≥10 tasks old, not consolidated, not architectural
  - Cluster by repo, files_touched, and embedding similarity (min cluster size 3)
  - Generate consolidated summaries with max 350 tokens
  - Archive source memories and store consolidated record
  - Fall back to Type-Aware Decay if still over budget
  - _Requirements: 13_

- [ ]* 7.7 Write unit tests for all policies
  - Test No Memory returns empty (test_no_memory_returns_empty)
  - Test Full Memory never prunes (test_full_memory_never_prunes)
  - Test Random Prune seeded reproducibility (test_random_prune_seeded_reproducible)
  - Test Recency Prune oldest first (test_recency_prune_oldest_first)
  - Test Type-Aware Decay formula (test_type_aware_decay_formula)
  - Test CLS consolidation schedule (test_cls_consolidation_schedule)
  - Test retrieval identical across policies (test_retrieval_identical_across_policies)
  - _Requirements: 8, 9, 10, 11, 12, 13_


### 8. Reflection and Memory Writing

- [ ] 8.1 Implement structured reflection step
  - Create `src/memory/reflection.py` with reflection function
  - Extract issue_summary, patch_summary, failure_summary, test_summary from task trajectory
  - Record files_touched, functions_touched, commands_run
  - Record retrieved_memory_ids_used (which memories were shown to agent)
  - Invoke type classifier to assign memory_type
  - Fail entirely if classifier unavailable
  - _Requirements: 15_

- [ ] 8.2 Implement memory writing workflow
  - Pass structured memory record to active policy's write() method
  - Ensure type assignment completes before writing
  - Update usage tracking for retrieved memories
  - _Requirements: 15_

- [ ]* 8.3 Write unit tests for reflection
  - Test required fields extraction (test_reflection_extracts_required_fields)
  - Test retrieved IDs recorded (test_reflection_records_retrieved_ids)
  - Test fails without type (test_reflection_fails_without_type)
  - _Requirements: 15_


### 9. Coding Agent Implementation

- [ ] 9.1 Implement LangGraph agent structure
  - Create `src/agents/langgraph_agent.py` with 12-node agent graph
  - Define nodes: task_setup, memory_retrieval, context_construction, planning, code_search, file_editing, test_execution, repair_loop, final_patch_generation, reflection, memory_write, memory_prune_or_consolidate
  - Implement state management for agent execution
  - _Requirements: 14_

- [ ] 9.2 Implement agent tools
  - Create `src/agents/tools.py` with all required tools
  - Implement: read_file, write_file, edit_file, search_code, list_files, run_command, run_tests, get_patch
  - Add tool call tracking for behavioral metrics
  - _Requirements: 14, 29_

- [ ] 9.3 Implement agent execution limits
  - Enforce max 20 steps per task with hard force-fail
  - Add max 80 tool calls, max 5 test runs, max 20 minutes wall time
  - Set temperature=0 for all LLM calls
  - Log timeout=true when limits exceeded
  - _Requirements: 14_

- [ ] 9.4 Implement prompt construction
  - Create `src/agents/prompts.py` with prompt templates
  - Build context with retrieved memories sorted ascending (best LAST)
  - Render each memory with memory_id, rank, similarity score, age, type
  - Include task body after memory block
  - _Requirements: 7, 14_

- [ ]* 9.5 Write unit tests for agent
  - Test max steps enforcement (test_max_steps_enforcement)
  - Test temperature zero (test_temperature_zero)
  - Test injection order best last (test_injection_order_best_last)
  - _Requirements: 7, 14_


### 10. Task Environment and Evaluation

- [ ] 10.1 Implement task environment manager
  - Create `src/benchmark/task_env.py` for Docker container lifecycle
  - Perform clean repository checkout per task
  - Handle uncommitted changes and file system errors (fail entire sequence)
  - Provide repository metadata to agent
  - _Requirements: 2, 17_

- [ ] 10.2 Implement eval_v3 Docker harness wrapper
  - Create `src/benchmark/evaluator.py` wrapping standard SWE-Bench eval_v3
  - Invoke Docker container for each generated patch
  - Return binary pass/fail result
  - Handle Docker failures gracefully and log as evaluation errors
  - Log execution time and errors
  - _Requirements: 17_

- [ ]* 10.3 Write integration tests for evaluation
  - Test Docker container invocation with mocked containers
  - Test failure handling
  - Test logging of evaluation results
  - _Requirements: 17_


### 11. Logging System

- [ ] 11.1 Implement task results logging
  - Create `src/logging/task_logger.py`
  - Write one row to task_results.jsonl per completed task
  - Include all required fields from schema: run_id, policy, seed, task_id, resolved, costs, metrics, retrieved memories, memory counts
  - Validate logged values match actual run parameters
  - _Requirements: 18, 27_

- [ ] 11.2 Implement memory events logging
  - Append to memory_events.jsonl for write, archive, consolidate operations
  - Include event_id, step, policy, event_type, memory_id, replacement_id, reason, metadata
  - _Requirements: 18_

- [ ] 11.3 Implement trajectory logging
  - Write trajectory JSON file per task with action-observation pairs
  - Include step, action, action_input, observation_summary, timestamp
  - Do NOT log agent's private chain-of-thought (action summaries only)
  - _Requirements: 18_

- [ ] 11.4 Implement memory snapshot logging
  - Generate before_task_n.json and after_task_n.json at every task boundary
  - Include step, boundary, active_records with memory_id and importance_score
  - Store in runs/{run_id}/memory/snapshots/
  - _Requirements: 25_

- [ ]* 11.5 Write unit tests for logging
  - Test task results schema complete (test_task_results_schema_complete)
  - Test memory events schema complete (test_memory_events_schema_complete)
  - Test trajectory no private thoughts (test_trajectory_no_private_thoughts)
  - Test snapshots at every boundary (test_snapshots_at_every_boundary)
  - _Requirements: 18, 25_


### 12. Sequence Runner and Experiment Orchestration

- [ ] 12.1 Implement sequence runner
  - Create `src/benchmark/sequence_runner.py`
  - Orchestrate execution of all tasks in a sequence
  - Maintain persistent memory store across task boundaries
  - Ensure clean repository checkout per task
  - Coordinate agent execution, evaluation, reflection, policy maintenance
  - Generate memory snapshots before/after each task
  - _Requirements: 2, 16_

- [ ] 12.2 Implement experiment matrix execution
  - Execute all 8 sequences for each of 6 policies
  - Execute 3 independent runs with different seeds per sequence-policy combination
  - Use seeds to initialize RNGs for Random Prune and stochastic components
  - Log policy name, sequence name, seed, run_id for each run
  - Validate logged values match actual run parameters
  - _Requirements: 16_

- [ ] 12.3 Implement cost tracking
  - Log token count and estimated cost for each LLM call (agent, classifier, consolidation)
  - Log token count and estimated cost for each embedding call
  - Aggregate costs per run and write cost_summary.json
  - Support daily cost report generation across all active runs
  - _Requirements: 27_

- [ ]* 12.4 Write integration tests for sequence runner
  - Test sequence execution with mocked components
  - Test memory persistence across tasks
  - Test seed reproducibility
  - Test cost tracking accuracy
  - _Requirements: 2, 16, 27_


### 13. Continual Learning Metrics

- [ ] 13.1 Implement accuracy matrix construction
  - Create `src/benchmark/cl_metrics.py`
  - Construct accuracy matrix a_{i,j} where a_{i,j} is accuracy on task i after training through task j
  - Validate minimum learning occurred before computing CL metrics
  - _Requirements: 19_

- [ ] 13.2 Implement CL-F1, Plasticity, and Stability
  - Compute Plasticity as mean of diagonal elements (accuracy on current task immediately after learning)
  - Compute Stability as mean of lower-triangular elements (accuracy on past tasks after learning new tasks)
  - Compute CL-F1 as 2 × (Plasticity × Stability) / (Plasticity + Stability)
  - Compute Forward Transfer and Backward Transfer
  - _Requirements: 19_

- [ ]* 13.3 Write unit tests for CL metrics
  - Test accuracy matrix construction with synthetic data
  - Test Plasticity, Stability, CL-F1 calculations
  - Test minimum learning validation
  - _Requirements: 19_


### 14. Statistical Analysis Implementation

- [ ] 14.1 Implement sequence-level aggregation
  - Create `src/analysis/aggregate_results.py`
  - Aggregate task-level results into sequence-level means for each policy-seed combination
  - Compute mean CL-F1 across 3 seeds for each sequence-policy pair (N=8 paired observations)
  - _Requirements: 20_

- [ ] 14.2 Implement Wilcoxon signed-rank test with Holm correction
  - Create `src/analysis/statistical_tests.py`
  - Apply Wilcoxon signed-rank test to paired sequence means
  - Test 5 pre-registered contrasts
  - Apply Holm correction to control family-wise error rate
  - Compute rank-biserial effect size r_rb for each contrast
  - _Requirements: 20_

- [ ] 14.3 Implement bootstrap confidence intervals
  - Perform 5000 bootstrap iterations for each effect size estimate
  - Use BCa (bias-corrected and accelerated) method
  - Report median paired difference and 95% BCa confidence interval for each contrast
  - _Requirements: 21_

- [ ] 14.4 Implement task-level GLMM
  - Create `src/analysis/glmm.py`
  - Fit binomial GLMM with logit link: `task_success ~ condition + difficulty + position + (1|seq/seed) + (1|task_id)`
  - Include crossed random effects for sequence/seed combination and task_id
  - Report fixed-effect coefficients, standard errors, z-values, p-values
  - _Requirements: 22_

- [ ]* 14.5 Write unit tests for statistical analysis
  - Test Wilcoxon on sequence means (test_wilcoxon_on_sequence_means)
  - Test Holm correction (test_holm_correction_5_contrasts)
  - Test bootstrap BCa (test_bootstrap_bca_5000_iterations)
  - Test GLMM crossed random effects (test_glmm_crossed_random_effects)
  - _Requirements: 20, 21, 22_


### 15. Feature Importance and Memory Prediction

- [ ] 15.1 Implement helpful/harmful memory prediction
  - Create `src/analysis/feature_importance.py`
  - Train classifier to predict success_after_retrieval (binary) from memory features
  - Use PR-AUC (Precision-Recall Area Under Curve) as evaluation metric
  - Check variance inflation factors (VIF) for all features and flag VIF > 5
  - Apply class weights to handle imbalanced positive class (~20%)
  - Do NOT use success_after_retrieval_count or failure_after_retrieval_count as causal predictors
  - _Requirements: 23_

- [ ]* 15.2 Write unit tests for feature importance
  - Test PR-AUC not accuracy (test_pr_auc_not_accuracy)
  - Test VIF check implementation
  - Test class weight handling
  - _Requirements: 23_


### 16. Pareto Analysis and Behavioral Metrics

- [ ] 16.1 Implement Pareto frontier analysis
  - Create `src/analysis/pareto.py`
  - Compute total cost for each policy-sequence-seed run (agent LLM + embedding + consolidation costs)
  - Plot each policy as point with CL-F1 on y-axis and total cost on x-axis
  - Identify Pareto frontier (policies where no other achieves both higher CL-F1 and lower cost)
  - Annotate policy points with names and confidence ellipses
  - _Requirements: 24_

- [ ] 16.2 Implement behavioral metrics
  - Create `src/metrics/behavioral.py`
  - Count tool calls per task for each policy
  - Count syntax errors per task for each policy
  - Compute mean tool-call count and syntax-error rate per policy across all tasks
  - Test whether Full Memory has significantly higher tool-call counts or syntax-error rates than pruning policies
  - _Requirements: 29_

- [ ]* 16.3 Write unit tests for Pareto and behavioral metrics
  - Test Pareto frontier identification with synthetic data
  - Test behavioral metric calculations
  - _Requirements: 24, 29_


### 17. Failure Analysis and Error Handling

- [ ] 17.1 Implement failure categorization
  - Create `src/analysis/failure_analysis.py`
  - Categorize task failures: timeout, test_failure, syntax_error, tool_error, unknown
  - Log both error message and stack trace when available
  - Compute per-policy failure rates by category
  - Identify tasks where Full Memory fails but pruning policy succeeds (boundary condition for H5)
  - _Requirements: 28_

- [ ] 17.2 Implement comprehensive error handling
  - Add repository checkout failure handling (fail entire sequence)
  - Add Docker container failure handling (log as evaluation error)
  - Add type classifier failure handling (fail reflection step)
  - Add embedding size violation handling (truncate patch_summary)
  - Add memory budget violation handling (drop lowest-scoring memories)
  - Add agent timeout handling (force-fail, log timeout=true)
  - Add configuration validation failure handling (fail fast)
  - _Requirements: 2, 4, 5, 6, 14, 15, 17, 26_

- [ ]* 17.3 Write unit tests for error handling
  - Test each error handling path with appropriate triggers
  - Test failure categorization logic
  - _Requirements: 28_


### 18. Visualization and Reporting

- [ ] 18.1 Implement plotting functions
  - Create `src/analysis/plots.py`
  - Generate CL-F1 vs cost Pareto frontier plot
  - Generate sequence-level performance comparison plots
  - Generate memory usage over time plots
  - Generate behavioral metrics comparison plots
  - Generate failure analysis plots
  - _Requirements: 24, 29_

- [ ] 18.2 Implement result tables
  - Generate statistical test results tables
  - Generate effect size tables with confidence intervals
  - Generate per-policy performance summary tables
  - Generate cost breakdown tables
  - _Requirements: 20, 21, 27_


### 19. Calibration and Pilot Testing

- [ ] 19.1 Implement pilot mode support
  - Add pilot mode configuration for 2 sequences × 6 policies × 1 seed = 12 runs
  - Log retrieval quality metrics (precision@k, recall@k) during pilot runs
  - Support updating top_k and max_context_tokens after pilot analysis
  - Support updating Type-Aware Decay decay_d parameters per type after Week 4 pilot
  - Lock all hyperparameters after calibration
  - _Requirements: 30_

- [ ] 19.2 Implement smoke test (3 tasks)
  - Load 3 tasks from one sequence
  - Execute with No Memory policy
  - Verify eval_v3 Docker invocation
  - Verify logging schemas
  - Gate: >15% pass rate = GO for full experiment
  - _Requirements: 30_

- [ ]* 19.3 Run pilot test and calibrate hyperparameters
  - Execute 12 pilot runs (2 sequences × 6 policies × 1 seed)
  - Analyze retrieval quality metrics
  - Calibrate top_k and max_context_tokens (locked after Week 4)
  - Calibrate Type-Aware Decay decay_d parameters (locked after Week 4)
  - Document calibration results
  - _Requirements: 30_


### 20. Integration and End-to-End Testing

- [ ] 20.1 Checkpoint - Verify core infrastructure
  - Ensure all unit tests pass for configuration, data models, memory store, retrieval
  - Verify frozen invariants are enforced (embedding size, retrieval scoring, injection order, max steps, temperature)
  - Verify logging schemas are complete
  - Ask user if questions arise
  - _Requirements: 1-30_

- [ ] 20.2 Run smoke test and validate
  - Execute 3-task smoke test with No Memory policy
  - Verify >15% pass rate gate
  - Verify all logging files generated correctly
  - Verify Docker eval_v3 integration works
  - Fix any issues before proceeding
  - _Requirements: 30_

- [ ] 20.3 Run policy comparison test
  - Execute same sequence with all 6 policies
  - Verify retrieval scoring identical across policies
  - Verify memory counts differ as expected (Full Memory grows, others prune)
  - Verify Full Memory never prunes
  - _Requirements: 6, 8, 9, 10, 11, 12, 13_

- [ ] 20.4 Run seed reproducibility test
  - Execute same sequence with same policy, different seeds
  - Verify Random Prune produces different results with different seeds
  - Verify Type-Aware Decay produces identical results (deterministic)
  - _Requirements: 10, 12, 16_

- [ ] 20.5 Checkpoint - Ready for pilot
  - Ensure all integration tests pass
  - Verify cost tracking accurate
  - Verify memory snapshots generated correctly
  - Ask user if questions arise before pilot runs
  - _Requirements: 1-30_


### 21. Full Experiment Execution

- [ ] 21.1 Execute full experiment matrix (144 runs)
  - Run all 8 sequences × 6 policies × 3 seeds = 144 runs
  - Monitor via wandb and tmux
  - Track daily costs and alert if exceeding budget
  - Handle failures gracefully and log all errors
  - Generate all required logs and snapshots
  - _Requirements: 16, 27_

- [ ] 21.2 Validate experimental data
  - Verify all 144 runs completed successfully
  - Check for missing log files or incomplete data
  - Validate logged values match actual run parameters
  - Verify memory snapshots generated for all task boundaries
  - _Requirements: 16, 18, 25_


### 22. Final Analysis and Results

- [ ] 22.1 Run complete statistical analysis
  - Aggregate all 144 runs into sequence-level means
  - Compute Wilcoxon signed-rank tests with Holm correction
  - Compute bootstrap BCa confidence intervals (5000 iterations)
  - Fit task-level GLMM with crossed random effects
  - Generate all statistical test result tables
  - _Requirements: 19, 20, 21, 22_

- [ ] 22.2 Run feature importance analysis
  - Train helpful/harmful memory prediction classifier
  - Compute PR-AUC and check VIF
  - Identify memory characteristics associated with success/failure
  - Generate feature importance tables and plots
  - _Requirements: 23_

- [ ] 22.3 Generate Pareto frontier analysis
  - Compute total costs for all runs
  - Plot CL-F1 vs cost Pareto frontier
  - Identify Pareto-optimal policies
  - Generate cost breakdown analysis
  - _Requirements: 24, 27_

- [ ] 22.4 Generate behavioral metrics analysis
  - Compute tool-call counts and syntax-error rates per policy
  - Test for analysis paralysis in Full Memory
  - Generate behavioral comparison plots
  - _Requirements: 29_

- [ ] 22.5 Generate failure analysis
  - Categorize all task failures
  - Compute per-policy failure rates by category
  - Identify boundary conditions (Full Memory fails, pruning succeeds)
  - Generate failure analysis tables and plots
  - _Requirements: 28_

- [ ] 22.6 Generate all visualizations and final report
  - Generate all plots (Pareto, performance, memory usage, behavioral, failures)
  - Generate all result tables
  - Compile final results summary
  - Verify all hypotheses (H1-H5) addressed
  - _Requirements: 19-29_


---

## Notes

### Task Execution Guidelines

- **Tasks marked with `*` are optional** and can be skipped for faster MVP. These are primarily test-related sub-tasks.
- **Core implementation tasks** (without `*`) must be completed for the system to function.
- Each task references specific requirements for traceability.
- Checkpoints ensure incremental validation and provide opportunities to ask questions.

### Frozen Invariants (CRITICAL)

The following invariants from THESIS_FINAL_v5.md §0.1 are enforced throughout implementation:

1. **All 8 official SWE-Bench-CL sequences** - no subsetting or re-ordering
2. **3 seeds for ALL 6 conditions** - total 144 runs
3. **Max 20 steps per task** - hard force-fail
4. **Embedding payload < 7500 tokens** - Issue + Error + Diff only
5. **Pure cosine retrieval** - identical across all 6 policies, no bonuses/penalties
6. **Best item LAST** - Lost-in-the-Middle mitigation
7. **5-type taxonomy** - architectural, api_change, bug_fix, test_update, config (NOT outcome-based)
8. **Type-Aware Decay formula** - Anderson-Schooler multiplicative: `base × age^(-d) × (1+use_count)^0.5`
9. **CLS consolidation schedule** - fixed every 5 tasks (NOT trigger-on-overflow)
10. **Memory labels are associated, not causal** - no causal claims from feature analysis
11. **Wilcoxon + Holm on N=8 sequence means** - primary statistical test
12. **Rank-biserial r_rb** - effect size metric (NOT Cohen's d or Cliff's delta)
13. **PR-AUC + VIF** - feature analysis metrics (NOT accuracy or ROC-AUC)
14. **GLMM with crossed random effects** - task-level analysis
15. **5000 BCa bootstrap iterations** - confidence intervals
16. **Same-repo retrieval only** - main experiment

### Calibration Windows

Two parameters are **TBD until calibration** and should not be hard-coded prematurely:

1. **`top_k` and `max_context_tokens`** - confirmed at end of Spike Week (Friday gate)
   - Defaults: `top_k=5`, `max_context_tokens=2000`
   - If pilot shows different optima, change once, then lock

2. **Type-Aware Decay `decay_d` per type** - confirmed at end of Week 4 pilot
   - Initial values in THESIS_FINAL_v5.md §8 P4
   - One-parameter-per-type calibration only

After Week 4, all hyperparameters are frozen for the full 144 runs.

### Logging Requirements

Every task MUST produce:
- One row in `task_results.jsonl` with complete schema
- Events in `memory_events.jsonl` for all memory operations
- Trajectory file `trajectories/{task_id}.json` with action-observation pairs
- Memory snapshots `before_task_n.json` and `after_task_n.json`

**If a field is missing at run time, it cannot be recovered. Log everything from Day 1.**

### Testing Strategy

This system is **NOT suitable for property-based testing** because:
- Infrastructure as Code (Docker, file systems, external APIs)
- Stochastic experimental design (controlled randomness via seeds)
- External dependencies (SWE-Bench eval_v3, OpenAI/Anthropic APIs, FAISS)
- Statistical analysis (one-shot analyses on experimental data)

**Focus on:**
- Unit tests for frozen invariants (100% coverage required)
- Integration tests for end-to-end workflows
- Manual testing for type classifier audit and cost monitoring

### Implementation Priority

1. **Core infrastructure** (Tasks 1-4) - foundation for all other work
2. **Memory system** (Tasks 5-8) - retrieval, classification, policies, reflection
3. **Agent and evaluation** (Tasks 9-10) - coding agent and Docker harness
4. **Logging and orchestration** (Tasks 11-12) - essential for data collection
5. **Metrics and analysis** (Tasks 13-16) - compute CL metrics and statistics
6. **Error handling and testing** (Tasks 17-20) - robustness and validation
7. **Execution and results** (Tasks 21-22) - run experiments and analyze

### Anti-Patterns to Avoid

- Do NOT add conditions 7, 8, 9 (six policies are locked)
- Do NOT modify retrieval scoring to add bonuses/penalties
- Do NOT embed raw trajectories (will exceed 8K token limit)
- Do NOT use Cliff's delta (use rank-biserial r_rb)
- Do NOT use McNemar test on per-task data (use Wilcoxon on sequence means)
- Do NOT use accuracy for helpful/harmful prediction (use PR-AUC)
- Do NOT collapse outcome into memory_type (orthogonal axes)
- Do NOT log agent's private chain-of-thought (action summaries only)


## Task Dependency Graph

```json
{
  "waves": [
    {
      "id": 0,
      "tasks": ["1.1", "1.2"]
    },
    {
      "id": 1,
      "tasks": ["1.3", "2.1", "2.2", "2.3", "2.4"]
    },
    {
      "id": 2,
      "tasks": ["3.1"]
    },
    {
      "id": 3,
      "tasks": ["3.2", "4.1", "4.2", "4.3"]
    },
    {
      "id": 4,
      "tasks": ["4.4", "5.1", "5.2"]
    },
    {
      "id": 5,
      "tasks": ["5.3", "6.1", "6.2"]
    },
    {
      "id": 6,
      "tasks": ["6.3", "7.1", "7.2", "7.3", "7.4", "7.5", "7.6"]
    },
    {
      "id": 7,
      "tasks": ["7.7", "8.1", "8.2"]
    },
    {
      "id": 8,
      "tasks": ["8.3", "9.1", "9.2", "9.3", "9.4"]
    },
    {
      "id": 9,
      "tasks": ["9.5", "10.1", "10.2"]
    },
    {
      "id": 10,
      "tasks": ["10.3", "11.1", "11.2", "11.3", "11.4"]
    },
    {
      "id": 11,
      "tasks": ["11.5", "12.1", "12.2", "12.3"]
    },
    {
      "id": 12,
      "tasks": ["12.4", "13.1", "13.2"]
    },
    {
      "id": 13,
      "tasks": ["13.3", "14.1", "14.2", "14.3", "14.4"]
    },
    {
      "id": 14,
      "tasks": ["14.5", "15.1"]
    },
    {
      "id": 15,
      "tasks": ["15.2", "16.1", "16.2"]
    },
    {
      "id": 16,
      "tasks": ["16.3", "17.1", "17.2"]
    },
    {
      "id": 17,
      "tasks": ["17.3", "18.1", "18.2"]
    },
    {
      "id": 18,
      "tasks": ["19.1", "19.2"]
    },
    {
      "id": 19,
      "tasks": ["19.3", "20.1"]
    },
    {
      "id": 20,
      "tasks": ["20.2"]
    },
    {
      "id": 21,
      "tasks": ["20.3", "20.4"]
    },
    {
      "id": 22,
      "tasks": ["20.5"]
    },
    {
      "id": 23,
      "tasks": ["21.1"]
    },
    {
      "id": 24,
      "tasks": ["21.2"]
    },
    {
      "id": 25,
      "tasks": ["22.1", "22.2", "22.3", "22.4", "22.5"]
    },
    {
      "id": 26,
      "tasks": ["22.6"]
    }
  ]
}
```
