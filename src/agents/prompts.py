"""Prompt construction for the coding agent.

This module implements prompt templates and context building functions
for the LangGraph-based coding agent.

Frozen Invariants (THESIS_FINAL_v5.md §0.1):
- Injection order = relevance-sorted, best item LAST (Lost-in-the-Middle fix) (Invariant #6)
- Temperature = 0 for all LLM calls (reproducibility) (Invariant #26)
- Memory format: [MEM-ID] (rank=X, sim=Y, age=Z, type=T) with content below

Requirements: 7, 14
Design: §4.5 Prompt Structure, §9 Coding Agent Implementation
"""

import logging
from typing import Any

from ..memory.record import MemoryRecord

logger = logging.getLogger(__name__)


# System prompt for the coding agent (matches THESIS_FINAL_v5.md §4.5)
SYSTEM_PROMPT = """You are an autonomous software-engineering agent. Solve the GitHub issue by EDITING the repository.

You have a HARD budget of {max_steps} steps (tool calls), after which you are force-stopped. The budget is scarce — spend it on EDITING, not exploring:
- First few steps: locate the file(s) to change with search_code / read_file.
- Within the FIRST HALF of your budget you MUST have made at least one code edit (edit_file or write_file).
- Then, if steps remain, run_tests ONCE to verify and fix if needed, then call finish.
- NEVER end with no changes: a run that produces an empty patch scores ZERO. If you are unsure, make your best-guess MINIMAL edit before the budget runs out — a plausible attempt beats no patch.
- Use run_command SPARINGLY. Prefer read_file/edit_file over shell exploration; do not burn steps grepping and running ad-hoc python.

Retrieved memories may be stale or wrong. Prefer direct evidence from the current repository. Do not blindly copy old solutions.

Tools:
- read_file(path, start_line, end_line), write_file(path, content), edit_file(path, diff)
- search_code(query), list_files(path)
- run_command(command)  # sparingly
- run_tests(test_command), finish

Read the range around a search_code hit. Lines are shown as `N<TAB>...` — NEVER include the `N<TAB>` prefix in edit_file diffs or write_file content.

Re-read the exact lines with read_file before editing them. Prefer write_file with full new contents for small/whole-file changes (no diff syntax needed). Use ONLY the provided tools — there is no shell `grep`/`sed`/`get_patch`; use search_code and run_command.

edit_file takes a STANDARD unified diff (with `@@` hunk headers and exact context lines, as `git apply` expects). If edit_file reports it could not apply your diff, do NOT retry the same diff — switch to write_file with the full new file contents.

Paths may be repo-relative (e.g. "src/pkg/mod.py") or absolute ("/testbed/..."). Make MINIMAL changes — modify only what the issue requires. Respond with tool calls, not prose.
"""


# Template for rendering retrieved memories in the prompt
# Format matches THESIS_FINAL_v5.md §4.5: [MEM-ID] (rank=X, sim=Y, age=Z, type=T)
MEMORY_BLOCK_HEADER = """
RETRIEVED MEMORY:
"""


# Template for rendering a single memory entry
# Format: [MEM-ID] (rank=X, sim=Y, age=Z, type=T)
# Content follows on next lines
MEMORY_ENTRY_TEMPLATE = """[{memory_id}] (rank={rank}, sim={similarity:.2f}, age={age}, type={memory_type})
{content}
"""


# Template for the task body (matches THESIS_FINAL_v5.md §4.5)
TASK_TEMPLATE = """
TASK:
Repository: {repo}
Base commit: {base_commit}
Issue:
{issue_text}
"""


def build_prompt_context(
    task: Any,
    scored_memories: list[tuple[float, MemoryRecord]],
    current_step: int,
    max_steps: int = 20
) -> str:
    """Build the complete prompt context for the agent.

    This function constructs the agent prompt by:
    1. Including retrieved memories sorted ascending (best LAST)
    2. Rendering each memory with format: [MEM-ID] (rank=X, sim=Y, age=Z, type=T)
    3. Including the task body after the memory block

    Memory Injection Format (FROZEN INVARIANT):
    ```
    Retrieved Memories (sorted by relevance, most relevant last):

    Memory #1 (rank: 5, similarity: 0.65, age: 3 tasks, type: bug_fix)
    [memory content]

    Memory #2 (rank: 4, similarity: 0.72, age: 1 task, type: api_change)
    [memory content]

    ...

    Memory #5 (rank: 1, similarity: 0.89, age: 2 tasks, type: bug_fix)
    [memory content]

    Current Task:
    [task body]
    ```

    Args:
        task: Task object with attributes:
            - task_id: Task identifier
            - repo: Repository name
            - base_commit: Git commit hash
            - issue_text: GitHub issue description
            - sequence_index: Position in sequence
        scored_memories: List of (similarity_score, MemoryRecord) tuples,
                        sorted ascending (best LAST for Lost-in-the-Middle mitigation)
        current_step: Current step number in the sequence (for calculating age)
        max_steps: Maximum steps allowed (default: 20)

    Returns:
        Complete prompt string ready for agent execution

    Notes:
        - Assumes scored_memories is already sorted ascending (best LAST)
        - Requirement 7: Highest-relevance memory injected last, immediately before task body
        - Format matches THESIS_FINAL_v5.md §4.5: [MEM-ID] (rank=X, sim=Y, age=Z, type=T)
        - Rank 1 = HIGHEST relevance (injected LAST, closest to task)
        - Rank N = LOWEST relevance (injected FIRST, farthest from task)
        - Age is calculated as (current_step - memory.sequence_index)

    Frozen Invariants:
        - Injection order: best item LAST (Lost-in-the-Middle mitigation)
        - Memory format: [MEM-ID] (rank=X, sim=Y, age=Z, type=T)
        - Best memory has rank=1 and appears LAST in the list

    Example:
        >>> task = Task(task_id="django-123", repo="django/django", issue_text="Fix bug")
        >>> memories = [(0.7, mem1), (0.8, mem2), (0.9, mem3)]  # ascending
        >>> prompt = build_prompt_context(task, memories, current_step=10)
        >>> # mem1 appears first (rank 3, lowest relevance)
        >>> # mem3 appears last (rank 1, highest relevance, immediately before task)
    """
    # Build memory block if memories are provided
    memory_block = ""
    if scored_memories:
        memory_block = _format_memory_block(scored_memories, current_step)

    # Build task block
    task_block = TASK_TEMPLATE.format(
        repo=task.repo,
        base_commit=getattr(task, 'base_commit', 'HEAD'),
        issue_text=task.issue_text
    )

    # Build complete prompt with system instructions
    system_with_limits = SYSTEM_PROMPT.format(max_steps=max_steps)

    # Combine: system + memories (best LAST) + task
    # This ensures the highest-relevance memory is closest to the task body
    prompt = system_with_limits + memory_block + task_block

    logger.info(
        f"Built prompt context for task {task.task_id}: "
        f"{len(scored_memories)} memories, "
        f"{len(prompt)} chars"
    )

    return prompt


def _format_memory_block(
    scored_memories: list[tuple[float, MemoryRecord]],
    current_step: int
) -> str:
    """Format retrieved memories into a prompt block.

    Renders memories in ascending order of relevance (best LAST) with the format:
    [MEM-ID] (rank=X, sim=Y, age=Z, type=T)
    [memory content]

    CRITICAL: Rank numbering is INVERTED for Lost-in-the-Middle mitigation:
    - Rank 1 = HIGHEST relevance (appears LAST, closest to task)
    - Rank N = LOWEST relevance (appears FIRST, farthest from task)

    This matches THESIS_FINAL_v5.md §4.5 example:
    ```
    [MEM-0042] (rank=5, sim=0.61, age=12, type=test_update)    ← FIRST = lowest
    [MEM-0091] (rank=4, sim=0.68, age=3,  type=bug_fix)
    [MEM-0188] (rank=3, sim=0.72, age=7,  type=api_change)
    [MEM-0211] (rank=2, sim=0.78, age=1,  type=bug_fix)
    [MEM-0303] (rank=1, sim=0.84, age=2,  type=architectural)  ← LAST = highest
    ```

    Args:
        scored_memories: List of (score, MemoryRecord) tuples, sorted ascending
                        (best LAST for Lost-in-the-Middle mitigation)
        current_step: Current step number for calculating age

    Returns:
        Formatted memory block string

    Notes:
        - Renders memories in ascending order of relevance (best LAST)
        - Each memory includes metadata for traceability
        - Age calculated as (current_step - memory.sequence_index)
        - Rank is inverted: rank=1 is the BEST memory (appears LAST)
    """
    if not scored_memories:
        return ""

    memory_entries = []
    total = len(scored_memories)

    # Iterate in order (already sorted ascending - best LAST)
    # Assign ranks in REVERSE: last item gets rank=1 (highest relevance)
    for idx, (score, record) in enumerate(scored_memories):
        # Calculate age (how many tasks ago this memory was created)
        age = current_step - record.sequence_index

        # Calculate rank: INVERTED so rank=1 is the BEST (last) memory
        # If we have 5 memories: first gets rank=5, last gets rank=1
        rank = total - idx

        # Format this memory entry with the exact format from thesis
        entry = MEMORY_ENTRY_TEMPLATE.format(
            memory_id=record.memory_id,
            rank=rank,
            similarity=score,
            age=age,
            memory_type=record.memory_type,
            content=record.embedding_text.strip()
        )
        memory_entries.append(entry)

    # Join all entries and wrap in memory block header
    entries_text = "\n".join(memory_entries)
    return MEMORY_BLOCK_HEADER + entries_text


def get_system_prompt(max_steps: int = 20) -> str:
    """Get the system prompt for the coding agent.

    Args:
        max_steps: Maximum steps allowed (default: 20)

    Returns:
        System prompt string with max_steps filled in

    Notes:
        - This is the base system prompt used for all agent executions
        - Temperature=0 is enforced for reproducibility
        - Max steps limit is parameterized
    """
    return SYSTEM_PROMPT.format(max_steps=max_steps)


def format_step_message(step: int, action: str, observation: str) -> str:
    """Format a step message for the agent trajectory.

    Args:
        step: Step number
        action: Action taken by the agent
        observation: Observation/result from the action

    Returns:
        Formatted step message

    Notes:
        - Used for logging and trajectory construction
        - Does NOT include agent's private chain-of-thought
        - Only action summaries and observations (Requirement 18)
    """
    return f"Step {step}: {action}\nObservation: {observation}"


def validate_prompt_length(prompt: str, max_tokens: int = 100000) -> bool:
    """Validate that the prompt length is within acceptable limits.

    Args:
        prompt: The complete prompt string
        max_tokens: Maximum allowed tokens (default: 100k for GPT-4)

    Returns:
        True if prompt is within limits, False otherwise

    Notes:
        - Uses rough approximation: 1 token ≈ 4 characters
        - Actual tokenization may vary by model
        - This is a safety check to prevent excessive prompt lengths
    """
    # Rough approximation: 1 token ≈ 4 characters
    estimated_tokens = len(prompt) // 4

    if estimated_tokens > max_tokens:
        logger.warning(
            f"Prompt length exceeds limit: {estimated_tokens} > {max_tokens} tokens "
            f"({len(prompt)} chars)"
        )
        return False

    return True


# ============================================================================
# Node-Specific Prompt Templates
# ============================================================================
# These templates are used by specific nodes in the LangGraph agent

PLANNING_NODE_PROMPT = """Based on the issue description and retrieved memories, create a plan to solve this task.

Your plan should:
1. Identify the root cause of the issue
2. List the files that need to be modified
3. Outline the specific changes needed
4. Identify tests that should be run to verify the fix

Be specific and concrete. Use information from retrieved memories if relevant, but verify against the current codebase.
"""


EDITING_NODE_PROMPT = """Make the necessary code changes to implement your plan.

Guidelines:
- Make minimal, targeted changes
- Preserve existing code style and conventions
- Add comments only where necessary for clarity
- Ensure changes are syntactically correct

After editing, you should run tests to verify your changes.
"""


REPAIR_LOOP_PROMPT = """The tests failed. Analyze the error and fix the issue.

Error output:
{error_output}

Steps:
1. Understand why the tests failed
2. Identify what needs to be changed
3. Make the necessary corrections
4. Run tests again to verify

Be systematic and avoid making the same mistake twice.
"""


REFLECTION_NODE_PROMPT = """Reflect on the task execution and extract key learnings.

Provide:
1. A brief summary of the issue (2-3 sentences)
2. A summary of the changes made (what files, what modifications)
3. Any errors encountered and how they were resolved
4. Key insights or patterns that might be useful for future tasks

Be concise and focus on information that would be valuable for solving similar issues in the future.
"""


def get_planning_prompt() -> str:
    """Get the prompt for the planning node.

    Returns:
        Planning prompt string
    """
    return PLANNING_NODE_PROMPT


def get_editing_prompt() -> str:
    """Get the prompt for the editing node.

    Returns:
        Editing prompt string
    """
    return EDITING_NODE_PROMPT


def get_repair_prompt(error_output: str) -> str:
    """Get the prompt for the repair loop node.

    Args:
        error_output: The error message from failed tests

    Returns:
        Repair prompt string with error output filled in
    """
    return REPAIR_LOOP_PROMPT.format(error_output=error_output)


def get_reflection_prompt() -> str:
    """Get the prompt for the reflection node.

    Returns:
        Reflection prompt string
    """
    return REFLECTION_NODE_PROMPT
