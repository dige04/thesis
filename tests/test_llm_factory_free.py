"""FREE_LLM_* provider override (free-unlimited MiniMax M3 path)."""

from src.config import llm_factory as f

_FREE = [
    "FREE_LLM_CHAT_BASE_URL",
    "FREE_LLM_CHAT_API_KEY",
    "FREE_LLM_MAIN_MODEL",
    "FREE_LLM_SUMMARY_MODEL",
    "FREE_LLM_CLASSIFIER_MODEL",
]


def test_free_vars_override_chat(monkeypatch):
    monkeypatch.setenv("FREE_LLM_CHAT_BASE_URL", "https://free.example/v1")
    monkeypatch.setenv("FREE_LLM_CHAT_API_KEY", "freekey")
    monkeypatch.setenv("FREE_LLM_MAIN_MODEL", "minimax-m3")
    monkeypatch.setenv("FREE_LLM_SUMMARY_MODEL", "minimax-m3")
    monkeypatch.setenv("FREE_LLM_CLASSIFIER_MODEL", "minimax-m3")
    assert f.chat_base_url() == "https://free.example/v1"
    assert f.chat_api_key() == "freekey"
    assert f.main_model() == "minimax-m3"
    assert f.summary_model() == "minimax-m3"
    assert f.classifier_model() == "minimax-m3"
    # FREE_* must NOT touch embeddings (they stay on local Ollama).
    assert f.embedding_base_url() == "http://localhost:11434/v1"


def test_falls_back_to_llm_when_no_free(monkeypatch):
    for k in _FREE:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LLM_MAIN_MODEL", "kimi-k2.6")
    monkeypatch.setenv("LLM_CHAT_BASE_URL", "https://opencode.ai/zen/go/v1")
    assert f.main_model() == "kimi-k2.6"
    assert f.chat_base_url() == "https://opencode.ai/zen/go/v1"


def test_explicit_override_beats_free(monkeypatch):
    monkeypatch.setenv("FREE_LLM_MAIN_MODEL", "minimax-m3")
    assert f.main_model(override="explicit-model") == "explicit-model"
