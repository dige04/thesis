# Requirements Document

## Introduction

This document specifies requirements for a comprehensive research system that evaluates memory pruning and forgetting policies for AI coding agents. The system executes 144 controlled experimental runs across 6 memory policies and 8 SWE-Bench-CL sequences, evaluates performance using standard and custom metrics, and analyzes results using sequence-level non-parametric statistics and task-level generalized linear mixed models. The research tests whether proactive forgetting matches or beats full-memory accumulation on the Pareto frontier of continual learning F1-score versus operational cost.

## Glossary

- **System**: The complete memory-pruning research system
- **Agent**: The LangGraph-based coding agent that solves tasks
- **Memory_Store**: The persistent semantic memory backend (SQLite + FAISS)
- **Policy**: A memory management strategy (one of 6: No Memory, Full Memory, Random Prune, Recency Prune, Type-Aware Decay, CLS Consolidation)
- **Sequence**: An ordered list of coding tasks from a single repository in SWE-Bench-CL
- **Task**: A single GitHub issue resolution problem from SWE-Bench
- **Run**: One complete execution of all tasks in a sequence under a specific policy and seed
- **Retrieval**: The process of fetching relevant memories using cosine similarity
- **Embedding**: A vector representation of memory content
- **Consolidation**: The process of compressing multiple memories into a summary
- **CL-F1**: Continual Learning F1-score (harmonic mean of Plasticity and Stability)
- **Eval_Harness**: The standard SWE-Bench eval_v3 Docker-based evaluation system
- **Memory_Record**: A structured representation of task experience stored in memory
- **Type_Classifier**: A component that categorizes memories into 5 content types
- **Reflection_Step**: Post-task structured analysis that generates memory records

## Requirements

### Requirement 1: Benchmark Data Loading

**User Story:** As a researcher, I want to load all 8 official SWE-Bench-CL sequences in their original order, so that experimental integrity is preserved.

#### Acceptance Criteria

1. THE System SHALL load task data from the official SWE-Bench-CL-Curriculum.json file
2. THE System SHALL preserve the original chronological ordering of tasks within each sequence
3. THE System SHALL load all 8 sequences without subsetting or filtering
4. WHEN a sequence is loaded, THE System SHALL extract task_id, repo, base_commit, issue_text, test_patch, gold_patch, created_at, sequence_index, and difficulty_label for each task
5. THE System SHALL validate that each sequence contains at least 15 tasks

### Requirement 2: Memory Store Persistence

**User Story:** As a researcher, I want memory to persist across tasks within a sequence while the codebase resets, so that I can isolate the effect of memory accumulation.

#### Acceptance Criteria

1. WHEN a new sequence run begins, THE Memory_Store SHALL initialize an empty memory bank
2. WHILE a sequence is executing, THE Memory_Store SHALL persist all active memory records across task boundaries
3. WHEN a task completes, THE Agent SHALL operate on a clean repository checkout
4. IF repository checkout fails due to uncommitted changes or file system errors, THEN THE System SHALL fail the entire sequence run immediately
5. THE Memory_Store SHALL maintain separate storage for metadata (SQLite) and embeddings (FAISS)
6. THE Memory_Store SHALL support filtering by repository and archived status

### Requirement 3: Memory Record Structure

**User Story:** As a researcher, I want memory records to capture task experience with orthogonal type and outcome dimensions, so that I can analyze memory characteristics independently.

#### Acceptance Criteria

1. THE Memory_Record SHALL include identity fields: memory_id, task_id, repo, sequence_index
2. THE Memory_Record SHALL include orthogonal classification fields: memory_type (one of 5 content types) and outcome (pass, fail, partial, unknown)
3. THE Memory_Record SHALL include content fields: issue_summary, patch_summary, failure_summary, test_summary
4. THE Memory_Record SHALL include structural metadata: files_touched, functions_touched, commands_run
5. THE Memory_Record SHALL include retrieval provenance: retrieved_memory_ids_used
6. THE Memory_Record SHALL include embedding fields: embedding_text, embedding_vector_id, token_length
7. THE Memory_Record SHALL include usage tracking: use_count, last_retrieved_at_step, success_after_retrieval_count, failure_after_retrieval_count
8. THE Memory_Record SHALL include lifecycle fields: importance_score, is_consolidated, source_memory_ids, is_archived, archived_reason, archived_at_step

### Requirement 4: Embedding Payload Construction

**User Story:** As a researcher, I want embeddings to contain only issue, error, and diff information under 7500 tokens, so that embeddings are not silently truncated by the 8K model limit.

#### Acceptance Criteria

1. THE System SHALL construct embedding_text as the concatenation of issue_summary, failure_summary, and patch_summary only
2. THE System SHALL verify that embedding_text contains fewer than 7500 tokens before embedding
3. IF embedding_text exceeds 7500 tokens, THEN THE System SHALL truncate patch_summary from the end until the limit is satisfied
4. THE System SHALL NOT include memory_type, outcome, files_touched, or any other metadata in embedding_text

### Requirement 5: Type Classification

**User Story:** As a researcher, I want memories classified into 5 content-based types using a deterministic classifier, so that type-aware policies can prioritize memories appropriately.

#### Acceptance Criteria

1. THE Type_Classifier SHALL classify each memory into exactly one of 5 types: architectural, api_change, bug_fix, test_update, config
2. THE Type_Classifier SHALL use Structured Outputs or Tool Use with temperature 0 for deterministic classification
3. IF the Type_Classifier is configured with temperature other than 0, THEN THE System SHALL automatically override the temperature to 0
4. THE Type_Classifier SHALL NOT use outcome (pass/fail) as a classification criterion
5. THE Type_Classifier SHALL classify based on content: module structure for architectural, signature changes for api_change, bug patterns for bug_fix, test modifications for test_update, configuration changes for config

### Requirement 6: Identical Retrieval Across Policies

**User Story:** As a researcher, I want retrieval scoring to be identical across all 6 policies, so that policy differences reflect storage decisions only.

#### Acceptance Criteria

1. THE System SHALL use pure cosine similarity for retrieval scoring across all 6 policies
2. THE System SHALL NOT apply bonuses or penalties based on memory_type, outcome, age, or retrieval_count during retrieval
3. THE System SHALL filter candidates by same repository and non-archived status before scoring
4. THE System SHALL return the top-k highest-scoring memories within the token budget
5. IF the top-k memories exceed the token budget, THEN THE System SHALL drop the lowest-scoring memories until the token budget is satisfied and SHALL guarantee the final result fits within the budget
6. WHEN the System logs run metadata, THE System SHALL validate that logged values match the actual run parameters

### Requirement 7: Lost-in-the-Middle Mitigation

**User Story:** As a researcher, I want the highest-relevance memory injected last in the prompt, so that retrieval effectiveness is not degraded by positional bias.

#### Acceptance Criteria

1. WHEN constructing the agent prompt, THE System SHALL sort retrieved memories in ascending order of relevance score
2. IF multiple memories have identical relevance scores, THEN THE System SHALL use age as a secondary sort criterion with more recent memories sorted later
3. THE System SHALL inject the lowest-relevance memory first in the prompt
4. THE System SHALL inject the highest-relevance memory last, immediately before the task body
5. THE System SHALL render each memory with its memory_id, rank, similarity score, age, and type for traceability

### Requirement 8: No Memory Policy

**User Story:** As a researcher, I want a baseline policy that stores nothing, so that I can measure the effect of memory versus no memory.

#### Acceptance Criteria

1. THE No_Memory_Policy SHALL return an empty list for all retrieval requests
2. THE No_Memory_Policy SHALL discard all memory write requests but return success acknowledgments to maintain API compatibility with other policies
3. THE No_Memory_Policy SHALL perform no maintenance operations

### Requirement 9: Full Memory Policy

**User Story:** As a researcher, I want a policy that stores all memories without pruning, so that I can measure the effect of unbounded memory accumulation.

#### Acceptance Criteria

1. THE Full_Memory_Policy SHALL use the shared retrieval function with identical scoring to all other policies and SHALL override or bypass any pruning or archiving logic in shared functions
2. THE Full_Memory_Policy SHALL explicitly prohibit all archiving, pruning, and storage limits to maintain all memories
3. THE Full_Memory_Policy SHALL store all memory records without limit
4. THE Full_Memory_Policy SHALL perform no pruning or archiving during maintenance

### Requirement 10: Random Prune Policy

**User Story:** As a researcher, I want a policy that randomly prunes memories when capacity is exceeded, so that I can isolate the volume effect from semantic selection.

#### Acceptance Criteria

1. THE Random_Prune_Policy SHALL use the shared retrieval function with identical scoring to all other policies
2. THE Random_Prune_Policy SHALL store all incoming memory records
3. WHEN the active record count exceeds max_records, THE Random_Prune_Policy SHALL randomly select a victim and archive it
4. THE Random_Prune_Policy SHALL use a seeded random number generator for reproducibility
5. THE Random_Prune_Policy SHALL repeat random selection until the active count is at or below max_records

### Requirement 11: Recency Prune Policy

**User Story:** As a researcher, I want a policy that retains only the most recent memories, so that I can test whether recency alone is sufficient for effective memory management.

#### Acceptance Criteria

1. THE Recency_Prune_Policy SHALL use the shared retrieval function with identical scoring to all other policies
2. THE Recency_Prune_Policy SHALL store all incoming memory records
3. WHEN the active record count exceeds max_records, THE Recency_Prune_Policy SHALL archive the oldest memories by sequence_index
4. THE Recency_Prune_Policy SHALL retain the max_records most recent memories after pruning

### Requirement 12: Type-Aware Decay Policy

**User Story:** As a researcher, I want a policy that scores memories using Anderson-Schooler power-law decay with type-specific parameters, so that I can test whether semantic prioritization outperforms random pruning.

#### Acceptance Criteria

1. THE Type_Aware_Decay_Policy SHALL use the shared retrieval function with identical scoring to all other policies
2. THE Type_Aware_Decay_Policy SHALL store all incoming memory records
3. WHEN the active record count exceeds max_records, THE Type_Aware_Decay_Policy SHALL compute importance_score for each memory using the formula: base_value(type) × age^(-decay_d(type)) × (1 + use_count)^0.5
4. THE Type_Aware_Decay_Policy SHALL use type-specific base_value and decay_d parameters: architectural (1.0, 0.05), api_change (0.8, 0.15), bug_fix (0.6, 0.25), test_update (0.4, 0.35), config (0.3, 0.40)
5. THE Type_Aware_Decay_Policy SHALL archive the lowest-scoring memories until the active count is at or below max_records

### Requirement 13: CLS Consolidation Policy

**User Story:** As a researcher, I want a policy that consolidates old memories into summaries on a fixed schedule, so that I can test whether abstractive compression improves the performance-cost trade-off.

#### Acceptance Criteria

1. THE CLS_Consolidation_Policy SHALL use the shared retrieval function with identical scoring to all other policies
2. THE CLS_Consolidation_Policy SHALL store all incoming memory records
3. THE CLS_Consolidation_Policy SHALL trigger consolidation every 5 tasks on a fixed schedule
4. WHEN consolidation is triggered, THE CLS_Consolidation_Policy SHALL select candidate memories that are at least 10 tasks old, not already consolidated, and not of type architectural
5. THE CLS_Consolidation_Policy SHALL cluster candidates by repository, files_touched, and embedding similarity with a minimum cluster size of 3
6. FOR ALL clusters meeting the minimum size, THE CLS_Consolidation_Policy SHALL generate a consolidated summary record with max 350 tokens
7. THE CLS_Consolidation_Policy SHALL archive source memories and store the consolidated record with is_consolidated=True and source_memory_ids populated
8. IF the active count still exceeds max_records after consolidation, THEN THE CLS_Consolidation_Policy SHALL fall back to Type-Aware Decay pruning

### Requirement 14: Agent Execution Limits

**User Story:** As a researcher, I want hard limits on agent execution to prevent infinite loops and cap API costs, so that experiments complete within budget.

#### Acceptance Criteria

1. THE Agent SHALL terminate task execution after 20 steps
2. WHEN the step count exceeds 20, THE System SHALL force-fail the task and log timeout=true regardless of how execution stops
3. THE Agent SHALL use temperature 0 for all LLM calls to ensure reproducibility
4. THE Agent SHALL operate on a clean repository checkout at the start of each task

### Requirement 15: Reflection and Memory Writing

**User Story:** As a researcher, I want a structured reflection step after each task to generate memory records, so that memory content is consistent and traceable.

#### Acceptance Criteria

1. WHEN a task completes, THE Reflection_Step SHALL generate a structured memory record from the task, trajectory, patch, and evaluation result
2. THE Reflection_Step SHALL extract issue_summary, patch_summary, failure_summary, test_summary, files_touched, functions_touched, and commands_run
3. THE Reflection_Step SHALL record which memory_ids were retrieved and shown to the agent
4. THE Reflection_Step SHALL invoke the Type_Classifier to assign memory_type
5. IF the Type_Classifier is unavailable or fails, THEN THE Reflection_Step SHALL fail entirely
6. THE Reflection_Step SHALL require type assignment to complete before passing the memory record to the active policy's write method

### Requirement 16: Experiment Matrix Execution

**User Story:** As a researcher, I want to execute 144 runs (8 sequences × 6 policies × 3 seeds) with reproducible seeding, so that results are statistically valid.

#### Acceptance Criteria

1. THE System SHALL execute all 8 SWE-Bench-CL sequences for each of the 6 policies
2. THE System SHALL execute 3 independent runs with different seeds for each sequence-policy combination
3. THE System SHALL use seeds to initialize random number generators for Random_Prune_Policy and any stochastic components
4. THE System SHALL log the policy name, sequence name, seed, and run_id for each run
5. THE System SHALL validate that logged values match the actual run parameters before proceeding with execution

### Requirement 17: Evaluation Harness Integration

**User Story:** As a researcher, I want to evaluate patches using the standard SWE-Bench eval_v3 Docker harness, so that results are comparable to published benchmarks.

#### Acceptance Criteria

1. THE System SHALL invoke the eval_v3 Docker container for each generated patch
2. THE Eval_Harness SHALL return a binary pass/fail result for each task
3. THE System SHALL log the evaluation result, execution time, and any errors
4. THE System SHALL handle Docker container failures gracefully and log them as evaluation errors

### Requirement 18: Logging Schema Compliance

**User Story:** As a researcher, I want all runs to produce structured logs in a consistent schema, so that analysis scripts can process results without manual intervention.

#### Acceptance Criteria

1. THE System SHALL write one row to task_results.jsonl for each completed task
2. THE System SHALL append memory events to memory_events.jsonl for each write, archive, and consolidation operation
3. THE System SHALL write a trajectory JSON file for each task containing action-observation pairs
4. THE System SHALL write memory snapshots before_task_n.json and after_task_n.json at every task boundary
5. THE System SHALL include all fields specified in the logging schema without omissions

### Requirement 19: Continual Learning Metrics

**User Story:** As a researcher, I want to compute CL-F1, Plasticity, and Stability from the full accuracy matrix, so that I can measure sequential learning performance.

#### Acceptance Criteria

1. THE System SHALL construct an accuracy matrix a_{i,j} where a_{i,j} is the accuracy on task i after training through task j
2. THE System SHALL validate that at least some learning occurred by requiring minimum accuracy thresholds or non-zero learning before computing continual learning metrics
3. THE System SHALL compute Plasticity as the mean of diagonal elements (accuracy on the current task immediately after learning it)
4. THE System SHALL compute Stability as the mean of lower-triangular elements (accuracy on past tasks after learning new tasks)
5. THE System SHALL compute CL-F1 as 2 × (Plasticity × Stability) / (Plasticity + Stability)
6. THE System SHALL compute Forward Transfer and Backward Transfer as specified in the CL literature

### Requirement 20: Sequence-Level Statistical Analysis

**User Story:** As a researcher, I want to test hypotheses using Wilcoxon signed-rank tests on sequence-level means with Holm correction, so that statistical conclusions respect the experimental design.

#### Acceptance Criteria

1. THE System SHALL aggregate task-level results into sequence-level means for each policy-seed combination
2. THE System SHALL compute the mean CL-F1 across 3 seeds for each sequence-policy pair, yielding N=8 paired observations per policy comparison
3. THE System SHALL apply Wilcoxon signed-rank test to paired sequence means for 5 pre-registered contrasts
4. THE System SHALL apply Holm correction to control family-wise error rate across the 5 contrasts
5. THE System SHALL compute rank-biserial effect size r_rb for each contrast

### Requirement 21: Bootstrap Confidence Intervals

**User Story:** As a researcher, I want BCa bootstrap confidence intervals with 5000 iterations for effect sizes, so that uncertainty is properly quantified.

#### Acceptance Criteria

1. THE System SHALL perform 5000 bootstrap iterations for each effect size estimate
2. THE System SHALL use the BCa (bias-corrected and accelerated) method for confidence interval construction
3. THE System SHALL report the median paired difference and 95% BCa confidence interval for each contrast

### Requirement 22: Task-Level Mixed Model

**User Story:** As a researcher, I want to fit a generalized linear mixed model at the task level with crossed random effects, so that I can explore task-level variance while controlling for pseudo-replication.

#### Acceptance Criteria

1. THE System SHALL fit a binomial GLMM with logit link: task_success ~ condition + difficulty + position + (1|seq/seed) + (1|task_id)
2. THE System SHALL include fixed effects for condition (policy), difficulty (task difficulty label), and position (sequence index)
3. THE System SHALL include crossed random effects for sequence/seed combination and task_id
4. THE System SHALL report fixed-effect coefficients, standard errors, z-values, and p-values

### Requirement 23: Helpful/Harmful Memory Prediction

**User Story:** As a researcher, I want to predict which memory characteristics are associated with success or failure using PR-AUC, so that I can identify useful memory features despite class imbalance.

#### Acceptance Criteria

1. THE System SHALL train a classifier to predict success_after_retrieval (binary) from memory features
2. THE System SHALL use PR-AUC (Precision-Recall Area Under Curve) as the evaluation metric
3. THE System SHALL check variance inflation factors (VIF) for all features and flag VIF > 5
4. THE System SHALL apply class weights to handle the imbalanced positive class (~20%)
5. THE System SHALL NOT use success_after_retrieval_count or failure_after_retrieval_count as causal predictors in policy scoring

### Requirement 24: Pareto Frontier Analysis

**User Story:** As a researcher, I want to plot policies on a CL-F1 versus cost Pareto frontier, so that I can identify which policies achieve the best performance-cost trade-off.

#### Acceptance Criteria

1. THE System SHALL compute total cost for each policy-sequence-seed run as the sum of agent LLM costs, embedding costs, and consolidation costs
2. THE System SHALL plot each policy as a point with CL-F1 on the y-axis and total cost on the x-axis
3. THE System SHALL identify the Pareto frontier as the set of policies where no other policy achieves both higher CL-F1 and lower cost
4. THE System SHALL annotate each policy point with its name and confidence ellipse

### Requirement 25: Memory Snapshot Persistence

**User Story:** As a researcher, I want memory snapshots saved before and after each task, so that I can perform post-hoc analysis without re-running experiments.

#### Acceptance Criteria

1. WHEN a task begins, THE System SHALL write before_task_n.json containing all active memory_ids and their importance_scores
2. WHEN a task completes and maintenance finishes, THE System SHALL write after_task_n.json containing all active memory_ids and their importance_scores
3. THE System SHALL store snapshots in runs/{run_id}/memory/snapshots/
4. THE System SHALL include metadata: task_id, sequence_index, policy_name, timestamp

### Requirement 26: Configuration Management

**User Story:** As a researcher, I want a base configuration file with per-policy overrides, so that hyperparameters are centralized and version-controlled.

#### Acceptance Criteria

1. THE System SHALL load configuration from base.yaml and merge policy-specific overrides from configs/policies/{policy_name}.yaml
2. THE System SHALL include configuration for: top_k, max_context_tokens, max_records, max_storage_tokens, max_steps_per_task, temperature, seeds
3. THE System SHALL validate that all required configuration keys are present before starting a run
4. THE System SHALL prevent zero or negative values for critical parameters like max_context_tokens and max_records by enforcing minimum value constraints
5. THE System SHALL log the full merged configuration at the start of each run

### Requirement 27: Cost Monitoring

**User Story:** As a researcher, I want to track API costs per run and generate daily cost reports, so that I can stay within budget.

#### Acceptance Criteria

1. THE System SHALL log the token count and estimated cost for each LLM call (agent, classifier, consolidation)
2. THE System SHALL log the token count and estimated cost for each embedding call
3. THE System SHALL aggregate costs per run and write a cost summary to runs/{run_id}/cost_summary.json
4. THE System SHALL support generating a daily cost report across all active runs

### Requirement 28: Failure Analysis Protocol

**User Story:** As a researcher, I want to identify and categorize task failures, so that I can understand when and why policies fail.

#### Acceptance Criteria

1. WHEN a task fails, THE System SHALL log the failure category: timeout, test_failure, syntax_error, tool_error, or unknown
2. WHEN both error message and stack trace are available, THE System SHALL log both the final error message and stack trace
3. THE System SHALL compute per-policy failure rates by category
4. THE System SHALL identify tasks where Full_Memory_Policy fails but a pruning policy succeeds (boundary condition for H5)

### Requirement 29: Behavioral Metrics

**User Story:** As a researcher, I want to measure tool-call frequency and syntax-error rates, so that I can test whether memory accumulation induces analysis paralysis.

#### Acceptance Criteria

1. THE System SHALL count the number of tool calls per task for each policy
2. THE System SHALL count the number of syntax errors per task for each policy
3. THE System SHALL compute mean tool-call count and syntax-error rate per policy across all tasks
4. THE System SHALL test whether Full_Memory_Policy has significantly higher tool-call counts or syntax-error rates than pruning policies

### Requirement 30: Calibration Window Support

**User Story:** As a researcher, I want to run pilot experiments to calibrate top_k, max_context_tokens, and decay_d parameters before the full experiment, so that hyperparameters are empirically justified.

#### Acceptance Criteria

1. THE System SHALL support a pilot mode that runs 2 sequences × 6 policies × 1 seed = 12 runs
2. THE System SHALL log retrieval quality metrics (precision@k, recall@k) during pilot runs
3. THE System SHALL support updating top_k and max_context_tokens in the configuration after pilot analysis
4. THE System SHALL support updating Type-Aware Decay decay_d parameters per type after Week 4 pilot
5. THE System SHALL lock all hyperparameters after calibration and prevent further changes without explicit documentation

