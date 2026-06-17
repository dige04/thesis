"""Tolerant parsing of model output for reasoning / non-JSON-mode providers.

Deviation context (CLAUDE.md D1/D4, extended 2026-06-17)
--------------------------------------------------------
The frozen experiment runs on **MiniMax M3** (free-unlimited, OpenAI-compatible
via the 0G router). M3 differs from the earlier kimi/Ollama providers in two
ways that this module exists to absorb, *identically across all 6 conditions*:

1. **Reasoning model** — M3 emits chain-of-thought wrapped in ``<think>...
   </think>`` (thinking is on by default and cannot be disabled). That CoT must
   never be (a) parsed as JSON, (b) embedded into a memory record (Invariant #4
   payload), or (c) persisted as CoT (v5 §11.3). :func:`strip_reasoning` removes
   it.
2. **No JSON mode** — M3 returns ``400 model_not_capable`` for
   ``response_format={"type": "json_object"}``. The three structured-output
   sites (classifier #7, reflection, CLS consolidation #9) therefore drop JSON
   mode and rely on prompt-instructed JSON + :func:`extract_json_object` +
   Pydantic validation. Tolerant of reasoning preambles, markdown fences, and
   trailing prose.

Both helpers are provider-agnostic: on a non-reasoning / JSON-mode provider the
input is already clean JSON and they act as the identity transform, so the code
remains runnable on kimi / OpenAI by editing ``.env`` only (deviation reversible).
"""

from __future__ import annotations

import json
import re
from typing import Any

# <think>...</think>, DOTALL so it spans newlines, IGNORECASE for <THINK>.
_THINK_RE = re.compile(r"<think\b[^>]*>.*?</think\s*>", re.DOTALL | re.IGNORECASE)
# An opening <think> with no closing tag (output truncated by max_tokens) — drop
# from the tag to end of string.
_UNTERMINATED_THINK_RE = re.compile(r"<think\b[^>]*>.*\Z", re.DOTALL | re.IGNORECASE)
# Leading/trailing markdown code fences (```json ... ``` or ``` ... ```).
_FENCE_OPEN_RE = re.compile(r"^\s*```(?:json|JSON)?\s*", re.IGNORECASE)
_FENCE_CLOSE_RE = re.compile(r"\s*```\s*\Z")


def strip_reasoning(text: str) -> str:
    """Remove ``<think>...</think>`` reasoning blocks from model output.

    Handles multiple blocks, an unterminated trailing ``<think>`` (truncated
    output), and is case-insensitive / multiline. Returns ``text`` unchanged when
    no reasoning tag is present.
    """
    if not text or "<think" not in text.lower():
        return text
    text = _THINK_RE.sub("", text)
    text = _UNTERMINATED_THINK_RE.sub("", text)
    return text.strip()


def _strip_fences(text: str) -> str:
    text = _FENCE_OPEN_RE.sub("", text)
    text = _FENCE_CLOSE_RE.sub("", text)
    return text.strip()


def extract_json_object(text: str) -> dict[str, Any]:
    """Extract the first top-level JSON object from (possibly messy) model output.

    Tolerant of a ``<think>`` reasoning preamble, ``` fences, and trailing prose.
    Raises :class:`ValueError` if no parseable JSON object is found, so callers
    keep their existing malformed-output retry / fallback behavior.
    """
    if not text or not isinstance(text, str):
        raise ValueError("empty/non-string model output")

    cleaned = _strip_fences(strip_reasoning(text))

    # Fast path: the whole (cleaned) string is a JSON object.
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj
    except (json.JSONDecodeError, ValueError):
        pass

    # Scan for the first balanced {...}, respecting strings/escapes so that a
    # brace inside a string value does not unbalance the scan.
    start = cleaned.find("{")
    if start == -1:
        raise ValueError(f"no JSON object found in model output: {cleaned[:120]!r}")

    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(cleaned)):
        ch = cleaned[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = cleaned[start : i + 1]
                try:
                    obj = json.loads(candidate)
                except (json.JSONDecodeError, ValueError) as e:
                    raise ValueError(
                        f"matched brace block is not valid JSON: {e}"
                    ) from e
                if isinstance(obj, dict):
                    return obj
                raise ValueError("matched JSON is not an object")

    raise ValueError(f"unbalanced JSON braces in model output: {cleaned[:120]!r}")
