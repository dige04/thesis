"""Tests for termination_reason tracking in the CodingAgent ReAct loop.

Drives _run_react_loop (the ACTIVE loop in solve_task) to each exit
and asserts the termination_reason field is set correctly on AgentState.
The 12-node LangGraph (self.graph) is dead code — never invoked.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.agents import langgraph_agent
from src.agents.langgraph_agent import AgentState, CodingAgent, LimitTracker


# ---------------------------------------------------------------------------
# Mock helpers (same pattern as test_agent_react_loop.py)
# ---------------------------------------------------------------------------

class _FakeFunc:
    def __init__(self, name, arguments="{}"):
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, call_id, name, arguments="{}"):
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
    def __init__(self, scripts):
        self._scripts = list(scripts)
        self._i = 0

    def create(self, **kwargs):
        if self._i < len(self._scripts):
            msg = self._scripts[self._i]
            self._i += 1
            return _FakeResponse(msg)
        # fallback: finish
        return _FakeResponse(_FakeMessage(tool_calls=[_FakeToolCall("z", "finish")]))


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


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_agent_and_state(tmp_path):
    """Return (agent, state) with a real working dir."""
    import subprocess
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "foo.py").write_text("x = 1\n")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"],
        cwd=repo, check=True,
    )
    config = {
        "agent": {"max_steps_per_task": 20, "temperature": 0},
        "memory": {"top_k": 5, "max_context_tokens": 2000},
    }
    policy = SimpleNamespace(name="no_memory", retrieve=lambda **kw: [], maintain=lambda store: None)
    task_env = SimpleNamespace(working_dir=str(repo))
    agent = CodingAgent(
        memory_store=MagicMock(),
        policy=policy,
        config=config,
        task_env=task_env,
    )
    from src.agents.tools import AgentTools
    tools = AgentTools(working_dir=str(repo))
    state = AgentState(task_id="t1", repo="r", issue_text="i")
    state.limit_tracker = LimitTracker(
        max_steps=20, max_tool_calls=80, max_test_runs=5, max_wall_time_seconds=1200
    )
    return agent, tools, state


# ---------------------------------------------------------------------------
# Test 1: finished_tool — model calls `finish`
# ---------------------------------------------------------------------------

def test_termination_reason_finished_tool(tmp_path, monkeypatch):
    agent, tools, state = _make_agent_and_state(tmp_path)

    scripts = [
        _FakeMessage(tool_calls=[_FakeToolCall("c1", "finish")]),
    ]
    monkeypatch.setattr(langgraph_agent, "get_chat_client",
                        lambda: _client(_ScriptedCompletions(scripts)))
    monkeypatch.setattr(langgraph_agent, "main_model", lambda: "fake-model")

    agent._run_react_loop(tools, "ctx", state)

    assert state.termination_reason == "finished_tool"
    assert state.finished is True
    assert state.timeout is False


# ---------------------------------------------------------------------------
# Test 2: model_no_tool_calls — model returns no tool calls
# ---------------------------------------------------------------------------

def test_termination_reason_model_no_tool_calls(tmp_path, monkeypatch):
    agent, tools, state = _make_agent_and_state(tmp_path)

    scripts = [
        _FakeMessage(tool_calls=None, content="I'm done."),
    ]
    monkeypatch.setattr(langgraph_agent, "get_chat_client",
                        lambda: _client(_ScriptedCompletions(scripts)))
    monkeypatch.setattr(langgraph_agent, "main_model", lambda: "fake-model")

    agent._run_react_loop(tools, "ctx", state)

    assert state.termination_reason == "model_no_tool_calls"
    assert state.finished is True


# ---------------------------------------------------------------------------
# Test 3: step_limit — tracker.increment_step trips (21st call → over 20)
# ---------------------------------------------------------------------------

def test_termination_reason_step_limit(tmp_path, monkeypatch):
    agent, tools, state = _make_agent_and_state(tmp_path)

    looping = _LoopingCompletions(_FakeToolCall("r", "read_file", '{"path": "foo.py"}'))
    monkeypatch.setattr(langgraph_agent, "get_chat_client", lambda: _client(looping))
    monkeypatch.setattr(langgraph_agent, "main_model", lambda: "fake-model")

    agent._run_react_loop(tools, "ctx", state)

    assert state.termination_reason == "step_limit"
    assert state.timeout is True


# ---------------------------------------------------------------------------
# Test 4: tool_call_limit — tracker.increment_tool_call trips
# ---------------------------------------------------------------------------

def test_termination_reason_tool_call_limit(tmp_path, monkeypatch):
    agent, tools, state = _make_agent_and_state(tmp_path)
    # Set max_tool_calls very low so it trips before step_limit
    state.limit_tracker = LimitTracker(
        max_steps=20, max_tool_calls=2, max_test_runs=5, max_wall_time_seconds=1200
    )

    looping = _LoopingCompletions(_FakeToolCall("r", "read_file", '{"path": "foo.py"}'))
    monkeypatch.setattr(langgraph_agent, "get_chat_client", lambda: _client(looping))
    monkeypatch.setattr(langgraph_agent, "main_model", lambda: "fake-model")

    agent._run_react_loop(tools, "ctx", state)

    assert state.termination_reason == "tool_call_limit"
    assert state.timeout is True


# ---------------------------------------------------------------------------
# Test 5: test_run_limit — tracker.increment_test_run trips
# ---------------------------------------------------------------------------

def test_termination_reason_test_run_limit(tmp_path, monkeypatch):
    agent, tools, state = _make_agent_and_state(tmp_path)
    state.limit_tracker = LimitTracker(
        max_steps=20, max_tool_calls=80, max_test_runs=1, max_wall_time_seconds=1200
    )

    # Return run_tests twice → first succeeds, second trips test_run_limit
    scripts = [
        _FakeMessage(tool_calls=[_FakeToolCall("r", "run_tests", '{"test_command": "pytest"}')]),
        _FakeMessage(tool_calls=[_FakeToolCall("r2", "run_tests", '{"test_command": "pytest"}')]),
    ]
    monkeypatch.setattr(langgraph_agent, "get_chat_client",
                        lambda: _client(_ScriptedCompletions(scripts)))
    monkeypatch.setattr(langgraph_agent, "main_model", lambda: "fake-model")

    agent._run_react_loop(tools, "ctx", state)

    assert state.termination_reason == "test_run_limit"
    assert state.timeout is True


# ---------------------------------------------------------------------------
# Test 6: llm_error — LLM call raises a non-usage-limit exception
# ---------------------------------------------------------------------------

def test_termination_reason_llm_error(tmp_path, monkeypatch):
    agent, tools, state = _make_agent_and_state(tmp_path)

    class _ErrorCompletions:
        def create(self, **kwargs):
            raise RuntimeError("network timeout")

    monkeypatch.setattr(langgraph_agent, "get_chat_client",
                        lambda: _client(_ErrorCompletions()))
    monkeypatch.setattr(langgraph_agent, "main_model", lambda: "fake-model")

    agent._run_react_loop(tools, "ctx", state)

    assert state.termination_reason == "llm_error"
    assert state.error_message is not None
    assert "LLM call failed" in state.error_message


# ---------------------------------------------------------------------------
# Test 7: termination_reason is present in solve_task return dict
# ---------------------------------------------------------------------------

def test_termination_reason_in_solve_task_result(tmp_path, monkeypatch):
    """solve_task must include termination_reason in its return dict."""
    import subprocess
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "foo.py").write_text("x = 1\n")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"],
        cwd=repo, check=True,
    )
    config = {
        "agent": {"max_steps_per_task": 20, "temperature": 0},
        "memory": {"top_k": 5, "max_context_tokens": 2000},
    }
    policy = SimpleNamespace(name="no_memory", retrieve=lambda **kw: [], maintain=lambda s: None)
    agent = CodingAgent(
        memory_store=MagicMock(),
        policy=policy,
        config=config,
        task_env=SimpleNamespace(working_dir=str(repo)),
    )
    scripts = [
        _FakeMessage(tool_calls=[_FakeToolCall("c1", "finish")]),
    ]
    monkeypatch.setattr(langgraph_agent, "get_chat_client",
                        lambda: _client(_ScriptedCompletions(scripts)))
    monkeypatch.setattr(langgraph_agent, "main_model", lambda: "fake-model")

    result = agent.solve_task({
        "task_id": "t1", "repo": "r", "base_commit": "HEAD",
        "issue_text": "fix it", "sequence_index": 0,
    })

    assert "termination_reason" in result
    assert result["termination_reason"] == "finished_tool"
