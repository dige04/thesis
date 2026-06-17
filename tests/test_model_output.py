"""Tolerant parsing of reasoning-model output (MiniMax M3 etc.).

M3 emits chain-of-thought wrapped in <think>...</think> and does NOT support
JSON mode, so model output may carry a reasoning preamble, markdown fences, or
trailing prose around the JSON. These helpers must recover the JSON robustly and
strip reasoning so it is never embedded into memory records or persisted as CoT.
"""

import pytest

from src.model_output import extract_json_object, strip_reasoning

# --- strip_reasoning -----------------------------------------------------------

def test_strip_removes_think_block():
    assert strip_reasoning("<think>plan the answer</think>\n\nHello") == "Hello"


def test_strip_passthrough_when_no_think():
    assert strip_reasoning("just text") == "just text"


def test_strip_handles_unterminated_think():
    # max_tokens truncated the output mid-reasoning (no closing tag).
    assert strip_reasoning("<think>reasoning was cut off here") == ""


def test_strip_multiple_blocks():
    out = strip_reasoning("<think>a</think>X<think>b</think>Y")
    assert out == "XY"


def test_strip_is_case_insensitive_and_multiline():
    assert strip_reasoning("<THINK>\nline1\nline2\n</THINK>\nfinal") == "final"


def test_strip_empty_string():
    assert strip_reasoning("") == ""


# --- extract_json_object -------------------------------------------------------

def test_extract_clean_json():
    assert extract_json_object('{"memory_type": "bug_fix", "reasoning": "x"}') == {
        "memory_type": "bug_fix",
        "reasoning": "x",
    }


def test_extract_think_prefixed_json():
    raw = '<think>The change adds a parameter, so api_change.</think>\n{"memory_type": "api_change"}'
    assert extract_json_object(raw) == {"memory_type": "api_change"}


def test_extract_markdown_fenced_json():
    raw = "```json\n{\"a\": 1}\n```"
    assert extract_json_object(raw) == {"a": 1}


def test_extract_with_trailing_prose():
    raw = '{"a": 1}\n\nHope that helps!'
    assert extract_json_object(raw) == {"a": 1}


def test_extract_nested_braces_and_string_braces():
    raw = '{"outer": {"inner": 2}, "s": "a } in a string"}'
    assert extract_json_object(raw) == {"outer": {"inner": 2}, "s": "a } in a string"}


def test_extract_think_with_braces_in_reasoning():
    # The reasoning itself contains braces that must NOT be mistaken for the object.
    raw = '<think>maybe {this}? no.</think>{"memory_type": "config"}'
    assert extract_json_object(raw) == {"memory_type": "config"}


def test_extract_raises_when_no_json():
    with pytest.raises(ValueError):
        extract_json_object("<think>no json here</think> sorry")


def test_extract_raises_on_empty():
    with pytest.raises(ValueError):
        extract_json_object("")
