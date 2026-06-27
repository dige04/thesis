<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-02 | Updated: 2026-06-02 -->

# agents

## Purpose
The coding agent that solves each SWE-Bench-CL task: a LangGraph-based ReAct tool-use loop running on a single frozen model (qwen3-coder:480b-cloud under the Ollama Cloud deviation), under hard execution limits. Implements v5 §4 (Agent specification) and §4.4 (agent loop). Memory is injected *into the prompt* (best item LAST), never appended wholesale.

## Key Files
| File | Description |
|------|-------------|
| `langgraph_agent.py` | Core agent. `solve_task` runs the real v5 §4.4 ReAct loop: binds the chat client, exposes 8 tools via `AgentTools`, enforces `LimitTracker`, produces a `git diff` patch + a no-CoT trajectory + token usage. 12 logical nodes (setup → retrieve → context → plan → search → edit → test → repair → patch → reflect → write → maintain). |
| `limit_tracker.py` | `LimitTracker` — hard caps on steps/tool-calls/test-runs/wall-time. On breach: stop, mark failed, log `timeout=true`, record which limit. Frozen invariants. |
| `tools.py` | The 8 agent tools: `read_file`, `write_file`, `edit_file`, `search_code`, `list_files`, `run_command`, `run_tests`, `get_patch`. Tracks tool-call counts for behavioral metrics (Req 29). |
| `prompts.py` | Prompt templates + context builder. Injection order = relevance-sorted, **best item LAST** (Lost-in-the-Middle fix, invariant #6). Memory line format `[MEM-ID] (rank, sim, age, type)`. v5 §4.5. |

## For AI Agents

### Working In This Directory
- **Never write the agent's private chain-of-thought to trajectory logs** — actions + observations only (root golden rule #4; `logging/trajectory_logger.py`).
- Injection order is frozen (best item LAST). Do not "improve" ordering.
- The prompt is **identical across all 6 conditions** except for the memory block content. Keep it that way.
- All LLM calls go through `config/llm_factory.py` at temperature 0.
- Limits are frozen invariants — do not relax them. Note the known off-by-one bug (`>` vs `>=` allowing 21 steps) flagged in root build status.

### Testing Requirements
- `tests/test_agent_limits.py`, `tests/test_agent_react_loop.py`, `tests/test_agents_tools.py`, `tests/agents/test_limit_tracker.py`.
- Live-model validation requires an Ollama Cloud key (see root `AGENTS.md` "Verify wiring").

### Common Patterns
- ReAct: think → act (tool) → observe, bounded by `LimitTracker`.
- Patch is the final `git diff`; it is what eval_v3 scores.

## Dependencies

### Internal
- `memory/retriever.py` (retrieval), `memory/reflection.py` (post-task record), `config/llm_factory.py` (client), `logging/trajectory_logger.py`, `benchmark/task_env.py` (repo checkout).

### External
- `langgraph`, `langchain`, `openai` SDK.

<!-- MANUAL: -->
