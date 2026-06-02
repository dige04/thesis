"""Unit tests for the ContainerBackend (Phase 4.8, decisions A+G).

Docker is not available in CI/unit context, so these tests monkeypatch
subprocess.run with a fake that records the docker argv and returns scripted
results — verifying command CONSTRUCTION and output PARSING. The real
in-container integration is exercised only with a live Docker daemon + an
swebench instance image.
"""

import subprocess

import pytest

from src.agents import tools as tools_mod
from src.agents.tools import AgentTools, ContainerBackend


class FakeRun:
    """Records docker calls; returns scripted (rc, stdout, stderr) by substring."""

    def __init__(self):
        self.calls: list[dict] = []
        self.script: dict[str, tuple[int, str, str]] = {}

    def __call__(self, argv, capture_output=True, text=True, timeout=None, input=None, **kw):
        cmd = argv[-1] if isinstance(argv, list) else argv
        self.calls.append({"argv": argv, "cmd": cmd, "input": input, "timeout": timeout})
        rc, out, err = 0, "", ""
        for key, (r, o, e) in self.script.items():
            if key in cmd:
                rc, out, err = r, o, e
                break
        return subprocess.CompletedProcess(argv, rc, out, err)


@pytest.fixture
def fake(monkeypatch):
    f = FakeRun()
    monkeypatch.setattr(tools_mod.subprocess, "run", f)
    return f


def test_exec_wraps_command_in_cd_repo_dir(fake):
    be = ContainerBackend("c123", repo_dir="/testbed")
    be.run("pytest -q", timeout=120)
    call = fake.calls[-1]
    assert call["argv"][:5] == ["docker", "exec", "-i", "c123", "sh"]
    assert call["argv"][5] == "-c"
    assert call["argv"][6] == "cd /testbed && pytest -q"
    assert call["timeout"] == 120


def test_run_returns_streams(fake):
    fake.script = {"pytest": (1, "F\n", "boom")}
    be = ContainerBackend("c1")
    out = be.run("pytest", timeout=60)
    assert out == {"stdout": "F\n", "stderr": "boom", "return_code": 1}


def test_exists_is_file_is_dir_use_test_flags(fake):
    be = ContainerBackend("c1")
    be.exists("a.py")
    assert "test -e /testbed/a.py" in fake.calls[-1]["cmd"]
    be.is_file("a.py")
    assert "test -f /testbed/a.py" in fake.calls[-1]["cmd"]
    be.is_dir("pkg")
    assert "test -d /testbed/pkg" in fake.calls[-1]["cmd"]


def test_read_text_ok_and_missing(fake):
    fake.script = {"cat /testbed/there.py": (0, "hello\n", ""),
                   "cat /testbed/missing.py": (1, "", "no such file")}
    be = ContainerBackend("c1")
    assert be.read_text("there.py") == "hello\n"
    with pytest.raises(FileNotFoundError):
        be.read_text("missing.py")


def test_write_text_pipes_content_via_stdin(fake):
    be = ContainerBackend("c1")
    be.write_text("pkg/new.py", "print(1)\n")
    call = fake.calls[-1]
    assert call["input"] == "print(1)\n"
    assert "mkdir -p" in call["cmd"]
    assert "cat > /testbed/pkg/new.py" in call["cmd"]


def test_search_code_parses_and_strips_dot_slash(fake):
    fake.script = {"grep -rn -E": (0, "./a.py:3:def foo():\n./b.py:7:x = 1\n", "")}
    be = ContainerBackend("c1")
    matches = be.search_code("foo|x", "*")
    assert matches[0] == {"file": "a.py", "line": 3, "content": "def foo():"}
    assert matches[1] == {"file": "b.py", "line": 7, "content": "x = 1"}


def test_git_diff_includes_untracked(fake):
    fake.script = {
        "git diff HEAD": (0, "diff --git a/x b/x\n", ""),
        "git ls-files --others": (0, "new.py\n", ""),
        "cat new.py": (0, "line1\nline2", ""),
    }
    be = ContainerBackend("c1")
    patch = be.git_diff()
    assert "diff --git a/x b/x" in patch
    assert "+++ b/new.py" in patch
    assert "+line1" in patch and "+line2" in patch


def test_list_files_maxdepth_and_relative(fake):
    fake.script = {"find /testbed/pkg": (0, "/testbed/pkg/a.py\n/testbed/pkg/b.py\n", "")}
    be = ContainerBackend("c1")
    files = be.list_files("pkg", "*.py")
    assert files == ["pkg/a.py", "pkg/b.py"]
    assert "-maxdepth 1 -type f" in fake.calls[-1]["cmd"]


def test_agent_tools_routes_through_container_backend(fake):
    """AgentTools(backend=ContainerBackend) drives the container, with tracking."""
    fake.script = {
        "test -e /testbed/a.py": (0, "", ""),
        "test -f /testbed/a.py": (0, "", ""),
        "cat /testbed/a.py": (0, "CONTENT", ""),
    }
    tools = AgentTools(backend=ContainerBackend("c1"))
    assert tools.read_file("a.py") == "CONTENT"
    stats = tools.get_tracker_stats()
    assert stats["tool_call_breakdown"]["read_file"] == 1
