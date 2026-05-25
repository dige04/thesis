"""
Unit tests for agent execution limit tracker.

Tests all hard limits and frozen invariants:
- Max 20 steps per task (FROZEN INVARIANT)
- Max 80 tool calls per task
- Max 5 test runs per task
- Max 20 minutes wall time per task
- Temperature=0 validation (FROZEN INVARIANT)
"""

import time

import pytest

from src.agents.limit_tracker import LimitTracker, LimitType, validate_temperature


class TestLimitTrackerFrozenInvariants:
    """Test frozen invariants that must never be violated."""

    def test_max_steps_frozen_at_20(self):
        """Test that max_steps is frozen at 20 (FROZEN INVARIANT)."""
        tracker = LimitTracker()
        assert tracker.max_steps == 20, "max_steps must be frozen at 20"

    def test_max_steps_cannot_be_changed(self):
        """Test that attempting to change max_steps raises an error."""
        with pytest.raises(ValueError, match="FROZEN INVARIANT VIOLATION"):
            LimitTracker(max_steps=25)

    def test_temperature_zero_validation(self):
        """Test that temperature=0 is enforced (FROZEN INVARIANT)."""
        # Should not raise
        validate_temperature(0)
        validate_temperature(0.0)

        # Should raise
        with pytest.raises(ValueError, match="FROZEN INVARIANT VIOLATION"):
            validate_temperature(0.1)

        with pytest.raises(ValueError, match="FROZEN INVARIANT VIOLATION"):
            validate_temperature(1.0)


class TestLimitTrackerStepLimit:
    """Test step count limit enforcement."""

    def test_step_count_increments(self):
        """Test that step count increments correctly."""
        tracker = LimitTracker()
        assert tracker.step_count == 0

        tracker.increment_step()
        assert tracker.step_count == 1

        tracker.increment_step()
        assert tracker.step_count == 2

    def test_step_limit_not_exceeded_at_20(self):
        """Test that step limit is not exceeded at exactly 20 steps."""
        tracker = LimitTracker()

        for i in range(20):
            exceeded = tracker.increment_step()
            assert not exceeded, f"Step {i+1} should not exceed limit"

        assert tracker.step_count == 20
        assert not tracker.limit_exceeded

    def test_step_limit_exceeded_at_21(self):
        """Test that step limit is exceeded at 21 steps."""
        tracker = LimitTracker()

        # First 20 steps should not exceed
        for _ in range(20):
            tracker.increment_step()

        # 21st step should exceed
        exceeded = tracker.increment_step()
        assert exceeded, "Step 21 should exceed limit"
        assert tracker.step_count == 21
        assert tracker.limit_exceeded
        assert tracker.exceeded_limit_type == LimitType.STEPS

    def test_step_limit_failure_reason(self):
        """Test that step limit failure reason is descriptive."""
        tracker = LimitTracker()

        for _ in range(21):
            tracker.increment_step()

        reason = tracker.get_failure_reason()
        assert "Exceeded maximum steps" in reason
        assert "21 > 20" in reason


class TestLimitTrackerToolCallLimit:
    """Test tool call limit enforcement."""

    def test_tool_call_count_increments(self):
        """Test that tool call count increments correctly."""
        tracker = LimitTracker()
        assert tracker.tool_call_count == 0

        tracker.increment_tool_call()
        assert tracker.tool_call_count == 1

        tracker.increment_tool_call()
        assert tracker.tool_call_count == 2

    def test_tool_call_limit_not_exceeded_at_80(self):
        """Test that tool call limit is not exceeded at exactly 80 calls."""
        tracker = LimitTracker()

        for i in range(80):
            exceeded = tracker.increment_tool_call()
            assert not exceeded, f"Tool call {i+1} should not exceed limit"

        assert tracker.tool_call_count == 80
        assert not tracker.limit_exceeded

    def test_tool_call_limit_exceeded_at_81(self):
        """Test that tool call limit is exceeded at 81 calls."""
        tracker = LimitTracker()

        # First 80 calls should not exceed
        for _ in range(80):
            tracker.increment_tool_call()

        # 81st call should exceed
        exceeded = tracker.increment_tool_call()
        assert exceeded, "Tool call 81 should exceed limit"
        assert tracker.tool_call_count == 81
        assert tracker.limit_exceeded
        assert tracker.exceeded_limit_type == LimitType.TOOL_CALLS

    def test_tool_call_limit_failure_reason(self):
        """Test that tool call limit failure reason is descriptive."""
        tracker = LimitTracker()

        for _ in range(81):
            tracker.increment_tool_call()

        reason = tracker.get_failure_reason()
        assert "Exceeded maximum tool calls" in reason
        assert "81 > 80" in reason


class TestLimitTrackerTestRunLimit:
    """Test test run limit enforcement."""

    def test_test_run_count_increments(self):
        """Test that test run count increments correctly."""
        tracker = LimitTracker()
        assert tracker.test_run_count == 0

        tracker.increment_test_run()
        assert tracker.test_run_count == 1

        tracker.increment_test_run()
        assert tracker.test_run_count == 2

    def test_test_run_limit_not_exceeded_at_5(self):
        """Test that test run limit is not exceeded at exactly 5 runs."""
        tracker = LimitTracker()

        for i in range(5):
            exceeded = tracker.increment_test_run()
            assert not exceeded, f"Test run {i+1} should not exceed limit"

        assert tracker.test_run_count == 5
        assert not tracker.limit_exceeded

    def test_test_run_limit_exceeded_at_6(self):
        """Test that test run limit is exceeded at 6 runs."""
        tracker = LimitTracker()

        # First 5 runs should not exceed
        for _ in range(5):
            tracker.increment_test_run()

        # 6th run should exceed
        exceeded = tracker.increment_test_run()
        assert exceeded, "Test run 6 should exceed limit"
        assert tracker.test_run_count == 6
        assert tracker.limit_exceeded
        assert tracker.exceeded_limit_type == LimitType.TEST_RUNS

    def test_test_run_limit_failure_reason(self):
        """Test that test run limit failure reason is descriptive."""
        tracker = LimitTracker()

        for _ in range(6):
            tracker.increment_test_run()

        reason = tracker.get_failure_reason()
        assert "Exceeded maximum test runs" in reason
        assert "6 > 5" in reason


class TestLimitTrackerWallTimeLimit:
    """Test wall time limit enforcement."""

    def test_wall_time_not_exceeded_initially(self):
        """Test that wall time is not exceeded immediately."""
        tracker = LimitTracker()
        exceeded = tracker.check_wall_time()
        assert not exceeded
        assert not tracker.limit_exceeded

    def test_wall_time_elapsed_time(self):
        """Test that elapsed time is tracked correctly."""
        tracker = LimitTracker()
        time.sleep(0.1)
        elapsed = tracker.get_elapsed_time()
        assert elapsed >= 0.1, "Elapsed time should be at least 0.1 seconds"

    def test_wall_time_limit_exceeded(self):
        """Test that wall time limit is exceeded when time passes."""
        # Use a very short time limit for testing
        tracker = LimitTracker(max_wall_time_seconds=0)
        time.sleep(0.01)

        exceeded = tracker.check_wall_time()
        assert exceeded, "Wall time should be exceeded"
        assert tracker.limit_exceeded
        assert tracker.exceeded_limit_type == LimitType.WALL_TIME

    def test_wall_time_limit_failure_reason(self):
        """Test that wall time limit failure reason is descriptive."""
        tracker = LimitTracker(max_wall_time_seconds=0)
        time.sleep(0.01)
        tracker.check_wall_time()

        reason = tracker.get_failure_reason()
        assert "Exceeded maximum wall time" in reason
        assert ">" in reason


class TestLimitTrackerMultipleLimits:
    """Test behavior when multiple limits are involved."""

    def test_first_limit_exceeded_is_recorded(self):
        """Test that the first limit exceeded is recorded."""
        tracker = LimitTracker()

        # Exceed step limit first
        for _ in range(21):
            tracker.increment_step()

        # Try to exceed tool call limit
        tracker.increment_tool_call()

        # Should still show step limit as the exceeded one
        assert tracker.exceeded_limit_type == LimitType.STEPS

    def test_check_any_limit_exceeded(self):
        """Test that check_any_limit_exceeded works correctly."""
        tracker = LimitTracker()

        # No limits exceeded initially
        assert not tracker.check_any_limit_exceeded()

        # Exceed step limit
        for _ in range(21):
            tracker.increment_step()

        # Should detect limit exceeded
        assert tracker.check_any_limit_exceeded()


class TestLimitTrackerStatus:
    """Test status reporting functionality."""

    def test_get_status_returns_all_fields(self):
        """Test that get_status returns all required fields."""
        tracker = LimitTracker()
        tracker.increment_step()
        tracker.increment_tool_call()
        tracker.increment_test_run()

        status = tracker.get_status()

        assert "step_count" in status
        assert "max_steps" in status
        assert "tool_call_count" in status
        assert "max_tool_calls" in status
        assert "test_run_count" in status
        assert "max_test_runs" in status
        assert "elapsed_time_seconds" in status
        assert "max_wall_time_seconds" in status
        assert "limit_exceeded" in status
        assert "exceeded_limit_type" in status

        assert status["step_count"] == 1
        assert status["tool_call_count"] == 1
        assert status["test_run_count"] == 1
        assert status["max_steps"] == 20

    def test_get_status_with_exceeded_limit(self):
        """Test that get_status includes exceeded limit type."""
        tracker = LimitTracker()

        for _ in range(21):
            tracker.increment_step()

        status = tracker.get_status()
        assert status["limit_exceeded"] is True
        assert status["exceeded_limit_type"] == "max_steps"

    def test_get_failure_reason_empty_when_no_limit_exceeded(self):
        """Test that get_failure_reason returns empty string when no limit exceeded."""
        tracker = LimitTracker()
        reason = tracker.get_failure_reason()
        assert reason == ""


class TestLimitTrackerReset:
    """Test reset functionality."""

    def test_reset_clears_all_counters(self):
        """Test that reset clears all counters and state."""
        tracker = LimitTracker()

        # Increment all counters
        tracker.increment_step()
        tracker.increment_tool_call()
        tracker.increment_test_run()

        # Exceed a limit
        for _ in range(21):
            tracker.increment_step()

        # Reset
        tracker.reset()

        # All counters should be zero
        assert tracker.step_count == 0
        assert tracker.tool_call_count == 0
        assert tracker.test_run_count == 0
        assert not tracker.limit_exceeded
        assert tracker.exceeded_limit_type is None

    def test_reset_updates_start_time(self):
        """Test that reset updates the start time."""
        tracker = LimitTracker()
        original_start = tracker.start_time

        time.sleep(0.01)
        tracker.reset()

        assert tracker.start_time > original_start


class TestLimitTrackerConfiguration:
    """Test configuration of limit values."""

    def test_custom_tool_call_limit(self):
        """Test that custom tool call limit can be set."""
        tracker = LimitTracker(max_tool_calls=100)
        assert tracker.max_tool_calls == 100

        # Should not exceed at 100
        for _ in range(100):
            exceeded = tracker.increment_tool_call()
            assert not exceeded

        # Should exceed at 101
        exceeded = tracker.increment_tool_call()
        assert exceeded

    def test_custom_test_run_limit(self):
        """Test that custom test run limit can be set."""
        tracker = LimitTracker(max_test_runs=10)
        assert tracker.max_test_runs == 10

        # Should not exceed at 10
        for _ in range(10):
            exceeded = tracker.increment_test_run()
            assert not exceeded

        # Should exceed at 11
        exceeded = tracker.increment_test_run()
        assert exceeded

    def test_custom_wall_time_limit(self):
        """Test that custom wall time limit can be set."""
        tracker = LimitTracker(max_wall_time_seconds=60)
        assert tracker.max_wall_time_seconds == 60
