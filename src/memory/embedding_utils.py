"""Embedding utilities for memory record construction.

This module provides utilities for constructing and validating embedding payloads
according to the frozen invariants from THESIS_FINAL_v5.md.

Frozen Invariants:
- Embedding payload = [Issue + Final Error + Final Diff] only, < 7500 tokens (Invariant #4)
- No metadata (type, outcome, files) included in embedding_text
- Truncate patch_summary from end if limit exceeded
"""

import logging

import tiktoken

# Frozen token limit (Requirement 4, Invariant #4)
# 7500 tokens provides 500 token safety margin below 8K embedding model cap
MAX_EMBEDDING_TOKENS = 7500

# Default encoding for token counting (matches OpenAI embedding models)
DEFAULT_ENCODING = "cl100k_base"

logger = logging.getLogger(__name__)


def count_tokens(text: str, encoding_name: str = DEFAULT_ENCODING) -> int:
    """Count tokens in text using tiktoken.

    Args:
        text: Text to count tokens for
        encoding_name: Tiktoken encoding name (default: cl100k_base for OpenAI)

    Returns:
        Number of tokens in the text

    Notes:
        - Uses cl100k_base encoding (matches text-embedding-3-* models)
        - Handles empty strings gracefully (returns 0)
    """
    if not text:
        return 0

    try:
        encoding = tiktoken.get_encoding(encoding_name)
        return len(encoding.encode(text))
    except Exception as e:
        logger.error(f"Error counting tokens: {e}")
        # Fallback: rough estimate (1 token ≈ 4 characters)
        return len(text) // 4


def construct_embedding_text(
    issue_summary: str,
    failure_summary: str | None,
    patch_summary: str,
    max_tokens: int = MAX_EMBEDDING_TOKENS
) -> tuple[str, int, bool]:
    """Construct embedding text from Issue + Error + Diff only.

    This function implements Frozen Invariant #4:
    - Embedding payload = [Issue + Final Error + Final Diff] only
    - Must be < 7500 tokens
    - Truncate patch_summary from end if limit exceeded
    - NO metadata (type, outcome, files) included

    Args:
        issue_summary: Task issue description
        failure_summary: Final error message (None if task passed)
        patch_summary: Final diff/patch content
        max_tokens: Maximum token limit (default: 7500)

    Returns:
        Tuple of (embedding_text, token_count, was_truncated)
        - embedding_text: Constructed text ready for embedding
        - token_count: Final token count after any truncation
        - was_truncated: Whether patch_summary was truncated

    Notes:
        - Issue and error are never truncated (assumed to be reasonably sized)
        - Only patch_summary is truncated from the end if needed
        - Truncation is binary search to find maximum fitting length
        - Logs truncation events with original and final sizes

    Example:
        >>> text, tokens, truncated = construct_embedding_text(
        ...     issue_summary="Fix bug in QuerySet.exclude",
        ...     failure_summary="AssertionError: Expected 2, got 3",
        ...     patch_summary="diff --git a/django/db/models/query.py..."
        ... )
        >>> assert tokens < 7500
    """
    # Build initial embedding text
    parts = [
        f"Issue:\n{issue_summary}",
    ]

    if failure_summary:
        parts.append(f"\nError:\n{failure_summary}")

    parts.append(f"\nDiff:\n{patch_summary}")

    embedding_text = "\n".join(parts)
    token_count = count_tokens(embedding_text)

    # Check if within limit
    if token_count <= max_tokens:
        return embedding_text, token_count, False

    # Need to truncate patch_summary
    logger.warning(
        f"Embedding text exceeds {max_tokens} tokens ({token_count} tokens). "
        f"Truncating patch_summary from end."
    )

    # Calculate budget for patch_summary
    issue_part = f"Issue:\n{issue_summary}"
    error_part = f"\nError:\n{failure_summary}" if failure_summary else ""
    diff_header = "\nDiff:\n"

    fixed_parts = issue_part + error_part + diff_header
    fixed_tokens = count_tokens(fixed_parts)

    # Reserve tokens for patch_summary
    patch_budget = max_tokens - fixed_tokens

    if patch_budget <= 0:
        # Issue + Error already exceed limit (should be rare)
        logger.error(
            f"Issue and error alone exceed {max_tokens} tokens "
            f"({fixed_tokens} tokens). Cannot include patch."
        )
        embedding_text = fixed_parts + "[patch truncated - no budget remaining]"
        token_count = count_tokens(embedding_text)
        return embedding_text, token_count, True

    # Binary search to find maximum patch length that fits
    truncated_patch = _truncate_to_token_budget(
        patch_summary,
        patch_budget
    )

    # Reconstruct embedding text with truncated patch
    parts = [issue_part]
    if error_part:
        parts.append(error_part)
    parts.append(diff_header + truncated_patch)

    embedding_text = "".join(parts)
    final_token_count = count_tokens(embedding_text)

    logger.info(
        f"Truncated patch_summary: "
        f"original={token_count} tokens, "
        f"final={final_token_count} tokens, "
        f"patch_original={count_tokens(patch_summary)} tokens, "
        f"patch_final={count_tokens(truncated_patch)} tokens"
    )

    return embedding_text, final_token_count, True


def _truncate_to_token_budget(text: str, budget: int) -> str:
    """Truncate text from end to fit within token budget.

    Uses binary search to find the maximum character length that fits
    within the token budget.

    Args:
        text: Text to truncate
        budget: Maximum number of tokens allowed

    Returns:
        Truncated text that fits within budget

    Notes:
        - Truncates from end (preserves beginning of patch)
        - Uses binary search for efficiency
        - Adds "[truncated]" marker at end
    """
    if count_tokens(text) <= budget:
        return text

    # Binary search for maximum length
    left, right = 0, len(text)
    best_length = 0
    truncation_marker = "\n[... truncated ...]"
    marker_tokens = count_tokens(truncation_marker)

    # Adjust budget for marker - ensure final result is < budget (not <=)
    adjusted_budget = budget - marker_tokens - 1  # -1 to ensure strictly less than

    while left <= right:
        mid = (left + right) // 2
        candidate = text[:mid]
        tokens = count_tokens(candidate)

        if tokens < adjusted_budget:  # Changed from <= to <
            best_length = mid
            left = mid + 1
        else:
            right = mid - 1

    truncated = text[:best_length] + truncation_marker
    return truncated


def verify_embedding_size(
    embedding_text: str,
    max_tokens: int = MAX_EMBEDDING_TOKENS
) -> None:
    """Verify embedding text is under token limit.

    This enforces Frozen Invariant #4: embedding payload < 7500 tokens
    to prevent silent truncation by the 8K token embedding model.

    Args:
        embedding_text: Text to verify
        max_tokens: Maximum token limit (default: 7500)

    Raises:
        AssertionError: If text exceeds token limit

    Notes:
        - Called by MemoryStore.add() before generating embeddings
        - Caller should use construct_embedding_text() to ensure compliance
        - 7500 token limit provides 500 token safety margin
    """
    token_count = count_tokens(embedding_text)
    assert token_count < max_tokens, (
        f"Embedding text exceeds {max_tokens} token limit: "
        f"{token_count} tokens. "
        f"Use construct_embedding_text() to truncate patch_summary."
    )
