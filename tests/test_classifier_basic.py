"""
Basic tests for the memory classifier module.

These tests verify that the classifier module can be imported and
instantiated correctly. Full integration tests with actual API calls
are in test_classifier_integration.py.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.memory.classifier import (
    ClassifierError,
    MemoryClassifier,
    MemoryTypeEnum,
    classify_memory_type,
)
from src.memory.record import VALID_MEMORY_TYPES


class TestMemoryTypeEnum:
    """Test the MemoryTypeEnum enum."""

    def test_enum_has_all_5_types(self):
        """Test that enum contains all 5 valid memory types."""
        enum_values = {e.value for e in MemoryTypeEnum}
        assert enum_values == VALID_MEMORY_TYPES

    def test_enum_values_are_strings(self):
        """Test that enum values are strings."""
        for memory_type in MemoryTypeEnum:
            assert isinstance(memory_type.value, str)


class TestMemoryClassifierInit:
    """Test MemoryClassifier initialization (factory-based, deviation D4)."""

    @patch('src.memory.classifier.get_aux_client')
    def test_init_uses_factory_chat_client_by_default(self, mock_get_client):
        """Default init uses the shared llm_factory chat client (no api_key)."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        classifier = MemoryClassifier()

        mock_get_client.assert_called_once_with()
        assert classifier.client is mock_client

    @patch('src.memory.classifier.OpenAI')
    def test_init_with_api_key_builds_explicit_client(self, mock_openai):
        """An explicit api_key builds a client against the chat endpoint."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        classifier = MemoryClassifier(api_key="test-key")

        _, kwargs = mock_openai.call_args
        assert kwargs["api_key"] == "test-key"
        assert "base_url" in kwargs
        assert classifier.client is mock_client

    @patch('src.memory.classifier.get_aux_client')
    def test_init_failure_raises_classifier_error(self, mock_get_client):
        """Client init failure surfaces as ClassifierError."""
        mock_get_client.side_effect = Exception("endpoint unreachable")

        with pytest.raises(ClassifierError, match="Failed to initialize classifier"):
            MemoryClassifier()


class TestMemoryClassifierConstants:
    """Test that classifier uses frozen constants."""

    @patch('src.memory.classifier.get_aux_client')
    def test_default_model_comes_from_factory(self, mock_get_client):
        """Model is config-driven via llm_factory.classifier_model() (deviation D1)."""
        from src.config.llm_factory import classifier_model

        mock_get_client.return_value = MagicMock()
        assert MemoryClassifier().model == classifier_model()

    def test_temperature_is_one(self):
        """Classifier temperature held constant; amended to 1 (Kimi reasoning) 2026-06-14."""
        assert MemoryClassifier.TEMPERATURE == 1


class TestClassifierErrorHandling:
    """Test classifier error handling (JSON mode)."""

    @patch('src.memory.classifier.get_aux_client')
    def test_classify_raises_classifier_error_on_api_failure(self, mock_get_client):
        """Test that API failures raise ClassifierError."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API error")
        mock_get_client.return_value = mock_client

        classifier = MemoryClassifier()

        with pytest.raises(ClassifierError, match="Classifier failed"):
            classifier.classify(
                issue_summary="Test issue",
                patch_summary="Test patch",
                files_touched=["test.py"],
                functions_touched=["test_func"],
                task_id="TEST-001",
            )

    @patch('src.memory.classifier.get_aux_client')
    def test_classify_raises_error_on_empty_content(self, mock_get_client):
        """Empty content (after retries) raises ClassifierError."""
        mock_client = MagicMock()
        msg = MagicMock()
        msg.content = ""
        mock_client.chat.completions.create.return_value.choices = [
            MagicMock(message=msg)
        ]
        mock_get_client.return_value = mock_client

        classifier = MemoryClassifier()

        with pytest.raises(ClassifierError, match="Classifier failed"):
            classifier.classify(
                issue_summary="Test issue",
                patch_summary="Test patch",
                files_touched=["test.py"],
                functions_touched=["test_func"],
                max_retries=1,
            )


class TestClassifyMemoryTypeFunction:
    """Test the convenience function classify_memory_type."""

    @patch('src.memory.classifier.MemoryClassifier')
    def test_creates_classifier_and_calls_classify(self, mock_classifier_class):
        """Test that convenience function creates classifier and calls classify."""
        mock_classifier = MagicMock()
        mock_classifier.classify.return_value = "bug_fix"
        mock_classifier_class.return_value = mock_classifier

        result = classify_memory_type(
            issue_summary="Fix null pointer",
            patch_summary="Add null check",
            files_touched=["service.py"],
            functions_touched=["process_data"],
            task_id="TEST-001",
            retry_count=0,
            api_key="test-key"
        )

        mock_classifier_class.assert_called_once_with(api_key="test-key")
        mock_classifier.classify.assert_called_once_with(
            issue_summary="Fix null pointer",
            patch_summary="Add null check",
            files_touched=["service.py"],
            functions_touched=["process_data"],
            task_id="TEST-001",
            retry_count=0,
            usage_sink=None,  # E1: convenience fn forwards the optional cost sink
        )
        assert result == "bug_fix"


class TestBuildClassificationInput:
    """Test the _build_classification_input method."""

    @patch('src.memory.classifier.OpenAI')
    def test_builds_input_with_all_fields(self, mock_openai):
        """Test that classification input includes all required fields."""
        mock_openai.return_value = MagicMock()
        classifier = MemoryClassifier()

        input_text = classifier._build_classification_input(
            issue_summary="Fix bug in user service",
            patch_summary="Add null check before accessing user.name",
            files_touched=["user_service.py", "user_model.py"],
            functions_touched=["get_user_name", "validate_user"]
        )

        assert "Fix bug in user service" in input_text
        assert "Add null check before accessing user.name" in input_text
        assert "user_service.py" in input_text
        assert "user_model.py" in input_text
        assert "get_user_name" in input_text
        assert "validate_user" in input_text

    @patch('src.memory.classifier.OpenAI')
    def test_handles_empty_lists(self, mock_openai):
        """Test that empty lists are handled gracefully."""
        mock_openai.return_value = MagicMock()
        classifier = MemoryClassifier()

        input_text = classifier._build_classification_input(
            issue_summary="Test issue",
            patch_summary="Test patch",
            files_touched=[],
            functions_touched=[]
        )

        assert "(none)" in input_text
        assert "Test issue" in input_text
        assert "Test patch" in input_text


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3.2: classifier runs via llm_factory chat client in JSON mode (Ollama
# ignores OpenAI json_schema response_format), with Pydantic validation + retry.
# ─────────────────────────────────────────────────────────────────────────────

class TestClassifierJsonMode:
    @patch("src.memory.classifier.get_aux_client")
    def test_classify_no_json_mode_and_parses(self, mock_get_client):
        mock_client = MagicMock()
        msg = MagicMock()
        msg.content = '{"memory_type": "bug_fix", "reasoning": "adds a null check"}'
        mock_client.chat.completions.create.return_value.choices = [
            MagicMock(message=msg)
        ]
        mock_get_client.return_value = mock_client

        classifier = MemoryClassifier()
        result = classifier.classify(
            issue_summary="Fix null deref",
            patch_summary="add guard",
            files_touched=["a.py"],
            functions_touched=["f"],
        )

        assert result == "bug_fix"
        _, kwargs = mock_client.chat.completions.create.call_args
        # D4 extended (2026-06-17): MiniMax M3 returns 400 model_not_capable for
        # response_format=json_object, so JSON mode is dropped — rely on
        # prompt-instructed JSON + tolerant extraction + Pydantic validation.
        assert "response_format" not in kwargs
        assert kwargs["temperature"] == 1  # 2026-06-14 amendment: Kimi reasoning models
        # Must NOT use the OpenAI beta structured-output path (Ollama ignores it).
        mock_client.beta.chat.completions.parse.assert_not_called()

    @patch("src.memory.classifier.get_aux_client")
    def test_classify_parses_think_prefixed_content(self, mock_get_client):
        # MiniMax M3 is a reasoning model: it prepends <think>...</think> CoT to
        # the JSON. The classifier must strip it and still recover the type.
        mock_client = MagicMock()
        msg = MagicMock()
        msg.content = (
            "<think>The change adds a parameter to a public function, so this is "
            'an interface change.</think>\n{"memory_type": "api_change", '
            '"reasoning": "new param on public fn"}'
        )
        mock_client.chat.completions.create.return_value.choices = [
            MagicMock(message=msg)
        ]
        mock_get_client.return_value = mock_client

        result = MemoryClassifier().classify(
            issue_summary="i", patch_summary="p", files_touched=[], functions_touched=[]
        )
        assert result == "api_change"

    @patch("src.memory.classifier.get_aux_client")
    def test_classify_retries_on_invalid_then_raises(self, mock_get_client):
        mock_client = MagicMock()
        bad = MagicMock()
        bad.content = "this is not json"
        mock_client.chat.completions.create.return_value.choices = [
            MagicMock(message=bad)
        ]
        mock_get_client.return_value = mock_client

        classifier = MemoryClassifier()
        with pytest.raises(ClassifierError):
            classifier.classify(
                issue_summary="i",
                patch_summary="p",
                files_touched=[],
                functions_touched=[],
                max_retries=1,
            )
        # initial attempt + 1 retry == 2 create calls
        assert mock_client.chat.completions.create.call_count == 2

    @patch("src.memory.classifier.get_aux_client")
    def test_classify_recovers_on_retry(self, mock_get_client):
        mock_client = MagicMock()
        bad = MagicMock(); bad.content = "oops"
        good = MagicMock(); good.content = '{"memory_type": "config", "reasoning": "settings"}'
        mock_client.chat.completions.create.return_value.choices = [MagicMock(message=bad)]
        # first call bad, second good
        mock_client.chat.completions.create.side_effect = [
            MagicMock(choices=[MagicMock(message=bad)]),
            MagicMock(choices=[MagicMock(message=good)]),
        ]
        mock_get_client.return_value = mock_client

        classifier = MemoryClassifier()
        result = classifier.classify(
            issue_summary="i", patch_summary="p",
            files_touched=[], functions_touched=[], max_retries=2,
        )
        assert result == "config"
