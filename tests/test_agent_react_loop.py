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
from src.memory.record import MemoryRecord

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
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
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


class _CapturingCompletions:
    """Records the kwargs of the last create() call; returns `finish` immediately."""

    def __init__(self):
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return _FakeResponse(_FakeMessage(tool_calls=[_FakeToolCall("z", "finish", "{}")]))


def _agent_with(config_agent, repo):
    config = {
        "agent": {"max_steps_per_task": 20, "temperature": 1, **config_agent},
        "memory": {"top_k": 5, "max_context_tokens": 2000},
    }
    return CodingAgent(
        memory_store=MagicMock(),
        policy=SimpleNamespace(name="no_memory", retrieve=lambda **kw: []),
        config=config,
        task_env=SimpleNamespace(working_dir=str(repo)),
    )


def test_agent_passes_reasoning_effort_when_configured(tmp_path, monkeypatch):
    repo = _git_repo(tmp_path)
    cap = _CapturingCompletions()
    monkeypatch.setattr(langgraph_agent, "get_chat_client", lambda: _client(cap))
    monkeypatch.setattr(langgraph_agent, "main_model", lambda: "fake-model")
    _agent_with({"reasoning_effort": "high"}, repo).solve_task(TASK)
    assert cap.last_kwargs.get("reasoning_effort") == "high"


def test_agent_omits_reasoning_effort_when_unset(tmp_path, monkeypatch):
    repo = _git_repo(tmp_path)
    cap = _CapturingCompletions()
    monkeypatch.setattr(langgraph_agent, "get_chat_client", lambda: _client(cap))
    monkeypatch.setattr(langgraph_agent, "main_model", lambda: "fake-model")
    _agent_with({}, repo).solve_task(TASK)
    assert "reasoning_effort" not in cap.last_kwargs


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
    # C3 regression (THESIS_REVIEW): the cap must fire BEFORE a 21st model call.
    # Exactly 20 chat.completions.create calls execute — the 21st iteration trips
    # increment_step() and breaks before reaching the client. Guards Invariant #3
    # against any future loop refactor that would re-introduce the off-by-one.
    assert looping.calls == 20


def _counting_policy():
    calls = {"n": 0}

    def _retrieve(**kw):
        calls["n"] += 1
        return []

    return SimpleNamespace(name="full_memory", retrieve=_retrieve), calls


def _agent_with_policy(repo, policy):
    return CodingAgent(
        memory_store=MagicMock(),
        policy=policy,
        config={
            "agent": {"max_steps_per_task": 20, "temperature": 0},
            "memory": {"top_k": 5, "max_context_tokens": 2000},
        },
        task_env=SimpleNamespace(working_dir=str(repo)),
    )


def test_runner_supplied_retrieval_is_authoritative(tmp_path, monkeypatch):
    """C4 (THESIS_REVIEW): when the runner passes its retrieval in, the agent must
    NOT re-retrieve. The supplied scored list is exactly what is shown to the model
    and logged — eliminating the double retrieval and logged-vs-shown divergence."""
    repo = _git_repo(tmp_path)
    # Model finishes immediately — we exercise retrieval handling, not the loop.
    scripts = [_FakeMessage(tool_calls=[_FakeToolCall("c1", "finish", "{}")])]
    monkeypatch.setattr(langgraph_agent, "get_chat_client",
                        lambda: _client(_ScriptedCompletions(scripts)))
    monkeypatch.setattr(langgraph_agent, "main_model", lambda: "fake-model")

    policy, calls = _counting_policy()
    agent = _agent_with_policy(repo, policy)

    rec = MemoryRecord(
        memory_id="MEM-supplied", task_id="t-0", repo="demo/demo",
        sequence_index=0, memory_type="bug_fix", outcome="pass",
        issue_summary="prior issue", patch_summary="prior patch",
        embedding_text="e", token_length=10,
    )
    result = agent.solve_task(TASK, retrieved_memories=[(0.95, rec)])

    assert calls["n"] == 0, "agent re-retrieved despite the runner supplying the list"
    assert result["retrieved_memory_ids"] == ["MEM-supplied"]


def test_agent_self_retrieves_when_none_supplied(tmp_path, monkeypatch):
    """Backward-compat: a standalone call (no supplied list) retrieves exactly once."""
    repo = _git_repo(tmp_path)
    scripts = [_FakeMessage(tool_calls=[_FakeToolCall("c1", "finish", "{}")])]
    monkeypatch.setattr(langgraph_agent, "get_chat_client",
                        lambda: _client(_ScriptedCompletions(scripts)))
    monkeypatch.setattr(langgraph_agent, "main_model", lambda: "fake-model")

    policy, calls = _counting_policy()
    agent = _agent_with_policy(repo, policy)

    agent.solve_task(TASK)

    assert calls["n"] == 1


def test_assistant_message_strips_think_from_resent_content():
    """MiniMax M3 is a reasoning model: its <think>...</think> CoT must not be
    re-sent to the provider each turn (keeps prompt-token cost lean; trajectory
    already excludes content). The tool_calls themselves are preserved."""
    msg = SimpleNamespace(content="<think>I should edit foo.py first</think>\nEditing.")
    tc = SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(name="edit_file", arguments='{"path": "foo.py"}'),
    )

    out = CodingAgent._assistant_message(msg, [tc])

    assert "<think>" not in out["content"]
    assert "I should edit foo.py first" not in out["content"]
    assert out["content"] == "Editing."
    # tool calls survive untouched
    assert out["tool_calls"][0]["function"]["name"] == "edit_file"
    assert out["tool_calls"][0]["function"]["arguments"] == '{"path": "foo.py"}'
