"""Loader for the canonical SWE-bench_Verified dataset (deviation E).

The SWE-Bench-CL curriculum dropped FAIL_TO_PASS / PASS_TO_PASS / version /
environment_setup_commit, so eval ground-truth is recovered from the canonical
``princeton-nlp/SWE-bench_Verified`` split, keyed by ``instance_id`` (decision E).
The swebench eval harness loads these itself when pointed at the Verified
dataset; this module is for our own coverage checks (the Phase 5.0 build-probe)
and for any place we need the test specs directly.

All 8 SWE-Bench-CL repos are a strict subset of SWE-bench_Verified, so every
curriculum instance_id is expected to be present (research-confirmed). The
build-probe asserts this and fails loud on any miss (version drift signal).

``datasets`` is imported lazily so importing this module never requires it; a
``loader`` callable can be injected for offline unit tests.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterable
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_DATASET = "princeton-nlp/SWE-bench_Verified"
DEFAULT_SPLIT = "test"

# Cache: (dataset_name, split) -> {instance_id: normalized_row}
_INDEX_CACHE: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}


def _as_list(value: Any) -> list[str]:
    """FAIL_TO_PASS / PASS_TO_PASS are JSON-encoded strings in Verified."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else [value]
        except json.JSONDecodeError:
            return [value]
    return list(value)


def _normalize(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "instance_id": row["instance_id"],
        "repo": row.get("repo"),
        "base_commit": row.get("base_commit"),
        "environment_setup_commit": row.get("environment_setup_commit"),
        "version": row.get("version"),
        "test_patch": row.get("test_patch"),
        "patch": row.get("patch"),
        "fail_to_pass": _as_list(row.get("FAIL_TO_PASS")),
        "pass_to_pass": _as_list(row.get("PASS_TO_PASS")),
    }


def _default_loader(dataset_name: str, split: str) -> Iterable[dict[str, Any]]:
    from datasets import load_dataset  # lazy: only needed for a real load

    logger.info(f"Loading {dataset_name} split={split} (HF datasets)")
    return load_dataset(dataset_name, split=split)


def load_verified_index(
    dataset_name: str = DEFAULT_DATASET,
    split: str = DEFAULT_SPLIT,
    *,
    loader: Callable[[str, str], Iterable[dict[str, Any]]] | None = None,
    refresh: bool = False,
) -> dict[str, dict[str, Any]]:
    """Return ``{instance_id: normalized_row}`` for the Verified split.

    Args:
        dataset_name / split: HF dataset coordinates.
        loader: optional ``(dataset_name, split) -> iterable[row]`` for offline
            tests; defaults to ``datasets.load_dataset``.
        refresh: bypass the module cache.
    """
    key = (dataset_name, split)
    if not refresh and key in _INDEX_CACHE:
        return _INDEX_CACHE[key]

    load = loader or _default_loader
    index: dict[str, dict[str, Any]] = {}
    for row in load(dataset_name, split):
        index[row["instance_id"]] = _normalize(row)

    _INDEX_CACHE[key] = index
    logger.info(f"Indexed {len(index)} Verified instances")
    return index


def get_verified_instance(
    instance_id: str,
    *,
    dataset_name: str = DEFAULT_DATASET,
    split: str = DEFAULT_SPLIT,
    loader: Callable[[str, str], Iterable[dict[str, Any]]] | None = None,
) -> dict[str, Any] | None:
    """Return the normalized Verified row for one instance, or None if absent."""
    return load_verified_index(dataset_name, split, loader=loader).get(instance_id)


def verified_instance_ids(
    *,
    dataset_name: str = DEFAULT_DATASET,
    split: str = DEFAULT_SPLIT,
    loader: Callable[[str, str], Iterable[dict[str, Any]]] | None = None,
) -> set[str]:
    """Set of instance_ids present in the Verified split (for coverage checks)."""
    return set(load_verified_index(dataset_name, split, loader=loader))


def clear_cache() -> None:
    """Drop the in-memory index cache (test hygiene)."""
    _INDEX_CACHE.clear()
