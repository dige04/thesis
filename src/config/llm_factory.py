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


def chat_api_keys() -> list[str]:
    """Pool of chat API keys for rotation (the 0G free tier rate-limits PER key).

    ``FREE_LLM_CHAT_API_KEYS`` (comma-separated) takes precedence over the single
    ``chat_api_key()``. ``get_chat_client()`` builds a :class:`KeyRotatingClient`
    from a >1 pool that fails over to the next key on a 402/429 quota error,
    sustaining the matrix across many keys without a single-key wall.
    """
    pool = os.environ.get("FREE_LLM_CHAT_API_KEYS")
    if pool:
        keys = [k.strip() for k in pool.split(",") if k.strip()]
        if keys:
            return keys
    return [chat_api_key()]


def main_model(override: str | None = None) -> str:
    return _chat_env("LLM_MAIN_MODEL", override)


def summary_model(override: str | None = None) -> str:
    return _chat_env("LLM_SUMMARY_MODEL", override)


def classifier_model(override: str | None = None) -> str:
    return _chat_env("LLM_CLASSIFIER_MODEL", override)


# --- Auxiliary chat endpoint (classifier / reflection / CLS summary) -----------
# The coding agent runs on the main chat endpoint (LLM_CHAT_*); the auxiliary
# roles can be routed to a SEPARATE, cheaper endpoint (e.g. deepseek-v4-flash on
# OpenCode go) via AUX_LLM_CHAT_*. When AUX_LLM_CHAT_BASE_URL is unset the aux
# roles share the main chat client (backward-compatible single-endpoint setup).
# Only the ENDPOINT moves; the per-role model NAME still comes from
# summary_model()/classifier_model().

def aux_base_url() -> str:
    """Aux chat endpoint URL, or "" when aux shares the main chat client."""
    return os.environ.get("AUX_LLM_CHAT_BASE_URL", "") or ""


def aux_api_keys() -> list[str]:
    """Pool of aux API keys (``AUX_LLM_CHAT_API_KEYS`` comma-separated) or the
    single ``AUX_LLM_CHAT_API_KEY``; falls back to the literal "ollama"."""
    pool = os.environ.get("AUX_LLM_CHAT_API_KEYS")
    if pool:
        keys = [k.strip() for k in pool.split(",") if k.strip()]
        if keys:
            return keys
    single = os.environ.get("AUX_LLM_CHAT_API_KEY")
    return [single] if single else ["ollama"]


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

def _is_auth_error(exc: BaseException) -> bool:
    """True for an invalid/expired API key (HTTP 401) — rotate past a dead key
    so one bad key in the pool never silently fails the tasks it would serve."""
    text = str(exc).lower()
    if "invalid_auth" in text or "invalid authentication" in text:
        return True
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    return status == 401


class _RotatingCompletions:
    def __init__(self, parent: KeyRotatingClient) -> None:
        self._parent = parent

    def create(self, **kwargs: Any) -> Any:
        return self._parent._create_with_rotation(**kwargs)


class _RotatingChat:
    def __init__(self, parent: KeyRotatingClient) -> None:
        self.completions = _RotatingCompletions(parent)


class KeyRotatingClient:
    """OpenAI-SDK-compatible client that rotates over a pool of API keys.

    On a provider quota/balance error (402/429-quota, per
    :func:`src.errors.is_usage_limit_error`) it fails over to the next key and
    retries; only when EVERY key in the pool is exhausted does it raise
    ``UsageLimitError`` (fail-closed — never a silent corruption). Non-quota
    errors propagate immediately (no rotation). ``start_index`` (e.g.
    ``os.getpid()``) spreads load across keys when many worker processes run.
    Only ``.chat.completions.create`` is supported (all this codebase uses).
    """

    def __init__(self, clients: list[Any], start_index: int = 0) -> None:
        if not clients:
            raise ValueError("KeyRotatingClient requires at least one client")
        self._clients = clients
        self._n = len(clients)
        self._idx = start_index % self._n
        self.chat = _RotatingChat(self)

    def _create_with_rotation(self, **kwargs: Any) -> Any:
        from src.errors import UsageLimitError, is_usage_limit_error

        last_exc: Exception | None = None
        for _ in range(self._n):
            client = self._clients[self._idx]
            try:
                return client.chat.completions.create(**kwargs)
            except Exception as e:
                # Rotate past a rate/balance-limited (402/429) OR dead (401) key.
                if is_usage_limit_error(e) or _is_auth_error(e):
                    last_exc = e
                    self._idx = (self._idx + 1) % self._n  # fail over to next key
                    continue
                raise
        raise UsageLimitError(
            f"All {self._n} chat API keys hit a usage/balance limit: {last_exc}"
        )


@lru_cache(maxsize=1)
def get_chat_client() -> Any:
    """Chat client for the generative endpoint.

    Returns a :class:`KeyRotatingClient` when a multi-key pool is configured
    (``FREE_LLM_CHAT_API_KEYS``), else a plain OpenAI client. Cached per process;
    a KeyRotatingClient seeds its start index from the PID to spread key load.
    """
    from openai import OpenAI

    base = chat_base_url()
    keys = chat_api_keys()
    if len(keys) > 1:
        clients = [OpenAI(base_url=base, api_key=k) for k in keys]
        return KeyRotatingClient(clients, start_index=os.getpid())
    return OpenAI(base_url=base, api_key=keys[0])


@lru_cache(maxsize=1)
def get_aux_client() -> Any:
    """Chat client for auxiliary roles (classifier, reflection, CLS summary).

    With ``AUX_LLM_CHAT_BASE_URL`` set, build a SEPARATE client at that endpoint
    (KeyRotatingClient for a >1 key pool, else a plain client) — lets aux run on a
    cheaper model/provider while the agent stays on the main endpoint. Unset ⇒
    return the main ``get_chat_client()`` (backward-compatible). Only the ENDPOINT
    is routed here; the per-role model name still comes from the model getters.
    """
    base = aux_base_url()
    if not base:
        return get_chat_client()
    from openai import OpenAI

    keys = aux_api_keys()
    if len(keys) > 1:
        clients = [OpenAI(base_url=base, api_key=k) for k in keys]
        return KeyRotatingClient(clients, start_index=os.getpid())
    return OpenAI(base_url=base, api_key=keys[0])


@lru_cache(maxsize=1)
def get_embedding_client() -> Any:
    """OpenAI-SDK client pointed at the embedding endpoint (local Ollama / OpenAI)."""
    from openai import OpenAI

    return OpenAI(base_url=embedding_base_url(), api_key=embedding_api_key())


def reset_clients() -> None:
    """Clear cached clients (call after changing env vars, e.g. in tests)."""
    get_chat_client.cache_clear()
    get_aux_client.cache_clear()
    get_embedding_client.cache_clear()
