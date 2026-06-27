"""Test basic project setup and structure."""

import sys
from pathlib import Path


def test_python_version() -> None:
    """Verify Python version is 3.11 or higher."""
    assert sys.version_info >= (3, 11), f"Python 3.11+ required, got {sys.version_info}"


def test_project_structure() -> None:
    """Verify required directories exist."""
    project_root = Path(__file__).parent.parent

    required_dirs = [
        "src",
        "tests",
        "configs",
        "runs",
        "results",
        "logs",
    ]

    for dir_name in required_dirs:
        dir_path = project_root / dir_name
        assert dir_path.exists(), f"Required directory missing: {dir_name}"
        assert dir_path.is_dir(), f"Path exists but is not a directory: {dir_name}"


def test_results_subdirectories() -> None:
    """Verify results subdirectories exist."""
    project_root = Path(__file__).parent.parent
    results_dir = project_root / "results"

    required_subdirs = ["raw", "aggregated", "plots"]

    for subdir_name in required_subdirs:
        subdir_path = results_dir / subdir_name
        assert subdir_path.exists(), f"Required subdirectory missing: results/{subdir_name}"


def test_pyproject_toml_exists() -> None:
    """Verify pyproject.toml exists."""
    project_root = Path(__file__).parent.parent
    pyproject_path = project_root / "pyproject.toml"

    assert pyproject_path.exists(), "pyproject.toml not found"
    assert pyproject_path.is_file(), "pyproject.toml is not a file"


def test_gitignore_exists() -> None:
    """Verify .gitignore exists."""
    project_root = Path(__file__).parent.parent
    gitignore_path = project_root / ".gitignore"

    assert gitignore_path.exists(), ".gitignore not found"
    assert gitignore_path.is_file(), ".gitignore is not a file"


def test_makefile_exists() -> None:
    """Verify Makefile exists."""
    project_root = Path(__file__).parent.parent
    makefile_path = project_root / "Makefile"

    assert makefile_path.exists(), "Makefile not found"
    assert makefile_path.is_file(), "Makefile is not a file"


def test_gitignore_content() -> None:
    """Verify .gitignore contains required patterns."""
    project_root = Path(__file__).parent.parent
    gitignore_path = project_root / ".gitignore"

    content = gitignore_path.read_text()

    required_patterns = [
        "runs/",
        "results/raw/",
        "*.faiss",
        "*.sqlite",
        "wandb",
        "logs/",
    ]

    for pattern in required_patterns:
        assert pattern in content, f"Required pattern missing in .gitignore: {pattern}"
