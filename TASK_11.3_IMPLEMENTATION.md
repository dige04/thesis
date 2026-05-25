# Task 11.3 Implementation: Trajectory Logging

## Overview

Implemented trajectory logging for agent execution traces as specified in THESIS_FINAL_v5.md §11.3.

## Implementation Summary

### Files Created

1. **`src/logging/trajectory_logger.py`** (50 lines, 100% test coverage)
   - `TrajectoryStep` dataclass: Represents a single action-observation pair
   - `TrajectoryLogger` class: Accumulates steps in memory and writes JSON atomically
   - `load_trajectory()` function: Loads trajectory from JSON file

2. **`src/logging/__init__.py`**
   - Module initialization with exports

3. **`tests/test_trajectory_logger.py`** (19 tests, all passing)
   - Comprehensive unit tests for all functionality
   - Integration tests for complete task trajectories
   - Tests for frozen invariants (no private chain-of-thought)

4. **`examples/trajectory_logger_usage.py`**
   - Usage examples for agent integration
   - Examples of what NOT to log (private reasoning)

### Key Features

#### 1. TrajectoryLogger Class

```python
logger = TrajectoryLogger(
    run_id="run_001",
    task_id="django__django-12345",
    policy="type_aware_decay",
    seed=2
)

# During agent execution
logger.log_step(
    step=1,
    action="search_code",
    action_input="QuerySet.exclude",
    observation_summary="Found in django/db/models/query.py:823"
)

# At end of task
logger.save()  # Writes to runs/{run_id}/trajectories/{task_id}.json
```

#### 2. Schema Compliance

Matches THESIS_FINAL_v5.md §11.3 schema exactly:

```json
{
  "task_id": "django__django-12345",
  "policy": "type_aware_decay",
  "seed": 2,
  "steps": [
    {
      "step": 1,
      "action": "search_code",
      "action_input": "QuerySet.exclude",
      "observation_summary": "Found in django/db/models/query.py:823",
      "timestamp": "2026-05-17T10:23:01Z"
    }
  ]
}
```

#### 3. No Private Chain-of-Thought

**CRITICAL REQUIREMENT**: Only logs WHAT the agent did and WHAT it observed, NOT WHY.

✅ **Correct** (action summaries only):
- `action="search_code"` (tool name)
- `action_input="QuerySet.exclude"` (arguments)
- `observation_summary="Found in django/db/models/query.py:823"` (factual result)

❌ **Wrong** (private reasoning):
- `action="I think I should search for..."` (reasoning)
- `observation_summary="This means I need to..."` (interpretation)

#### 4. Atomic Writes

- Accumulates steps in memory during execution
- Writes entire trajectory once at end (atomic operation)
- Prevents partial trajectory files
- Prevents logging after save (raises RuntimeError)

#### 5. Storage Location

Trajectories stored at: `runs/{run_id}/trajectories/{task_id}.json`

Example:
```
runs/
  run_001/
    trajectories/
      django__django-12345.json
      django__django-67890.json
```

### Test Coverage

**19 tests, all passing, 100% code coverage**

Test categories:
1. **TrajectoryStep tests** (4 tests)
   - Creation with all fields
   - Auto-generated timestamps
   - Dictionary conversion
   - Dict action_input support

2. **TrajectoryLogger tests** (10 tests)
   - Initialization
   - Single and multiple step logging
   - Save functionality
   - Directory creation
   - Empty trajectory handling
   - Error handling (cannot log after save, cannot save twice)
   - Clear/reset functionality
   - **No private thoughts validation** (critical test)

3. **Load trajectory tests** (3 tests)
   - Loading from file
   - Error handling (nonexistent file, invalid JSON)

4. **Integration tests** (2 tests)
   - Complete task trajectory with 6 steps
   - Multiple tasks in same run

### Code Quality

- ✅ All tests pass (19/19)
- ✅ Ruff linter: No issues
- ✅ Mypy strict mode: No issues
- ✅ 100% test coverage on trajectory_logger.py
- ✅ Comprehensive docstrings
- ✅ Type hints throughout

### Integration Points

The trajectory logger integrates with the LangGraph agent at these points:

1. **Agent initialization**: Create TrajectoryLogger instance
2. **Each agent step**: Call `logger.log_step()` after tool execution
3. **Task completion**: Call `logger.save()` to write trajectory

Example integration pattern:

```python
def agent_step_node(state: dict, logger: TrajectoryLogger):
    """Agent node that logs its action and observation."""
    step_number = state["step_count"]
    
    # Execute action
    action = "search_code"
    action_input = state["search_query"]
    observation = execute_search_tool(action_input)
    
    # Log the step (WHAT, not WHY)
    logger.log_step(
        step=step_number,
        action=action,
        action_input=action_input,
        observation_summary=observation["summary"],
    )
    
    return state
```

### Frozen Invariants Enforced

From THESIS_FINAL_v5.md §0.1:

1. ✅ **No private chain-of-thought**: Only action summaries and observations logged
2. ✅ **Schema compliance**: Exact match to §11.3 schema
3. ✅ **Storage location**: `runs/{run_id}/trajectories/{task_id}.json`
4. ✅ **JSON format**: Single array, not JSON Lines
5. ✅ **Required fields**: step, action, action_input, observation_summary, timestamp

### Usage in Experiment

For each of the 144 runs (8 sequences × 6 policies × 3 seeds):
- Each task generates one trajectory file
- Trajectories enable failure analysis and debugging
- Trajectories support behavioral metrics (tool call counts, etc.)
- Trajectories are NOT embedded (would exceed 8K token limit)

### Next Steps

To complete the logging system (Task 11):
- ✅ 11.3 Trajectory logging (this task)
- ⏳ 11.1 Task results logging (task_results.jsonl)
- ⏳ 11.2 Memory events logging (memory_events.jsonl)
- ⏳ 11.4 Memory snapshot logging (before/after task boundaries)

### References

- **Specification**: THESIS_FINAL_v5.md §11.3
- **Implementation**: `src/logging/trajectory_logger.py`
- **Tests**: `tests/test_trajectory_logger.py`
- **Examples**: `examples/trajectory_logger_usage.py`
- **Task Plan**: `.kiro/specs/memory-pruning-research-system/tasks.md` Task 11.3

---

**Status**: ✅ Complete

**Date**: 2025-01-XX

**Test Results**: 19/19 passing, 100% coverage

**Code Quality**: Ruff ✅, Mypy ✅, Type hints ✅
