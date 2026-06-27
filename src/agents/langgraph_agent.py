"""
LangGraph-based coding agent with 12 explicit nodes for SWE-Bench-CL task solving.

This module implements the core agent architecture with the following nodes:
1. task_setup: Initialize task state and environment
2. memory_retrieval: Retrieve relevant memories using pure cosine similarity
3. context_construction: Build prompt context with best memory LAST
4. planning: Generate high-level solution plan
5. code_search: Search codebase for relevant code
6. file_editing: Edit files to implement solution
7. test_execution: Run tests to verify solution
8. repair_loop: Fix errors and iterate
9. final_patch_generation: Generate final patch
10. reflection: Structured analysis of task execution
11. memory_write: Write memory record to store
12. memory_prune_or_consolidate: Apply policy maintenance

Frozen invariants:
- Max 20 steps per task (hard force-fail)
- Temperature=0 for all LLM calls (reproducibility)
- Best memory item injected LAST (Lost-in-the-Middle mitigation)
- Pure cosine retrieval (identical across all policies)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from langgraph.graph import END, StateGraph

from src.config.llm_factory import get_chat_client, main_model
from src.errors import UsageLimitError, is_usage_limit_error
from src.model_output import strip_reasoning

from .limit_tracker import LimitTracker, validate_temperature
from .prompts import build_prompt_context, get_system_prompt
from .tools import AgentTools, ContainerSession, tool_mode, _LEGACY_OBS_CAP

logger = logging.getLogger(__name__)

# Max characters of a tool observation fed back to the model / stored in the
# trajectory (keeps context bounded; trajectory stores action summaries +
# observations only — NO chain-of-thought, per v5 §11.3).
# Fixed mode: 12000, tail-preserving.  Legacy mode: 4000, plain head-truncation.
_MAX_OBS = 12000


def _truncate_obs(text: str, limit: int = _MAX_OBS, mode: str | None = None) -> str:
    """Truncate observation text to fit within context budget.

    mode=="legacy"  → plain head-truncation at 4000 chars (pre-task-3 behavior).
    mode=="fixed"   → tail-preserving at 12000 chars (default; post-task-3 behavior).
    mode==None      → resolved from AGENT_TOOL_MODE env var.
    """
    resolved = mode if mode in ("legacy", "fixed") else tool_mode()
    if resolved == "legacy":
        return text[:_LEGACY_OBS_CAP]
    # fixed: tail-preserving
    if len(text) <= limit:
        return text
    tmpl = "\n...[{} chars omitted]...\n"
    reserve = len(tmpl.format(len(text)))
    budget = max(0, limit - reserve)
    head = (budget * 2) // 3
    tail = budget - head
    omitted = len(text) - head - tail
    return (text[:head] + tmpl.format(omitted) + (text[len(text) - tail:] if tail else ""))[:limit]


# Appended to the v5 §4.5 prompt (which build_prompt_context already produces).
_TOOL_USE_SUFFIX = (
    "\n\nYou can inspect and modify the repository ONLY through the provided "
    "tools. Make the minimal edit that fixes the issue, optionally verify with "
    "run_tests, then call `finish`. Respond with tool calls, not prose."
)


def _tool(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def build_tool_schemas(mode: str | None = None) -> list[dict[str, Any]]:
    """Build the OpenAI-compatible tool schema list for the given mode.

    mode=="legacy"  → read_file schema has only {path} (no start_line/end_line).
    mode=="fixed"   → read_file schema includes start_line and end_line.
    mode==None      → resolved from AGENT_TOOL_MODE env var.

    All other tools are identical between modes.
    """
    resolved = mode if mode in ("legacy", "fixed") else tool_mode()
    if resolved == "legacy":
        read_file_schema = _tool(
            "read_file", "Read a file's contents.",
            {"path": {"type": "string"}}, ["path"],
        )
    else:
        read_file_schema = _tool(
            "read_file", "Read a file's contents. Pass start_line/end_line (1-indexed, "
            "inclusive) to read a range; lines are shown as `N<TAB>text`. Output is bounded; "
            "follow the 'call read_file(...) to continue' hint to page.",
            {"path": {"type": "string"},
             "start_line": {"type": "integer"}, "end_line": {"type": "integer"}}, ["path"],
        )
    return [
        read_file_schema,
        _tool("write_file", "Write (overwrite/create) a file.",
              {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),
        _tool("edit_file", "Apply a standard unified diff to a file via `git apply` "
              "(include the `@@ -a,b +c,d @@` hunk header and exact surrounding context "
              "lines). If it reports the diff could not be applied, fix the diff or use "
              "write_file with the full new file contents.",
              {"path": {"type": "string"}, "diff": {"type": "string"}}, ["path", "diff"]),
        _tool("search_code", "Regex-search the repository.",
              {"query": {"type": "string"}, "file_pattern": {"type": "string"}}, ["query"]),
        _tool("list_files", "List files under a directory (glob pattern).",
              {"path": {"type": "string"}, "pattern": {"type": "string"}}, []),
        _tool("run_command", "Run a shell command in the repo.", {"command": {"type": "string"}}, ["command"]),
        _tool("run_tests", "Run a test command in the repo.", {"test_command": {"type": "string"}}, ["test_command"]),
        _tool("finish", "Signal that the patch is complete.", {}, []),
    ]


# Module-level alias: fixed-mode schemas (default for all 144 production runs).
# Existing callers that import _TOOL_SCHEMAS directly continue to work unchanged.
_TOOL_SCHEMAS: list[dict[str, Any]] = build_tool_schemas("fixed")


@dataclass
class AgentState:
    """
    State object for the LangGraph agent execution.

    This state is passed between nodes and accumulates information
    throughout the task-solving process.
    """

    # Task information
    task_id: str = ""
    repo: str = ""
    base_commit: str = ""
    issue_text: str = ""
    sequence_index: int = 0

    # Retrieved memories (sorted ascending: best LAST)
    retrieved_memories: list[dict[str, Any]] = field(default_factory=list)
    retrieved_memory_ids: list[str] = field(default_factory=list)

    # Prompt context
    context: str = ""

    # Execution tracking
    step_count: int = 0
    tool_calls: int = 0
    test_runs: int = 0
    files_read: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    commands_run: list[str] = field(default_factory=list)

    # Limit tracker (monitors all execution limits)
    limit_tracker: LimitTracker | None = None

    # Trajectory (action-observation pairs)
    trajectory: list[dict[str, Any]] = field(default_factory=list)

    # Solution artifacts
    plan: str = ""
    patch: str = ""
    patch_generated: bool = False

    # Execution status
    finished: bool = False
    timeout: bool = False
    syntax_error: bool = False
    error_message: str | None = None

    # Evaluation result
    eval_result: dict[str, Any] | None = None

    # Memory record (generated during reflection)
    memory_record: dict[str, Any] | None = None

    # Why the ReAct loop ended (set by _run_react_loop at each exit).
    # One of: finished_tool | model_no_tool_calls | step_limit | wall_time |
    #         tool_call_limit | test_run_limit | llm_error
    # NOTE: UsageLimitError re-raises and does NOT set this field.
    termination_reason: str | None = None

    # Next node routing
    next_node: str = "planning"

    # Token usage accumulated across LLM calls in the ReAct loop
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class CodingAgent:
    """
    LangGraph-based coding agent with 12 explicit nodes.

    This agent solves SWE-Bench-CL tasks by:
    1. Retrieving relevant memories from the memory store
    2. Constructing a prompt with memories (best LAST)
    3. Planning a solution approach
    4. Searching code and editing files
    5. Running tests and repairing errors
    6. Generating a final patch
    7. Reflecting on the execution
    8. Writing memory records and applying policy maintenance

    Frozen invariants:
    - Max 20 steps per task (hard force-fail)
    - Temperature=0 for all LLM calls
    - Best memory item injected LAST
    """

    def __init__(
        self,
        memory_store: Any,
        policy: Any,
        config: dict[str, Any],
        task_env: Any,
    ):
        """
        Initialize the coding agent.

        Args:
            memory_store: Memory store instance for retrieval and writing
            policy: Memory policy instance for retrieval and maintenance
            config: Configuration dictionary with agent parameters
            task_env: Task environment manager for repository operations
        """
        self.memory_store = memory_store
        self.policy = policy
        self.config = config
        self.task_env = task_env

        # Extract configuration parameters
        self.max_steps = config.get("agent", {}).get("max_steps_per_task", 20)
        self.max_tool_calls = config.get("agent", {}).get("max_tool_calls_per_task", 80)
        self.max_test_runs = config.get("agent", {}).get("max_test_runs_per_task", 5)
        self.max_wall_time_seconds = config.get("agent", {}).get("max_wall_time_seconds", 1200)
        self.temperature = config.get("agent", {}).get("temperature", 0)
        # Optional reasoning level for the AGENT only (e.g. "high" on a thinking
        # model like deepseek-v4-flash). Passed to the chat call when set; omitted
        # otherwise (back-compat). Held constant across conditions (fixed factor).
        self.reasoning_effort = config.get("agent", {}).get("reasoning_effort")
        self.top_k = config.get("memory", {}).get("top_k", 5)
        self.max_context_tokens = config.get("memory", {}).get("max_context_tokens", 2000)

        # Validate frozen invariants
        if self.max_steps != 20:
            raise ValueError(
                f"FROZEN INVARIANT VIOLATION: max_steps must be 20, got {self.max_steps}"
            )
        validate_temperature(self.temperature)

        # Resolve tool-behavior mode once at construction time so all tool calls
        # in this run are consistent (A/B variant flag — Task 5c).
        self.resolved_tool_mode = tool_mode()

        # Build the LangGraph
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """
        Build the 12-node LangGraph agent structure.

        Returns:
            Compiled StateGraph ready for execution
        """
        workflow = StateGraph(AgentState)

        # Add all 12 nodes
        workflow.add_node("task_setup", self.task_setup)
        workflow.add_node("memory_retrieval", self.memory_retrieval)
        workflow.add_node("context_construction", self.context_construction)
        workflow.add_node("planning", self.planning)
        workflow.add_node("code_search", self.code_search)
        workflow.add_node("file_editing", self.file_editing)
        workflow.add_node("test_execution", self.test_execution)
        workflow.add_node("repair_loop", self.repair_loop)
        workflow.add_node("final_patch_generation", self.final_patch_generation)
        workflow.add_node("reflection", self.reflection)
        workflow.add_node("memory_write", self.memory_write)
        workflow.add_node("memory_prune_or_consolidate", self.memory_prune_or_consolidate)

        # Define edges (linear flow with conditional routing)
        workflow.set_entry_point("task_setup")
        workflow.add_edge("task_setup", "memory_retrieval")
        workflow.add_edge("memory_retrieval", "context_construction")
        workflow.add_edge("context_construction", "planning")

        # Main execution loop
        workflow.add_conditional_edges(
            "planning",
            self._route_from_planning,
            {
                "code_search": "code_search",
                "file_editing": "file_editing",
                "test_execution": "test_execution",
                "final_patch_generation": "final_patch_generation",
            }
        )

        workflow.add_conditional_edges(
            "code_search",
            self._route_from_code_search,
            {
                "file_editing": "file_editing",
                "planning": "planning",
                "final_patch_generation": "final_patch_generation",
            }
        )

        workflow.add_conditional_edges(
            "file_editing",
            self._route_from_file_editing,
            {
                "test_execution": "test_execution",
                "code_search": "code_search",
                "planning": "planning",
                "final_patch_generation": "final_patch_generation",
            }
        )

        workflow.add_conditional_edges(
            "test_execution",
            self._route_from_test_execution,
            {
                "repair_loop": "repair_loop",
                "final_patch_generation": "final_patch_generation",
            }
        )

        workflow.add_conditional_edges(
            "repair_loop",
            self._route_from_repair_loop,
            {
                "file_editing": "file_editing",
                "code_search": "code_search",
                "planning": "planning",
                "final_patch_generation": "final_patch_generation",
            }
        )

        # Post-execution flow
        workflow.add_edge("final_patch_generation", "reflection")
        workflow.add_edge("reflection", "memory_write")
        workflow.add_edge("memory_write", "memory_prune_or_consolidate")
        workflow.add_edge("memory_prune_or_consolidate", END)

        return workflow.compile()

    # ========================================================================
    # Node implementations
    # ========================================================================

    def task_setup(self, state: AgentState) -> AgentState:
        """
        Node 1: Initialize task state and environment.

        Sets up the task information and prepares the environment
        for execution. Initializes the LimitTracker for this task.
        """
        # Initialize limit tracker with configured limits
        state.limit_tracker = LimitTracker(
            max_steps=self.max_steps,
            max_tool_calls=self.max_tool_calls,
            max_test_runs=self.max_test_runs,
            max_wall_time_seconds=self.max_wall_time_seconds,
        )

        # Reset execution tracking
        state.step_count = 0
        state.tool_calls = 0
        state.test_runs = 0
        state.finished = False
        state.timeout = False

        return state

    def memory_retrieval(self, state: AgentState) -> AgentState:
        """
        Node 2: Retrieve relevant memories using pure cosine similarity.

        Uses the policy's retrieve method which MUST use shared_retrieve
        for all policies except No Memory. Retrieval scoring is identical
        across all 6 policies (pure cosine, no bonuses/penalties).
        """
        # Build task object for retrieval
        task = {
            "task_id": state.task_id,
            "repo": state.repo,
            "issue_text": state.issue_text,
            "sequence_index": state.sequence_index,
        }

        # Retrieve memories using policy (pure cosine, identical across policies)
        retrieved = self.policy.retrieve(
            task=task,
            memory_store=self.memory_store,
            top_k=self.top_k,
            token_budget=self.max_context_tokens,
        )

        # Store retrieved memories (already sorted ascending: best LAST).
        # policy.retrieve() returns list[tuple[float, MemoryRecord]].
        state.retrieved_memories = retrieved
        state.retrieved_memory_ids = [record.memory_id for _, record in retrieved]

        return state

    def context_construction(self, state: AgentState) -> AgentState:
        """
        Node 3: Build prompt context with best memory LAST.

        Constructs the agent prompt with retrieved memories sorted
        ascending by relevance (lowest-relevance first, highest-relevance
        immediately before task body). This implements Lost-in-the-Middle
        mitigation.

        Uses build_prompt_context from prompts.py which implements:
        - Requirement 7: Best memory item injected LAST
        - Each memory rendered with memory_id, rank, similarity, age, type
        """
        # Build task object for prompt construction
        task = type('Task', (), {
            'task_id': state.task_id,
            'repo': state.repo,
            'issue_text': state.issue_text,
            'sequence_index': state.sequence_index,
        })()

        # state.retrieved_memories is already list[tuple[float, MemoryRecord]]
        # from policy.retrieve(); build_prompt_context consumes that shape
        # directly (best item LAST is preserved by the ascending sort).
        scored_memories = list(state.retrieved_memories)

        # Build prompt context using the proper function
        # This ensures consistent formatting and Lost-in-the-Middle mitigation
        state.context = build_prompt_context(
            task=task,
            scored_memories=scored_memories,
            current_step=state.sequence_index
        )

        return state

    def planning(self, state: AgentState) -> AgentState:
        """
        Node 4: Generate high-level solution plan.

        Creates a plan for solving the task based on the issue
        description and retrieved memories.
        """
        # Increment step count and check limit
        if state.limit_tracker and state.limit_tracker.increment_step():
            state.timeout = True
            state.finished = True
            state.error_message = state.limit_tracker.get_failure_reason()
            state.next_node = "final_patch_generation"
            return state

        state.step_count = state.limit_tracker.step_count if state.limit_tracker else state.step_count + 1

        # Check wall time limit
        if state.limit_tracker and state.limit_tracker.check_wall_time():
            state.timeout = True
            state.finished = True
            state.error_message = state.limit_tracker.get_failure_reason()
            state.next_node = "final_patch_generation"
            return state

        # TODO: Implement LLM call for planning
        # For now, set a placeholder plan
        state.plan = "Plan: Analyze issue, search code, edit files, run tests"
        state.next_node = "code_search"

        return state

    def code_search(self, state: AgentState) -> AgentState:
        """
        Node 5: Search codebase for relevant code.

        Uses code search tools to find relevant files and functions
        for implementing the solution.
        """
        # Increment step count and check limit
        if state.limit_tracker and state.limit_tracker.increment_step():
            state.timeout = True
            state.finished = True
            state.error_message = state.limit_tracker.get_failure_reason()
            state.next_node = "final_patch_generation"
            return state

        state.step_count = state.limit_tracker.step_count if state.limit_tracker else state.step_count + 1

        # Increment tool call count and check limit
        if state.limit_tracker and state.limit_tracker.increment_tool_call():
            state.timeout = True
            state.finished = True
            state.error_message = state.limit_tracker.get_failure_reason()
            state.next_node = "final_patch_generation"
            return state

        state.tool_calls = state.limit_tracker.tool_call_count if state.limit_tracker else state.tool_calls + 1

        # Check wall time limit
        if state.limit_tracker and state.limit_tracker.check_wall_time():
            state.timeout = True
            state.finished = True
            state.error_message = state.limit_tracker.get_failure_reason()
            state.next_node = "final_patch_generation"
            return state

        # TODO: Implement code search logic
        state.next_node = "file_editing"

        return state

    def file_editing(self, state: AgentState) -> AgentState:
        """
        Node 6: Edit files to implement solution.

        Modifies repository files to implement the planned solution.
        """
        # Increment step count and check limit
        if state.limit_tracker and state.limit_tracker.increment_step():
            state.timeout = True
            state.finished = True
            state.error_message = state.limit_tracker.get_failure_reason()
            state.next_node = "final_patch_generation"
            return state

        state.step_count = state.limit_tracker.step_count if state.limit_tracker else state.step_count + 1

        # Increment tool call count and check limit
        if state.limit_tracker and state.limit_tracker.increment_tool_call():
            state.timeout = True
            state.finished = True
            state.error_message = state.limit_tracker.get_failure_reason()
            state.next_node = "final_patch_generation"
            return state

        state.tool_calls = state.limit_tracker.tool_call_count if state.limit_tracker else state.tool_calls + 1

        # Check wall time limit
        if state.limit_tracker and state.limit_tracker.check_wall_time():
            state.timeout = True
            state.finished = True
            state.error_message = state.limit_tracker.get_failure_reason()
            state.next_node = "final_patch_generation"
            return state

        # TODO: Implement file editing logic
        state.next_node = "test_execution"

        return state

    def test_execution(self, state: AgentState) -> AgentState:
        """
        Node 7: Run tests to verify solution.

        Executes tests to check if the solution works correctly.
        """
        # Increment step count and check limit
        if state.limit_tracker and state.limit_tracker.increment_step():
            state.timeout = True
            state.finished = True
            state.error_message = state.limit_tracker.get_failure_reason()
            state.next_node = "final_patch_generation"
            return state

        state.step_count = state.limit_tracker.step_count if state.limit_tracker else state.step_count + 1

        # Increment test run count and check limit
        if state.limit_tracker and state.limit_tracker.increment_test_run():
            state.timeout = True
            state.finished = True
            state.error_message = state.limit_tracker.get_failure_reason()
            state.next_node = "final_patch_generation"
            return state

        state.test_runs = state.limit_tracker.test_run_count if state.limit_tracker else state.test_runs + 1

        # Check wall time limit
        if state.limit_tracker and state.limit_tracker.check_wall_time():
            state.timeout = True
            state.finished = True
            state.error_message = state.limit_tracker.get_failure_reason()
            state.next_node = "final_patch_generation"
            return state

        # TODO: Implement test execution logic
        # For now, assume tests pass
        state.next_node = "final_patch_generation"

        return state

    def repair_loop(self, state: AgentState) -> AgentState:
        """
        Node 8: Fix errors and iterate.

        Analyzes test failures and errors, then routes back to
        appropriate node for fixing.
        """
        # Increment step count and check limit
        if state.limit_tracker and state.limit_tracker.increment_step():
            state.timeout = True
            state.finished = True
            state.error_message = state.limit_tracker.get_failure_reason()
            state.next_node = "final_patch_generation"
            return state

        state.step_count = state.limit_tracker.step_count if state.limit_tracker else state.step_count + 1

        # Check wall time limit
        if state.limit_tracker and state.limit_tracker.check_wall_time():
            state.timeout = True
            state.finished = True
            state.error_message = state.limit_tracker.get_failure_reason()
            state.next_node = "final_patch_generation"
            return state

        # TODO: Implement repair logic
        # For now, route to file editing
        state.next_node = "file_editing"

        return state

    def final_patch_generation(self, state: AgentState) -> AgentState:
        """
        Node 9: Generate final patch.

        Creates the final patch from all file modifications made
        during execution.
        """
        # TODO: Implement patch generation logic
        # For now, set placeholder
        state.patch = ""
        state.patch_generated = True
        state.finished = True

        return state

    def reflection(self, state: AgentState) -> AgentState:
        """
        Node 10: Structured analysis of task execution.

        Generates a structured memory record from the task, trajectory,
        patch, and evaluation result. This record will be classified
        and written to memory.
        """
        # TODO: Implement reflection logic
        # For now, create placeholder memory record
        state.memory_record = {
            "task_id": state.task_id,
            "repo": state.repo,
            "sequence_index": state.sequence_index,
            "issue_summary": state.issue_text[:200],  # Truncated
            "patch_summary": state.patch[:200] if state.patch else "",
            "files_touched": state.files_modified,
            "commands_run": state.commands_run,
            "retrieved_memory_ids_used": state.retrieved_memory_ids,
            "outcome": "unknown",  # Will be set based on eval_result
        }

        return state

    def memory_write(self, state: AgentState) -> AgentState:
        """
        Node 11: Write memory record to store.

        Passes the structured memory record to the active policy's
        write method. Type classification must complete before this step.
        """
        if state.memory_record:
            # TODO: Invoke type classifier before writing
            # For now, skip writing
            pass

        return state

    def memory_prune_or_consolidate(self, state: AgentState) -> AgentState:
        """
        Node 12: Apply policy maintenance.

        Invokes the policy's maintain() method to perform pruning
        or consolidation according to the policy's strategy.
        """
        # Apply policy maintenance (prune/consolidate)
        self.policy.maintain(self.memory_store)

        return state

    # ========================================================================
    # Routing functions
    # ========================================================================

    def _route_from_planning(self, state: AgentState) -> str:
        """Route from planning node based on state."""
        if state.finished or state.timeout:
            return "final_patch_generation"
        return state.next_node

    def _route_from_code_search(self, state: AgentState) -> str:
        """Route from code_search node based on state."""
        if state.finished or state.timeout:
            return "final_patch_generation"
        return state.next_node

    def _route_from_file_editing(self, state: AgentState) -> str:
        """Route from file_editing node based on state."""
        if state.finished or state.timeout:
            return "final_patch_generation"
        return state.next_node

    def _route_from_test_execution(self, state: AgentState) -> str:
        """Route from test_execution node based on state."""
        if state.finished or state.timeout:
            return "final_patch_generation"
        # If tests failed, go to repair_loop
        # For now, assume tests pass
        return state.next_node

    def _route_from_repair_loop(self, state: AgentState) -> str:
        """Route from repair_loop node based on state."""
        if state.finished or state.timeout:
            return "final_patch_generation"
        return state.next_node

    # ========================================================================
    # Public API
    # ========================================================================

    def _build_task_obj(self, task: dict[str, Any]) -> SimpleNamespace:
        """Lightweight task object for retrieval + prompt construction."""
        return SimpleNamespace(
            task_id=task["task_id"],
            repo=task["repo"],
            base_commit=task.get("base_commit", ""),
            issue_text=task["issue_text"],
            sequence_index=task.get("sequence_index", 0),
        )

    def solve_task(
        self,
        task: dict[str, Any],
        retrieved_memories: list[tuple[float, Any]] | None = None,
    ) -> dict[str, Any]:
        """Solve a single SWE-Bench-CL task via the v5 §4.4 ReAct tool-use loop.

        ``retrieved_memories`` (C4): the SequenceRunner performs the single
        authoritative retrieval and passes its scored ``(score, record)`` list in,
        so the memories shown to the model are exactly the ones logged. When None
        (standalone/test calls), the agent retrieves once itself.

        Pipeline: retrieve memories (pure cosine, best LAST) -> build prompt ->
        iterate tool calls under hard limits -> generate the patch via `git diff`.
        Reflection / memory write / policy maintenance (v5 nodes 10-12) are done
        by SequenceRunner, NOT here (avoids running maintain() twice). The legacy
        12-node graph built in __init__ is superseded by this loop.

        Args:
            task: Task dict with task_id, repo, base_commit, issue_text, sequence_index.

        Returns:
            Result dict (patch, trajectory, counts, token usage, timeout, ...).
        """
        state = AgentState(
            task_id=task["task_id"],
            repo=task["repo"],
            base_commit=task.get("base_commit", ""),
            issue_text=task["issue_text"],
            sequence_index=task.get("sequence_index", 0),
        )
        state.limit_tracker = LimitTracker(
            max_steps=self.max_steps,
            max_tool_calls=self.max_tool_calls,
            max_test_runs=self.max_test_runs,
            max_wall_time_seconds=self.max_wall_time_seconds,
        )

        task_obj = self._build_task_obj(task)

        # Node 2: retrieve (pure cosine, identical across conditions). C4: prefer
        # the runner's single authoritative retrieval (passed in) so the context
        # shown to the model is exactly what gets logged and no second embedding
        # query is issued. Only retrieve here when called standalone.
        if retrieved_memories is None:
            try:
                retrieved = self.policy.retrieve(
                    task=task_obj,
                    memory_store=self.memory_store,
                    top_k=self.top_k,
                    token_budget=self.max_context_tokens,
                )
            except Exception as e:  # retrieval must never crash the task
                logger.warning(f"Retrieval failed for {state.task_id}: {e}")
                retrieved = []
        else:
            retrieved = list(retrieved_memories)
        state.retrieved_memories = retrieved
        state.retrieved_memory_ids = [record.memory_id for _, record in retrieved]

        # Node 3: build prompt context (best item LAST, Invariant #6).
        context = build_prompt_context(
            task=task_obj,
            scored_memories=list(retrieved),
            current_step=state.sequence_index,
        )

        # §4.4 loop over the working tree, then node 9 (final patch via git diff).
        # Backend = local checkout by default; per-task swebench instance
        # container when configured (decision A+G). The container (if any) must
        # stay alive through get_patch (also a backend call), then be removed.
        tools, container_session = self._make_tools(state)
        try:
            self._run_react_loop(tools, context, state)

            try:
                state.patch = tools.get_patch()
            except Exception as e:
                state.patch = ""
                state.error_message = state.error_message or f"get_patch failed: {e}"
            state.patch_generated = bool(state.patch.strip())
            state.syntax_error = tools.tracker.syntax_errors > 0
            state.step_count = state.limit_tracker.step_count
            state.tool_calls = state.limit_tracker.tool_call_count
            state.test_runs = state.limit_tracker.test_run_count
        finally:
            if container_session is not None:
                container_session.stop()

        return {
            "task_id": state.task_id,
            "patch": state.patch,
            "patch_generated": state.patch_generated,
            "timeout": state.timeout,
            "syntax_error": state.syntax_error,
            "error_message": state.error_message,
            "step_count": state.step_count,
            "tool_calls": state.tool_calls,
            "test_runs": state.test_runs,
            "files_read": state.files_read,
            "files_modified": state.files_modified,
            "commands_run": state.commands_run,
            "retrieved_memory_ids": state.retrieved_memory_ids,
            "trajectory": state.trajectory,
            "prompt_tokens": state.prompt_tokens,
            "completion_tokens": state.completion_tokens,
            "total_tokens": state.total_tokens,
            "estimated_cost_usd": 0.0,  # flat-rate Ollama; cost tracked as tokens (D3)
            "limit_status": state.limit_tracker.get_status(),
            "termination_reason": state.termination_reason,
            # A/B variant flag (Task 5c): records which tool-behavior mode was active.
            "tool_mode": self.resolved_tool_mode,
        }

    def _make_tools(self, state: AgentState) -> tuple[AgentTools, ContainerSession | None]:
        """Select the execution backend for this task (decision A+G).

        Default ``local`` runs the 8 tools against the checked-out working tree.
        ``container`` (config ``agent.execution_backend``) starts a per-task
        swebench instance container and runs tools inside it via ``docker exec``
        — so run_command/run_tests act against installed deps. Returns the tools
        plus the session to stop (or None for local).
        """
        agent_cfg = self.config.get("agent", {})
        if agent_cfg.get("execution_backend", "local") == "container":
            arch = agent_cfg.get("instance_arch", "x86_64")
            namespace = agent_cfg.get("instance_namespace") or None
            image = agent_cfg.get("instance_image") or ContainerSession.image_for(
                state.task_id, arch=arch, namespace=namespace
            )
            session = ContainerSession(image, repo_dir=agent_cfg.get("repo_dir", "/testbed"))
            session.start()
            logger.info(
                f"Started instance container {(session.container_id or '')[:12]} "
                f"from {image} for {state.task_id}"
            )
            return AgentTools(backend=session.backend()), session
        return AgentTools(working_dir=str(self.task_env.working_dir)), None

    def _run_react_loop(self, tools: AgentTools, context: str, state: AgentState) -> None:
        """Drive the tool-calling loop until the model finishes or a limit trips."""
        client = get_chat_client()
        model = main_model()
        tracker = state.limit_tracker
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": context + _TOOL_USE_SUFFIX},
            {"role": "user", "content": "Begin. Solve the issue using tool calls."},
        ]

        while True:
            # One model turn == one step. increment_step() is post-increment and
            # returns True when the count EXCEEDS max_steps (20 turns run, the
            # 21st trips) — strict Invariant #3.
            # Split the two checks so termination_reason is unambiguous.
            if tracker.increment_step():
                state.timeout = True
                state.error_message = tracker.get_failure_reason()
                state.termination_reason = "step_limit"
                break
            if tracker.check_wall_time():
                state.timeout = True
                state.error_message = tracker.get_failure_reason()
                state.termination_reason = "wall_time"
                break

            try:
                create_kwargs: dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "tools": build_tool_schemas(self.resolved_tool_mode),
                    "temperature": self.temperature,  # A2: temp=1 (Kimi/reasoning models)
                }
                if self.reasoning_effort:
                    create_kwargs["reasoning_effort"] = self.reasoning_effort
                response = client.chat.completions.create(**create_kwargs)
            except Exception as e:
                # Provider quota/usage-limit is fatal — abort the run instead of
                # silently producing empty patches for every remaining task.
                if is_usage_limit_error(e):
                    raise UsageLimitError(
                        f"Provider usage limit hit during agent loop "
                        f"({state.task_id}): {e}"
                    ) from e
                state.error_message = f"LLM call failed: {e}"
                state.termination_reason = "llm_error"
                break

            usage = getattr(response, "usage", None)
            if usage is not None:
                state.prompt_tokens += getattr(usage, "prompt_tokens", 0) or 0
                state.completion_tokens += getattr(usage, "completion_tokens", 0) or 0
                state.total_tokens += getattr(usage, "total_tokens", 0) or 0

            message = response.choices[0].message
            tool_calls = getattr(message, "tool_calls", None)

            # No tool call → the model is done.
            if not tool_calls:
                state.finished = True
                state.termination_reason = "model_no_tool_calls"
                break

            messages.append(self._assistant_message(message, tool_calls))

            stop = False
            for tc in tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except (json.JSONDecodeError, TypeError):
                    args = {}

                if name == "finish":
                    state.finished = True
                    state.termination_reason = "finished_tool"
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": "acknowledged"})
                    stop = True
                    break

                if tracker.increment_tool_call():
                    state.timeout = True
                    state.error_message = tracker.get_failure_reason()
                    state.termination_reason = "tool_call_limit"
                    stop = True
                    break
                if name == "run_tests" and tracker.increment_test_run():
                    state.timeout = True
                    state.error_message = tracker.get_failure_reason()
                    state.termination_reason = "test_run_limit"
                    stop = True
                    break

                observation = self._execute_tool(tools, name, args, state)
                state.trajectory.append({
                    "action": name,
                    "action_input": args,
                    "observation_summary": _truncate_obs(observation, mode=self.resolved_tool_mode),
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": _truncate_obs(observation, mode=self.resolved_tool_mode),
                })

            if stop:
                break

    @staticmethod
    def _assistant_message(message: Any, tool_calls: Any) -> dict[str, Any]:
        """Serialize the assistant tool-call turn for the next request.

        Only the tool calls are echoed back — the model's free-text reasoning is
        intentionally NOT persisted to the trajectory (v5 §11.3, no CoT). Reasoning
        models (MiniMax M3) wrap CoT in <think>...</think>; we strip it from the
        re-sent content so it is not re-billed as prompt tokens each turn.
        """
        return {
            "role": "assistant",
            "content": strip_reasoning(getattr(message, "content", "") or ""),
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments or "{}",
                    },
                }
                for tc in tool_calls
            ],
        }

    def _execute_tool(self, tools: AgentTools, name: str, args: dict[str, Any], state: AgentState) -> str:
        """Dispatch a tool call to AgentTools and return an observation string."""
        try:
            if name == "read_file":
                path = args["path"]
                content = tools.read_file(path, args.get("start_line"), args.get("end_line"))
                if path not in state.files_read:
                    state.files_read.append(path)
                return content
            if name == "write_file":
                path = args["path"]
                tools.write_file(path, args.get("content", ""))
                if path not in state.files_modified:
                    state.files_modified.append(path)
                return f"Wrote {path}"
            if name == "edit_file":
                path = args["path"]
                tools.edit_file(path, args.get("diff", ""))
                if path not in state.files_modified:
                    state.files_modified.append(path)
                return f"Edited {path}"
            if name == "search_code":
                matches = tools.search_code(args["query"], args.get("file_pattern", "*"))
                return json.dumps(matches[:20])
            if name == "list_files":
                files = tools.list_files(args.get("path", "."), args.get("pattern", "*"))
                return json.dumps(files[:100])
            if name == "run_command":
                cmd = args["command"]
                state.commands_run.append(cmd)
                out = tools.run_command(cmd)
                return f"exit_code={out['return_code']}\nstdout:\n{out['stdout']}\nstderr:\n{out['stderr']}"
            if name == "run_tests":
                cmd = args["test_command"]
                state.commands_run.append(cmd)
                out = tools.run_tests(cmd)
                return f"tests_passed={out['tests_passed']}\nstdout:\n{out['stdout']}\nstderr:\n{out['stderr']}"
            return f"ERROR: unknown tool '{name}'"
        except KeyError as e:
            return f"ERROR: missing required argument {e} for tool '{name}'"
        except Exception as e:
            return f"ERROR: tool '{name}' failed: {e}"
