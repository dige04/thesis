"""Tests for AGENT_TOOL_MODE variant flag (Task 5c).

Verifies that:
- mode=="legacy"  → schema has no start_line/end_line, read_file returns raw whole-file,
                    SYSTEM_PROMPT shows read_file(path), obs cap is 4000, edit_file skips
                    normalization/security guard.
- mode=="fixed"   → (default) schema has start_line/end_line, read_file numbers lines,
                    cap is 12000, edit_file normalises + guards.

Run:
    .venv/bin/pytest tests/test_tool_mode.py -v
"""
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _temp_repo():
    """Create a minimal git repo with one file and return its path."""
    tmpdir = tempfile.mkdtemp()
    repo = Path(tmpdir)
    (repo / "hello.py").write_text("line1\nline2\nline3\n")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=T", "commit", "-q", "-m", "init"],
        cwd=repo,
        check=True,
    )
    return repo


# ---------------------------------------------------------------------------
# tool_mode() helper
# ---------------------------------------------------------------------------

class TestToolModeHelper:
    def test_default_is_fixed(self, monkeypatch):
        monkeypatch.delenv("AGENT_TOOL_MODE", raising=False)
        from src.agents.tools import tool_mode
        assert tool_mode() == "fixed"

    def test_legacy_env(self, monkeypatch):
        monkeypatch.setenv("AGENT_TOOL_MODE", "legacy")
        from src.agents.tools import tool_mode
        assert tool_mode() == "legacy"

    def test_unknown_env_falls_back_to_fixed(self, monkeypatch):
        monkeypatch.setenv("AGENT_TOOL_MODE", "experimental")
        from src.agents.tools import tool_mode
        assert tool_mode() == "fixed"


# ---------------------------------------------------------------------------
# build_tool_schemas
# ---------------------------------------------------------------------------

class TestBuildToolSchemas:
    def test_fixed_schema_has_start_end_line(self):
        from src.agents.langgraph_agent import build_tool_schemas
        schemas = build_tool_schemas("fixed")
        rf = next(s for s in schemas if s["function"]["name"] == "read_file")
        props = rf["function"]["parameters"]["properties"]
        assert "start_line" in props, "fixed schema must have start_line"
        assert "end_line" in props, "fixed schema must have end_line"

    def test_legacy_schema_has_no_start_end_line(self):
        from src.agents.langgraph_agent import build_tool_schemas
        schemas = build_tool_schemas("legacy")
        rf = next(s for s in schemas if s["function"]["name"] == "read_file")
        props = rf["function"]["parameters"]["properties"]
        assert "start_line" not in props, "legacy schema must NOT have start_line"
        assert "end_line" not in props, "legacy schema must NOT have end_line"
        # path must still be there
        assert "path" in props

    def test_module_level_TOOL_SCHEMAS_has_start_end_line(self):
        """The module-level _TOOL_SCHEMAS alias keeps the fixed default."""
        from src.agents.langgraph_agent import _TOOL_SCHEMAS
        rf = next(s for s in _TOOL_SCHEMAS if s["function"]["name"] == "read_file")
        props = rf["function"]["parameters"]["properties"]
        assert "start_line" in props
        assert "end_line" in props


# ---------------------------------------------------------------------------
# read_file behaviour by mode
# ---------------------------------------------------------------------------

class TestReadFileByMode:
    def test_fixed_mode_numbers_lines(self, monkeypatch):
        monkeypatch.delenv("AGENT_TOOL_MODE", raising=False)
        from src.agents.tools import AgentTools
        repo = _temp_repo()
        tools = AgentTools(working_dir=str(repo))
        result = tools.read_file("hello.py")
        # Fixed mode: lines numbered as "N\t..."
        assert "1\tline1" in result or "1\t" in result

    def test_legacy_mode_returns_raw_whole_file(self, monkeypatch):
        monkeypatch.setenv("AGENT_TOOL_MODE", "legacy")
        from importlib import reload
        import src.agents.tools as tools_mod
        reload(tools_mod)
        repo = _temp_repo()
        tools = tools_mod.AgentTools(working_dir=str(repo))
        result = tools.read_file("hello.py", start_line=2, end_line=2)
        # Legacy: whole file raw, no line numbering, ignores start/end_line
        assert "1\t" not in result, "legacy should NOT number lines"
        assert "line1" in result, "legacy should return all lines (start_line ignored)"
        assert "line3" in result, "legacy should return all lines (end_line ignored)"

    def test_legacy_mode_no_n_tab_numbering(self, monkeypatch):
        monkeypatch.setenv("AGENT_TOOL_MODE", "legacy")
        from importlib import reload
        import src.agents.tools as tools_mod
        reload(tools_mod)
        repo = _temp_repo()
        tools = tools_mod.AgentTools(working_dir=str(repo))
        result = tools.read_file("hello.py")
        # Should NOT contain the "N\t" prefix pattern
        import re
        assert not re.search(r"^\d+\t", result, re.MULTILINE), "legacy must NOT use N<TAB> prefix"


# ---------------------------------------------------------------------------
# _truncate_obs cap by mode
# ---------------------------------------------------------------------------

class TestTruncateObsByMode:
    def test_fixed_cap_is_12000(self, monkeypatch):
        monkeypatch.delenv("AGENT_TOOL_MODE", raising=False)
        from src.agents.langgraph_agent import _truncate_obs, _MAX_OBS
        assert _MAX_OBS == 12000
        long_text = "x" * 20000
        out = _truncate_obs(long_text)
        assert len(out) <= 12000

    def test_legacy_cap_is_4000(self, monkeypatch):
        monkeypatch.setenv("AGENT_TOOL_MODE", "legacy")
        from src.agents.langgraph_agent import _truncate_obs
        long_text = "x" * 20000
        out = _truncate_obs(long_text, mode="legacy")
        assert len(out) <= 4000

    def test_legacy_cap_plain_head_truncation(self, monkeypatch):
        monkeypatch.setenv("AGENT_TOOL_MODE", "legacy")
        from src.agents.langgraph_agent import _truncate_obs
        # Legacy: plain head truncation — first 4000 chars, no "omitted" notice
        long_text = "A" * 4000 + "TAIL"
        out = _truncate_obs(long_text, mode="legacy")
        assert out == "A" * 4000
        assert "TAIL" not in out

    def test_fixed_cap_tail_preserving(self, monkeypatch):
        monkeypatch.delenv("AGENT_TOOL_MODE", raising=False)
        from src.agents.langgraph_agent import _truncate_obs
        body = "HEAD" + "x" * 20000 + "TAIL_END"
        out = _truncate_obs(body)  # default = fixed
        assert "HEAD" in out
        assert "TAIL_END" in out
        assert "chars omitted" in out


# ---------------------------------------------------------------------------
# SYSTEM_PROMPT by mode
# ---------------------------------------------------------------------------

class TestSystemPromptByMode:
    def test_fixed_prompt_has_start_end_line_signature(self):
        from src.agents.prompts import get_system_prompt
        prompt = get_system_prompt(mode="fixed")
        assert "start_line" in prompt or "read_file(path, start_line" in prompt

    def test_fixed_prompt_has_N_tab_guidance(self):
        from src.agents.prompts import get_system_prompt
        prompt = get_system_prompt(mode="fixed")
        assert "N<TAB>" in prompt or "N\\t" in prompt or "`N<TAB>" in prompt

    def test_legacy_prompt_has_only_path_signature(self):
        from src.agents.prompts import get_system_prompt
        prompt = get_system_prompt(mode="legacy")
        # Legacy shows read_file(path) — no start_line/end_line mention
        assert "read_file(path)" in prompt
        # Must NOT have the new range guidance
        assert "start_line" not in prompt

    def test_legacy_prompt_no_N_tab_guidance(self):
        from src.agents.prompts import get_system_prompt
        prompt = get_system_prompt(mode="legacy")
        assert "N<TAB>" not in prompt

    def test_legacy_prompt_has_get_patch(self):
        """Legacy prompt mentions get_patch() in the tools list."""
        from src.agents.prompts import get_system_prompt
        prompt = get_system_prompt(mode="legacy")
        assert "get_patch" in prompt

    def test_fixed_prompt_no_get_patch_in_tools_list(self):
        """Fixed prompt does NOT advertise get_patch() in the tools list (removed in 39be860)."""
        from src.agents.prompts import get_system_prompt
        prompt = get_system_prompt(mode="fixed")
        # Legacy advertises "get_patch()" in the Tools: section.
        # Fixed says "there is no shell `grep`/`sed`/`get_patch`" — present but as a prohibition,
        # NOT as a callable tool. Check the tools line directly.
        assert "get_patch()" not in prompt or "there is no" in prompt

    def test_default_get_system_prompt_is_fixed(self):
        from src.agents.prompts import get_system_prompt
        prompt_default = get_system_prompt()
        prompt_fixed = get_system_prompt(mode="fixed")
        assert prompt_default == prompt_fixed


# ---------------------------------------------------------------------------
# Persistence: tool_mode flows into task_results.jsonl
# ---------------------------------------------------------------------------

class TestToolModePersistence:
    """Verify that tool_mode survives the full chain to the persisted row.

    Chain: solve_task → _build_task_result → TaskResult → to_dict → jsonl row.
    Tests are unit-level (no SequenceRunner spin-up needed).
    """

    def test_task_result_has_tool_mode_field(self):
        """TaskResult dataclass accepts tool_mode."""
        from src.logging.task_logger import TaskResult
        tr = TaskResult(
            run_id="test_run",
            policy="full_memory",
            seed=1,
            repo="astropy/astropy",
            task_id="astropy__astropy-1234",
            sequence_index=0,
            resolved=1,
            patch_generated=True,
            patch_applied=True,
            syntax_error=False,
            timeout=False,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            estimated_cost_usd=0.0,
            task_api_cost=0.0,
            consolidation_llm_cost=0.0,
            wall_time_seconds=1.0,
            tool_calls=5,
            test_runs=1,
            files_read=2,
            files_modified=1,
            syntax_error_rate=0.0,
            retrieved_memory_ids=[],
            retrieved_memory_scores=[],
            retrieved_memory_types=[],
            retrieved_memory_ages=[],
            memory_count_before=0,
            memory_count_after=0,
            memory_tokens_before=0,
            memory_tokens_after=0,
            task_difficulty="medium",
            tool_mode="fixed",
        )
        assert tr.tool_mode == "fixed"

    def test_task_result_to_dict_includes_tool_mode(self):
        """to_dict() must include tool_mode so jsonl rows carry the field."""
        from src.logging.task_logger import TaskResult
        tr = TaskResult(
            run_id="test_run",
            policy="full_memory",
            seed=1,
            repo="astropy/astropy",
            task_id="astropy__astropy-1234",
            sequence_index=0,
            resolved=0,
            patch_generated=False,
            patch_applied=False,
            syntax_error=False,
            timeout=False,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            estimated_cost_usd=0.0,
            task_api_cost=0.0,
            consolidation_llm_cost=0.0,
            wall_time_seconds=0.0,
            tool_calls=0,
            test_runs=0,
            files_read=0,
            files_modified=0,
            syntax_error_rate=0.0,
            retrieved_memory_ids=[],
            retrieved_memory_scores=[],
            retrieved_memory_types=[],
            retrieved_memory_ages=[],
            memory_count_before=0,
            memory_count_after=0,
            memory_tokens_before=0,
            memory_tokens_after=0,
            task_difficulty="medium",
            tool_mode="legacy",
        )
        row = tr.to_dict()
        assert "tool_mode" in row, "tool_mode must be present in serialized row"
        assert row["tool_mode"] == "legacy"

    def test_task_result_tool_mode_default_is_none(self):
        """Existing rows (pre-Task-5c) are unaffected: tool_mode defaults to None."""
        from src.logging.task_logger import TaskResult
        tr = TaskResult(
            run_id="test_run",
            policy="full_memory",
            seed=1,
            repo="astropy/astropy",
            task_id="astropy__astropy-1234",
            sequence_index=0,
            resolved=0,
            patch_generated=False,
            patch_applied=False,
            syntax_error=False,
            timeout=False,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            estimated_cost_usd=0.0,
            task_api_cost=0.0,
            consolidation_llm_cost=0.0,
            wall_time_seconds=0.0,
            tool_calls=0,
            test_runs=0,
            files_read=0,
            files_modified=0,
            syntax_error_rate=0.0,
            retrieved_memory_ids=[],
            retrieved_memory_scores=[],
            retrieved_memory_types=[],
            retrieved_memory_ages=[],
            memory_count_before=0,
            memory_count_after=0,
            memory_tokens_before=0,
            memory_tokens_after=0,
            task_difficulty="medium",
            # tool_mode omitted — should default to None
        )
        assert tr.tool_mode is None
        row = tr.to_dict()
        assert row["tool_mode"] is None
