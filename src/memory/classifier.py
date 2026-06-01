"""
Memory type classifier for the memory pruning research system.

This module implements deterministic classification of memory records into 5 content types
using OpenAI's Structured Outputs with temperature=0 for reproducibility.

Frozen Invariants:
- 5-type taxonomy: architectural, api_change, bug_fix, test_update, config
- Classification based on CONTENT only (NOT outcome)
- Temperature=0 for deterministic classification
- Uses Structured Outputs with 1-of-5 enum
- Cheapest model (gpt-4o-mini)

Requirements: 5, 15
Design: §6 Type Classification System
"""

import logging
from enum import StrEnum

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from src.config.llm_factory import chat_base_url, classifier_model, get_chat_client
from src.errors import ClassifierError

from .record import VALID_MEMORY_TYPES

logger = logging.getLogger(__name__)


class MemoryTypeEnum(StrEnum):
    """
    Enum for the 5 memory content types.

    This enum is used for OpenAI Structured Outputs to enforce
    deterministic 1-of-5 classification.
    """
    ARCHITECTURAL = "architectural"
    API_CHANGE = "api_change"
    BUG_FIX = "bug_fix"
    TEST_UPDATE = "test_update"
    CONFIG = "config"


class MemoryTypeClassification(BaseModel):
    """
    Pydantic model for structured output from OpenAI.

    This model enforces that the classifier returns exactly one
    of the 5 valid memory types.
    """
    memory_type: MemoryTypeEnum
    reasoning: str  # Brief explanation for debugging/auditing


class MemoryClassifier:
    """
    Deterministic memory type classifier using OpenAI Structured Outputs.

    This classifier categorizes memory records into 5 content-based types:
    - architectural: Module structure, class hierarchies, design patterns
    - api_change: Function signatures, parameter changes, return types
    - bug_fix: Bug patterns, error handling, edge cases
    - test_update: Test modifications, test coverage, test fixtures
    - config: Configuration changes, environment variables, settings

    Classification is based on CONTENT only, NOT outcome (pass/fail).

    Requirements: 5, 15
    Design: §6 Type Classification System
    """

    # Frozen temperature (deterministic)
    TEMPERATURE = 0

    # Appended to the system prompt. Ollama's OpenAI-compatible endpoint ignores
    # the OpenAI json_schema response_format (ollama/ollama #10001), so we use
    # plain JSON mode + explicit schema instructions + Pydantic validation
    # instead of beta.chat.completions.parse (deviation D4, see CLAUDE.md).
    JSON_FORMAT_INSTRUCTIONS = (
        "\n\nRespond with ONLY a JSON object of exactly this shape "
        "(no markdown fences, no commentary):\n"
        '{"memory_type": "<one of: architectural, api_change, bug_fix, '
        'test_update, config>", "reasoning": "<brief explanation>"}'
    )

    # Classification prompt template
    CLASSIFICATION_PROMPT = """You are a code change classifier for a research system studying memory management in AI coding agents.

Your task is to classify a code change into exactly ONE of these 5 content types:

1. **architectural**: Changes to module structure, class hierarchies, design patterns, or overall code organization
   - Examples: Adding new classes, refactoring module structure, introducing design patterns

2. **api_change**: Changes to function signatures, parameters, return types, or public interfaces
   - Examples: Adding/removing function parameters, changing return types, renaming public methods

3. **bug_fix**: Changes that fix bugs, handle errors, or address edge cases
   - Examples: Fixing null pointer exceptions, handling edge cases, correcting logic errors

4. **test_update**: Changes to test files, test coverage, test fixtures, or test infrastructure
   - Examples: Adding new tests, updating test assertions, modifying test fixtures

5. **config**: Changes to configuration files, environment variables, settings, or build configuration
   - Examples: Updating config files, changing environment variables, modifying build scripts

CRITICAL RULES:
- Classify based on CONTENT only (what changed), NOT outcome (whether it passed or failed)
- Choose the MOST SPECIFIC type that applies
- If multiple types apply, choose the PRIMARY change
- Do NOT use outcome information (pass/fail) in your classification

You will be given:
- Issue summary: Description of the problem
- Patch summary: Description of the code changes
- Files touched: List of modified files
- Functions touched: List of modified functions

Classify the change into ONE of the 5 types above."""

    def __init__(self, model: str | None = None, api_key: str | None = None):
        """
        Initialize the memory classifier.

        Args:
            model: Chat model id (defaults to llm_factory.classifier_model()).
            api_key: Optional explicit key. If given, builds a client against the
                configured chat endpoint with that key; otherwise uses the shared
                llm_factory chat client (Ollama Cloud by default).

        Raises:
            ClassifierError: If chat client initialization fails
        """
        self.model = model or classifier_model()
        try:
            if api_key is not None:
                self.client = OpenAI(base_url=chat_base_url(), api_key=api_key)
            else:
                self.client = get_chat_client()
            logger.info(
                f"Initialized MemoryClassifier with model={self.model}, "
                f"temp={self.TEMPERATURE}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize chat client: {e}")
            raise ClassifierError(f"Failed to initialize classifier: {e}") from e

    def classify(
        self,
        issue_summary: str,
        patch_summary: str,
        files_touched: list[str],
        functions_touched: list[str],
        task_id: str | None = None,
        retry_count: int = 0,
        max_retries: int = 2,
    ) -> str:
        """
        Classify a memory record into one of 5 content types.

        This method uses OpenAI's Structured Outputs with temperature=0
        for deterministic classification.

        Args:
            issue_summary: Description of the problem/issue
            patch_summary: Description of the code changes
            files_touched: List of modified files
            functions_touched: List of modified functions
            task_id: Optional task ID for logging
            retry_count: Number of retries attempted (for logging)

        Returns:
            One of the 5 valid memory types: architectural, api_change,
            bug_fix, test_update, config

        Raises:
            ClassifierError: If classification fails or returns invalid type

        Requirements: 5, 15
        """
        # Build classification input
        classification_input = self._build_classification_input(
            issue_summary=issue_summary,
            patch_summary=patch_summary,
            files_touched=files_touched,
            functions_touched=functions_touched
        )

        messages = [
            {
                "role": "system",
                "content": self.CLASSIFICATION_PROMPT + self.JSON_FORMAT_INSTRUCTIONS,
            },
            {"role": "user", "content": classification_input},
        ]

        last_error: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                # JSON mode (NOT beta.parse) + Pydantic validation — temperature
                # is ALWAYS 0 (frozen invariant). See JSON_FORMAT_INSTRUCTIONS / D4.
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=self.TEMPERATURE,  # FROZEN: Always 0
                )

                content = response.choices[0].message.content
                if not content or not isinstance(content, str):
                    raise ValueError("classifier returned empty/non-string content")

                classification = MemoryTypeClassification.model_validate_json(content)
                memory_type = classification.memory_type.value

                # Redundant with the enum, but explicit per Invariant #7.
                if memory_type not in VALID_MEMORY_TYPES:
                    raise ValueError(
                        f"invalid memory_type '{memory_type}' "
                        f"(valid: {sorted(VALID_MEMORY_TYPES)})"
                    )

                logger.info(
                    f"Classified memory type={memory_type} "
                    f"(task_id={task_id}, attempt={attempt}): {classification.reasoning}"
                )
                return memory_type

            except (ValidationError, ValueError) as e:
                # Malformed/invalid output — retry with a corrective nudge.
                last_error = e
                logger.warning(
                    f"Classifier attempt {attempt} produced invalid output "
                    f"(task_id={task_id}): {e}"
                )
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Your previous response was not valid."
                            + self.JSON_FORMAT_INSTRUCTIONS
                        ),
                    }
                )
            except Exception as e:
                # Transport/API errors — do not silently swallow, fail fast.
                last_error = e
                logger.error(
                    f"Classifier API call failed "
                    f"(task_id={task_id}, attempt={attempt}): {e}"
                )
                break

        error_msg = (
            f"Classifier failed for task_id={task_id} after "
            f"{max_retries + 1} attempt(s): {last_error}"
        )
        logger.error(error_msg)
        raise ClassifierError(error_msg) from last_error

    def _build_classification_input(
        self,
        issue_summary: str,
        patch_summary: str,
        files_touched: list[str],
        functions_touched: list[str]
    ) -> str:
        """
        Build the classification input text from memory record fields.

        Args:
            issue_summary: Description of the problem/issue
            patch_summary: Description of the code changes
            files_touched: List of modified files
            functions_touched: List of modified functions

        Returns:
            Formatted classification input text
        """
        # Format files and functions
        files_str = "\n".join(f"  - {f}" for f in files_touched) if files_touched else "  (none)"
        functions_str = "\n".join(f"  - {f}" for f in functions_touched) if functions_touched else "  (none)"

        return f"""Issue Summary:
{issue_summary}

Patch Summary:
{patch_summary}

Files Touched:
{files_str}

Functions Touched:
{functions_str}

Classify this change into ONE of the 5 types: architectural, api_change, bug_fix, test_update, config"""


def classify_memory_type(
    issue_summary: str,
    patch_summary: str,
    files_touched: list[str],
    functions_touched: list[str],
    task_id: str | None = None,
    retry_count: int = 0,
    api_key: str | None = None
) -> str:
    """
    Convenience function to classify a memory type without creating a classifier instance.

    This function creates a new classifier instance for each call. For batch
    classification, create a MemoryClassifier instance and call classify() directly.

    Args:
        issue_summary: Description of the problem/issue
        patch_summary: Description of the code changes
        files_touched: List of modified files
        functions_touched: List of modified functions
        task_id: Optional task ID for logging
        retry_count: Number of retries attempted (for logging)
        api_key: Optional OpenAI API key

    Returns:
        One of the 5 valid memory types

    Raises:
        ClassifierError: If classification fails

    Requirements: 5, 15
    """
    classifier = MemoryClassifier(api_key=api_key)
    return classifier.classify(
        issue_summary=issue_summary,
        patch_summary=patch_summary,
        files_touched=files_touched,
        functions_touched=functions_touched,
        task_id=task_id,
        retry_count=retry_count
    )
