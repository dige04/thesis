"""Unit tests for src/config/llm_factory.py.

Covers the provider-configurable LLM / embedding client factory:
  * config precedence: explicit override arg > env var > built-in default
  * embedding_dim() integer coercion (env "768" -> int 768) and int override
  * chat vs embedding clients point at DIFFERENT base_urls
  * chat_api_key()/embedding_api_key() fall back to "ollama" when unset

All env-mutating tests use monkeypatch.setenv and call reset_clients() so the
lru_cache'd clients do not leak between tests.
"""

import pytest

from src.config import llm_factory


@pytest.fixture(autouse=True)
def _clean_clients(monkeypatch):
    """Isolate from cached clients AND the real .env FREE_LLM_* layer.

    ``load_dotenv()`` loads ``.env`` at import time, so a developer/CI ``.env``
    that sets the FREE_LLM_* free-provider override would otherwise sit ABOVE the
    LLM_* layer these tests monkeypatch — making them assert against, e.g.,
    minimax-m3 instead of the LLM_/default values under test. The FREE_ layer has
    its own dedicated tests in test_llm_factory_free.py; here we neutralize it so
    these precedence/default tests are hermetic regardless of .env contents.
    """
    for _k in (
        "FREE_LLM_CHAT_BASE_URL",
        "FREE_LLM_CHAT_API_KEY",
        # The multi-key pool: when a fleet .env sets it, get_chat_client() returns
        # a KeyRotatingClient (no .base_url) and the single-client precedence tests
        # below break. Scrub it so they stay hermetic regardless of .env.
        "FREE_LLM_CHAT_API_KEYS",
        "FREE_LLM_MAIN_MODEL",
        "FREE_LLM_SUMMARY_MODEL",
        "FREE_LLM_CLASSIFIER_MODEL",
        # AUX split layer — keep hermetic once AUX_LLM_CHAT_* is configured in .env.
        "AUX_LLM_CHAT_BASE_URL",
        "AUX_LLM_CHAT_API_KEY",
        "AUX_LLM_CHAT_API_KEYS",
    ):
        monkeypatch.delenv(_k, raising=False)
    llm_factory.reset_clients()
    yield
    llm_factory.reset_clients()


# --- Precedence: explicit override > env var > built-in default ---------------


def test_main_model_default(monkeypatch):
    monkeypatch.delenv("LLM_MAIN_MODEL", raising=False)
    assert llm_factory.main_model() == "kimi-k2.6"


def test_main_model_env_overrides_default(monkeypatch):
    monkeypatch.setenv("LLM_MAIN_MODEL", "from-env-model")
    assert llm_factory.main_model() == "from-env-model"


def test_main_model_override_arg_beats_env(monkeypatch):
    monkeypatch.setenv("LLM_MAIN_MODEL", "from-env-model")
    assert llm_factory.main_model("explicit-override") == "explicit-override"


def test_embedding_model_precedence(monkeypatch):
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    assert llm_factory.embedding_model() == "nomic-embed-text-v2-moe"
    monkeypatch.setenv("EMBEDDING_MODEL", "env-embed")
    assert llm_factory.embedding_model() == "env-embed"
    assert llm_factory.embedding_model("arg-embed") == "arg-embed"


def test_cost_metric_mode_precedence_and_lowercasing(monkeypatch):
    monkeypatch.delenv("COST_METRIC_MODE", raising=False)
    assert llm_factory.cost_metric_mode() == "tokens"
    monkeypatch.setenv("COST_METRIC_MODE", "USD")
    # value is lower-cased by the getter
    assert llm_factory.cost_metric_mode() == "usd"
    # explicit override beats env (and is also lower-cased)
    assert llm_factory.cost_metric_mode("WallTime") == "walltime"


# --- embedding_dim(): int coercion + int override -----------------------------


def test_embedding_dim_default_coerces_env_string_to_int(monkeypatch):
    monkeypatch.delenv("EMBEDDING_DIM", raising=False)
    dim = llm_factory.embedding_dim()
    assert dim == 768
    assert isinstance(dim, int)


def test_embedding_dim_coerces_env_string(monkeypatch):
    monkeypatch.setenv("EMBEDDING_DIM", "1024")
    dim = llm_factory.embedding_dim()
    assert dim == 1024
    assert isinstance(dim, int)


def test_embedding_dim_respects_int_override(monkeypatch):
    monkeypatch.setenv("EMBEDDING_DIM", "1024")
    dim = llm_factory.embedding_dim(override=512)
    assert dim == 512
    assert isinstance(dim, int)


# --- chat vs embedding clients use DIFFERENT base_urls ------------------------


def test_chat_and_embedding_clients_use_distinct_base_urls(monkeypatch):
    # Neutralize any FREE_LLM_CHAT_* override/key-pool from the matrix .env so
    # this targets the base LLM_CHAT_* layer (else get_chat_client is a pool client).
    for _k in ("FREE_LLM_CHAT_BASE_URL", "FREE_LLM_CHAT_API_KEY", "FREE_LLM_CHAT_API_KEYS"):
        monkeypatch.delenv(_k, raising=False)
    monkeypatch.setenv("LLM_CHAT_BASE_URL", "https://chat.example.com/v1")
    monkeypatch.setenv("EMBEDDING_BASE_URL", "https://embed.example.com/v1")
    monkeypatch.setenv("LLM_CHAT_API_KEY", "chat-key")
    monkeypatch.setenv("EMBEDDING_API_KEY", "embed-key")
    llm_factory.reset_clients()

    chat = llm_factory.get_chat_client()
    embed = llm_factory.get_embedding_client()

    chat_url = str(chat.base_url)
    embed_url = str(embed.base_url)

    assert "chat.example.com" in chat_url
    assert "embed.example.com" in embed_url
    assert chat_url != embed_url


# --- api_key fallback to "ollama" when unset ----------------------------------


def test_chat_api_key_falls_back_to_ollama(monkeypatch):
    monkeypatch.delenv("LLM_CHAT_API_KEY", raising=False)
    assert llm_factory.chat_api_key() == "ollama"


def test_embedding_api_key_default_is_ollama(monkeypatch):
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    assert llm_factory.embedding_api_key() == "ollama"


def test_api_keys_respect_explicit_values(monkeypatch):
    monkeypatch.setenv("LLM_CHAT_API_KEY", "real-chat-token")
    monkeypatch.setenv("EMBEDDING_API_KEY", "real-embed-token")
    assert llm_factory.chat_api_key() == "real-chat-token"
    assert llm_factory.embedding_api_key() == "real-embed-token"
    # explicit override beats env
    assert llm_factory.chat_api_key("arg-token") == "arg-token"


# --- caching + reset semantics -------------------------------------------------


def test_get_chat_client_is_cached_until_reset(monkeypatch):
    for _k in ("FREE_LLM_CHAT_BASE_URL", "FREE_LLM_CHAT_API_KEY", "FREE_LLM_CHAT_API_KEYS"):
        monkeypatch.delenv(_k, raising=False)
    monkeypatch.setenv("LLM_CHAT_BASE_URL", "https://first.example.com/v1")
    llm_factory.reset_clients()
    first = llm_factory.get_chat_client()
    # Same cached instance on repeated calls (lru_cache, connection pooling).
    assert llm_factory.get_chat_client() is first
    # reset_clients() forces a fresh build that picks up new env.
    llm_factory.reset_clients()
    monkeypatch.setenv("LLM_CHAT_BASE_URL", "https://second.example.com/v1")
    rebuilt = llm_factory.get_chat_client()
    assert rebuilt is not first
    assert "second.example.com" in str(rebuilt.base_url)
