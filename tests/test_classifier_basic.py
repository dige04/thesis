"""
Basic tests for the memory classifier module.

These tests verify that the classifier module can be imported and
instantiated correctly. Full integration tests with actual API calls
are in test_classifier_integration.py.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.memory.classifier import (
    MemoryClassifier,
    ClassifierError,
    classify_memory_type,
    MemoryTypeEnum,
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
    """Test MemoryClassifier initialization."""

    @patch('src.memory.classifier.OpenAI')
    def test_init_creates_openai_client(self, mock_openai):
        """Test that initialization creates OpenAI client."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        classifier = MemoryClassifier()

        mock_openai.assert_called_once_with(api_key=None)
        assert classifier.client == mock_client

    @patch('src.memory.classifier.OpenAI')
    def test_init_with_api_key(self, mock_openai):
        """Test initialization with explicit API key."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        classifier = MemoryClassifier(api_key="test-key")

        mock_openai.assert_called_once_with(api_key="test-key")

    @patch('src.memory.classifier.OpenAI')
    def test_init_failure_raises_classifier_error(self, mock_openai):
        """Test that initialization failure raises ClassifierError."""
        mock_openai.side_effect = Exception("API key invalid")

        with pytest.raises(ClassifierError, match="Failed to initialize classifier"):
            MemoryClassifier()


class TestMemoryClassifierConstants:
    """Test that classifier uses frozen constants."""

    def test_model_is_gpt4o_mini(self):
        """Test that classifier uses gpt-4o-mini (cheapest model)."""
        assert MemoryClassifier.MODEL == "gpt-4o-mini"

    def test_temperature_is_zero(self):
        """Test that classifier uses temperature=0 (deterministic)."""
        assert MemoryClassifier.TEMPERATURE == 0


class TestClassifierErrorHandling:
    """Test classifier error handling."""

    @patch('src.memory.classifier.OpenAI')
    def test_classify_raises_classifier_error_on_api_failure(self, mock_openai):
        """Test that API failures raise ClassifierError."""
        mock_client = MagicMock()
        mock_client.beta.chat.completions.parse.side_effect = Exception("API error")
        mock_openai.return_value = mock_client

        classifier = MemoryClassifier()

        with pytest.raises(ClassifierError, match="Classifier failed"):
            classifier.classify(
                issue_summary="Test issue",
                patch_summary="Test patch",
                files_touched=["test.py"],
                functions_touched=["test_func"],
                task_id="TEST-001"
            )

    @patch('src.memory.classifier.OpenAI')
    def test_classify_raises_error_on_none_response(self, mock_openai):
        """Test that None response raises ClassifierError."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.parsed = None
        mock_client.beta.chat.completions.parse.return_value = mock_response
        mock_openai.return_value = mock_client

        classifier = MemoryClassifier()

        with pytest.raises(ClassifierError, match="Classifier returned None"):
            classifier.classify(
                issue_summary="Test issue",
                patch_summary="Test patch",
                files_touched=["test.py"],
                functions_touched=["test_func"]
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
            retry_count=0
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
