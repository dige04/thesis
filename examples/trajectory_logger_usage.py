"""
Example usage of TrajectoryLogger for agent execution traces.

This demonstrates how to integrate trajectory logging into the LangGraph agent
execution flow as specified in THESIS_FINAL_v5.md §11.3.

CRITICAL: Only log action summaries and observations, NOT private reasoning.
"""

from pathlib import Path

from src.logging.trajectory_logger import TrajectoryLogger


def example_basic_usage():
    """Basic example of logging a task trajectory."""
    # Initialize logger for a task
    logger = TrajectoryLogger(
        run_id="run_001",
        task_id="django__django-12345",
        policy="type_aware_decay",
        seed=2,
        base_dir="runs",
    )

    # Log each step during agent execution
    logger.log_step(
        step=1,
        action="search_code",
        action_input="QuerySet.exclude",
        observation_summary="Found in django/db/models/query.py:823",
    )

    logger.log_step(
        step=2,
        action="read_file",
        action_input="django/db/models/query.py",
        observation_summary="File content retrieved, 1500 lines",
    )

    logger.log_step(
        step=3,
        action="edit_file",
        action_input={"file": "query.py", "start_line": 823, "end_line": 830},
        observation_summary="Modified exclude() method implementation",
    )

    # Save trajectory at end of task
    output_path = logger.save()
    print(f"Trajectory saved to: {output_path}")


def example_agent_integration():
    """
    Example of integrating trajectory logger into agent execution.

    This shows the pattern for LangGraph agent nodes.
    """

    def agent_step_node(state: dict, logger: TrajectoryLogger):
        """
        Example agent node that logs its action and observation.

        This demonstrates the pattern for logging in LangGraph nodes:
        1. Execute the action
        2. Get the observation
        3. Log the step (WHAT was done and WHAT was observed)
        4. Do NOT log WHY (no reasoning or planning)
        """
        step_number = state["step_count"]

        # Execute action (example: search code)
        action = "search_code"
        action_input = state["search_query"]

        # Get observation from tool execution
        observation = execute_search_tool(action_input)  # noqa: F821

        # Log the step - only WHAT, not WHY
        logger.log_step(
            step=step_number,
            action=action,
            action_input=action_input,
            observation_summary=observation["summary"],
        )

        return state

    # In the main agent execution loop:
    logger = TrajectoryLogger(
        run_id="run_001",
        task_id="django__django-12345",
        policy="type_aware_decay",
        seed=2,
    )

    # Execute agent nodes...
    # Each node logs its action and observation

    # At end of task execution
    logger.save()


def example_complete_task_execution():
    """
    Example of logging a complete task execution with multiple steps.

    This simulates a realistic agent execution flow.
    """
    logger = TrajectoryLogger(
        run_id="run_001",
        task_id="django__django-12345",
        policy="type_aware_decay",
        seed=2,
    )

    # Step 1: Search for relevant code
    logger.log_step(
        step=1,
        action="search_code",
        action_input="QuerySet.exclude",
        observation_summary="Found in django/db/models/query.py:823",
    )

    # Step 2: Read the file
    logger.log_step(
        step=2,
        action="read_file",
        action_input="django/db/models/query.py",
        observation_summary="File content retrieved, 1500 lines",
    )

    # Step 3: Edit the file
    logger.log_step(
        step=3,
        action="edit_file",
        action_input={"file": "query.py", "start_line": 823, "end_line": 830},
        observation_summary="Modified exclude() method implementation",
    )

    # Step 4: Run tests
    logger.log_step(
        step=4,
        action="run_tests",
        action_input="tests/queries/test_exclude.py",
        observation_summary="3 tests passed, 1 test failed",
    )

    # Step 5: Fix the issue
    logger.log_step(
        step=5,
        action="edit_file",
        action_input={"file": "query.py", "line": 825},
        observation_summary="Fixed edge case handling",
    )

    # Step 6: Run tests again
    logger.log_step(
        step=6,
        action="run_tests",
        action_input="tests/queries/test_exclude.py",
        observation_summary="All 4 tests passed",
    )

    # Save trajectory
    output_path = logger.save()
    print(f"Complete trajectory saved to: {output_path}")

    # Verify the trajectory
    from src.logging.trajectory_logger import load_trajectory

    trajectory = load_trajectory(output_path)
    print(f"\nTask: {trajectory['task_id']}")
    print(f"Policy: {trajectory['policy']}")
    print(f"Seed: {trajectory['seed']}")
    print(f"Steps: {len(trajectory['steps'])}")

    for step in trajectory["steps"]:
        print(f"  Step {step['step']}: {step['action']} -> {step['observation_summary']}")


def example_what_not_to_log():
    """
    Example showing what NOT to log (private chain-of-thought).

    CRITICAL: Do NOT log the agent's reasoning or planning.
    """
    logger = TrajectoryLogger(
        run_id="run_001",
        task_id="django__django-12345",
        policy="type_aware_decay",
        seed=2,
    )

    # ❌ WRONG - Do NOT log reasoning like this:
    # logger.log_step(
    #     step=1,
    #     action="I think I should search for the QuerySet.exclude method",
    #     action_input="because the issue mentions exclude() not working",
    #     observation_summary="This means I need to look at the query.py file",
    # )

    # ✅ CORRECT - Log only action summaries and observations:
    logger.log_step(
        step=1,
        action="search_code",  # WHAT the agent did (tool name)
        action_input="QuerySet.exclude",  # WHAT arguments
        observation_summary="Found in django/db/models/query.py:823",  # WHAT it observed
    )

    # ❌ WRONG - Do NOT include planning or reasoning:
    # logger.log_step(
    #     step=2,
    #     action="read_file",
    #     action_input="query.py",
    #     observation_summary="I see the problem now - the exclude method doesn't handle None values",
    # )

    # ✅ CORRECT - Observation is factual, not interpretive:
    logger.log_step(
        step=2,
        action="read_file",
        action_input="django/db/models/query.py",
        observation_summary="File content retrieved, 1500 lines",
    )

    logger.save()


if __name__ == "__main__":
    print("=== Basic Usage ===")
    example_basic_usage()

    print("\n=== Complete Task Execution ===")
    example_complete_task_execution()

    print("\n=== What NOT to Log ===")
    example_what_not_to_log()

    print("\nAll examples completed successfully!")
