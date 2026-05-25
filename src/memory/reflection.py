"""
Structured reflection step for memory record generation.

This module implements the post-task reflection step that generates structured
memory records from task execution traces. The reflection step:

1. Extracts key information from task trajectory (issue, patch, errors, tests)
2. Invokes the type classifier to assign memory_type
3. Constructs a complete MemoryRecord with all required fields
4. Passes the record to the active policy's write() method
5. Updates usage tracking for retrieved memories

Requirements: 15
Design: §9 Memory writing & reflection step
"""

import logging
from datetime import datetime
from typing import Any

from .classifier import classify_memory_type
from .record import MemoryRecord
from .store import MemoryStore
from src.errors import ClassifierError, ReflectionError, handle_classifier_failure, handle_reflection_failure

logger = logging.getLogger(__name__)


def reflect_and_write_memory(
    task: Any,
    trajectory: dict[str, Any],
    patch: str | None,
    evaluation_result: dict[str, Any],
    memory_store: MemoryStore,
    policy: Any,
    retrieved_memory_ids: list[str],
    sequence_index: int,
    model: str = "gpt-4o-mini",
    temperature: float = 0.0
) -> MemoryRecord | None:
    """Execute reflection step and write memory record.

    This is the main entry point for the reflection and memory writing workflow.
    It orchestrates the entire process from reflection to storage.

    Args:
        task: The task object containing task_id, repo, issue_text, etc.
        trajectory: Dictionary containing agent execution trace with:
                   - steps: list of action-observation pairs
                   - files_read: list of files inspected
                   - files_modified: list of files changed
                   - commands_run: list of commands executed
                   - test_output: final test execution output
        patch: The generated patch diff (None if no patch generated)
        evaluation_result: Dictionary containing:
                          - resolved: bool (pass/fail)
                          - error_message: str | None
                          - test_output: str | None
        memory_store: The persistent memory storage backend
        policy: The active memory policy instance
        retrieved_memory_ids: List of memory IDs that were shown to the agent
        sequence_index: Position of this task in the sequence
        model: Model to use for reflection LLM call (default: gpt-4o-mini)
        temperature: Temperature for reflection LLM call (default: 0.0)

    Returns:
        MemoryRecord if successfully created and written, None if reflection failed

    Raises:
        ReflectionError: If reflection step fails critically
        ClassifierError: If type classification fails (propagated from classifier)

    Requirements:
        - Requirement 15.1: Extract structured information from trajectory
        - Requirement 15.2: Record files_touched, functions_touched, commands_run
        - Requirement 15.3: Record retrieved_memory_ids_used
        - Requirement 15.4: Invoke type classifier
        - Requirement 15.5: Fail entirely if classifier unavailable
        - Requirement 15.6: Ensure type assignment before write

    Design: §9.1-9.4 Reflection step
    """
    try:
        # Step 1: Extract structured information from trajectory
        logger.info(f"Starting reflection for task {task.task_id}")

        reflection_data = _extract_reflection_data(
            task=task,
            trajectory=trajectory,
            patch=patch,
            evaluation_result=evaluation_result,
            model=model,
            temperature=temperature
        )

        # Step 2: Invoke type classifier (CRITICAL - must succeed)
        logger.info(f"Classifying memory type for task {task.task_id}")

        try:
            memory_type = classify_memory_type(
                issue_summary=reflection_data["issue_summary"],
                patch_summary=reflection_data["patch_summary"],
                files_touched=reflection_data["files_touched"],
                functions_touched=reflection_data["functions_touched"],
                task_id=task.task_id
            )
        except ClassifierError as e:
            # Requirement 15.5: Fail entirely if classifier unavailable
            logger.error(
                f"Type classification failed for task {task.task_id}: {e}"
            )
            raise ReflectionError(
                f"Reflection failed: type classification unavailable for task {task.task_id}"
            ) from e

        # Step 3: Construct MemoryRecord with type assignment
        logger.info(
            f"Constructing memory record for task {task.task_id} "
            f"with type {memory_type}"
        )

        record = _construct_memory_record(
            task=task,
            reflection_data=reflection_data,
            memory_type=memory_type,
            retrieved_memory_ids=retrieved_memory_ids,
            sequence_index=sequence_index
        )

        # Step 4: Write memory record via policy
        logger.info(
            f"Writing memory record {record.memory_id} via policy {policy.name}"
        )

        policy.write(memory_store, record)

        # Step 5: Update usage tracking for retrieved memories
        # This happens AFTER writing the new memory, so we know the task outcome
        task_succeeded = evaluation_result.get("resolved", False)

        _update_retrieved_memory_usage(
            memory_store=memory_store,
            retrieved_memory_ids=retrieved_memory_ids,
            sequence_index=sequence_index,
            task_succeeded=task_succeeded
        )

        logger.info(
            f"Successfully completed reflection and memory write for task {task.task_id}"
        )

        return record

    except ClassifierError:
        # Re-raise classifier errors (already logged)
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error during reflection for task {task.task_id}: {e}",
            exc_info=True
        )
        raise ReflectionError(
            f"Reflection failed unexpectedly for task {task.task_id}: {e}"
        ) from e


def _extract_reflection_data(
    task: Any,
    trajectory: dict[str, Any],
    patch: str | None,
    evaluation_result: dict[str, Any],
    model: str,
    temperature: float
) -> dict[str, Any]:
    """Extract structured reflection data from task execution.

    This function performs the actual reflection LLM call to generate
    structured summaries from the raw task execution trace.

    Args:
        task: Task object
        trajectory: Agent execution trace
        patch: Generated patch diff
        evaluation_result: Evaluation results
        model: Model for reflection LLM call
        temperature: Temperature for reflection LLM call

    Returns:
        Dictionary containing:
        - issue_summary: str
        - patch_summary: str
        - failure_summary: str | None
        - test_summary: str | None
        - files_touched: list[str]
        - functions_touched: list[str]
        - commands_run: list[str]
        - outcome: str (pass | fail | partial | unknown)

    Design: §9.2 Reflection output (Structured Output)
    """
    # TODO: Implement actual LLM call for structured reflection
    # For now, extract basic information from trajectory

    # Extract files touched
    files_touched = []
    if "files_modified" in trajectory:
        files_touched.extend(trajectory["files_modified"])
    if "files_read" in trajectory:
        # Add unique files that were read but not modified
        for f in trajectory["files_read"]:
            if f not in files_touched:
                files_touched.append(f)

    # Extract commands run
    commands_run = trajectory.get("commands_run", [])

    # Extract functions touched (TODO: parse from patch or trajectory)
    functions_touched = trajectory.get("functions_touched", [])

    # Determine outcome
    resolved = evaluation_result.get("resolved", False)
    if resolved:
        outcome = "pass"
    elif patch is not None:
        outcome = "fail"  # Patch generated but tests failed
    else:
        outcome = "unknown"  # No patch generated

    # Generate summaries (simplified for now - TODO: use LLM)
    issue_summary = task.issue_text[:200] + "..." if len(task.issue_text) > 200 else task.issue_text

    if patch:
        patch_summary = f"Modified {len(files_touched)} files"
        if patch:
            # Extract first few lines of patch for summary
            patch_lines = patch.split("\n")[:5]
            patch_summary = "\n".join(patch_lines)
    else:
        patch_summary = "No patch generated"

    failure_summary = None
    if not resolved and evaluation_result.get("error_message"):
        failure_summary = evaluation_result["error_message"]

    test_summary = None
    if "test_output" in evaluation_result and evaluation_result["test_output"]:
        test_output = evaluation_result["test_output"]
        # Extract last few lines of test output
        test_lines = test_output.split("\n")[-10:]
        test_summary = "\n".join(test_lines)

    return {
        "issue_summary": issue_summary,
        "patch_summary": patch_summary,
        "failure_summary": failure_summary,
        "test_summary": test_summary,
        "files_touched": files_touched,
        "functions_touched": functions_touched,
        "commands_run": commands_run,
        "outcome": outcome
    }


def _construct_memory_record(
    task: Any,
    reflection_data: dict[str, Any],
    memory_type: str,
    retrieved_memory_ids: list[str],
    sequence_index: int
) -> MemoryRecord:
    """Construct a complete MemoryRecord from reflection data.

    Args:
        task: Task object
        reflection_data: Extracted reflection data
        memory_type: Classified memory type (from classifier)
        retrieved_memory_ids: Memory IDs shown to agent
        sequence_index: Position in sequence

    Returns:
        Complete MemoryRecord ready for storage

    Requirements: 3 (Memory Record Structure)
    Design: §2 Components and Interfaces - MemoryRecord Dataclass
    """
    # Generate unique memory ID
    memory_id = MemoryRecord.generate_id()

    # Construct embedding text (Issue + Error + Diff only, < 7500 tokens)
    # Requirement 4: Embedding payload construction
    embedding_text = _construct_embedding_text(
        issue_summary=reflection_data["issue_summary"],
        failure_summary=reflection_data["failure_summary"],
        patch_summary=reflection_data["patch_summary"]
    )

    # Create MemoryRecord
    record = MemoryRecord(
        # Identity
        memory_id=memory_id,
        task_id=task.task_id,
        repo=task.repo,
        sequence_index=sequence_index,

        # Type & outcome (orthogonal axes)
        memory_type=memory_type,
        outcome=reflection_data["outcome"],

        # Content (preprocessed for embedding)
        issue_summary=reflection_data["issue_summary"],
        patch_summary=reflection_data["patch_summary"],
        failure_summary=reflection_data["failure_summary"],
        test_summary=reflection_data["test_summary"],

        # Structural metadata
        files_touched=reflection_data["files_touched"],
        functions_touched=reflection_data["functions_touched"],
        commands_run=reflection_data["commands_run"],

        # Retrieval provenance
        retrieved_memory_ids_used=retrieved_memory_ids,

        # Embedding (vector_id will be set by MemoryStore.add())
        embedding_text=embedding_text,
        embedding_vector_id="",  # Set by store

        # Size (will be computed by store)
        token_length=0,  # Set by store
        raw_trace_ref=None,  # TODO: Set if trajectory saved to disk

        # Usage tracking (initialized to 0)
        use_count=0,
        last_retrieved_at_step=None,
        success_after_retrieval_count=0,
        failure_after_retrieval_count=0,

        # Scoring / lifecycle (initialized)
        importance_score=0.0,
        is_consolidated=False,
        source_memory_ids=None,
        is_archived=False,
        archived_reason=None,
        archived_at_step=None,

        # Timestamps (auto-generated)
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat()
    )

    return record


def _construct_embedding_text(
    issue_summary: str,
    failure_summary: str | None,
    patch_summary: str
) -> str:
    """Construct embedding text from Issue + Error + Diff only.

    Requirement 4: Embedding payload = [Issue + Final Error + Final Diff] only

    Args:
        issue_summary: Issue description
        failure_summary: Error message (if any)
        patch_summary: Patch diff summary

    Returns:
        Concatenated embedding text (will be validated < 7500 tokens by store)

    Design: §4 Embedding payload construction
    """
    parts = [f"Issue: {issue_summary}"]

    if failure_summary:
        parts.append(f"Error: {failure_summary}")

    parts.append(f"Patch: {patch_summary}")

    return "\n\n".join(parts)


def _update_retrieved_memory_usage(
    memory_store: MemoryStore,
    retrieved_memory_ids: list[str],
    sequence_index: int,
    task_succeeded: bool
) -> None:
    """Update usage tracking for memories that were retrieved.

    This function updates use_count, last_retrieved_at_step, and
    success/failure counts for all memories that were shown to the agent.

    Args:
        memory_store: Memory storage backend
        retrieved_memory_ids: List of memory IDs that were retrieved
        sequence_index: Current sequence step
        task_succeeded: Whether the task succeeded after using these memories

    Requirements:
        - Requirement 3.7: Usage tracking fields
        - Requirement 15: Update usage tracking for retrieved memories

    Notes:
        - These counts are ASSOCIATED with outcomes, not causal
        - Updates happen AFTER the new memory is written

    Design: §2 MemoryStore Interface - update_usage()
    """
    for memory_id in retrieved_memory_ids:
        try:
            memory_store.update_usage(
                memory_id=memory_id,
                step=sequence_index,
                task_succeeded=task_succeeded
            )
            logger.debug(
                f"Updated usage for memory {memory_id} at step {sequence_index} "
                f"(task_succeeded={task_succeeded})"
            )
        except Exception as e:
            # Log but don't fail the entire reflection if usage update fails
            logger.warning(
                f"Failed to update usage for memory {memory_id}: {e}"
            )
