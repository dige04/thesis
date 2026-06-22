"""
Unit tests for agent execution limits.

Migrated 2026-06-02 from the deleted ``src/agents/coding_agent.py`` scaffold
(plan decision M / Phase 2.10). The live agent is
``src.agents.langgraph_agent.CodingAgent``, which enforces the frozen
invariants via ``src.agents.limit_tracker.LimitTracker`` +
``validate_temperature`` and a config-driven constructor gate.

Tests frozen decisions from THESIS_FINAL_v5.md §0.1:
- Frozen decision #3: Max 20 steps per task, hard force-fail
- Frozen decision #26: Temperature=0 for all LLM calls

The *agent-level* force-fail boundary (20 turns run, the 21st trips) is covered
end-to-end in ``tests/test_agent_react_loop.py``. Here we unit-test the
canonical limit mechanisms and the constructor's invariant gate.
"""

import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.agents.langgraph_agent import CodingAgent
from src.agents.limit_tracker import LimitTracker, LimitType, validate_temperature
from src.errors import AgentTimeoutError


class TestLimitTrackerFrozenValues:
    """LimitTracker carries the frozen default caps."""

    def test_default_limits_match_frozen_decisions(self):
        tracker = LimitTracker()
        assert tracker.max_steps == 20  # Frozen decision #3
        assert tracker.max_tool_calls == 80
        assert tracker.max_test_runs == 5
        assert tracker.max_wall_time_seconds == 1200  # 20 minutes

    def test_max_steps_must_be_20(self):
        """Frozen invariant #3: max_steps cannot be changed from 20."""
        with pytest.raises(ValueError, match="max_steps must be 20"):
            LimitTracker(max_steps=15)
        with pytest.raises(ValueError, match="max_steps must be 20"):
            LimitTracker(max_steps=25)


class TestTemperatureInvariant:
    """Frozen decision #26, amended 2026-06-14: temperature held CONSTANT across all
    conditions; value is 0 OR 1 (1 for Kimi reasoning models, which reject 0)."""

    def test_temperature_0_or_1_ok(self):
        validate_temperature(0)  # determinism providers
        validate_temperature(0.0)
        validate_temperature(1)  # reasoning providers (Kimi) — 2026-06-14 amendment
        validate_temperature(1.0)

    def test_temperature_other_values_rejected(self):
        with pytest.raises(ValueError, match="must be 0 or 1"):
            validate_temperature(0.5)
        with pytest.raises(ValueError, match="must be 0 or 1"):
            validate_temperature(2.0)


class TestLimitTrackerBoundaries:
    """Strict boundaries: the Nth use is allowed, the (N+1)th trips.

    increment_* is post-increment and returns True only when the count
    EXCEEDS the cap, so 20 steps all pass and the 21st trips (strict
    Invariant #3).
    """

    def test_step_boundary_20_allowed_21_trips(self):
        tracker = LimitTracker()
        for _ in range(20):
            assert tracker.increment_step() is False
        assert tracker.step_count == 20
        assert tracker.limit_exceeded is False

        # The 21st step trips the hard limit.
        assert tracker.increment_step() is True
        assert tracker.step_count == 21
        assert tracker.limit_exceeded is True
        assert tracker.exceeded_limit_type == LimitType.STEPS

    def test_tool_call_boundary_80_allowed_81_trips(self):
        tracker = LimitTracker()
        for _ in range(80):
            assert tracker.increment_tool_call() is False
        assert tracker.increment_tool_call() is True
        assert tracker.exceeded_limit_type == LimitType.TOOL_CALLS

    def test_test_run_boundary_5_allowed_6_trips(self):
        tracker = LimitTracker()
        for _ in range(5):
            assert tracker.increment_test_run() is False
        assert tracker.increment_test_run() is True
        assert tracker.exceeded_limit_type == LimitType.TEST_RUNS

    def test_wall_time_exceeded(self):
        tracker = LimitTracker(max_wall_time_seconds=0)
        time.sleep(0.01)
        assert tracker.check_wall_time() is True
        assert tracker.exceeded_limit_type == LimitType.WALL_TIME

    def test_reset_clears_counts(self):
        tracker = LimitTracker()
        tracker.increment_step()
        tracker.increment_tool_call()
        tracker.increment_test_run()
        tracker.reset()
        assert tracker.step_count == 0
        assert tracker.tool_call_count == 0
        assert tracker.test_run_count == 0
        assert tracker.limit_exceeded is False
        assert tracker.exceeded_limit_type is None


def _agent_config(max_steps: int = 20, temperature: float = 0) -> dict:
    return {
        "agent": {"max_steps_per_task": max_steps, "temperature": temperature},
        "memory": {"top_k": 5, "max_context_tokens": 2000},
    }


def _make_agent(config: dict) -> CodingAgent:
    return CodingAgent(
        memory_store=MagicMock(),
        policy=SimpleNamespace(name="no_memory", retrieve=lambda **kw: []),
        config=config,
        task_env=SimpleNamespace(working_dir="/tmp"),
    )


class TestCodingAgentConstructorInvariants:
    """The live agent rejects non-frozen limits at construction time."""

    def test_constructor_accepts_frozen_defaults(self):
        agent = _make_agent(_agent_config())
        assert agent.max_steps == 20
        assert agent.temperature == 0

    def test_constructor_rejects_non_20_max_steps(self):
        with pytest.raises(ValueError, match="max_steps must be 20"):
            _make_agent(_agent_config(max_steps=25))

    def test_constructor_rejects_invalid_temperature(self):
        # 0.5 is neither 0 (determinism) nor 1 (Kimi reasoning) — still invalid.
        with pytest.raises(ValueError, match="must be 0 or 1"):
            _make_agent(_agent_config(temperature=0.5))


class TestCanonicalTimeoutError:
    """errors.AgentTimeoutError carries the canonical limit-failure signature."""

    def test_canonical_signature(self):
        err = AgentTimeoutError(
            "step limit exceeded",
            task_id="repo__repo-1",
            limit_type="max_steps",
            limit_value=20,
            actual_value=21,
        )
        assert err.task_id == "repo__repo-1"
        assert err.limit_type == "max_steps"
        assert err.limit_value == 20
        assert err.actual_value == 21
