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

from dataclasses import dataclass, field
from typing import Any

from langgraph.graph import END, StateGraph

from .limit_tracker import LimitTracker, validate_temperature
from .prompts import build_prompt_context


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

    # Next node routing
    next_node: str = "planning"


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
        self.top_k = config.get("memory", {}).get("top_k", 5)
        self.max_context_tokens = config.get("memory", {}).get("max_context_tokens", 2000)

        # Validate frozen invariants
        if self.max_steps != 20:
            raise ValueError(
                f"FROZEN INVARIANT VIOLATION: max_steps must be 20, got {self.max_steps}"
            )
        validate_temperature(self.temperature)

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

    def solve_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """
        Solve a single SWE-Bench-CL task.

        Args:
            task: Task dictionary with task_id, repo, base_commit, issue_text, etc.

        Returns:
            Dictionary with execution results including patch, eval_result, trajectory, etc.
        """
        # Initialize state
        initial_state = AgentState(
            task_id=task["task_id"],
            repo=task["repo"],
            base_commit=task["base_commit"],
            issue_text=task["issue_text"],
            sequence_index=task.get("sequence_index", 0),
        )

        # Execute graph
        final_state = self.graph.invoke(initial_state)

        # Get limit tracker status
        limit_status = final_state.limit_tracker.get_status() if final_state.limit_tracker else {}

        # Return results
        return {
            "task_id": final_state.task_id,
            "patch": final_state.patch,
            "patch_generated": final_state.patch_generated,
            "timeout": final_state.timeout,
            "syntax_error": final_state.syntax_error,
            "error_message": final_state.error_message,
            "step_count": final_state.step_count,
            "tool_calls": final_state.tool_calls,
            "test_runs": final_state.test_runs,
            "files_read": final_state.files_read,
            "files_modified": final_state.files_modified,
            "commands_run": final_state.commands_run,
            "retrieved_memory_ids": final_state.retrieved_memory_ids,
            "trajectory": final_state.trajectory,
            "eval_result": final_state.eval_result,
            "limit_status": limit_status,  # Include detailed limit tracking info
        }
