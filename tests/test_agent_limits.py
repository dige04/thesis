"""
Unit tests for agent execution limits.

Tests frozen decisions from THESIS_FINAL_v5.md §0.1:
- Frozen decision #3: Max 20 steps per task, hard force-fail
- Frozen decision #26: Temperature=0 for all LLM calls
"""

import time
import pytest
from src.agents.coding_agent import (
    CodingAgent,
    AgentExecutionLimits,
    AgentExecutionState,
    AgentTimeoutError,
    create_agent_from_config,
)


class TestAgentExecutionLimits:
    """Test AgentExecutionLimits dataclass and validation."""
    
    def test_default_limits_match_frozen_decisions(self):
        """Test that default limits match frozen decisions from THESIS_FINAL_v5.md."""
        limits = AgentExecutionLimits()
        
        # Frozen decision #3: max 20 steps
        assert limits.max_steps == 20
        
        # Frozen decision #26: temperature=0
        assert limits.temperature == 0.0
        
        # Other locked limits
        assert limits.max_tool_calls == 80
        assert limits.max_test_runs == 5
        assert limits.max_wall_time_minutes == 20
    
    def test_max_steps_must_be_20(self):
        """Test that max_steps cannot be changed from frozen value of 20."""
        with pytest.raises(ValueError, match="max_steps must be 20"):
            AgentExecutionLimits(max_steps=15)
        
        with pytest.raises(ValueError, match="max_steps must be 20"):
            AgentExecutionLimits(max_steps=25)
    
    def test_temperature_must_be_zero(self):
        """Test that temperature cannot be changed from frozen value of 0."""
        with pytest.raises(ValueError, match="temperature must be 0"):
            AgentExecutionLimits(temperature=0.5)
        
        with pytest.raises(ValueError, match="temperature must be 0"):
            AgentExecutionLimits(temperature=1.0)


class TestAgentExecutionState:
    """Test AgentExecutionState tracking."""
    
    def test_initial_state(self):
        """Test initial state values."""
        state = AgentExecutionState()
        
        assert state.step_count == 0
        assert state.tool_call_count == 0
        assert state.test_run_count == 0
        assert state.timeout is False
        assert state.timeout_reason is None
    
    def test_reset_state(self):
        """Test state reset between tasks."""
        state = AgentExecutionState()
        
        # Modify state
        state.step_count = 10
        state.tool_call_count = 50
        state.test_run_count = 3
        state.timeout = True
        state.timeout_reason = "max_steps_exceeded"
        
        # Reset
        state.reset()
        
        # Verify reset
        assert state.step_count == 0
        assert state.tool_call_count == 0
        assert state.test_run_count == 0
        assert state.timeout is False
        assert state.timeout_reason is None
        assert state.start_time > 0
    
    def test_elapsed_time_tracking(self):
        """Test elapsed time calculation."""
        state = AgentExecutionState()
        state.reset()
        
        # Wait a bit
        time.sleep(0.1)
        
        elapsed = state.elapsed_minutes()
        assert elapsed > 0
        assert elapsed < 1  # Should be less than 1 minute


class TestCodingAgent:
    """Test CodingAgent initialization and configuration."""
    
    def test_agent_initialization_with_defaults(self):
        """Test agent initialization with default limits."""
        agent = CodingAgent()
        
        assert agent.limits.max_steps == 20
        assert agent.limits.temperature == 0.0
        assert agent.model == "gpt-5.4"
        assert agent.summary_model == "gpt-4o-mini"
    
    def test_agent_initialization_with_custom_models(self):
        """Test agent initialization with custom model names."""
        agent = CodingAgent(
            model="gpt-4o",
            summary_model="gpt-3.5-turbo"
        )
        
        assert agent.model == "gpt-4o"
        assert agent.summary_model == "gpt-3.5-turbo"
        assert agent.limits.temperature == 0.0  # Still enforced
    
    def test_agent_rejects_non_zero_temperature(self):
        """Test that agent rejects non-zero temperature."""
        limits = AgentExecutionLimits.__new__(AgentExecutionLimits)
        limits.max_steps = 20
        limits.max_tool_calls = 80
        limits.max_test_runs = 5
        limits.max_wall_time_minutes = 20
        limits.temperature = 0.7  # Invalid
        
        with pytest.raises(ValueError, match="Temperature must be 0"):
            CodingAgent(limits=limits)
    
    def test_llm_config_enforces_temperature_zero(self):
        """Test that LLM config always has temperature=0."""
        agent = CodingAgent()
        
        config = agent.get_llm_config()
        assert config["temperature"] == 0.0
        assert config["model"] == "gpt-5.4"
        
        summary_config = agent.get_summary_llm_config()
        assert summary_config["temperature"] == 0.0
        assert summary_config["model"] == "gpt-4o-mini"


class TestAgentLimitEnforcement:
    """Test hard limit enforcement during execution."""
    
    def test_max_steps_enforcement(self):
        """Test that agent force-fails at step 21 (after 20 steps)."""
        agent = CodingAgent()
        
        # Simulate 20 steps (should succeed)
        for i in range(20):
            agent._increment_step()
        
        assert agent.state.step_count == 20
        assert agent.state.timeout is False
        
        # Step 21 should trigger timeout
        with pytest.raises(AgentTimeoutError) as exc_info:
            agent._increment_step()
        
        assert agent.state.timeout is True
        assert agent.state.timeout_reason == "max_steps_exceeded"
        assert exc_info.value.limit_type == "max_steps"
        assert exc_info.value.limit_value == 20
        assert exc_info.value.actual_value == 21
    
    def test_max_tool_calls_enforcement(self):
        """Test that agent force-fails at 81st tool call."""
        agent = CodingAgent()
        
        # Simulate 80 tool calls (should succeed)
        for i in range(80):
            agent._increment_tool_call()
        
        assert agent.state.tool_call_count == 80
        assert agent.state.timeout is False
        
        # 81st tool call should trigger timeout
        with pytest.raises(AgentTimeoutError) as exc_info:
            agent._increment_tool_call()
        
        assert agent.state.timeout is True
        assert agent.state.timeout_reason == "max_tool_calls_exceeded"
        assert exc_info.value.limit_type == "max_tool_calls"
    
    def test_max_test_runs_enforcement(self):
        """Test that agent force-fails at 6th test run."""
        agent = CodingAgent()
        
        # Simulate 5 test runs (should succeed)
        for i in range(5):
            agent._increment_test_run()
        
        assert agent.state.test_run_count == 5
        assert agent.state.timeout is False
        
        # 6th test run should trigger timeout
        with pytest.raises(AgentTimeoutError) as exc_info:
            agent._increment_test_run()
        
        assert agent.state.timeout is True
        assert agent.state.timeout_reason == "max_test_runs_exceeded"
        assert exc_info.value.limit_type == "max_test_runs"
    
    def test_max_wall_time_enforcement(self):
        """Test that agent force-fails after 20 minutes."""
        # Use shorter time limit for testing
        limits = AgentExecutionLimits.__new__(AgentExecutionLimits)
        limits.max_steps = 20
        limits.max_tool_calls = 80
        limits.max_test_runs = 5
        limits.max_wall_time_minutes = 0.001  # ~60ms for testing
        limits.temperature = 0.0
        
        agent = CodingAgent(limits=limits)
        agent.state.reset()
        
        # Wait for timeout
        time.sleep(0.1)  # 100ms > 60ms limit
        
        # Should trigger timeout
        with pytest.raises(AgentTimeoutError) as exc_info:
            agent._check_limits()
        
        assert agent.state.timeout is True
        assert agent.state.timeout_reason == "max_wall_time_exceeded"
        assert exc_info.value.limit_type == "max_wall_time_minutes"
    
    def test_timeout_logged_in_result(self):
        """Test that timeout=true is logged when limits exceeded."""
        agent = CodingAgent()
        
        # Initialize state and set step count to trigger timeout on first increment
        agent.state.reset()
        agent.state.step_count = 21  # Already exceeded limit
        
        # Check limits should trigger timeout
        try:
            agent._check_limits()
            assert False, "Should have raised AgentTimeoutError"
        except AgentTimeoutError:
            pass
        
        # Verify timeout state is set
        assert agent.state.timeout is True
        assert agent.state.timeout_reason == "max_steps_exceeded"


class TestAgentConfigurationLoading:
    """Test agent creation from configuration."""
    
    def test_create_agent_from_config(self):
        """Test creating agent from config dict."""
        config = {
            "agent": {
                "main_model": "gpt-5.4",
                "summary_model": "gpt-4o-mini",
                "temperature": 0,
                "max_steps_per_task": 20,
                "max_tool_calls_per_task": 80,
                "max_test_runs_per_task": 5,
                "max_wall_time_minutes": 20,
            }
        }
        
        agent = create_agent_from_config(config)
        
        assert agent.model == "gpt-5.4"
        assert agent.summary_model == "gpt-4o-mini"
        assert agent.limits.max_steps == 20
        assert agent.limits.temperature == 0.0
    
    def test_create_agent_rejects_invalid_config(self):
        """Test that invalid config is rejected."""
        config = {
            "agent": {
                "max_steps_per_task": 25,  # Invalid - must be 20
                "temperature": 0,
            }
        }
        
        with pytest.raises(ValueError, match="max_steps must be 20"):
            create_agent_from_config(config)
    
    def test_create_agent_with_defaults(self):
        """Test creating agent with minimal config."""
        config = {}
        
        agent = create_agent_from_config(config)
        
        # Should use defaults
        assert agent.limits.max_steps == 20
        assert agent.limits.temperature == 0.0
        assert agent.model == "gpt-5.4"


class TestFrozenDecisionCompliance:
    """Test compliance with frozen decisions from THESIS_FINAL_v5.md."""
    
    def test_frozen_decision_3_max_20_steps(self):
        """
        Test frozen decision #3: Max 20 steps per task, hard force-fail.
        
        From THESIS_FINAL_v5.md §0.1 #3:
        "Max 20 steps per task, hard force-fail if exceeded"
        """
        agent = CodingAgent()
        
        # Verify limit is exactly 20
        assert agent.limits.max_steps == 20
        
        # Verify hard force-fail at step 21
        agent.state.step_count = 20
        with pytest.raises(AgentTimeoutError):
            agent._increment_step()
        
        assert agent.state.timeout is True
    
    def test_frozen_decision_26_temperature_zero(self):
        """
        Test frozen decision #26: Temperature=0 for all LLM calls.
        
        From THESIS_FINAL_v5.md §0.1 #26:
        "Temperature: 0 for all LLM calls (reproducibility)"
        """
        agent = CodingAgent()
        
        # Verify temperature is exactly 0
        assert agent.limits.temperature == 0.0
        
        # Verify LLM configs enforce temperature=0
        assert agent.get_llm_config()["temperature"] == 0.0
        assert agent.get_summary_llm_config()["temperature"] == 0.0
        
        # Verify non-zero temperature is rejected
        with pytest.raises(ValueError, match="temperature must be 0"):
            AgentExecutionLimits(temperature=0.1)
    
    def test_all_limits_locked(self):
        """Test that all execution limits are locked to frozen values."""
        agent = CodingAgent()
        
        # Verify all frozen limits
        assert agent.limits.max_steps == 20              # Frozen #3
        assert agent.limits.max_tool_calls == 80         # Locked
        assert agent.limits.max_test_runs == 5           # Locked
        assert agent.limits.max_wall_time_minutes == 20  # Locked
        assert agent.limits.temperature == 0.0           # Frozen #26
