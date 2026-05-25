"""Task environment manager for Docker container lifecycle management.

This module provides clean repository checkout per task and manages Docker
container lifecycle for isolated task execution with SWE-Bench eval_v3 harness.

Key responsibilities:
- Clean repository checkout at specific commit per task
- Error handling for repository issues (uncommitted changes, checkout failures)
- Provide repository metadata to agent
- Manage working directory lifecycle
- Fail entire sequence if repository cannot be prepared

Frozen invariants enforced:
- Clean repo checkout per task (THESIS_FINAL_v5.md §0, frozen decision #2)
- Fail entire sequence on repository errors (Requirements.md #2)
"""

import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.benchmark.models import Task
from src.errors import RepositoryCheckoutError

logger = logging.getLogger(__name__)


@dataclass
class RepositoryMetadata:
    """Metadata about the repository state for agent context.

    Attributes:
        repo: Repository name (e.g., "django/django")
        base_commit: Git commit hash for the base state
        working_dir: Absolute path to the working directory
        files_count: Number of files in the repository
        primary_language: Primary programming language detected
    """

    repo: str
    base_commit: str
    working_dir: str
    files_count: int
    primary_language: str


class TaskEnvironment:
    """Manages Docker container lifecycle and repository state for task execution.

    This class provides clean repository checkout per task and manages the
    working directory lifecycle. Each task gets a fresh repository state,
    ensuring isolation between tasks while the memory system persists.

    The core principle: "The agent's codebase state resets per task;
    its external memory persists across tasks."

    Attributes:
        task: The task being executed
        working_dir: Path to the working directory (None until checkout)
        _temp_dir: Temporary directory handle (managed internally)
    """

    def __init__(self, task: Task):
        """Initialize task environment for a specific task.

        Args:
            task: The task to execute
        """
        self.task = task
        self.working_dir: Path | None = None
        self._temp_dir: Any = None  # tempfile.TemporaryDirectory handle

    def checkout_clean_repo(self) -> Path:
        """Perform clean repository checkout at the task's base commit.

        This method:
        1. Creates a temporary working directory
        2. Clones the repository
        3. Checks out the specific base commit
        4. Verifies the checkout is clean (no uncommitted changes)

        Returns:
            Path to the working directory

        Raises:
            RepositoryCheckoutError: If checkout fails for any reason.
                This should cause the entire sequence run to fail.
        """
        try:
            # Create temporary directory for this task
            self._temp_dir = tempfile.TemporaryDirectory(prefix=f"swebench_{self.task.task_id}_")
            working_dir = Path(self._temp_dir.name)

            logger.info(
                f"Checking out repository {self.task.repo} at commit {self.task.base_commit[:8]} "
                f"for task {self.task.task_id}"
            )

            # Extract repository URL from repo name
            # Format: "owner/repo" -> "https://github.com/owner/repo.git"
            repo_url = f"https://github.com/{self.task.repo}.git"

            # Clone repository
            try:
                subprocess.run(
                    ["git", "clone", "--quiet", repo_url, str(working_dir)],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 minute timeout for clone
                )
            except subprocess.CalledProcessError as e:
                raise RepositoryCheckoutError(
                    f"Failed to clone repository {self.task.repo}: {e.stderr}"
                ) from e
            except subprocess.TimeoutExpired as e:
                raise RepositoryCheckoutError(
                    f"Timeout while cloning repository {self.task.repo}"
                ) from e

            # Checkout specific commit
            try:
                subprocess.run(
                    ["git", "checkout", "--quiet", self.task.base_commit],
                    cwd=working_dir,
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
            except subprocess.CalledProcessError as e:
                raise RepositoryCheckoutError(
                    f"Failed to checkout commit {self.task.base_commit} in {self.task.repo}: {e.stderr}"
                ) from e
            except subprocess.TimeoutExpired as e:
                raise RepositoryCheckoutError(
                    f"Timeout while checking out commit {self.task.base_commit}"
                ) from e

            # Verify clean checkout (no uncommitted changes)
            try:
                result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=working_dir,
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.stdout.strip():
                    raise RepositoryCheckoutError(
                        f"Repository has uncommitted changes after checkout:\n{result.stdout}"
                    )
            except subprocess.CalledProcessError as e:
                raise RepositoryCheckoutError(
                    f"Failed to verify clean checkout: {e.stderr}"
                ) from e

            self.working_dir = working_dir
            logger.info(f"Successfully checked out clean repository at {working_dir}")

            return working_dir

        except RepositoryCheckoutError:
            # Clean up on failure
            self.cleanup()
            raise
        except Exception as e:
            # Catch any unexpected errors and wrap them
            self.cleanup()
            raise RepositoryCheckoutError(
                f"Unexpected error during repository checkout: {str(e)}"
            ) from e

    def repo_metadata(self) -> RepositoryMetadata:
        """Get repository metadata for agent context.

        Returns:
            RepositoryMetadata with repository information

        Raises:
            RuntimeError: If called before checkout_clean_repo()
        """
        if self.working_dir is None:
            raise RuntimeError("Must call checkout_clean_repo() before repo_metadata()")

        # Count files (excluding .git directory)
        files_count = sum(
            1
            for root, dirs, files in os.walk(self.working_dir)
            if ".git" not in root
            for _ in files
        )

        # Detect primary language (simple heuristic based on file extensions)
        language_counts: dict[str, int] = {}
        for root, _dirs, files in os.walk(self.working_dir):
            if ".git" in root:
                continue
            for file in files:
                ext = Path(file).suffix.lower()
                if ext:
                    language_counts[ext] = language_counts.get(ext, 0) + 1

        # Map extensions to languages
        ext_to_lang = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".java": "Java",
            ".cpp": "C++",
            ".c": "C",
            ".go": "Go",
            ".rs": "Rust",
            ".rb": "Ruby",
            ".php": "PHP",
        }

        primary_language = "Unknown"
        if language_counts:
            most_common_ext = max(language_counts, key=language_counts.get)  # type: ignore
            primary_language = ext_to_lang.get(most_common_ext, most_common_ext)

        return RepositoryMetadata(
            repo=self.task.repo,
            base_commit=self.task.base_commit,
            working_dir=str(self.working_dir),
            files_count=files_count,
            primary_language=primary_language,
        )

    def get_patch(self) -> str:
        """Get the current diff as a patch string.

        Returns:
            Git diff output as a string

        Raises:
            RuntimeError: If called before checkout_clean_repo()
        """
        if self.working_dir is None:
            raise RuntimeError("Must call checkout_clean_repo() before get_patch()")

        try:
            result = subprocess.run(
                ["git", "diff", "HEAD"],
                cwd=self.working_dir,
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get patch: {e.stderr}")
            return ""
        except subprocess.TimeoutExpired:
            logger.error("Timeout while getting patch")
            return ""

    def cleanup(self) -> None:
        """Clean up the working directory and temporary files.

        This method is safe to call multiple times and will not raise
        exceptions if cleanup fails (only logs warnings).
        """
        if self._temp_dir is not None:
            try:
                self._temp_dir.cleanup()
                logger.debug(f"Cleaned up temporary directory for task {self.task.task_id}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temporary directory: {e}")
            finally:
                self._temp_dir = None
                self.working_dir = None

    def __enter__(self) -> "TaskEnvironment":
        """Context manager entry: checkout clean repository.

        Returns:
            Self for context manager usage

        Raises:
            RepositoryCheckoutError: If checkout fails
        """
        self.checkout_clean_repo()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit: cleanup working directory.

        Args:
            exc_type: Exception type (if any)
            exc_val: Exception value (if any)
            exc_tb: Exception traceback (if any)
        """
        self.cleanup()

    def __del__(self) -> None:
        """Destructor: ensure cleanup happens even if not explicitly called."""
        self.cleanup()
