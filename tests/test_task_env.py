"""Tests for task environment manager.

This module tests the TaskEnvironment class for Docker container lifecycle
management and clean repository checkout functionality.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.benchmark.models import Task
from src.benchmark.task_env import (
    RepositoryCheckoutError,
    RepositoryMetadata,
    TaskEnvironment,
)


@pytest.fixture
def sample_task() -> Task:
    """Create a sample task for testing."""
    return Task(
        task_id="test__test-123",
        repo="test/repo",
        base_commit="abc123def456",
        issue_text="Test issue",
        test_patch="test patch content",
        gold_patch="gold patch content",
        created_at="2024-01-01T00:00:00Z",
        sequence_index=0,
        difficulty_label="easy",
    )


def test_task_environment_initialization(sample_task: Task) -> None:
    """Test TaskEnvironment initialization."""
    env = TaskEnvironment(sample_task)

    assert env.task == sample_task
    assert env.working_dir is None
    assert env._temp_dir is None


def test_checkout_clean_repo_success(sample_task: Task) -> None:
    """Test successful repository checkout."""
    env = TaskEnvironment(sample_task)

    # Mock subprocess calls
    with patch("subprocess.run") as mock_run:
        # Mock successful git clone
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),  # git clone
            MagicMock(returncode=0, stdout="", stderr=""),  # git checkout
            MagicMock(returncode=0, stdout="", stderr=""),  # git status
        ]

        working_dir = env.checkout_clean_repo()

        assert working_dir is not None
        assert env.working_dir == working_dir
        assert working_dir.exists()

        # Verify git commands were called correctly
        assert mock_run.call_count == 3

        # Check git clone call
        clone_call = mock_run.call_args_list[0]
        assert "git" in clone_call[0][0]
        assert "clone" in clone_call[0][0]
        assert f"https://github.com/{sample_task.repo}.git" in clone_call[0][0]

        # Check git checkout call
        checkout_call = mock_run.call_args_list[1]
        assert "git" in checkout_call[0][0]
        assert "checkout" in checkout_call[0][0]
        assert sample_task.base_commit in checkout_call[0][0]

        # Check git status call
        status_call = mock_run.call_args_list[2]
        assert "git" in status_call[0][0]
        assert "status" in status_call[0][0]

    env.cleanup()


def test_checkout_clean_repo_clone_failure(sample_task: Task) -> None:
    """Test repository checkout failure during clone."""
    env = TaskEnvironment(sample_task)

    from subprocess import CalledProcessError

    with patch("subprocess.run") as mock_run:
        # Mock failed git clone
        mock_run.side_effect = CalledProcessError(
            1, ["git", "clone"], stderr="fatal: repository not found"
        )

        # Should raise RepositoryCheckoutError
        with pytest.raises(RepositoryCheckoutError) as exc_info:
            env.checkout_clean_repo()

        assert "clone" in str(exc_info.value).lower()
        assert env.working_dir is None


def test_checkout_clean_repo_uncommitted_changes(sample_task: Task) -> None:
    """Test repository checkout failure due to uncommitted changes."""
    env = TaskEnvironment(sample_task)

    with patch("subprocess.run") as mock_run:
        # Mock git commands with uncommitted changes
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),  # git clone
            MagicMock(returncode=0, stdout="", stderr=""),  # git checkout
            MagicMock(
                returncode=0, stdout=" M modified_file.py\n", stderr=""
            ),  # git status
        ]

        # Should raise RepositoryCheckoutError due to uncommitted changes
        with pytest.raises(RepositoryCheckoutError) as exc_info:
            env.checkout_clean_repo()

        assert "uncommitted changes" in str(exc_info.value).lower()
        assert env.working_dir is None


def test_repo_metadata_before_checkout(sample_task: Task) -> None:
    """Test repo_metadata() raises error before checkout."""
    env = TaskEnvironment(sample_task)

    with pytest.raises(RuntimeError) as exc_info:
        env.repo_metadata()

    assert "checkout_clean_repo" in str(exc_info.value)


def test_repo_metadata_after_checkout(sample_task: Task) -> None:
    """Test repo_metadata() returns correct metadata after checkout."""
    env = TaskEnvironment(sample_task)

    # Create a temporary directory to simulate checkout
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        env.working_dir = temp_path

        # Create some test files
        (temp_path / "test.py").write_text("print('hello')")
        (temp_path / "test.js").write_text("console.log('hello')")
        (temp_path / "test2.py").write_text("print('world')")

        metadata = env.repo_metadata()

        assert isinstance(metadata, RepositoryMetadata)
        assert metadata.repo == sample_task.repo
        assert metadata.base_commit == sample_task.base_commit
        assert metadata.working_dir == str(temp_path)
        assert metadata.files_count == 3
        assert metadata.primary_language == "Python"  # Most .py files

    env.cleanup()


def test_get_patch_before_checkout(sample_task: Task) -> None:
    """Test get_patch() raises error before checkout."""
    env = TaskEnvironment(sample_task)

    with pytest.raises(RuntimeError) as exc_info:
        env.get_patch()

    assert "checkout_clean_repo" in str(exc_info.value)


def test_get_patch_after_checkout(sample_task: Task) -> None:
    """Test get_patch() returns diff after checkout."""
    env = TaskEnvironment(sample_task)

    with patch("subprocess.run") as mock_run:
        # Set working_dir to simulate successful checkout
        with tempfile.TemporaryDirectory() as temp_dir:
            env.working_dir = Path(temp_dir)

            # Mock git diff
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="diff --git a/file.py b/file.py\n+new line",
                stderr="",
            )

            patch_content = env.get_patch()

            assert "diff --git" in patch_content
            assert "+new line" in patch_content

            # Verify git diff was called
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert "git" in call_args[0][0]
            assert "diff" in call_args[0][0]

    env.cleanup()


def test_cleanup_multiple_calls(sample_task: Task) -> None:
    """Test cleanup() can be called multiple times safely."""
    env = TaskEnvironment(sample_task)

    # Create a mock temp directory
    env._temp_dir = MagicMock()
    env.working_dir = Path("/fake/path")

    # First cleanup
    env.cleanup()
    assert env._temp_dir is None
    assert env.working_dir is None

    # Second cleanup should not raise
    env.cleanup()
    assert env._temp_dir is None
    assert env.working_dir is None


def test_context_manager_success(sample_task: Task) -> None:
    """Test TaskEnvironment as context manager with successful checkout."""
    with patch("subprocess.run") as mock_run:
        # Mock successful git operations
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),  # git clone
            MagicMock(returncode=0, stdout="", stderr=""),  # git checkout
            MagicMock(returncode=0, stdout="", stderr=""),  # git status
        ]

        with TaskEnvironment(sample_task) as env:
            assert env.working_dir is not None

        # After context exit, should be cleaned up
        assert env.working_dir is None
        assert env._temp_dir is None


def test_context_manager_failure(sample_task: Task) -> None:
    """Test TaskEnvironment context manager with checkout failure."""
    with patch("subprocess.run") as mock_run:
        # Mock failed git clone
        from subprocess import CalledProcessError

        mock_run.side_effect = CalledProcessError(
            1, ["git", "clone"], stderr="fatal: repository not found"
        )

        # Should raise RepositoryCheckoutError and cleanup
        with pytest.raises(RepositoryCheckoutError):
            with TaskEnvironment(sample_task) as env:
                pass

        # Should be cleaned up even after error
        # (env is not accessible here, but cleanup should have been called)


def test_repository_metadata_language_detection() -> None:
    """Test language detection in repository metadata."""
    task = Task(
        task_id="test__test-456",
        repo="test/java-repo",
        base_commit="def456abc789",
        issue_text="Test issue",
        test_patch="test patch",
        gold_patch="gold patch",
        created_at="2024-01-01T00:00:00Z",
        sequence_index=0,
        difficulty_label="medium",
    )

    env = TaskEnvironment(task)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        env.working_dir = temp_path

        # Create Java files
        (temp_path / "Main.java").write_text("public class Main {}")
        (temp_path / "Test.java").write_text("public class Test {}")
        (temp_path / "Utils.java").write_text("public class Utils {}")

        metadata = env.repo_metadata()

        assert metadata.primary_language == "Java"
        assert metadata.files_count == 3

    env.cleanup()


def test_repository_metadata_unknown_language() -> None:
    """Test language detection with unknown file types."""
    task = Task(
        task_id="test__test-789",
        repo="test/unknown-repo",
        base_commit="ghi789jkl012",
        issue_text="Test issue",
        test_patch="test patch",
        gold_patch="gold patch",
        created_at="2024-01-01T00:00:00Z",
        sequence_index=0,
        difficulty_label="hard",
    )

    env = TaskEnvironment(task)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        env.working_dir = temp_path

        # Create files with unknown extensions
        (temp_path / "file.xyz").write_text("content")
        (temp_path / "file.abc").write_text("content")

        metadata = env.repo_metadata()

        # Should detect the most common extension
        assert metadata.primary_language in [".xyz", ".abc"]
        assert metadata.files_count == 2

    env.cleanup()
