"""
Unit tests for agent tools.

Tests basic functionality of all agent tools and tool call tracking.
"""

import os
import tempfile
from pathlib import Path

import pytest

from src.agents.tools import AgentTools, ToolCallTracker


@pytest.fixture
def temp_repo():
    """Create a temporary repository for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)

        # Initialize git repo
        os.system(f"cd {repo_path} && git init")
        os.system(f"cd {repo_path} && git config user.email 'test@test.com'")
        os.system(f"cd {repo_path} && git config user.name 'Test User'")

        # Create some test files
        (repo_path / "test.py").write_text("print('hello')\n")
        (repo_path / "subdir").mkdir()
        (repo_path / "subdir" / "module.py").write_text("def foo():\n    pass\n")

        # Initial commit
        os.system(f"cd {repo_path} && git add -A && git commit -m 'Initial commit'")

        yield repo_path


def test_tool_call_tracker():
    """Test tool call tracking for behavioral metrics."""
    tracker = ToolCallTracker()

    # Record some calls
    tracker.record_call("read_file", {"path": "test.py"}, 100)
    tracker.record_call("write_file", {"path": "new.py"}, "success")
    tracker.record_call("read_file", {"path": "missing.py"}, None, "File not found")
    tracker.record_syntax_error()
    tracker.record_syntax_error()

    stats = tracker.get_stats()

    assert stats["total_tool_calls"] == 3
    assert stats["syntax_errors"] == 2
    assert stats["tool_call_breakdown"]["read_file"] == 2
    assert stats["tool_call_breakdown"]["write_file"] == 1


def test_read_file(temp_repo):
    """Test reading files."""
    tools = AgentTools(str(temp_repo))

    # Read existing file
    content = tools.read_file("test.py")
    assert content == "print('hello')\n"

    # Read file in subdirectory
    content = tools.read_file("subdir/module.py")
    assert "def foo():" in content

    # Try to read non-existent file (this also gets tracked)
    with pytest.raises(FileNotFoundError):
        tools.read_file("missing.py")

    # Try to read a directory (this also gets tracked)
    with pytest.raises(ValueError):
        tools.read_file("subdir")

    # Check tracking - all calls including failed ones are tracked
    stats = tools.get_tracker_stats()
    assert stats["total_tool_calls"] == 4
    assert stats["tool_call_breakdown"]["read_file"] == 4


def test_write_file(temp_repo):
    """Test writing files."""
    tools = AgentTools(str(temp_repo))

    # Write new file
    tools.write_file("new.py", "print('new')\n")
    assert (temp_repo / "new.py").read_text() == "print('new')\n"

    # Write file in new subdirectory
    tools.write_file("newdir/another.py", "# comment\n")
    assert (temp_repo / "newdir" / "another.py").read_text() == "# comment\n"

    # Overwrite existing file
    tools.write_file("test.py", "print('modified')\n")
    assert (temp_repo / "test.py").read_text() == "print('modified')\n"

    # Check tracking
    stats = tools.get_tracker_stats()
    assert stats["total_tool_calls"] == 3
    assert stats["tool_call_breakdown"]["write_file"] == 3


def test_edit_file(temp_repo):
    """Test editing files with diff."""
    tools = AgentTools(str(temp_repo))

    # Simple edit
    diff = "-print('hello')\n+print('goodbye')\n"
    tools.edit_file("test.py", diff)

    content = tools.read_file("test.py")
    assert "goodbye" in content

    # Try to edit non-existent file (this also gets tracked)
    with pytest.raises(FileNotFoundError):
        tools.edit_file("missing.py", diff)

    # Check tracking - includes the read_file call and both edit_file calls
    stats = tools.get_tracker_stats()
    assert stats["tool_call_breakdown"]["edit_file"] == 2
    assert stats["tool_call_breakdown"]["read_file"] == 1


def test_list_files(temp_repo):
    """Test listing files."""
    tools = AgentTools(str(temp_repo))

    # List all files in root
    files = tools.list_files(".", "*.py")
    assert "test.py" in files

    # List files in subdirectory
    files = tools.list_files("subdir", "*.py")
    assert any("module.py" in f for f in files)

    # Try to list non-existent directory (this also gets tracked)
    with pytest.raises(FileNotFoundError):
        tools.list_files("missing")

    # Try to list a file instead of directory (this also gets tracked)
    with pytest.raises(ValueError):
        tools.list_files("test.py")

    # Check tracking - all calls including failed ones are tracked
    stats = tools.get_tracker_stats()
    assert stats["total_tool_calls"] == 4
    assert stats["tool_call_breakdown"]["list_files"] == 4


def test_search_code(temp_repo):
    """Test code search."""
    tools = AgentTools(str(temp_repo))

    # Search for pattern
    matches = tools.search_code("print")
    assert len(matches) > 0
    assert any(m["file"] == "test.py" for m in matches)

    # Search with file pattern
    matches = tools.search_code("def", "*.py")
    assert any("foo" in m["content"] for m in matches)

    # Check tracking
    stats = tools.get_tracker_stats()
    assert stats["tool_call_breakdown"]["search_code"] == 2


def test_run_command(temp_repo):
    """Test running shell commands."""
    tools = AgentTools(str(temp_repo))

    # Run successful command
    result = tools.run_command("echo 'test'")
    assert result["success"] is True
    assert "test" in result["stdout"]
    assert result["return_code"] == 0

    # Run failing command
    result = tools.run_command("exit 1")
    assert result["success"] is False
    assert result["return_code"] == 1

    # Check tracking
    stats = tools.get_tracker_stats()
    assert stats["tool_call_breakdown"]["run_command"] == 2


def test_run_tests(temp_repo):
    """Test running test commands."""
    tools = AgentTools(str(temp_repo))

    # Run simple test command (just echo for testing)
    result = tools.run_tests("echo 'tests passed'")
    assert result["success"] is True
    assert result["tests_passed"] is True

    # Check tracking
    stats = tools.get_tracker_stats()
    assert stats["tool_call_breakdown"]["run_tests"] == 1


def test_get_patch(temp_repo):
    """Test generating git patches."""
    tools = AgentTools(str(temp_repo))

    # Make some changes
    tools.write_file("test.py", "print('modified')\n")
    tools.write_file("new_file.py", "# new file\n")

    # Get patch
    patch = tools.get_patch()
    assert "test.py" in patch
    assert "modified" in patch or "new_file.py" in patch

    # Check tracking
    stats = tools.get_tracker_stats()
    assert stats["tool_call_breakdown"]["get_patch"] == 1


def test_syntax_error_tracking(temp_repo):
    """Test syntax error tracking in command output."""
    tools = AgentTools(str(temp_repo))

    # Create a file with syntax error
    tools.write_file("bad.py", "def foo(\n")  # Missing closing paren

    # Run Python on it (will produce syntax error)
    result = tools.run_command("python bad.py")

    # Check that syntax error was tracked
    stats = tools.get_tracker_stats()
    assert stats["syntax_errors"] >= 1


def test_tool_call_error_tracking(temp_repo):
    """Test that failed tool calls are tracked correctly."""
    tools = AgentTools(str(temp_repo))

    # Try operations that will fail
    try:
        tools.read_file("missing.py")
    except FileNotFoundError:
        pass

    try:
        tools.read_file("subdir")  # Try to read a directory
    except ValueError:
        pass

    try:
        tools.list_files("missing_dir")
    except FileNotFoundError:
        pass

    try:
        tools.list_files("test.py")  # Try to list a file
    except ValueError:
        pass

    # Check that failed calls are tracked
    stats = tools.get_tracker_stats()
    assert stats["total_tool_calls"] == 4

    # Check that errors are recorded
    for call in tools.tracker.tool_calls:
        if not call["success"]:
            assert call["error"] is not None
