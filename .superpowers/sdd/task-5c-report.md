# Task 5c Report: `AGENT_TOOL_MODE` variant flag

## Status
COMPLETE. 20/20 new tests pass, 50 regression tests pass (0 failures).

## What was implemented

### 1. `tool_mode()` helper — `src/agents/tools.py`
Added at module level. Reads `AGENT_TOOL_MODE` env var; returns `"legacy"` only if the value is exactly `"legacy"`, else `"fixed"`. Unknown values fall back to `"fixed"` safely.

```python
def tool_mode() -> str:
    raw = os.environ.get("AGENT_TOOL_MODE", "fixed").strip().lower()
    return "legacy" if raw == "legacy" else "fixed"
```

Also added `_LEGACY_OBS_CAP = 4000` as a named constant.

### 2. `read_file` mode branch — `src/agents/tools.py`
`read_file(path, start_line, end_line)` calls `tool_mode()` at call time:
- **legacy**: ignores `start_line`/`end_line`, returns raw whole-file content with no `N\t` numbering and no budget cap — exactly the pre-task-1 behavior (from `git show 6d28d92^`).
- **fixed** (default): existing ranged+numbered+budget behavior unchanged.

### 3. `edit_file` mode branch — `src/agents/tools.py`
`edit_file` wraps the `_normalize_diff_paths` + `_collect_diff_paths` security guard in `if tool_mode() == "fixed"`. Legacy mode skips both and applies the raw diff directly via the git-apply ladder — reproducing pre-task-2b behavior (from `git show 6c60242^`).

### 4. `build_tool_schemas(mode)` — `src/agents/langgraph_agent.py`
New function returns a `list[dict]` with mode-appropriate `read_file` schema:
- **fixed**: `path + start_line + end_line` properties, description includes `N<TAB>text` hint.
- **legacy**: `path` only — no `start_line`, no `end_line`.

Module-level `_TOOL_SCHEMAS = build_tool_schemas("fixed")` alias keeps all existing importers working unchanged.

### 5. `_truncate_obs(text, limit, mode)` — `src/agents/langgraph_agent.py`
Added `mode` parameter (default `None` → resolved from env):
- **legacy**: `return text[:4000]` — plain head-truncation, no "chars omitted" notice.
- **fixed** (default): existing 12000 tail-preserving logic unchanged.

`_MAX_OBS = 12000` module constant unchanged — `test_react_loop_truncation.py` imports it and it still holds.

### 6. System prompt by mode — `src/agents/prompts.py`
Added `_SYSTEM_PROMPT_LEGACY` string constant (verbatim from `git show 39be860^`):
- Shows `read_file(path)` (no range args).
- Advertises `get_patch()` in the tools list.
- No `N<TAB>` line-number guidance.

`get_system_prompt(max_steps, mode)` selects between `SYSTEM_PROMPT` and `_SYSTEM_PROMPT_LEGACY` based on resolved mode. Default (no `mode` arg) falls back to `tool_mode()`.

`build_prompt_context` updated to call `get_system_prompt(max_steps=max_steps)` instead of `SYSTEM_PROMPT.format(max_steps=max_steps)` directly, so the prompt respects the env var when called from production code.

### 7. Mode resolved once in `CodingAgent.__init__`
`self.resolved_tool_mode = tool_mode()` is set once at construction so all tool calls within a run are consistent. `_run_react_loop` uses:
- `build_tool_schemas(self.resolved_tool_mode)` for the LLM call.
- `_truncate_obs(observation, mode=self.resolved_tool_mode)` at both call sites.

### 8. Mode recorded in task result — full persistence chain
`"tool_mode": self.resolved_tool_mode` is added to the `solve_task` result dict.

The field is wired through the full persistence chain (commit f4b990b):
- `TaskResult` dataclass (`src/logging/task_logger.py`): `tool_mode: str | None = None` field added after `termination_reason`. Defaults to `None` so all pre-Task-5c rows remain valid.
- `TaskResult.to_dict()`: `"tool_mode": self.tool_mode` added to the serialised row.
- `SequenceRunner._build_task_result` (`src/benchmark/sequence_runner.py`): `tool_mode=agent_result.get("tool_mode")` wired in.

## Where mode is resolved
1. **Primary**: `tool_mode()` in `src/agents/tools.py` — reads `AGENT_TOOL_MODE` env var.
2. **Resolved once** at `CodingAgent.__init__` into `self.resolved_tool_mode` — all calls within a run use this stable value.
3. `read_file` and `edit_file` call `tool_mode()` directly at call time (consistent because the env var is set before the run and held constant).
4. `get_system_prompt` resolves mode lazily (via `tool_mode()`) when `mode=None`.

## Schema parameterization strategy
`build_tool_schemas(mode)` is a factory function, not a mutated global. The module-level `_TOOL_SCHEMAS` is a frozen alias to `build_tool_schemas("fixed")` — existing callers import it without change and always get fixed schemas regardless of env. The ReAct loop calls `build_tool_schemas(self.resolved_tool_mode)` per-turn, which is cheap (no IO).

## Prompt parameterization strategy
`_SYSTEM_PROMPT_LEGACY` is a separate string constant (NOT a mutated `SYSTEM_PROMPT`). `SYSTEM_PROMPT` is unchanged — existing callers that import it directly still get the fixed prompt. The only callers that need mode-awareness (`get_system_prompt`, `build_prompt_context`) go through the `get_system_prompt(mode)` function.

## Tests
- `tests/test_tool_mode.py` — 20 new tests covering all 6 toggle dimensions (tool_mode helper, schema, read_file behavior, _truncate_obs cap + style, system prompt content, default=fixed invariant).
- Regression: 50 existing tests in `test_agents_tools`, `test_react_loop_truncation`, `test_agent_react_loop`, and all `-k schema` / `-k truncation` tests pass unchanged.
