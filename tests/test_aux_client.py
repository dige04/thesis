"""Per-role auxiliary chat client (AUX_LLM_CHAT_*).

The coding agent runs on the main chat endpoint (e.g. the Kimi sub at
``LLM_CHAT_BASE_URL``); the auxiliary roles (5-type classifier, reflection,
CLS-consolidation summary) can be routed to a SEPARATE, cheaper endpoint
(e.g. ``deepseek-v4-flash`` on OpenCode go) via ``AUX_LLM_CHAT_BASE_URL``.

Backward-compat is mandatory: when ``AUX_LLM_CHAT_BASE_URL`` is unset, the aux
client IS the main chat client (existing single-endpoint behaviour preserved),
so every prior run/test/gate-3 config is unaffected.
"""

import pytest

from src.config import llm_factory
from src.config.llm_factory import KeyRotatingClient

_AUX = ["AUX_LLM_CHAT_BASE_URL", "AUX_LLM_CHAT_API_KEY", "AUX_LLM_CHAT_API_KEYS"]
_FREE = ["FREE_LLM_CHAT_BASE_URL", "FREE_LLM_CHAT_API_KEY", "FREE_LLM_CHAT_API_KEYS"]


@pytest.fixture(autouse=True)
def _reset_client_cache():
    # These tests build clients with fake URLs into the lru_cache; clear it
    # before AND after each test so no stale test client leaks into other tests.
    llm_factory.reset_clients()
    yield
    llm_factory.reset_clients()


def _clear(monkeypatch):
    for k in _AUX + _FREE:
        monkeypatch.delenv(k, raising=False)
    llm_factory.reset_clients()


def test_aux_base_url_empty_when_unset(monkeypatch):
    _clear(monkeypatch)
    assert llm_factory.aux_base_url() == ""


def test_aux_base_url_from_env(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("AUX_LLM_CHAT_BASE_URL", "https://aux.example/v1")
    assert llm_factory.aux_base_url() == "https://aux.example/v1"


def test_aux_falls_back_to_chat_client_when_unset(monkeypatch):
    # No AUX endpoint -> aux roles share the main chat client (backward-compat).
    _clear(monkeypatch)
    monkeypatch.setenv("LLM_CHAT_BASE_URL", "https://chat.example/v1")
    monkeypatch.setenv("LLM_CHAT_API_KEY", "k")
    llm_factory.reset_clients()
    assert llm_factory.get_aux_client() is llm_factory.get_chat_client()


def test_aux_uses_its_own_endpoint_when_set(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("LLM_CHAT_BASE_URL", "https://chat.example/v1")
    monkeypatch.setenv("LLM_CHAT_API_KEY", "ck")
    monkeypatch.setenv("AUX_LLM_CHAT_BASE_URL", "https://aux.example/v1")
    monkeypatch.setenv("AUX_LLM_CHAT_API_KEY", "ak")
    llm_factory.reset_clients()
    aux = llm_factory.get_aux_client()
    chat = llm_factory.get_chat_client()
    assert aux is not chat
    assert "aux.example" in str(aux.base_url)
    assert "chat.example" in str(chat.base_url)


def test_aux_client_rotates_when_pool(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("AUX_LLM_CHAT_BASE_URL", "https://aux.example/v1")
    monkeypatch.setenv("AUX_LLM_CHAT_API_KEYS", "a1,a2,a3")
    llm_factory.reset_clients()
    assert isinstance(llm_factory.get_aux_client(), KeyRotatingClient)


def test_classifier_uses_aux_client_when_configured(monkeypatch):
    # The 5-type classifier must route to the AUX endpoint (cheap aux model),
    # not the agent's main chat endpoint, when AUX_LLM_CHAT_BASE_URL is set.
    from src.memory.classifier import MemoryClassifier

    _clear(monkeypatch)
    monkeypatch.setenv("LLM_CHAT_BASE_URL", "https://chat.example/v1")
    monkeypatch.setenv("LLM_CHAT_API_KEY", "ck")
    monkeypatch.setenv("AUX_LLM_CHAT_BASE_URL", "https://aux.example/v1")
    monkeypatch.setenv("AUX_LLM_CHAT_API_KEY", "ak")
    llm_factory.reset_clients()
    clf = MemoryClassifier(model="deepseek-v4-flash")
    assert "aux.example" in str(clf.client.base_url)


def test_reset_clients_clears_aux(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("AUX_LLM_CHAT_BASE_URL", "https://aux.example/v1")
    monkeypatch.setenv("AUX_LLM_CHAT_API_KEY", "ak")
    llm_factory.reset_clients()
    first = llm_factory.get_aux_client()
    monkeypatch.setenv("AUX_LLM_CHAT_BASE_URL", "https://aux2.example/v1")
    llm_factory.reset_clients()
    second = llm_factory.get_aux_client()
    assert "aux2.example" in str(second.base_url)
    assert first is not second
