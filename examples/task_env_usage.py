"""Example usage of TaskEnvironment for clean repository checkout.

This example demonstrates how to use the TaskEnvironment class to:
1. Perform clean repository checkout at a specific commit
2. Get repository metadata for agent context
3. Extract patches after agent modifications
4. Handle errors and cleanup properly

This is critical infrastructure for the 144 experimental runs with proper isolation.
"""

from src.benchmark import Task, TaskEnvironment, RepositoryCheckoutError


def example_basic_usage() -> None:
    """Basic usage: checkout, get metadata, cleanup."""
    # Create a sample task
    task = Task(
        task_id="django__django-12345",
        repo="django/django",
        base_commit="abc123def456",
        issue_text="Fix bug in authentication",
        test_patch="test patch content",
        gold_patch="gold patch content",
        created_at="2024-01-01T00:00:00Z",
        sequence_index=0,
        difficulty_label="medium",
    )

    # Create task environment
    env = TaskEnvironment(task)

    try:
        # Checkout clean repository
        working_dir = env.checkout_clean_repo()
        print(f"Repository checked out at: {working_dir}")

        # Get repository metadata for agent context
        metadata = env.repo_metadata()
        print(f"Repository: {metadata.repo}")
        print(f"Base commit: {metadata.base_commit}")
        print(f"Files count: {metadata.files_count}")
        print(f"Primary language: {metadata.primary_language}")

        # Agent would work here...
        # After agent makes changes, get the patch
        patch = env.get_patch()
        print(f"Generated patch length: {len(patch)} characters")

    except RepositoryCheckoutError as e:
        print(f"Repository checkout failed: {e}")
        # This should fail the entire sequence run
        raise
    finally:
        # Always cleanup
        env.cleanup()


def example_context_manager() -> None:
    """Using TaskEnvironment as a context manager (recommended)."""
    task = Task(
        task_id="django__django-12345",
        repo="django/django",
        base_commit="abc123def456",
        issue_text="Fix bug in authentication",
        test_patch="test patch content",
        gold_patch="gold patch content",
        created_at="2024-01-01T00:00:00Z",
        sequence_index=0,
        difficulty_label="medium",
    )

    try:
        # Context manager automatically handles cleanup
        with TaskEnvironment(task) as env:
            metadata = env.repo_metadata()
            print(f"Working in: {metadata.working_dir}")

            # Agent execution happens here...
            # working_dir is automatically cleaned up on exit

    except RepositoryCheckoutError as e:
        print(f"Repository checkout failed: {e}")
        # Fail entire sequence run
        raise


def example_sequence_execution() -> None:
    """Example of executing multiple tasks in a sequence."""
    # Simulate a sequence of tasks
    tasks = [
        Task(
            task_id=f"django__django-{i}",
            repo="django/django",
            base_commit=f"commit{i}",
            issue_text=f"Issue {i}",
            test_patch="test patch",
            gold_patch="gold patch",
            created_at="2024-01-01T00:00:00Z",
            sequence_index=i,
            difficulty_label="easy",
        )
        for i in range(3)
    ]

    # Execute each task with clean checkout
    for task in tasks:
        print(f"\n=== Executing task {task.task_id} ===")

        try:
            with TaskEnvironment(task) as env:
                metadata = env.repo_metadata()
                print(f"Clean checkout at: {metadata.working_dir}")

                # Agent execution...
                # Memory persists across tasks, but codebase resets

                patch = env.get_patch()
                print(f"Generated patch: {len(patch)} chars")

        except RepositoryCheckoutError as e:
            print(f"FATAL: Repository checkout failed for {task.task_id}: {e}")
            print("Failing entire sequence run as per Requirements.md #2")
            raise


if __name__ == "__main__":
    print("TaskEnvironment Usage Examples")
    print("=" * 50)

    print("\n1. Basic Usage:")
    print("-" * 50)
    # example_basic_usage()  # Commented out - requires actual git repo

    print("\n2. Context Manager (Recommended):")
    print("-" * 50)
    # example_context_manager()  # Commented out - requires actual git repo

    print("\n3. Sequence Execution:")
    print("-" * 50)
    # example_sequence_execution()  # Commented out - requires actual git repo

    print("\nNote: Examples are commented out as they require actual git repositories.")
    print("Uncomment and modify with real repository URLs to test.")
