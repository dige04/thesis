"""Provider-configurable LLM / embedding client factory.

Single source of truth for the OpenAI-SDK clients used across ``src/`` so the
experiment can run against **Ollama Cloud** (OpenAI-compatible) for the
generative roles and a **separate endpoint** for embeddings — without
scattering ``base_url`` / ``api_key`` / model decisions through the codebase.

Why two clients
---------------
Ollama Cloud serves **no embedding model** (only large generative models:
qwen3-coder, gpt-oss, deepseek-v3.1). Chat and embedding calls must therefore
point at different endpoints. **Never** set a global ``OPENAI_BASE_URL`` — it
would silently redirect the embedding client too and break retrieval.

Deviation D1 from THESIS_FINAL_v5.md §0.1 (model is frozen to GPT-5.4)
---------------------------------------------------------------------
This factory defaults to OpenCode Zen "go" tier (OpenAI-compatible) using
``kimi-k2.6`` for the main coding agent and ``kimi-k2.5`` for the
reflection/summary/classifier roles, with a **local** Ollama embedder
(``nomic-embed-text-v2-moe``) for embeddings (OpenCode Zen serves no embedder).
See CLAUDE.md / AGENTS.md "Deviations from pre-registration". The model is held
**constant across all 6 conditions and 3 seeds**, so between-policy comparisons
remain valid; absolute resolution rates are not comparable to a GPT-5.4 design.
NOTE: on this tier the Qwen models are Anthropic-endpoint only (not oa-compat);
the kimi / glm / deepseek / minimax / mimo families ARE OpenAI-compatible.

Config precedence
-----------------
Environment variables (loaded from ``.env`` via python-dotenv) override the
built-in defaults below. Callers may pass explicit overrides to the getters,
which take precedence over both. This keeps a single ``configs/base.yaml`` and
the same code working for either OpenAI or Ollama by editing ``.env`` only.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

# Load .env once at import time if python-dotenv is available. Guarded so the
# module imports cleanly in environments where the dependency is not yet
# installed (e.g. during initial setup / unit tests that stub the clients).
try:  # pragma: no cover - trivial import guard
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass


# Built-in defaults — the lowest-precedence layer. Tuned for the chosen setup:
#   * generative roles  -> OpenCode Zen go (needs LLM_CHAT_API_KEY from opencode.ai)
#   * embeddings         -> local Ollama daemon at :11434 (after `ollama pull`)
# Override any of these via the matching env var in .env.
_DEFAULTS: dict[str, str] = {
    # --- chat / agent / summary / classifier (OpenCode Zen go, OpenAI-compatible) ---
    # Catalog: GET https://opencode.ai/zen/go/v1/models (Bearer key).
    "LLM_CHAT_BASE_URL": "https://opencode.ai/zen/go/v1",
    "LLM_CHAT_API_KEY": "",  # create at https://opencode.ai (OpenCode Zen console)
    "LLM_MAIN_MODEL": "kimi-k2.6",
    "LLM_SUMMARY_MODEL": "kimi-k2.5",
    "LLM_CLASSIFIER_MODEL": "kimi-k2.5",
    # --- embeddings (local Ollama; Ollama Cloud has no embedding model) ---
    "EMBEDDING_BASE_URL": "http://localhost:11434/v1",
    "EMBEDDING_API_KEY": "ollama",  # local daemon ignores the value but requires one
    "EMBEDDING_MODEL": "nomic-embed-text-v2-moe",
    "EMBEDDING_DIM": "768",  # MUST match the embedder; rebuild FAISS if changed
    # --- cost metric mode: usd | tokens | walltime (Ollama is flat-rate) ---
    "COST_METRIC_MODE": "tokens",
}


def _env(key: str, override: str | None = None) -> str:
    """Resolve a setting: explicit override > env var > built-in default."""
    if override is not None and override != "":
        return override
    value = os.environ.get(key)
    if value is not None and value != "":
        return value
    return _DEFAULTS[key]


def _chat_env(key: str, override: str | None = None) -> str:
    """Chat-role settings with a FREE-provider override.

    If ``FREE_<key>`` is set (e.g. ``FREE_LLM_CHAT_BASE_URL``), it wins over the
    normal ``<key>``. This lets an entire alternate chat provider (e.g. a
    free-unlimited MiniMax M3 endpoint) be switched on by dropping the
    ``FREE_LLM_*`` vars into ``.env``, and switched off by removing them — without
    disturbing the Kimi config or the embeddings (which stay on local Ollama).
    Explicit call-site override still wins over everything.
    """
    if override is not None and override != "":
        return override
    free = os.environ.get(f"FREE_{key}")
    if free is not None and free != "":
        return free
    return _env(key)


# --- Chat (generative) settings ------------------------------------------------

def chat_base_url(override: str | None = None) -> str:
    return _chat_env("LLM_CHAT_BASE_URL", override)


def chat_api_key(override: str | None = None) -> str:
    # Fall back to the literal "ollama" so a local daemon (which requires a
    # non-empty token but ignores its value) works without configuration.
    return _chat_env("LLM_CHAT_API_KEY", override) or "ollama"


def main_model(override: str | None = None) -> str:
    return _chat_env("LLM_MAIN_MODEL", override)


def summary_model(override: str | None = None) -> str:
    return _chat_env("LLM_SUMMARY_MODEL", override)


def classifier_model(override: str | None = None) -> str:
    return _chat_env("LLM_CLASSIFIER_MODEL", override)


# --- Embedding settings --------------------------------------------------------

def embedding_base_url(override: str | None = None) -> str:
    return _env("EMBEDDING_BASE_URL", override)


def embedding_api_key(override: str | None = None) -> str:
    return _env("EMBEDDING_API_KEY", override) or "ollama"


def embedding_model(override: str | None = None) -> str:
    return _env("EMBEDDING_MODEL", override)


def embedding_dim(override: int | None = None) -> int:
    if override is not None:
        return int(override)
    return int(_env("EMBEDDING_DIM"))


# --- Cost metric ---------------------------------------------------------------

def cost_metric_mode(override: str | None = None) -> str:
    return _env("COST_METRIC_MODE", override).lower()


# --- Client builders -----------------------------------------------------------
# Cached so we reuse a single connection-pooled client per process. Tests can
# call reset_clients() after monkeypatching env vars.

@lru_cache(maxsize=1)
def get_chat_client() -> Any:
    """OpenAI-SDK client pointed at the chat/generative endpoint (Ollama Cloud)."""
    from openai import OpenAI

    return OpenAI(base_url=chat_base_url(), api_key=chat_api_key())


@lru_cache(maxsize=1)
def get_embedding_client() -> Any:
    """OpenAI-SDK client pointed at the embedding endpoint (local Ollama / OpenAI)."""
    from openai import OpenAI

    return OpenAI(base_url=embedding_base_url(), api_key=embedding_api_key())


def reset_clients() -> None:
    """Clear cached clients (call after changing env vars, e.g. in tests)."""
    get_chat_client.cache_clear()
    get_embedding_client.cache_clear()
