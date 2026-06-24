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

    # Read existing file — new format: header + numbered lines
    content = tools.read_file("test.py")
    assert "1\tprint('hello')" in content

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
    """Test editing files with a standard unified diff (applied via git apply)."""
    tools = AgentTools(str(temp_repo))

    # Standard unified diff (the format the model emits and git apply accepts).
    diff = (
        "--- a/test.py\n"
        "+++ b/test.py\n"
        "@@ -1 +1 @@\n"
        "-print('hello')\n"
        "+print('goodbye')\n"
    )
    tools.edit_file("test.py", diff)

    content = tools.read_file("test.py")
    assert "goodbye" in content
    assert "hello" not in content  # the old line was actually removed, not appended

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


# ---------------------------------------------------------------------------
# read_file range + numbering + budget tests (Task 1)
# ---------------------------------------------------------------------------

def test_read_file_range_exact_when_fits(tmp_path):
    f = tmp_path/"b.py"; f.write_text("\n".join(f"line{i}" for i in range(1,501)))
    out = AgentTools(working_dir=str(tmp_path)).read_file("b.py", 180, 182)
    assert "180\tline180" in out and "182\tline182" in out and "183\t" not in out and "179\t" not in out

def test_read_file_budget_and_no_skip(tmp_path):
    from src.agents.tools import MAX_READ_CHARS
    f = tmp_path/"b.py"; f.write_text("\n".join(f"line{i}" for i in range(1,5001)))
    out = AgentTools(working_dir=str(tmp_path)).read_file("b.py", 1, 5000)
    assert len(out) <= MAX_READ_CHARS
    import re
    last = max(int(x) for x in re.findall(r"(?m)^(\d+)\t", out))   # highest line shown
    assert f"read_file(path, {last+1}," in out                    # continuation == last+1 (no skip)

def test_read_file_oversized_line_progresses(tmp_path):
    from src.agents.tools import MAX_READ_CHARS
    f = tmp_path/"b.py"; f.write_text("x"*(MAX_READ_CHARS*2)+"\nnext")
    out = AgentTools(working_dir=str(tmp_path)).read_file("b.py", 1, 2)
    assert len(out) <= MAX_READ_CHARS and "truncated" in out and "read_file(path, 2," in out

def test_read_file_invalid_and_oob(tmp_path):
    f = tmp_path/"s.py"; f.write_text("a\nb\nc"); t=AgentTools(working_dir=str(tmp_path))
    assert "invalid range" in t.read_file("s.py",3,1).lower()
    assert "past end" in t.read_file("s.py",99).lower()


# ---------------------------------------------------------------------------
# edit_file path normalisation + security guard tests (Task 2b)
# ---------------------------------------------------------------------------

@pytest.fixture
def git_repo(tmp_path):
    """Minimal git repo with m.py committed — mirrors temp_repo for edit_file tests."""
    repo = tmp_path
    os.system(f"cd {repo} && git init -q")
    os.system(f"cd {repo} && git config user.email 'test@test.com'")
    os.system(f"cd {repo} && git config user.name 'Test User'")
    (repo / "m.py").write_text("x = 1\n")
    (repo / "other.py").write_text("y = 2\n")
    os.system(f"cd {repo} && git add -A && git commit -q -m 'init'")
    return repo


def test_edit_file_testbed_git_prefix_applies(git_repo):
    """diff --git a/testbed/m.py b/testbed/m.py headers should be normalised and applied."""
    tools = AgentTools(str(git_repo))
    diff = (
        "diff --git a/testbed/m.py b/testbed/m.py\n"
        "--- a/testbed/m.py\n"
        "+++ b/testbed/m.py\n"
        "@@ -1 +1 @@\n"
        "-x = 1\n"
        "+x = 99\n"
    )
    tools.edit_file("m.py", diff)
    assert (git_repo / "m.py").read_text() == "x = 99\n"


def test_edit_file_absolute_testbed_path_applies(git_repo):
    """--- /testbed/m.py / +++ /testbed/m.py headers (absolute) should be normalised and applied."""
    tools = AgentTools(str(git_repo))
    diff = (
        "diff --git a/testbed/m.py b/testbed/m.py\n"
        "--- /testbed/m.py\n"
        "+++ /testbed/m.py\n"
        "@@ -1 +1 @@\n"
        "-x = 1\n"
        "+x = 42\n"
    )
    tools.edit_file("m.py", diff)
    assert (git_repo / "m.py").read_text() == "x = 42\n"


def test_edit_file_absolute_path_arg_applies(git_repo):
    """path='/testbed/m.py' (absolute container path) + relative diff headers must
    normalise BOTH sides and apply.

    Regression for the 2026-06-24 A/B STOP: 77/78 'security rejections' were false
    because the guard compared the NORMALISED diff path ('m.py') against the RAW
    absolute `path` arg ('/testbed/m.py') → false 'diff touches m.py but
    path=/testbed/m.py'. The LLM legitimately passes the absolute container path."""
    tools = AgentTools(str(git_repo))
    diff = (
        "--- a/m.py\n"
        "+++ b/m.py\n"
        "@@ -1 +1 @@\n"
        "-x = 1\n"
        "+x = 7\n"
    )
    tools.edit_file("/testbed/m.py", diff)
    assert (git_repo / "m.py").read_text() == "x = 7\n"


def test_edit_file_double_slash_testbed_applies(git_repo):
    """diff headers '--- a//testbed/m.py' (git 'a/' prefix + absolute '/testbed/...'
    path → double slash) must normalise and apply.

    Regression for the 2026-06-24 A/B normalize gap: `_strip_path` stripped 'a/'
    then failed to re-strip the now-exposed leading '/' before the 'testbed/'
    check, so 'a//testbed/m.py' survived → git apply 'b/testbed/...: No such file'."""
    tools = AgentTools(str(git_repo))
    diff = (
        "--- a//testbed/m.py\n"
        "+++ b//testbed/m.py\n"
        "@@ -1 +1 @@\n"
        "-x = 1\n"
        "+x = 5\n"
    )
    tools.edit_file("/testbed/m.py", diff)
    assert (git_repo / "m.py").read_text() == "x = 5\n"


def test_edit_file_cross_file_rejected_with_abs_path_arg(git_repo):
    """Even with an absolute path arg, a diff touching a DIFFERENT file must still
    be rejected — the fix must not over-permit after normalising both sides."""
    tools = AgentTools(str(git_repo))
    diff = (
        "--- a/other.py\n"
        "+++ b/other.py\n"
        "@@ -1 +1 @@\n"
        "-y = 2\n"
        "+y = 9\n"
    )
    with pytest.raises(ValueError, match=r"(?i)(security|other\.py|path)"):
        tools.edit_file("/testbed/m.py", diff)
    assert (git_repo / "m.py").read_text() == "x = 1\n"


def test_edit_file_double_slash_testbed_git_header_applies(git_repo):
    """'diff --git a//testbed/m.py b//testbed/m.py' (git-header double-slash form)
    must normalise and apply — covers the `diff --git` path of the a//testbed gap,
    complementing the ---/+++ form in test_edit_file_double_slash_testbed_applies.
    (Codex 2026-06-24 review item.)"""
    tools = AgentTools(str(git_repo))
    diff = (
        "diff --git a//testbed/m.py b//testbed/m.py\n"
        "--- a//testbed/m.py\n"
        "+++ b//testbed/m.py\n"
        "@@ -1 +1 @@\n"
        "-x = 1\n"
        "+x = 3\n"
    )
    tools.edit_file("/testbed/m.py", diff)
    assert (git_repo / "m.py").read_text() == "x = 3\n"


def test_edit_file_absolute_repo_root_path_arg_applies(git_repo):
    """path given as the absolute backend working_dir path (repo_root prefix, NOT
    /testbed) must normalise to repo-relative and apply. (Codex 2026-06-24 review
    item — exercises the repo_root strip branch of _strip_container_prefix.)"""
    tools = AgentTools(str(git_repo))
    abs_path = str(git_repo / "m.py")  # e.g. /private/tmp/.../m.py
    diff = (
        "--- a/m.py\n"
        "+++ b/m.py\n"
        "@@ -1 +1 @@\n"
        "-x = 1\n"
        "+x = 11\n"
    )
    tools.edit_file(abs_path, diff)
    assert (git_repo / "m.py").read_text() == "x = 11\n"


def test_edit_file_path_arg_traversal_rejected(git_repo):
    """A path ARG containing '..' must be rejected by the path-arg guard, before
    the existence check, regardless of the diff content. (Codex 2026-06-24 review
    item — path arg is the authority for what may change.)"""
    tools = AgentTools(str(git_repo))
    diff = (
        "--- a/../escape.py\n"
        "+++ b/../escape.py\n"
        "@@ -1 +1 @@\n"
        "-z = 0\n"
        "+z = 1\n"
    )
    with pytest.raises(ValueError, match=r"(?i)(traversal|\.\.|not allowed)"):
        tools.edit_file("../escape.py", diff)


def test_edit_file_cross_file_rejected(git_repo):
    """A diff touching other.py while path='m.py' must raise ValueError; m.py unchanged."""
    tools = AgentTools(str(git_repo))
    diff = (
        "--- a/other.py\n"
        "+++ b/other.py\n"
        "@@ -1 +1 @@\n"
        "-y = 2\n"
        "+y = 99\n"
    )
    with pytest.raises(ValueError, match=r"(?i)(path|other\.py|security|not allowed)"):
        tools.edit_file("m.py", diff)
    # m.py must be untouched
    assert (git_repo / "m.py").read_text() == "x = 1\n"


def test_edit_file_path_traversal_rejected(git_repo):
    """A diff path containing .. must be rejected."""
    tools = AgentTools(str(git_repo))
    diff = (
        "--- a/../escape.py\n"
        "+++ b/../escape.py\n"
        "@@ -1 +1 @@\n"
        "-z = 0\n"
        "+z = 1\n"
    )
    with pytest.raises(ValueError, match=r"(?i)(traversal|escape|path|\.\.)"):
        tools.edit_file("m.py", diff)


# ---------------------------------------------------------------------------
# Item 8a (final-review): legacy mode edit_file skips cross-file/path guard
# ---------------------------------------------------------------------------

def test_legacy_edit_file_does_not_enforce_cross_file_guard(git_repo, monkeypatch):
    """AGENT_TOOL_MODE=legacy must apply the diff raw without the cross-file
    security guard (Task 5c A/B invariant: legacy reproduces pre-fix behavior).

    The fixed-mode test (test_edit_file_cross_file_rejected) proves the guard
    fires under fixed mode.  This test proves it does NOT fire in legacy mode —
    i.e. a diff touching other.py while path='m.py' succeeds (or at worst fails
    only at git-apply, not at the guard).
    """
    monkeypatch.setenv("AGENT_TOOL_MODE", "legacy")
    tools = AgentTools(str(git_repo))

    # Build a diff that ONLY touches other.py (m.py is unchanged).
    # In fixed mode this raises ValueError("Security: diff touches ...").
    # In legacy mode the path guard is skipped and git apply is attempted.
    diff = (
        "--- a/other.py\n"
        "+++ b/other.py\n"
        "@@ -1 +1 @@\n"
        "-y = 2\n"
        "+y = 77\n"
    )

    # In legacy mode: no ValueError from the security guard.
    # The diff may succeed (git apply succeeds) or fail (git apply error for
    # another reason), but the *guard path* must NOT fire.
    # We assert no ValueError matching the security-guard message pattern.
    try:
        tools.edit_file("m.py", diff)
        # If git apply succeeded, other.py should be changed
        assert (git_repo / "other.py").read_text() == "y = 77\n"
    except ValueError as exc:
        msg = str(exc)
        # Must NOT be the security guard raising; only git-apply failures OK
        assert "Security" not in msg and "diff touches" not in msg, (
            f"Legacy mode raised a security guard ValueError: {msg!r}"
        )
    except Exception:
        # git-apply failures (e.g. RuntimeError) are acceptable in legacy mode
        pass


# ---------------------------------------------------------------------------
# Item 8b (final-review): read_file pagination continuity — next_start == last+1
# ---------------------------------------------------------------------------

def test_read_file_pagination_no_skipped_lines(tmp_path):
    """Two successive ranged reads of a >400-line file must be contiguous:
    the second read's start == first read's last_line_shown + 1 (no skipped lines).

    This validates the continuation hint embedded in the read_file output:
        Call read_file(path, {last+1}, {e}) to continue.
    """
    import re
    from src.agents.tools import AgentTools, MAX_READ_LINES

    # Create a file longer than 2 × MAX_READ_LINES so two ranged reads needed
    n_lines = MAX_READ_LINES * 2 + 50
    content = "\n".join(f"line{i}" for i in range(1, n_lines + 1))
    (tmp_path / "big.py").write_text(content)

    tools = AgentTools(working_dir=str(tmp_path))

    # First read: ask for the whole file
    out1 = tools.read_file("big.py", 1, n_lines)

    # Extract the highest line number shown in out1
    line_numbers = [int(x) for x in re.findall(r"(?m)^(\d+)\t", out1)]
    assert line_numbers, "No numbered lines found in first read output"
    last_shown = max(line_numbers)

    # The continuation hint must reference last_shown + 1 as next start
    expected_next = last_shown + 1
    assert f"read_file(path, {expected_next}," in out1, (
        f"Continuation hint missing or wrong: expected next_start={expected_next}, "
        f"last_shown={last_shown}.\nOutput: {out1[:500]}"
    )

    # Second read: start at the hinted next_start
    out2 = tools.read_file("big.py", expected_next, n_lines)
    line_numbers2 = [int(x) for x in re.findall(r"(?m)^(\d+)\t", out2)]
    assert line_numbers2, "No numbered lines found in second read output"

    first_in_second = min(line_numbers2)
    assert first_in_second == expected_next, (
        f"Second read started at line {first_in_second}, expected {expected_next} "
        f"(no skipped lines). Gap = {first_in_second - expected_next}"
    )


# ---------------------------------------------------------------------------
# Task 3: _TOOL_SCHEMAS — read_file range params; no get_patch advertisement
# ---------------------------------------------------------------------------

def test_read_file_schema_and_no_get_patch():
    from src.agents.langgraph_agent import _TOOL_SCHEMAS
    names = {t["function"]["name"] for t in _TOOL_SCHEMAS}
    assert "get_patch" not in names
    rf = next(t for t in _TOOL_SCHEMAS if t["function"]["name"] == "read_file")
    props = rf["function"]["parameters"]["properties"]
    assert "start_line" in props and "end_line" in props
