"""Unit tests for the ContainerBackend (Phase 4.8, decisions A+G).

Docker is not available in CI/unit context, so these tests monkeypatch
subprocess.run with a fake that records the docker argv and returns scripted
results — verifying command CONSTRUCTION and output PARSING. The real
in-container integration is exercised only with a live Docker daemon + an
swebench instance image.
"""

import subprocess
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.agents import tools as tools_mod
from src.agents.langgraph_agent import CodingAgent
from src.agents.tools import AgentTools, ContainerBackend, ContainerSession, LocalBackend


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


def test_git_diff_stages_then_diffs_cached(fake):
    # New files are captured via `git add -A` + `git diff --cached HEAD`, which
    # yields a valid git-apply-able patch (proper diff --git/new file/@@ headers).
    fake.script = {
        "git diff --cached HEAD": (
            0, "diff --git a/new.py b/new.py\nnew file mode 100644\n@@ -0,0 +1,2 @@\n+line1\n+line2\n", ""
        ),
    }
    be = ContainerBackend("c1")
    patch = be.git_diff()
    assert "diff --git a/new.py b/new.py" in patch
    assert "new file mode" in patch
    assert "+line1" in patch and "+line2" in patch
    cmds = [c["cmd"] for c in fake.calls]
    assert any("git add -A" in c for c in cmds)
    assert any("git diff --cached HEAD" in c for c in cmds)


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
    # read_file now returns line-numbered output with a header (Task 1); the
    # container backend's `cat` content must still flow through verbatim.
    assert "1\tCONTENT" in tools.read_file("a.py")
    stats = tools.get_tracker_stats()
    assert stats["tool_call_breakdown"]["read_file"] == 1


# -- ContainerSession + agent backend selection ------------------------------

def test_container_session_image_name():
    # Default (no namespace) = local-build convention, x86_64, no __ encoding.
    assert ContainerSession.image_for("django__django-123") == "sweb.eval.x86_64.django__django-123:latest"
    # arch override
    assert ContainerSession.image_for("django__django-123", arch="arm64") == "sweb.eval.arm64.django__django-123:latest"
    # Pulled (namespace set) matches swebench's published tag: namespaced AND
    # __ -> _1776_ (test_spec.py:107-110).
    assert (
        ContainerSession.image_for("django__django-123", namespace="swebench")
        == "swebench/sweb.eval.x86_64.django_1776_django-123:latest"
    )


def test_container_session_start_backend_stop(fake):
    fake.script = {"infinity": (0, "cid_abc\n", "")}
    session = ContainerSession("sweb.eval.arm64.x:latest")
    assert session.start() == "cid_abc"
    backend = session.backend()
    assert isinstance(backend, ContainerBackend) and backend.container_id == "cid_abc"
    # start argv = docker run -d --rm <image> sleep infinity
    start_argv = fake.calls[0]["argv"]
    assert start_argv[:4] == ["docker", "run", "-d", "--rm"]
    session.stop()
    assert session.container_id is None
    assert fake.calls[-1]["argv"][:3] == ["docker", "rm", "-f"]


def test_container_backend_abs_accepts_absolute_and_relative_paths():
    # Regression: the agent passes BOTH repo-relative and absolute /testbed paths;
    # blindly prefixing repo_dir double-prefixed absolute paths -> "File not found"
    # -> empty patches. _abs must keep absolute paths as-is.
    b = ContainerBackend("cid", repo_dir="/testbed")
    assert b._abs("sympy/core/basic.py") == "/testbed/sympy/core/basic.py"
    assert b._abs("/testbed/sympy/core/basic.py") == "/testbed/sympy/core/basic.py"
    assert b._abs("/abs/elsewhere.py") == "/abs/elsewhere.py"
    assert b._abs(".") == "/testbed"
    assert b._abs("") == "/testbed"


def _agent(cfg: dict, working_dir: str) -> CodingAgent:
    return CodingAgent(
        memory_store=MagicMock(),
        policy=SimpleNamespace(name="no_memory", retrieve=lambda **k: []),
        config=cfg,
        task_env=SimpleNamespace(working_dir=working_dir),
    )


def test_make_tools_local_by_default(tmp_path):
    agent = _agent({"agent": {"max_steps_per_task": 20, "temperature": 0}, "memory": {}}, str(tmp_path))
    tools, session = agent._make_tools(SimpleNamespace(task_id="django__django-1"))
    assert session is None
    assert isinstance(tools.backend, LocalBackend)


def test_make_tools_container_when_configured(fake, tmp_path):
    fake.script = {"infinity": (0, "cid9\n", "")}
    agent = _agent(
        {"agent": {"max_steps_per_task": 20, "temperature": 0, "execution_backend": "container"}, "memory": {}},
        str(tmp_path),
    )
    tools, session = agent._make_tools(SimpleNamespace(task_id="django__django-1"))
    assert session is not None and session.container_id == "cid9"
    assert isinstance(tools.backend, ContainerBackend)
    # image derived from the instance id (local-build convention); default arch
    # is x86_64 (swebench builds x86_64 on this host; arm64 prebuilt images are
    # unpublished). Override via config agent.instance_arch.
    assert session.image == "sweb.eval.x86_64.django__django-1:latest"
    session.stop()
