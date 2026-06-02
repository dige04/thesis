"""Tests for the v5 §4.4 ReAct tool-use loop in CodingAgent.solve_task.

Uses a fake tool-calling chat client (no network) driving real AgentTools
against a real temporary git repo, so the loop, tool dispatch, patch
generation, trajectory recording, and hard step limit are all exercised.
"""

import subprocess
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.agents import langgraph_agent
from src.agents.langgraph_agent import CodingAgent

# --- fake OpenAI-compatible chat client -------------------------------------

class _FakeFunc:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, call_id, name, arguments):
        self.id = call_id
        self.type = "function"
        self.function = _FakeFunc(name, arguments)


class _FakeMessage:
    def __init__(self, tool_calls=None, content=""):
        self.tool_calls = tool_calls
        self.content = content


class _FakeUsage:
    prompt_tokens = 10
    completion_tokens = 5
    total_tokens = 15


class _FakeResponse:
    def __init__(self, message):
        self.choices = [SimpleNamespace(message=message)]
        self.usage = _FakeUsage()


class _ScriptedCompletions:
    """Returns each scripted assistant message in turn, then a `finish`."""

    def __init__(self, scripts):
        self._scripts = scripts
        self._i = 0

    def create(self, **kwargs):
        if self._i < len(self._scripts):
            msg = self._scripts[self._i]
            self._i += 1
            return _FakeResponse(msg)
        return _FakeResponse(_FakeMessage(tool_calls=[_FakeToolCall("z", "finish", "{}")]))


class _LoopingCompletions:
    """Always returns the same (non-finish) tool call — never finishes."""

    def __init__(self, tool_call):
        self._tc = tool_call

    def create(self, **kwargs):
        return _FakeResponse(_FakeMessage(tool_calls=[self._tc]))


def _client(completions):
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


# --- fixtures ----------------------------------------------------------------

def _git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "bug.py").write_text("def add(a, b):\n    return a - b\n")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "init"],
        cwd=repo, check=True,
    )
    return repo


def _make_agent(repo):
    config = {
        "agent": {"max_steps_per_task": 20, "temperature": 0},
        "memory": {"top_k": 5, "max_context_tokens": 2000},
    }
    policy = SimpleNamespace(name="no_memory", retrieve=lambda **kw: [])
    task_env = SimpleNamespace(working_dir=str(repo))
    return CodingAgent(
        memory_store=MagicMock(),
        policy=policy,
        config=config,
        task_env=task_env,
    )


TASK = {
    "task_id": "demo__demo-1",
    "repo": "demo/demo",
    "base_commit": "HEAD",
    "issue_text": "add() subtracts instead of adding",
    "sequence_index": 0,
}


def test_agent_edits_file_and_produces_patch(tmp_path, monkeypatch):
    repo = _git_repo(tmp_path)
    scripts = [
        _FakeMessage(tool_calls=[
            _FakeToolCall(
                "c1", "write_file",
                '{"path": "bug.py", "content": "def add(a, b):\\n    return a + b\\n"}',
            )
        ]),
        _FakeMessage(tool_calls=[_FakeToolCall("c2", "finish", "{}")]),
    ]
    monkeypatch.setattr(langgraph_agent, "get_chat_client", lambda: _client(_ScriptedCompletions(scripts)))
    monkeypatch.setattr(langgraph_agent, "main_model", lambda: "fake-model")

    agent = _make_agent(repo)
    result = agent.solve_task(TASK)

    assert result["patch_generated"] is True
    assert "return a + b" in result["patch"]
    assert result["timeout"] is False
    assert "bug.py" in result["files_modified"]
    assert result["total_tokens"] > 0
    actions = [t["action"] for t in result["trajectory"]]
    assert "write_file" in actions
    # The agent (not the runner) must NOT run policy maintenance.
    assert "finish" not in actions  # finish is control flow, not a recorded tool action


def test_agent_times_out_after_max_steps(tmp_path, monkeypatch):
    repo = _git_repo(tmp_path)
    looping = _LoopingCompletions(_FakeToolCall("r", "read_file", '{"path": "bug.py"}'))
    monkeypatch.setattr(langgraph_agent, "get_chat_client", lambda: _client(looping))
    monkeypatch.setattr(langgraph_agent, "main_model", lambda: "fake-model")

    agent = _make_agent(repo)
    result = agent.solve_task(TASK)

    assert result["timeout"] is True
    assert result["step_count"] == 21  # 20 turns run; the 21st trips (strict max-20)
    assert "step" in (result["error_message"] or "").lower()
