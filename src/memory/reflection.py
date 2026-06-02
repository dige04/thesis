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

from pydantic import BaseModel, ValidationError

from src.config.llm_factory import get_chat_client
from src.errors import (
    ClassifierError,
    ReflectionError,
)

from .classifier import classify_memory_type
from .record import MemoryRecord
from .store import MemoryStore

logger = logging.getLogger(__name__)


class ReflectionSummary(BaseModel):
    """Structured reflection output produced by the reflection LLM call.

    Mirrors the JSON schema in THESIS_FINAL_v5.md §9.2 — EXCEPT ``outcome`` and
    ``files_touched``, which are computed deterministically by the caller and
    are NOT requested from the model (outcome comes from evaluation_result;
    files_touched from the trajectory). ``functions_touched`` is provided by the
    LLM here but the caller falls back to the trajectory list when empty.

    All summary fields are optional/nullable: a degraded (partial) summary is
    still useful, and downstream the classifier is the only must-succeed step.
    """

    issue_summary: str
    patch_summary: str
    failure_summary: str | None = None
    test_summary: str | None = None
    functions_touched: list[str] = []


# Appended to the reflection system prompt. Ollama's OpenAI-compatible endpoint
# ignores the OpenAI json_schema response_format (ollama/ollama #10001), so we
# use plain JSON mode + explicit schema instructions + Pydantic validation
# instead of beta.chat.completions.parse (deviation D4, see CLAUDE.md). This
# matches the established pattern in src/memory/classifier.py.
_REFLECTION_JSON_INSTRUCTIONS = (
    "\n\nRespond with ONLY a JSON object of exactly this shape "
    "(no markdown fences, no commentary):\n"
    '{"issue_summary": "<1-2 sentence summary of the issue/problem>", '
    '"patch_summary": "<1-2 sentence summary of what the patch changed>", '
    '"failure_summary": "<summary of the failure, or null if the task passed>", '
    '"test_summary": "<summary of tests added/run and their result, or null>", '
    '"functions_touched": ["<function or method name>", ...]}'
)

_REFLECTION_SYSTEM_PROMPT = (
    "You are a reflection assistant for a research system studying memory "
    "management in AI coding agents. Given the trace of a single coding task "
    "(the issue, the patch diff, the files modified, the commands run, and the "
    "test output), produce a compact STRUCTURED summary that another agent can "
    "later retrieve and reuse.\n\n"
    "Summarize faithfully and concisely:\n"
    "- issue_summary: what problem the task was trying to solve.\n"
    "- patch_summary: what the patch actually changed (key files / mechanism).\n"
    "- failure_summary: the failure mode if the task did not pass; null otherwise.\n"
    "- test_summary: which tests were added/run and their outcome; null if none.\n"
    "- functions_touched: the functions/methods the patch modified.\n\n"
    "Do NOT speculate about whether the task ultimately passed or failed — that "
    "is recorded separately. Base everything strictly on the provided trace."
) + _REFLECTION_JSON_INSTRUCTIONS


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

    Behaviour:
        Files touched, commands run, and outcome are derived DETERMINISTICALLY
        (files/commands from the trajectory; outcome from evaluation_result) and
        are never delegated to the LLM. The free-text summaries and
        functions_touched come from a real reflection LLM call
        (:func:`_llm_reflection_summary`). On ANY LLM failure (transport error,
        empty/invalid JSON) we fall back to a naive heuristic summary and log a
        warning — a degraded summary is preferable to failing the task, since the
        downstream classifier is the only must-succeed step.
    """
    # --- Deterministic fields (never from the LLM) ---------------------------
    # Files touched: modified first, then any read-but-not-modified files.
    files_touched: list[str] = []
    if "files_modified" in trajectory:
        files_touched.extend(trajectory["files_modified"])
    if "files_read" in trajectory:
        for f in trajectory["files_read"]:
            if f not in files_touched:
                files_touched.append(f)

    commands_run = trajectory.get("commands_run", [])
    trajectory_functions = trajectory.get("functions_touched", [])

    # Outcome is computed deterministically from evaluation_result — NOT asked
    # of the LLM (Invariant #10: labels are associated, not causal).
    resolved = evaluation_result.get("resolved", False)
    if resolved:
        outcome = "pass"
    elif patch is not None:
        outcome = "fail"  # Patch generated but tests failed
    else:
        outcome = "unknown"  # No patch generated

    # --- Naive heuristic summaries (used as the fallback) --------------------
    naive = _naive_reflection_summary(
        task=task,
        patch=patch,
        files_touched=files_touched,
        evaluation_result=evaluation_result,
        resolved=resolved,
    )

    # --- Real reflection LLM call (preferred) --------------------------------
    summary = _llm_reflection_summary(
        task=task,
        trajectory=trajectory,
        patch=patch,
        files_touched=files_touched,
        commands_run=commands_run,
        evaluation_result=evaluation_result,
        model=model,
        temperature=temperature,
    )

    if summary is not None:
        # functions_touched: prefer the LLM's list, else the trajectory's.
        functions_touched = summary.functions_touched or trajectory_functions
        return {
            "issue_summary": summary.issue_summary,
            "patch_summary": summary.patch_summary,
            "failure_summary": summary.failure_summary,
            "test_summary": summary.test_summary,
            "files_touched": files_touched,
            "functions_touched": functions_touched,
            "commands_run": commands_run,
            "outcome": outcome,
        }

    # Fallback: degraded naive extraction (warning already logged in helper).
    return {
        "issue_summary": naive["issue_summary"],
        "patch_summary": naive["patch_summary"],
        "failure_summary": naive["failure_summary"],
        "test_summary": naive["test_summary"],
        "files_touched": files_touched,
        "functions_touched": trajectory_functions,
        "commands_run": commands_run,
        "outcome": outcome,
    }


def _naive_reflection_summary(
    task: Any,
    patch: str | None,
    files_touched: list[str],
    evaluation_result: dict[str, Any],
    resolved: bool,
) -> dict[str, Any]:
    """Heuristic (non-LLM) reflection summaries used as the degraded fallback.

    This is the original truncation-based extraction, preserved verbatim so the
    task can still produce a (lower-quality) memory when the reflection LLM is
    unavailable.
    """
    issue_summary = (
        task.issue_text[:200] + "..."
        if len(task.issue_text) > 200
        else task.issue_text
    )

    if patch:
        # Extract first few lines of patch for summary.
        patch_lines = patch.split("\n")[:5]
        patch_summary = "\n".join(patch_lines)
    else:
        patch_summary = "No patch generated"

    failure_summary = None
    if not resolved and evaluation_result.get("error_message"):
        failure_summary = evaluation_result["error_message"]

    test_summary = None
    if evaluation_result.get("test_output"):
        test_output = evaluation_result["test_output"]
        # Extract last few lines of test output.
        test_lines = test_output.split("\n")[-10:]
        test_summary = "\n".join(test_lines)

    return {
        "issue_summary": issue_summary,
        "patch_summary": patch_summary,
        "failure_summary": failure_summary,
        "test_summary": test_summary,
    }


def _llm_reflection_summary(
    task: Any,
    trajectory: dict[str, Any],
    patch: str | None,
    files_touched: list[str],
    commands_run: list[str],
    evaluation_result: dict[str, Any],
    model: str,
    temperature: float,
) -> ReflectionSummary | None:
    """Call the reflection LLM and validate its structured JSON output.

    Returns a validated :class:`ReflectionSummary` on success, or ``None`` on
    ANY failure (transport/API error, empty/invalid JSON). On failure a warning
    is logged and the caller falls back to the naive heuristic — reflection must
    NOT raise (the classifier is the only must-succeed step). See §9.2 and the
    JSON-mode pattern in src/memory/classifier.py (deviation D4).
    """
    user_content = _build_reflection_input(
        task=task,
        trajectory=trajectory,
        patch=patch,
        files_touched=files_touched,
        commands_run=commands_run,
        evaluation_result=evaluation_result,
    )

    messages = [
        {"role": "system", "content": _REFLECTION_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    try:
        client = get_chat_client()
        # JSON mode (NOT beta.parse) + Pydantic validation. temperature is passed
        # through (frozen to 0 by the caller/config) per the classifier pattern.
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=temperature,
        )

        content = response.choices[0].message.content
        if not content or not isinstance(content, str):
            raise ValueError("reflection LLM returned empty/non-string content")

        return ReflectionSummary.model_validate_json(content)

    except (ValidationError, ValueError) as e:
        logger.warning(
            f"Reflection LLM produced invalid output for task "
            f"{getattr(task, 'task_id', '?')}; falling back to naive "
            f"extraction: {e}"
        )
        return None
    except Exception as e:
        logger.warning(
            f"Reflection LLM call failed for task "
            f"{getattr(task, 'task_id', '?')}; falling back to naive "
            f"extraction: {e}"
        )
        return None


def _build_reflection_input(
    task: Any,
    trajectory: dict[str, Any],
    patch: str | None,
    files_touched: list[str],
    commands_run: list[str],
    evaluation_result: dict[str, Any],
) -> str:
    """Assemble the user-message payload for the reflection LLM call.

    Bundles the issue text, patch diff, files modified, commands run, and test
    output from the trajectory / evaluation_result (§9.1 reflection input).
    """
    files_str = "\n".join(f"  - {f}" for f in files_touched) if files_touched else "  (none)"
    commands_str = "\n".join(f"  - {c}" for c in commands_run) if commands_run else "  (none)"
    patch_str = patch if patch else "(no patch generated)"
    test_output = evaluation_result.get("test_output") or "(no test output)"
    error_message = evaluation_result.get("error_message") or "(none)"

    return f"""Issue:
{task.issue_text}

Patch diff:
{patch_str}

Files modified:
{files_str}

Commands run:
{commands_str}

Test output:
{test_output}

Error message:
{error_message}

Summarize the above into the required JSON object."""


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

    # NOTE: embedding_text is deliberately left empty here. MemoryStore.add()
    # owns canonical embedding construction via embedding_utils.construct_
    # embedding_text, which enforces the <7500-token truncation (Invariant #4).
    # Pre-building it here would bypass that cap. The issue/failure/patch
    # summaries below give add() everything it needs.

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

        # Embedding (text + vector_id + token_length all set by MemoryStore.add())
        embedding_text="",
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
