"""CLS Consolidation policy implementation.

This module implements the CLS (Cluster-and-Summarize) Consolidation policy
that clusters old memories and generates consolidated summaries on a fixed
schedule.

**Validates: Requirements 13**

Design Principle:
CLS Consolidation tests whether abstractive compression improves the
performance-cost trade-off. It clusters semantically similar old memories
and generates compact summaries, then falls back to Type-Aware Decay if
still over budget.

Key Features:
- Fixed schedule: consolidation every 5 tasks (NOT trigger-on-overflow)
- Minimum cluster size: 3 memories
- Excludes architectural memories (Sacred tier)
- Falls back to Type-Aware Decay if still over budget after consolidation

Frozen Invariants:
- Uses shared_retrieve() for identical retrieval scoring (Invariant #5)
- Consolidation schedule is FIXED every 5 tasks (Invariant #9)
- Min cluster size = 3 (Invariant #9)
"""

import logging
from collections import defaultdict
from typing import TYPE_CHECKING, Any

import numpy as np
from openai import OpenAI

from ..retriever import shared_retrieve
from .base import MemoryPolicy

if TYPE_CHECKING:
    from ..record import MemoryRecord
    from ..store import MemoryStore

logger = logging.getLogger(__name__)


class CLSConsolidationPolicy(MemoryPolicy):
    """CLS Consolidation policy: cluster and consolidate old memories.

    This policy clusters semantically similar old memories and generates
    consolidated summaries on a fixed schedule (every 5 tasks). After
    consolidation, if still over budget, it falls back to Type-Aware Decay
    pruning.

    **Validates: Requirements 13**

    Acceptance Criteria:
    1. Uses shared_retrieve with identical scoring
    2. Stores all incoming records
    3. Triggers consolidation every 5 tasks on fixed schedule
    4. Selects candidates: ≥10 tasks old, not consolidated, not architectural
    5. Clusters by repo, files_touched, and embedding similarity (min size 3)
    6. Generates consolidated summaries with max 350 tokens
    7. Archives source memories and stores consolidated record
    8. Falls back to Type-Aware Decay if still over budget

    Attributes:
        name: Policy identifier "cls_consolidation"
        max_records: Maximum number of active records allowed
        consolidation_interval: Number of tasks between consolidations (5)
        min_cluster_size: Minimum memories required to form a cluster (3)
        max_summary_tokens: Maximum tokens for consolidated summary (350)
        old_memory_threshold: Minimum age in tasks for consolidation (10)
        similarity_threshold: Minimum cosine similarity for clustering (0.70)
        tasks_since_last_consolidation: Counter for fixed schedule

    Example:
        >>> policy = CLSConsolidationPolicy(max_records=100)
        >>> memories = policy.retrieve(task, store, top_k=5, token_budget=2000)
        >>> policy.write(store, record)
        >>> policy.maintain(store)  # Consolidates every 5 tasks
    """

    name = "cls_consolidation"

    # Frozen parameters (Requirement 13, Design §Policy 5)
    CONSOLIDATION_INTERVAL = 5
    MIN_CLUSTER_SIZE = 3
    MAX_SUMMARY_TOKENS = 350
    OLD_MEMORY_THRESHOLD = 10
    SIMILARITY_THRESHOLD = 0.70

    # Type-Aware Decay parameters for fallback
    TYPE_PARAMS = {
        "architectural": (1.0, 0.05),
        "api_change": (0.8, 0.15),
        "bug_fix": (0.6, 0.25),
        "test_update": (0.4, 0.35),
        "config": (0.3, 0.40),
    }
    FREQUENCY_EXPONENT = 0.5

    def __init__(self, max_records: int):
        """Initialize CLS Consolidation policy.

        Args:
            max_records: Maximum number of active records allowed
        """
        self.max_records = max_records
        self._tasks_since_last_consolidation = 0
        self._openai_client: OpenAI | None = None

    @property
    def openai_client(self) -> OpenAI:
        """Lazy initialization of OpenAI client."""
        if self._openai_client is None:
            self._openai_client = OpenAI()
        return self._openai_client

    def retrieve(
        self,
        task: Any,
        memory_store: "MemoryStore",
        top_k: int,
        token_budget: int
    ) -> list["MemoryRecord"]:
        """Retrieve relevant memories using shared_retrieve.

        Uses the shared retrieval function to ensure identical scoring
        across all policies.

        **Validates: Requirements 13.1**

        Args:
            task: The current task requiring memory retrieval
            memory_store: The persistent memory storage backend
            top_k: Maximum number of memories to retrieve
            token_budget: Maximum total tokens for retrieved memories

        Returns:
            List of MemoryRecord objects sorted ascending by relevance
            (best item LAST)
        """
        # shared_retrieve returns list[tuple[float, MemoryRecord]]
        # We need to extract just the MemoryRecord objects
        scored_memories = shared_retrieve(task, memory_store, top_k, token_budget)
        return [record for _, record in scored_memories]

    def write(self, memory_store: "MemoryStore", record: "MemoryRecord") -> None:
        """Store all incoming memory records.

        **Validates: Requirements 13.2**

        Args:
            memory_store: The persistent memory storage backend
            record: The MemoryRecord to store
        """
        memory_store.add(record)
        logger.debug(f"Stored memory {record.memory_id} for task {record.task_id}")

    def maintain(self, memory_store: "MemoryStore") -> None:
        """Perform consolidation on fixed schedule, then fallback pruning.

        This method:
        1. Increments task counter
        2. If counter reaches 5, triggers consolidation
        3. Selects old, non-consolidated, non-architectural memories
        4. Clusters by repo, files, and embedding similarity
        5. Generates consolidated summaries for clusters
        6. Archives source memories
        7. Falls back to Type-Aware Decay if still over budget

        **Validates: Requirements 13.3-13.8**

        Args:
            memory_store: The persistent memory storage backend
        """
        # Increment task counter
        self._tasks_since_last_consolidation += 1

        # Check if consolidation should trigger (fixed schedule)
        if self._tasks_since_last_consolidation >= self.CONSOLIDATION_INTERVAL:
            logger.info(
                f"Triggering consolidation (every {self.CONSOLIDATION_INTERVAL} tasks)"
            )
            self._consolidate(memory_store)
            self._tasks_since_last_consolidation = 0

        # Fallback to Type-Aware Decay if still over budget
        if memory_store.count_active() > self.max_records:
            logger.info(
                f"Still over budget after consolidation "
                f"({memory_store.count_active()} > {self.max_records}), "
                f"falling back to Type-Aware Decay"
            )
            self._fallback_prune(memory_store)

    def _consolidate(self, memory_store: "MemoryStore") -> None:
        """Perform consolidation: cluster and summarize old memories.

        **Validates: Requirements 13.4-13.7**

        Args:
            memory_store: The persistent memory storage backend
        """
        active = memory_store.active_records()
        if not active:
            logger.debug("No active memories to consolidate")
            return

        # Get current step for age calculation
        current_step = max(r.sequence_index for r in active)

        # Select candidates: ≥10 tasks old, not consolidated, not architectural
        candidates = [
            r for r in active
            if (current_step - r.sequence_index) >= self.OLD_MEMORY_THRESHOLD
            and not r.is_consolidated
            and r.memory_type != "architectural"
        ]

        if len(candidates) < self.MIN_CLUSTER_SIZE:
            logger.debug(
                f"Not enough candidates for consolidation "
                f"({len(candidates)} < {self.MIN_CLUSTER_SIZE})"
            )
            return

        logger.info(
            f"Found {len(candidates)} consolidation candidates "
            f"(age ≥ {self.OLD_MEMORY_THRESHOLD} tasks, "
            f"not consolidated, not architectural)"
        )

        # Cluster by repo, files_touched, and embedding similarity
        clusters = self._cluster_memories(candidates, memory_store)

        if not clusters:
            logger.debug("No clusters formed (all below minimum size)")
            return

        logger.info(f"Formed {len(clusters)} clusters for consolidation")

        # Generate consolidated summaries for each cluster
        for cluster_id, cluster_memories in enumerate(clusters, start=1):
            logger.info(
                f"Consolidating cluster {cluster_id}/{len(clusters)} "
                f"with {len(cluster_memories)} memories"
            )
            self._consolidate_cluster(cluster_memories, memory_store, current_step)

    def _cluster_memories(
        self,
        candidates: list["MemoryRecord"],
        memory_store: "MemoryStore"
    ) -> list[list["MemoryRecord"]]:
        """Cluster memories by repo, files_touched, and embedding similarity.

        Algorithm:
        1. Group by repository (same-repo clustering)
        2. Within each repo, group by overlapping files_touched
        3. Within each file group, cluster by embedding similarity
        4. Filter clusters to minimum size

        **Validates: Requirements 13.5**

        Args:
            candidates: List of candidate memories for consolidation
            memory_store: The persistent memory storage backend

        Returns:
            List of clusters, where each cluster is a list of MemoryRecord
        """
        # Group by repository
        repo_groups = defaultdict(list)
        for record in candidates:
            repo_groups[record.repo].append(record)

        all_clusters = []

        for repo, repo_memories in repo_groups.items():
            logger.debug(f"Clustering {len(repo_memories)} memories from {repo}")

            # Group by overlapping files_touched
            file_groups = self._group_by_files(repo_memories)

            # Within each file group, cluster by embedding similarity
            for file_group in file_groups:
                if len(file_group) < self.MIN_CLUSTER_SIZE:
                    continue

                # Cluster by embedding similarity
                similarity_clusters = self._cluster_by_similarity(
                    file_group,
                    memory_store
                )

                # Add clusters that meet minimum size
                for cluster in similarity_clusters:
                    if len(cluster) >= self.MIN_CLUSTER_SIZE:
                        all_clusters.append(cluster)

        return all_clusters

    def _group_by_files(
        self,
        memories: list["MemoryRecord"]
    ) -> list[list["MemoryRecord"]]:
        """Group memories by overlapping files_touched.

        Memories are grouped together if they share at least one file.

        Args:
            memories: List of memories to group

        Returns:
            List of file groups, where each group is a list of MemoryRecord
        """
        # Build file -> memories mapping
        file_to_memories = defaultdict(list)
        for record in memories:
            for file in record.files_touched:
                file_to_memories[file].append(record)

        # Build groups using union-find approach
        memory_to_group: dict[str, int] = {}
        groups: list[list[MemoryRecord]] = []

        for record in memories:
            # Find all groups this memory could belong to
            candidate_groups = set()
            for file in record.files_touched:
                for other in file_to_memories[file]:
                    if other.memory_id in memory_to_group:
                        candidate_groups.add(memory_to_group[other.memory_id])

            if not candidate_groups:
                # Create new group
                group_id = len(groups)
                groups.append([record])
                memory_to_group[record.memory_id] = group_id
            else:
                # Merge into first candidate group
                group_id = min(candidate_groups)
                groups[group_id].append(record)
                memory_to_group[record.memory_id] = group_id

                # Merge other candidate groups
                for other_group_id in candidate_groups:
                    if other_group_id != group_id:
                        groups[group_id].extend(groups[other_group_id])
                        for mem in groups[other_group_id]:
                            memory_to_group[mem.memory_id] = group_id
                        groups[other_group_id] = []

        # Filter out empty groups
        return [g for g in groups if g]

    def _cluster_by_similarity(
        self,
        memories: list["MemoryRecord"],
        memory_store: "MemoryStore"
    ) -> list[list["MemoryRecord"]]:
        """Cluster memories by embedding similarity.

        Uses agglomerative clustering with cosine similarity threshold.

        Args:
            memories: List of memories to cluster
            memory_store: The persistent memory storage backend

        Returns:
            List of similarity clusters
        """
        if len(memories) < self.MIN_CLUSTER_SIZE:
            return []

        # Get embedding vectors for all memories
        vectors = []
        valid_memories = []

        for record in memories:
            try:
                vector_id = int(record.embedding_vector_id)
                # Retrieve vector from FAISS
                vector = memory_store.faiss_index.reconstruct(vector_id)
                vectors.append(vector)
                valid_memories.append(record)
            except (ValueError, TypeError, RuntimeError) as e:
                logger.warning(
                    f"Could not retrieve vector for {record.memory_id}: {e}"
                )
                continue

        if len(valid_memories) < self.MIN_CLUSTER_SIZE:
            return []

        # Compute pairwise cosine similarities
        vectors_array = np.array(vectors)
        # Normalize vectors
        norms = np.linalg.norm(vectors_array, axis=1, keepdims=True)
        norms[norms == 0] = 1  # Avoid division by zero
        normalized = vectors_array / norms

        # Compute similarity matrix
        similarity_matrix = np.dot(normalized, normalized.T)

        # Simple agglomerative clustering
        clusters = [[i] for i in range(len(valid_memories))]
        cluster_to_memories = {i: [valid_memories[i]] for i in range(len(valid_memories))}

        while True:
            # Find most similar pair of clusters
            best_sim = -1
            best_pair = None

            for i in range(len(clusters)):
                if not clusters[i]:
                    continue
                for j in range(i + 1, len(clusters)):
                    if not clusters[j]:
                        continue

                    # Compute average similarity between clusters
                    sims = []
                    for idx_i in clusters[i]:
                        for idx_j in clusters[j]:
                            sims.append(similarity_matrix[idx_i, idx_j])

                    avg_sim = np.mean(sims)

                    if avg_sim > best_sim:
                        best_sim = avg_sim
                        best_pair = (i, j)

            # Stop if no pair exceeds threshold
            if best_sim < self.SIMILARITY_THRESHOLD or best_pair is None:
                break

            # Merge best pair
            i, j = best_pair
            clusters[i].extend(clusters[j])
            cluster_to_memories[i].extend(cluster_to_memories[j])
            clusters[j] = []
            cluster_to_memories[j] = []

        # Return non-empty clusters
        return [cluster_to_memories[i] for i in range(len(clusters)) if clusters[i]]

    def _consolidate_cluster(
        self,
        cluster: list["MemoryRecord"],
        memory_store: "MemoryStore",
        current_step: int
    ) -> None:
        """Generate consolidated summary for a cluster and archive sources.

        **Validates: Requirements 13.6-13.7**

        Args:
            cluster: List of memories to consolidate
            memory_store: The persistent memory storage backend
            current_step: Current sequence step
        """
        # Generate consolidated summary using LLM
        summary_record = self._generate_consolidated_summary(cluster, current_step)

        # Store consolidated record
        memory_store.add(summary_record)
        logger.info(
            f"Created consolidated memory {summary_record.memory_id} "
            f"from {len(cluster)} source memories"
        )

        # Archive source memories
        for source in cluster:
            memory_store.archive(
                memory_id=source.memory_id,
                reason="cls_consolidated",
                replacement_id=summary_record.memory_id,
                current_step=current_step
            )
            logger.debug(
                f"Archived source memory {source.memory_id} "
                f"(replaced by {summary_record.memory_id})"
            )

    def _generate_consolidated_summary(
        self,
        cluster: list["MemoryRecord"],
        current_step: int
    ) -> "MemoryRecord":
        """Generate consolidated summary using LLM.

        **Validates: Requirements 13.6**

        Args:
            cluster: List of memories to consolidate
            current_step: Current sequence step

        Returns:
            New MemoryRecord with consolidated summary
        """
        from ..record import MemoryRecord

        # Build consolidation prompt
        prompt = self._build_consolidation_prompt(cluster)

        # Call LLM to generate summary
        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are compressing coding-agent memories from a single repository."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0,
            max_tokens=self.MAX_SUMMARY_TOKENS
        )

        summary_text = response.choices[0].message.content

        # Extract common metadata from cluster
        repo = cluster[0].repo
        common_files = self._extract_common_files(cluster)
        source_ids = [r.memory_id for r in cluster]

        # Create consolidated memory record
        consolidated = MemoryRecord(
            memory_id=MemoryRecord.generate_id(),
            task_id=f"consolidated_{current_step}",
            repo=repo,
            sequence_index=current_step,
            memory_type="bug_fix",  # Default type for consolidated memories
            outcome="unknown",
            issue_summary=f"Consolidated summary of {len(cluster)} memories",
            patch_summary=summary_text or "",
            failure_summary=None,
            test_summary=None,
            files_touched=common_files,
            functions_touched=[],
            commands_run=[],
            retrieved_memory_ids_used=[],
            is_consolidated=True,
            source_memory_ids=source_ids if source_ids else []
        )

        return consolidated

    def _build_consolidation_prompt(self, cluster: list["MemoryRecord"]) -> str:
        """Build prompt for LLM consolidation.

        Args:
            cluster: List of memories to consolidate

        Returns:
            Prompt string for LLM
        """
        prompt_parts = [
            "Given several past task memories, produce one compact reusable memory.\n",
            "\nKeep: repository conventions, recurring files/functions, successful fix strategies,",
            "test commands, failure traps, assumptions proven wrong.\n",
            "\nRemove: duplicate details, irrelevant logs, one-off stack traces, exact patches",
            "unless the pattern is reusable.\n",
            f"\n=== {len(cluster)} Memories to Consolidate ===\n"
        ]

        for i, record in enumerate(cluster, start=1):
            prompt_parts.append(f"\n--- Memory {i} ---")
            prompt_parts.append(f"Type: {record.memory_type}")
            prompt_parts.append(f"Outcome: {record.outcome}")
            prompt_parts.append(f"Files: {', '.join(record.files_touched[:5])}")
            prompt_parts.append(f"\nIssue: {record.issue_summary[:200]}")
            if record.failure_summary:
                prompt_parts.append(f"Error: {record.failure_summary[:200]}")
            prompt_parts.append(f"Patch: {record.patch_summary[:200]}")

        prompt_parts.append("\n\n=== Generate Consolidated Summary ===")
        prompt_parts.append(f"Produce a compact summary (max {self.MAX_SUMMARY_TOKENS} tokens) that captures:")
        prompt_parts.append("- Common patterns across these memories")
        prompt_parts.append("- Recurring files and functions")
        prompt_parts.append("- Successful strategies")
        prompt_parts.append("- Common failure modes")
        prompt_parts.append("- Reusable insights")

        return "\n".join(prompt_parts)

    def _extract_common_files(self, cluster: list["MemoryRecord"]) -> list[str]:
        """Extract files that appear in multiple memories.

        Args:
            cluster: List of memories

        Returns:
            List of common files
        """
        file_counts: dict[str, int] = defaultdict(int)
        for record in cluster:
            for file in record.files_touched:
                file_counts[file] += 1

        # Return files that appear in at least 2 memories
        threshold = max(2, len(cluster) // 2)
        common = [f for f, count in file_counts.items() if count >= threshold]

        return sorted(common)[:10]  # Limit to top 10

    def _fallback_prune(self, memory_store: "MemoryStore") -> None:
        """Fall back to Type-Aware Decay pruning if still over budget.

        **Validates: Requirements 13.8**

        Args:
            memory_store: The persistent memory storage backend
        """
        active = memory_store.active_records()
        if len(active) <= self.max_records:
            return

        current_step = max(r.sequence_index for r in active)

        # Compute importance scores using Type-Aware Decay formula
        scored = []
        for r in active:
            base, decay = self.TYPE_PARAMS.get(r.memory_type, (0.3, 0.40))
            age = max(1, current_step - r.sequence_index)
            retrieval = r.use_count

            score = base * (age ** -decay) * ((1 + retrieval) ** self.FREQUENCY_EXPONENT)
            r.importance_score = score
            memory_store.update_importance_score(r.memory_id, score)
            scored.append((score, r))

        # Sort by score ascending (lowest first)
        scored.sort(key=lambda x: x[0])

        # Archive lowest-scoring until at or below max_records
        archived_count = 0
        while memory_store.count_active() > self.max_records and scored:
            _, victim = scored.pop(0)
            memory_store.archive(
                memory_id=victim.memory_id,
                reason="type_aware_decay_fallback",
                current_step=current_step
            )
            archived_count += 1

        logger.info(
            f"Fallback pruning archived {archived_count} memories "
            f"(now {memory_store.count_active()} active)"
        )
