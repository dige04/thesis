"""CLS Consolidation memory policy.

This policy consolidates old memories into summaries on a fixed schedule,
then falls back to Type-Aware Decay if still over budget.

**Validates: Requirements 13**

Purpose:
    Test whether abstractive compression (consolidation) improves the
    performance-cost trade-off compared to extractive pruning. CLS
    (Consolidate-Learn-Store) clusters similar old memories and generates
    LLM summaries, trading retrieval quality for reduced storage cost.

Frozen Invariants (THESIS_FINAL_v5.md §0.1):
- Retrieval scoring = pure cosine similarity, identical across all 6 conditions (Invariant #5)
- CLS consolidation = fixed every k=5 tasks (NOT trigger-on-overflow) (Invariant #9)
- Consolidation parameters locked from THESIS_FINAL_v5.md §8 P5 (Invariant #23)
- Falls back to Type-Aware Decay if still over budget after consolidation

Requirements: 13
Design: §2 Policy Specifications - Policy 5: CLS Consolidation
"""

import json
import logging
from typing import TYPE_CHECKING, Any

import numpy as np
from pydantic import BaseModel, Field, ValidationError
from sklearn.cluster import DBSCAN

from src.config.llm_factory import get_aux_client, summary_model
from src.metrics.cost_tracker import usage_from_chat_response
from src.model_output import extract_json_object

from ..embedding_utils import _truncate_to_token_budget, count_tokens
from ..retriever import shared_retrieve
from .base import MemoryPolicy
from .type_aware_decay import TypeAwareDecayPolicy

if TYPE_CHECKING:
    from ..record import MemoryRecord
    from ..store import MemoryStore

logger = logging.getLogger(__name__)


# Consolidation parameters (LOCKED from THESIS_FINAL_v5.md §8 P5)
CONSOLIDATION_INTERVAL = 5  # Trigger every 5 tasks
MIN_CLUSTER_SIZE = 3  # Minimum memories to consolidate
MAX_SUMMARY_TOKENS = 350  # Maximum tokens for consolidated summary
OLD_MEMORY_THRESHOLD = 5  # AMENDMENT A3 (2026-06-17): was 10. Lowered to cap/2 so CLS can consolidate at cap=10 — at cap=10 no active record ever reaches age 10, leaving CLS inert (gate-3). Derived from the A1 cap amendment; see AMENDMENTS.md / Invariant #23.
SIMILARITY_THRESHOLD = 0.70  # Minimum cosine similarity for clustering
EXCLUDE_TYPE = "architectural"  # Sacred tier - never consolidate

# Temperature held constant across conditions. AMENDMENT 2026-06-14: Kimi
# reasoning models (via CLIProxyAPI) only accept temp=1 (was 0); disclose.
SUMMARY_TEMPERATURE = 1


class ConsolidationSummary(BaseModel):
    """Validated shape of the consolidation LLM's JSON output (§P5).

    The §P5 example also shows a ``"memory_type": "consolidated_summary"`` field
    INSIDE this JSON. It is intentionally NOT modelled here: the consolidated
    MemoryRecord's ``memory_type`` must stay within the frozen 5-type taxonomy
    (Invariant #7) and is derived from the cluster MAJORITY type, not from the
    LLM. Pydantic ignores unknown keys by default, so the field is dropped.
    """

    summary: str = ""
    common_files: list[str] = Field(default_factory=list)
    recurring_pattern: str = ""
    successful_strategy: str = ""
    failure_traps: str = ""
    test_commands: list[str] = Field(default_factory=list)


# Consolidation prompt (verbatim intent from THESIS_FINAL_v5.md §8 P5).
CONSOLIDATION_SYSTEM_PROMPT = (
    "You are compressing coding-agent memories from a single repository.\n\n"
    "Given several past task memories, produce one compact reusable memory.\n\n"
    "Keep: repository conventions, recurring files/functions, successful fix "
    "strategies, test commands, failure traps, assumptions proven wrong.\n\n"
    "Remove: duplicate details, irrelevant logs, one-off stack traces, exact "
    "patches unless the pattern is reusable."
)

# Ollama's OpenAI-compatible endpoint ignores the json_schema response_format
# (ollama/ollama #10001), so we use plain JSON mode + explicit schema
# instructions + Pydantic validation (deviation D4, see CLAUDE.md), NOT
# beta.chat.completions.parse. The "memory_type" field from the §P5 example is
# deliberately omitted from the schema we ask for (see ConsolidationSummary).
CONSOLIDATION_JSON_INSTRUCTIONS = (
    "\n\nRespond with ONLY a JSON object of exactly this shape "
    "(no markdown fences, no commentary):\n"
    '{"summary": "...", "common_files": ["..."], "recurring_pattern": "...", '
    '"successful_strategy": "...", "failure_traps": "...", '
    '"test_commands": ["..."]}'
)


class CLSConsolidationPolicy(MemoryPolicy):
    """CLS Consolidation policy with Type-Aware Decay fallback.

    **Validates: Requirements 13**

    This policy consolidates old memories into summaries on a fixed schedule
    (every 5 tasks), then falls back to Type-Aware Decay pruning if still
    over budget. Implements abstractive compression via LLM summarization.

    Behavior:
        1. Retrieval: Uses shared_retrieve() with identical scoring to all other policies
        2. Write: Stores all incoming memory records without filtering
        3. Maintain: Every 5 tasks, consolidates old memories:
           a. Select candidates: >= 10 tasks old, not consolidated, not architectural
           b. Cluster by repo, files_touched, and embedding similarity (min size 3)
           c. Generate consolidated summary (max 350 tokens) for each cluster
           d. Archive source memories, store consolidated record
           e. If still over budget, fall back to Type-Aware Decay pruning

    Consolidation Algorithm:
        1. Filter candidates: age >= 10, not consolidated, type != architectural
        2. Group by repository (consolidation is repo-specific)
        3. For each repo group:
           a. Cluster by files_touched overlap and embedding similarity
           b. Use DBSCAN with cosine distance, eps=(1-similarity_threshold)
           c. Require min_samples=MIN_CLUSTER_SIZE
        4. For each cluster:
           a. Generate LLM summary (max 350 tokens)
           b. Create consolidated MemoryRecord with is_consolidated=True
           c. Archive source memories with reason="cls_consolidated"
           d. Store consolidated record

    Consolidation Parameters (LOCKED):
        - Interval: 5 tasks (fixed schedule, not trigger-on-overflow)
        - Min cluster size: 3 memories
        - Max summary tokens: 350
        - Old memory threshold: 10 tasks
        - Similarity threshold: 0.70 (cosine similarity)
        - Exclude type: architectural (Sacred tier)

    Fallback Behavior:
        If active count still exceeds max_records after consolidation,
        falls back to Type-Aware Decay pruning to reach target capacity.
        This ensures the policy never exceeds max_records.

    Attributes:
        name: Policy identifier ("cls_consolidation")
        max_records: Maximum number of active memories to retain
        tasks_since_last_consolidation: Counter for fixed schedule

    Design Rationale:
        CLS Consolidation tests whether abstractive compression (LLM summaries)
        can preserve retrieval quality while reducing storage cost. Fixed
        schedule (every 5 tasks) ensures consolidation happens proactively,
        not reactively. Fallback to Type-Aware Decay ensures capacity limits
        are respected even if consolidation is insufficient.

    Example:
        >>> policy = CLSConsolidationPolicy(max_records=100)
        >>> # After task 15 (3rd consolidation trigger):
        >>> policy.maintain(memory_store)
        >>> # Selects memories from tasks 1-5 (age >= 10)
        >>> # Clusters by repo + files + similarity
        >>> # Generates summaries for clusters with >= 3 memories
        >>> # Archives source memories, stores consolidated records
        >>> # If still > 100 active, falls back to Type-Aware Decay
    """

    name = "cls_consolidation"

    # Expose frozen parameters as class attributes for testing
    CONSOLIDATION_INTERVAL = CONSOLIDATION_INTERVAL
    MIN_CLUSTER_SIZE = MIN_CLUSTER_SIZE
    MAX_SUMMARY_TOKENS = MAX_SUMMARY_TOKENS
    OLD_MEMORY_THRESHOLD = OLD_MEMORY_THRESHOLD
    SIMILARITY_THRESHOLD = SIMILARITY_THRESHOLD

    def __init__(self, max_records: int):
        """Initialize CLS Consolidation policy.

        Args:
            max_records: Maximum number of active memories to retain (typically 100)

        Notes:
            - max_records is the capacity threshold for fallback pruning
            - Consolidation parameters are LOCKED from THESIS_FINAL_v5.md §8 P5
            - Consolidation happens every 5 tasks (fixed schedule)
            - Falls back to Type-Aware Decay if still over budget
        """
        self.max_records = max_records
        self._tasks_since_last_consolidation = 0

        # Consolidation LLM token usage buffer for cost telemetry (E1). Each
        # _generate_summary call appends a usage dict; the SequenceRunner drains
        # it after policy.maintain() via drain_consolidation_usage().
        self._consolidation_usage: list[dict[str, Any]] = []

        logger.info(
            f"Initialized CLSConsolidationPolicy: max_records={max_records}, "
            f"interval={CONSOLIDATION_INTERVAL}, min_cluster_size={MIN_CLUSTER_SIZE}, "
            f"max_summary_tokens={MAX_SUMMARY_TOKENS}, old_threshold={OLD_MEMORY_THRESHOLD}"
        )

    def retrieve(
        self,
        task: Any,
        memory_store: "MemoryStore",
        top_k: int,
        token_budget: int
    ) -> list[tuple[float, "MemoryRecord"]]:
        """Retrieve relevant memories using shared retrieval function.

        CRITICAL: Uses shared_retrieve() to ensure identical retrieval scoring
        across all 6 policies. This is a frozen invariant (Requirement 6).

        **Validates: Requirements 13.1**

        Args:
            task: Current task requiring memory retrieval
            memory_store: Persistent memory storage backend
            top_k: Maximum number of memories to retrieve
            token_budget: Maximum total tokens for retrieved memories

        Returns:
            List of (similarity_score, MemoryRecord) tuples, sorted ascending
            by relevance (best item LAST for Lost-in-the-Middle mitigation)

        Notes:
            - Pure cosine similarity scoring (no bonuses or penalties)
            - Filters by same repository and non-archived status
            - Enforces token budget by dropping lowest-scoring memories
            - Returns empty list if no candidates or all exceed budget
        """
        return shared_retrieve(task, memory_store, top_k, token_budget)

    def write(self, memory_store: "MemoryStore", record: "MemoryRecord") -> None:
        """Store a new memory record.

        CLS Consolidation stores ALL incoming records without filtering.
        Consolidation and pruning happen in maintain() after the record is stored.

        **Validates: Requirements 13.2**

        Args:
            memory_store: Persistent memory storage backend
            record: MemoryRecord to store (from reflection step)

        Notes:
            - No filtering at write time
            - All records stored regardless of type, outcome, or age
            - Consolidation deferred to maintain() phase
        """
        memory_store.add(record)

        logger.debug(
            f"Stored memory {record.memory_id} for task {record.task_id} "
            f"(type={record.memory_type}, outcome={record.outcome}, "
            f"seq_idx={record.sequence_index})"
        )

    def maintain(self, memory_store: "MemoryStore") -> None:
        """Perform CLS consolidation on fixed schedule, then fallback pruning.

        CRITICAL: Consolidation triggers every 5 tasks (fixed schedule), NOT
        when capacity is exceeded. This is a frozen invariant (Invariant #9).

        **Validates: Requirements 13.3, 13.4, 13.5, 13.6, 13.7, 13.8**

        Algorithm:
            1. Increment task counter
            2. If counter < 5, no action (wait for next trigger)
            3. If counter >= 5, reset counter and consolidate:
               a. Get current step (max sequence_index)
               b. Select candidates: age >= 10, not consolidated, not architectural
               c. Group candidates by repository
               d. For each repo group, cluster by files + embedding similarity
               e. For each cluster with >= 3 memories, generate summary
               f. Archive source memories, store consolidated record
            4. If still over budget, fall back to Type-Aware Decay pruning

        Args:
            memory_store: Persistent memory storage backend

        Notes:
            - Fixed schedule: every 5 tasks, regardless of capacity
            - Consolidation is repo-specific (clusters within same repo)
            - Excludes architectural memories (Sacred tier)
            - Falls back to Type-Aware Decay if still over max_records
            - Logs consolidation events and costs
        """
        # Increment task counter
        self._tasks_since_last_consolidation += 1

        # Check if consolidation should trigger
        if self._tasks_since_last_consolidation < CONSOLIDATION_INTERVAL:
            logger.debug(
                f"No consolidation: {self._tasks_since_last_consolidation}/{CONSOLIDATION_INTERVAL} tasks"
            )
            return

        # Reset counter
        self._tasks_since_last_consolidation = 0

        logger.info(
            f"CLS consolidation triggered (every {CONSOLIDATION_INTERVAL} tasks)"
        )

        # Delegate to _consolidate helper
        self._consolidate(memory_store)

        # Check if fallback pruning is needed
        active_count = memory_store.count_active()

        if active_count > self.max_records:
            logger.info(
                f"Fallback to Type-Aware Decay: {active_count} > {self.max_records}"
            )

            # Create Type-Aware Decay policy and run maintain
            fallback = TypeAwareDecayPolicy(max_records=self.max_records)
            fallback.maintain(memory_store)

            final_count = memory_store.count_active()

            logger.info(
                f"Fallback pruning complete: {active_count} -> {final_count}"
            )
        else:
            logger.debug(
                f"No fallback needed: {active_count} <= {self.max_records}"
            )

    def _consolidate(self, memory_store: "MemoryStore") -> None:
        """Perform CLS consolidation logic.

        This is a helper method extracted for testing purposes.
        The actual consolidation is triggered by maintain().

        Args:
            memory_store: Persistent memory storage backend
        """
        # Get all active records and compute current step
        active_records = memory_store.active_records()

        if not active_records:
            logger.debug("No active records to consolidate")
            return

        current_step = max(r.sequence_index for r in active_records)

        # Select consolidation candidates
        candidates = self._select_candidates(active_records, current_step)

        if not candidates:
            logger.info("No consolidation candidates found")
        else:
            logger.info(
                f"Found {len(candidates)} consolidation candidates "
                f"(age >= {OLD_MEMORY_THRESHOLD}, not consolidated, not {EXCLUDE_TYPE})"
            )

            # Group candidates by repository
            repo_groups = self._group_by_repo(candidates)

            # Consolidate each repo group
            total_clusters = 0
            total_consolidated = 0

            for repo, repo_candidates in repo_groups.items():
                logger.debug(
                    f"Processing repo {repo}: {len(repo_candidates)} candidates"
                )

                # Cluster candidates
                clusters = self._cluster_memories(repo_candidates, memory_store)

                logger.debug(
                    f"Found {len(clusters)} clusters in repo {repo}"
                )

                # Consolidate each cluster
                for cluster in clusters:
                    if len(cluster) >= MIN_CLUSTER_SIZE:
                        self._consolidate_cluster(
                            cluster, memory_store, current_step
                        )
                        total_clusters += 1
                        total_consolidated += len(cluster)

            logger.info(
                f"CLS consolidation complete: {total_clusters} clusters, "
                f"{total_consolidated} memories consolidated"
            )

    def _select_candidates(
        self,
        active_records: list["MemoryRecord"],
        current_step: int
    ) -> list["MemoryRecord"]:
        """Select consolidation candidates.

        **Validates: Requirements 13.4**

        Candidates must meet ALL criteria:
        - Age >= OLD_MEMORY_THRESHOLD (10 tasks old)
        - Not already consolidated (is_consolidated=False)
        - Not architectural type (Sacred tier)

        Args:
            active_records: All active (non-archived) memory records
            current_step: Current sequence step (max sequence_index)

        Returns:
            List of MemoryRecord instances that meet all criteria

        Notes:
            - Age = current_step - sequence_index
            - Architectural memories are never consolidated (Sacred tier)
            - Already-consolidated memories are not re-consolidated
        """
        candidates = []

        for record in active_records:
            age = current_step - record.sequence_index

            # Check all criteria
            if (
                age >= OLD_MEMORY_THRESHOLD
                and not record.is_consolidated
                and record.memory_type != EXCLUDE_TYPE
            ):
                candidates.append(record)

        return candidates

    def _group_by_repo(
        self,
        candidates: list["MemoryRecord"]
    ) -> dict[str, list["MemoryRecord"]]:
        """Group candidates by repository.

        Consolidation is repo-specific: memories from different repos
        are never consolidated together.

        Args:
            candidates: List of consolidation candidates

        Returns:
            Dictionary mapping repo name to list of candidates

        Notes:
            - Consolidation respects repository boundaries
            - Each repo is processed independently
        """
        repo_groups: dict[str, list[MemoryRecord]] = {}

        for record in candidates:
            if record.repo not in repo_groups:
                repo_groups[record.repo] = []
            repo_groups[record.repo].append(record)

        return repo_groups

    def _cluster_memories(
        self,
        candidates: list["MemoryRecord"],
        memory_store: "MemoryStore"
    ) -> list[list["MemoryRecord"]]:
        """Cluster memories by files_touched and embedding similarity.

        **Validates: Requirements 13.5**

        Uses DBSCAN clustering with:
        - Distance metric: Combined files overlap + embedding cosine distance
        - eps: 1 - SIMILARITY_THRESHOLD (0.30 for threshold 0.70)
        - min_samples: MIN_CLUSTER_SIZE (3)

        Args:
            candidates: List of consolidation candidates from same repo
            memory_store: Memory store for accessing embeddings

        Returns:
            List of clusters, where each cluster is a list of MemoryRecord

        Notes:
            - Clusters must have >= MIN_CLUSTER_SIZE members
            - Uses embedding vectors from FAISS for similarity
            - Combines structural (files) and semantic (embeddings) similarity
            - DBSCAN automatically filters noise points (cluster_id=-1)
        """
        if len(candidates) < MIN_CLUSTER_SIZE:
            # Not enough candidates to form a cluster
            return []

        # Extract embedding vectors
        embedding_vectors = []
        valid_candidates = []

        for record in candidates:
            try:
                vector_id = int(record.embedding_vector_id)
                # Get vector from FAISS
                vector = memory_store.faiss_index.reconstruct(vector_id)
                embedding_vectors.append(vector)
                valid_candidates.append(record)
            except (ValueError, TypeError, RuntimeError):
                # Skip records with invalid or missing embeddings
                logger.warning(
                    f"Skipping record {record.memory_id}: invalid embedding"
                )
                continue

        if len(valid_candidates) < MIN_CLUSTER_SIZE:
            return []

        # Compute pairwise distance matrix
        # Distance = (1 - cosine_similarity) * 0.5 + (1 - files_overlap) * 0.5
        n = len(valid_candidates)
        distance_matrix = np.zeros((n, n))

        for i in range(n):
            for j in range(i + 1, n):
                # Cosine distance (1 - cosine similarity)
                vec_i = embedding_vectors[i]
                vec_j = embedding_vectors[j]
                cosine_sim = np.dot(vec_i, vec_j)  # Already L2-normalized
                cosine_dist = 1 - cosine_sim

                # Files overlap distance
                files_i = set(valid_candidates[i].files_touched)
                files_j = set(valid_candidates[j].files_touched)

                if len(files_i) == 0 and len(files_j) == 0:
                    files_overlap = 1.0  # Both empty = perfect overlap
                elif len(files_i) == 0 or len(files_j) == 0:
                    files_overlap = 0.0  # One empty = no overlap
                else:
                    intersection = len(files_i & files_j)
                    union = len(files_i | files_j)
                    files_overlap = intersection / union if union > 0 else 0.0

                files_dist = 1 - files_overlap

                # Combined distance (equal weight)
                combined_dist = 0.5 * cosine_dist + 0.5 * files_dist

                distance_matrix[i, j] = combined_dist
                distance_matrix[j, i] = combined_dist

        # Run DBSCAN clustering
        # eps = 1 - SIMILARITY_THRESHOLD (0.30 for threshold 0.70)
        eps = 1 - SIMILARITY_THRESHOLD
        clustering = DBSCAN(
            eps=eps,
            min_samples=MIN_CLUSTER_SIZE,
            metric="precomputed"
        ).fit(distance_matrix)

        # Group by cluster ID
        clusters: dict[int, list[MemoryRecord]] = {}

        for idx, cluster_id in enumerate(clustering.labels_):
            if cluster_id == -1:
                # Noise point (not in any cluster)
                continue

            if cluster_id not in clusters:
                clusters[cluster_id] = []

            clusters[cluster_id].append(valid_candidates[idx])

        # Filter clusters by minimum size
        valid_clusters = [
            cluster for cluster in clusters.values()
            if len(cluster) >= MIN_CLUSTER_SIZE
        ]

        logger.debug(
            f"DBSCAN clustering: {len(valid_candidates)} candidates -> "
            f"{len(valid_clusters)} clusters (min_size={MIN_CLUSTER_SIZE})"
        )

        return valid_clusters

    @staticmethod
    def _majority_memory_type(cluster: list["MemoryRecord"]) -> str:
        """Return the most common memory_type among a cluster's records.

        Consolidated records must stay within the frozen 5-type taxonomy
        (Invariant #7). Instead of inventing a 6th type, a consolidated
        record inherits the MAJORITY memory_type of its constituent records.

        Tie-breaking is deterministic and alphabetical: among the types that
        share the maximum count, the lexicographically smallest type name is
        chosen (e.g. {"config": 2, "test_update": 2} -> "config"). This makes
        consolidation reproducible across runs and seeds.

        Args:
            cluster: Non-empty list of MemoryRecord instances to consolidate.

        Returns:
            The majority memory_type (one of the 5 valid content types).
        """
        counts: dict[str, int] = {}
        for record in cluster:
            counts[record.memory_type] = counts.get(record.memory_type, 0) + 1

        max_count = max(counts.values())
        tied_types = [mt for mt, c in counts.items() if c == max_count]
        # Deterministic tie-break: alphabetical (smallest type name wins)
        return min(tied_types)

    def _consolidate_cluster(
        self,
        cluster: list["MemoryRecord"],
        memory_store: "MemoryStore",
        current_step: int
    ) -> None:
        """Consolidate a cluster of memories into a summary.

        **Validates: Requirements 13.6, 13.7**

        Algorithm:
            1. Generate consolidated summary (max 350 tokens) via LLM
            2. Create consolidated MemoryRecord with is_consolidated=True
            3. Archive source memories with reason="cls_consolidated"
            4. Store consolidated record in memory store

        Args:
            cluster: List of MemoryRecord instances to consolidate
            memory_store: Memory store for archiving and storing
            current_step: Current sequence step

        Notes:
            - Summary is generated by the summary LLM (§8 P5); falls back to a
              placeholder on any LLM failure
            - Composed summary text is capped at MAX_SUMMARY_TOKENS via tiktoken
            - token_length is a real tiktoken count of the stored embedding_text
            - Consolidated record has is_consolidated=True and source_memory_ids
            - memory_type stays the cluster MAJORITY valid type (Invariant #7)
            - Source memories are archived, not deleted
            - Consolidated record inherits repo from cluster
        """
        logger.info(
            f"Consolidating cluster of {len(cluster)} memories: "
            f"{[r.memory_id for r in cluster]}"
        )

        # Generate the consolidated summary via the summary LLM (§8 P5). On ANY
        # LLM failure (API/JSON/empty) this falls back to the placeholder so a
        # run is never crashed by consolidation.
        summary = self._generate_summary(cluster)

        # Compose the consolidated content from the structured summary fields and
        # cap it at MAX_SUMMARY_TOKENS using a real tiktoken count (HARD
        # CONSTRAINT). issue_summary holds the prose synthesis; test_summary
        # carries the recurring test commands.
        issue_summary_text = self._compose_summary_text(summary)
        issue_summary_text = _truncate_to_token_budget(
            issue_summary_text, MAX_SUMMARY_TOKENS
        )
        test_commands = summary.get("test_commands") or []
        test_summary_text = (
            "; ".join(test_commands) if test_commands else None
        )

        # Embedding text mirrors the stored content so token_length is a real
        # token count of what the record actually carries.
        embedding_text = issue_summary_text
        if test_summary_text:
            embedding_text = f"{issue_summary_text}\nTest commands: {test_summary_text}"
        embedding_text = _truncate_to_token_budget(embedding_text, MAX_SUMMARY_TOKENS)
        token_length = count_tokens(embedding_text)

        # Create consolidated MemoryRecord
        from ..record import MemoryRecord

        # Consolidated records MUST use one of the 5 valid memory_types
        # (Invariant #7, 5-type taxonomy). We assign the cluster's MAJORITY
        # memory_type; is_consolidated=True keeps the record identifiable.
        # NOTE: the LLM JSON may include "memory_type": "consolidated_summary"
        # (per the §P5 example) — that is IGNORED here on purpose.
        consolidated_type = self._majority_memory_type(cluster)

        consolidated_record = MemoryRecord(
            memory_id=MemoryRecord.generate_id(),
            task_id=f"consolidated_{current_step}",
            repo=cluster[0].repo,  # All cluster members have same repo
            sequence_index=current_step,
            memory_type=consolidated_type,  # Majority type of cluster (5-type taxonomy)
            outcome="unknown",  # Consolidated summaries don't have outcomes
            issue_summary=issue_summary_text,
            patch_summary="",  # No patch for consolidated
            failure_summary=None,
            test_summary=test_summary_text,
            files_touched=summary.get("common_files") or [],
            functions_touched=[],
            commands_run=test_commands,
            retrieved_memory_ids_used=[],
            embedding_text=embedding_text,  # Use composed summary as embedding text
            token_length=token_length,  # Real tiktoken count, capped at MAX_SUMMARY_TOKENS
            is_consolidated=True,
            source_memory_ids=[r.memory_id for r in cluster]
        )

        # Store consolidated record
        memory_store.add(consolidated_record)

        logger.debug(
            f"Created consolidated record {consolidated_record.memory_id} "
            f"from {len(cluster)} source memories"
        )

        # Archive source memories
        for record in cluster:
            memory_store.archive(
                memory_id=record.memory_id,
                reason="cls_consolidated",
                replacement_id=consolidated_record.memory_id,
                current_step=current_step
            )

            logger.debug(
                f"Archived source memory {record.memory_id} "
                f"(replaced by {consolidated_record.memory_id})"
            )

    def _generate_summary(
        self,
        cluster: list["MemoryRecord"]
    ) -> dict[str, Any]:
        """Generate a consolidated summary for a cluster via the summary LLM.

        **Validates: Requirements 13.6**

        Calls ``get_chat_client().chat.completions.create`` with the §8 P5
        consolidation prompt at ``temperature=0`` (FROZEN) using JSON mode
        (``response_format={"type": "json_object"}``, deviation D4 — Ollama
        ignores json_schema), then validates the result against
        :class:`ConsolidationSummary`.

        On ANY failure (transport/API error, empty content, malformed/invalid
        JSON) this logs a warning and FALLS BACK to
        :meth:`_generate_summary_placeholder` so a run is never crashed by
        consolidation.

        Args:
            cluster: List of MemoryRecord instances to summarize (>= MIN_CLUSTER_SIZE).

        Returns:
            Dict with keys: summary, common_files, recurring_pattern,
            successful_strategy, failure_traps, test_commands.
        """
        messages = [
            {
                "role": "system",
                "content": CONSOLIDATION_SYSTEM_PROMPT + CONSOLIDATION_JSON_INSTRUCTIONS,
            },
            {"role": "user", "content": self._render_cluster(cluster)},
        ]

        try:
            client = get_aux_client()
            # Prompt-instructed JSON + tolerant extraction + Pydantic validation.
            # No response_format: MiniMax M3 returns 400 model_not_capable for
            # json_object mode (D4 extended 2026-06-17).
            response = client.chat.completions.create(
                model=summary_model(),
                messages=messages,
                temperature=SUMMARY_TEMPERATURE,
            )

            # Surface token usage for cost telemetry (E1). Recorded BEFORE
            # validation so a malformed-then-fallback response still counts its
            # real token spend toward the Pareto axis.
            prompt_tokens, completion_tokens = usage_from_chat_response(response)
            self._consolidation_usage.append(
                {
                    "call_type": "consolidation",
                    "model": summary_model(),
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                }
            )

            content = response.choices[0].message.content
            if not content or not isinstance(content, str):
                raise ValueError("consolidation LLM returned empty/non-string content")

            validated = ConsolidationSummary.model_validate(extract_json_object(content))
            return validated.model_dump()

        except (ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.warning(
                f"Consolidation LLM produced invalid output, falling back to "
                f"placeholder summary: {e}"
            )
            return self._generate_summary_placeholder(cluster)
        except Exception as e:
            # Transport / API errors — never crash a run, fall back instead.
            logger.warning(
                f"Consolidation LLM call failed, falling back to placeholder "
                f"summary: {e}"
            )
            return self._generate_summary_placeholder(cluster)

    def drain_consolidation_usage(self) -> list[dict[str, Any]]:
        """Return and clear accumulated consolidation LLM usage records (E1).

        The SequenceRunner calls this after policy.maintain() to attribute CLS
        consolidation token cost to the CostTracker. Only this policy emits
        consolidation calls, so the runner checks for the method via duck-typing.
        """
        drained = self._consolidation_usage
        self._consolidation_usage = []
        return drained

    @staticmethod
    def _compose_summary_text(summary: dict[str, Any]) -> str:
        """Compose the consolidated record's prose content from summary fields.

        Combines summary + recurring_pattern + successful_strategy +
        failure_traps into a single human-readable block (test_commands are
        stored separately on the record's ``test_summary``/``commands_run``).
        Empty fields are omitted so the placeholder fallback (which only fills
        ``summary``) stays clean.

        Args:
            summary: Validated/placeholder summary dict.

        Returns:
            Composed prose string (may be empty if every field is blank).
        """
        parts: list[str] = []
        if summary.get("summary"):
            parts.append(str(summary["summary"]).strip())
        if summary.get("recurring_pattern"):
            parts.append(f"Recurring pattern: {str(summary['recurring_pattern']).strip()}")
        if summary.get("successful_strategy"):
            parts.append(
                f"Successful strategy: {str(summary['successful_strategy']).strip()}"
            )
        if summary.get("failure_traps"):
            parts.append(f"Failure traps: {str(summary['failure_traps']).strip()}")
        return "\n".join(parts)

    @staticmethod
    def _render_cluster(cluster: list["MemoryRecord"]) -> str:
        """Render a cluster's records into the LLM user prompt.

        Args:
            cluster: List of MemoryRecord instances to summarize.

        Returns:
            A plain-text rendering of each record's salient fields.
        """
        repo = cluster[0].repo if cluster else "(unknown)"
        blocks: list[str] = [
            f"Repository: {repo}",
            f"Number of past task memories to compress: {len(cluster)}",
            "",
        ]
        for i, record in enumerate(cluster, start=1):
            files = ", ".join(record.files_touched) if record.files_touched else "(none)"
            commands = ", ".join(record.commands_run) if record.commands_run else "(none)"
            blocks.append(
                f"--- Memory {i} (type={record.memory_type}, outcome={record.outcome}) ---\n"
                f"Issue: {record.issue_summary}\n"
                f"Patch: {record.patch_summary}\n"
                f"Failure: {record.failure_summary or '(none)'}\n"
                f"Files: {files}\n"
                f"Commands: {commands}"
            )
        return "\n".join(blocks)

    def _generate_summary_placeholder(
        self,
        cluster: list["MemoryRecord"]
    ) -> dict[str, Any]:
        """Generate placeholder summary for a cluster.

        TODO: Replace with actual LLM summarization.

        Args:
            cluster: List of MemoryRecord instances to summarize

        Returns:
            Dictionary with summary fields:
                - summary: Consolidated text summary
                - common_files: List of files touched across cluster
                - recurring_pattern: Identified pattern (placeholder)
                - successful_strategy: Successful strategies (placeholder)
                - failure_traps: Common failure modes (placeholder)
                - test_commands: Test commands used (placeholder)

        Notes:
            - This is a placeholder implementation
            - Real implementation should use LLM with consolidation prompt
            - Summary should be max 350 tokens
        """
        # Collect common files
        all_files = set()
        for record in cluster:
            all_files.update(record.files_touched)

        # Collect test commands
        all_commands = set()
        for record in cluster:
            all_commands.update(record.commands_run)

        # Generate placeholder summary
        summary_text = (
            f"Consolidated summary of {len(cluster)} related memories. "
            f"Common files: {', '.join(sorted(all_files)[:5])}. "
            f"Memory types: {', '.join(set(r.memory_type for r in cluster))}. "
            f"Outcomes: {', '.join(set(r.outcome for r in cluster))}."
        )

        return {
            "summary": summary_text,
            "common_files": sorted(all_files),
            "recurring_pattern": "placeholder_pattern",
            "successful_strategy": "placeholder_strategy",
            "failure_traps": "placeholder_traps",
            "test_commands": sorted(all_commands)
        }
