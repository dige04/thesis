"""Unit tests for SWE-Bench-CL dataset loader.

Tests the loader's ability to:
- Load all 8 official sequences from curriculum JSON
- Preserve chronological ordering within sequences
- Extract all required task fields
- Validate minimum 15 tasks per sequence
- Handle malformed or missing data gracefully
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.benchmark.swebenchcl_loader import SWEBenchCLLoader


class TestSWEBenchCLLoader:
    """Test suite for SWEBenchCLLoader."""

    def _create_valid_task_data(
        self, task_id: str, repo: str, sequence_index: int
    ) -> dict:
        """Helper to create valid task data dictionary."""
        return {
            "task_id": task_id,
            "repo": repo,
            "base_commit": f"commit-{sequence_index}",
            "issue_text": f"Issue for {task_id}",
            "test_patch": f"test patch for {task_id}",
            "gold_patch": f"gold patch for {task_id}",
            "created_at": f"2023-01-{sequence_index+1:02d}T10:00:00Z",
            "sequence_index": sequence_index,
            "difficulty_label": "medium",
        }

    def _create_valid_sequence_data(
        self, sequence_name: str, repo: str, task_count: int = 15
    ) -> dict:
        """Helper to create valid sequence data dictionary."""
        tasks = [
            self._create_valid_task_data(f"{repo.replace('/', '__')}-{i}", repo, i)
            for i in range(task_count)
        ]
        return {
            "sequence_name": sequence_name,
            "repo": repo,
            "tasks": tasks,
        }

    def _create_curriculum_file(self, sequences_data: list[dict]) -> Path:
        """Helper to create a temporary curriculum JSON file."""
        curriculum = {"sequences": sequences_data}
        temp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        json.dump(curriculum, temp_file)
        temp_file.close()
        return Path(temp_file.name)

    def test_loader_initialization_valid_path(self):
        """Test loader initialization with valid curriculum path."""
        sequences_data = [
            self._create_valid_sequence_data(f"seq-{i}", f"repo{i}/repo{i}")
            for i in range(8)
        ]
        curriculum_path = self._create_curriculum_file(sequences_data)

        try:
            loader = SWEBenchCLLoader(curriculum_path)
            assert loader.curriculum_path == curriculum_path
        finally:
            curriculum_path.unlink()

    def test_loader_initialization_empty_path_raises_error(self):
        """Test that empty curriculum path raises ValueError."""
        with pytest.raises(ValueError, match="curriculum_path cannot be empty"):
            SWEBenchCLLoader("")

    def test_loader_initialization_nonexistent_file_raises_error(self):
        """Test that nonexistent curriculum file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Curriculum file not found"):
            SWEBenchCLLoader("/nonexistent/path/curriculum.json")

    def test_load_all_8_sequences(self):
        """Test loading all 8 official sequences.

        This enforces Requirement 1: "THE System SHALL load all 8 sequences
        without subsetting or filtering"
        """
        sequences_data = [
            self._create_valid_sequence_data(f"seq-{i}", f"repo{i}/repo{i}")
            for i in range(8)
        ]
        curriculum_path = self._create_curriculum_file(sequences_data)

        try:
            loader = SWEBenchCLLoader(curriculum_path)
            sequences = loader.load_all_sequences()

            assert len(sequences) == 8
            for i, sequence in enumerate(sequences):
                assert sequence.sequence_name == f"seq-{i}"
                assert sequence.repo == f"repo{i}/repo{i}"
        finally:
            curriculum_path.unlink()

    def test_load_fewer_than_8_sequences_raises_error(self):
        """Test that curriculum with fewer than 8 sequences raises ValueError.

        Frozen Decision #1: Must have exactly 8 sequences.
        """
        sequences_data = [
            self._create_valid_sequence_data(f"seq-{i}", f"repo{i}/repo{i}")
            for i in range(7)  # Only 7 sequences
        ]
        curriculum_path = self._create_curriculum_file(sequences_data)

        try:
            loader = SWEBenchCLLoader(curriculum_path)
            with pytest.raises(ValueError, match="must contain exactly 8 sequences"):
                loader.load_all_sequences()
        finally:
            curriculum_path.unlink()

    def test_load_more_than_8_sequences_raises_error(self):
        """Test that curriculum with more than 8 sequences raises ValueError.

        Frozen Decision #1: Must have exactly 8 sequences.
        """
        sequences_data = [
            self._create_valid_sequence_data(f"seq-{i}", f"repo{i}/repo{i}")
            for i in range(9)  # 9 sequences
        ]
        curriculum_path = self._create_curriculum_file(sequences_data)

        try:
            loader = SWEBenchCLLoader(curriculum_path)
            with pytest.raises(ValueError, match="must contain exactly 8 sequences"):
                loader.load_all_sequences()
        finally:
            curriculum_path.unlink()

    def test_preserve_chronological_ordering(self):
        """Test that chronological ordering is preserved within sequences.

        This enforces Requirement 1: "THE System SHALL preserve the original
        chronological ordering of tasks within each sequence"
        """
        # Create sequence with tasks in shuffled order
        tasks_data = [
            self._create_valid_task_data(f"task-{i}", "django/django", i)
            for i in range(15)
        ]
        # Shuffle the tasks
        import random

        shuffled_tasks = tasks_data.copy()
        random.shuffle(shuffled_tasks)

        sequence_data = {
            "sequence_name": "django",
            "repo": "django/django",
            "tasks": shuffled_tasks,
        }
        sequences_data = [sequence_data] + [
            self._create_valid_sequence_data(f"seq-{i}", f"repo{i}/repo{i}")
            for i in range(1, 8)
        ]
        curriculum_path = self._create_curriculum_file(sequences_data)

        try:
            loader = SWEBenchCLLoader(curriculum_path)
            sequences = loader.load_all_sequences()

            # Verify tasks are sorted by sequence_index
            django_sequence = sequences[0]
            for i, task in enumerate(django_sequence.tasks):
                assert task.sequence_index == i
        finally:
            curriculum_path.unlink()

    def test_extract_all_required_task_fields(self):
        """Test that all required task fields are extracted.

        This enforces Requirement 1: "WHEN a sequence is loaded, THE System
        SHALL extract task_id, repo, base_commit, issue_text, test_patch,
        gold_patch, created_at, sequence_index, and difficulty_label"
        """
        sequences_data = [
            self._create_valid_sequence_data("django", "django/django")
        ] + [
            self._create_valid_sequence_data(f"seq-{i}", f"repo{i}/repo{i}")
            for i in range(1, 8)
        ]
        curriculum_path = self._create_curriculum_file(sequences_data)

        try:
            loader = SWEBenchCLLoader(curriculum_path)
            sequences = loader.load_all_sequences()

            task = sequences[0].tasks[0]
            assert task.task_id is not None
            assert task.repo is not None
            assert task.base_commit is not None
            assert task.issue_text is not None
            assert task.test_patch is not None
            assert task.gold_patch is not None
            assert task.created_at is not None
            assert task.sequence_index is not None
            assert task.difficulty_label is not None
        finally:
            curriculum_path.unlink()

    def test_validate_minimum_15_tasks_per_sequence(self):
        """Test that sequences with fewer than 15 tasks raise ValueError.

        This enforces Requirement 1: "THE System SHALL validate that each
        sequence contains at least 15 tasks"
        """
        # Create one sequence with only 14 tasks
        sequences_data = [
            self._create_valid_sequence_data("django", "django/django", task_count=14)
        ] + [
            self._create_valid_sequence_data(f"seq-{i}", f"repo{i}/repo{i}")
            for i in range(1, 8)
        ]
        curriculum_path = self._create_curriculum_file(sequences_data)

        try:
            loader = SWEBenchCLLoader(curriculum_path)
            with pytest.raises(ValueError, match="must contain at least 15 tasks"):
                loader.load_all_sequences()
        finally:
            curriculum_path.unlink()

    def test_task_missing_required_field_raises_error(self):
        """Test that tasks missing required fields raise ValueError."""
        task_data = self._create_valid_task_data("task-0", "django/django", 0)
        del task_data["task_id"]  # Remove required field

        sequence_data = {
            "sequence_name": "django",
            "repo": "django/django",
            "tasks": [task_data] + [
                self._create_valid_task_data(f"task-{i}", "django/django", i)
                for i in range(1, 15)
            ],
        }
        sequences_data = [sequence_data] + [
            self._create_valid_sequence_data(f"seq-{i}", f"repo{i}/repo{i}")
            for i in range(1, 8)
        ]
        curriculum_path = self._create_curriculum_file(sequences_data)

        try:
            loader = SWEBenchCLLoader(curriculum_path)
            with pytest.raises(ValueError, match="missing required fields"):
                loader.load_all_sequences()
        finally:
            curriculum_path.unlink()

    def test_sequence_missing_sequence_name_raises_error(self):
        """Test that sequences missing sequence_name raise ValueError."""
        sequence_data = self._create_valid_sequence_data("django", "django/django")
        del sequence_data["sequence_name"]

        sequences_data = [sequence_data] + [
            self._create_valid_sequence_data(f"seq-{i}", f"repo{i}/repo{i}")
            for i in range(1, 8)
        ]
        curriculum_path = self._create_curriculum_file(sequences_data)

        try:
            loader = SWEBenchCLLoader(curriculum_path)
            with pytest.raises(ValueError, match="missing 'sequence_name' field"):
                loader.load_all_sequences()
        finally:
            curriculum_path.unlink()

    def test_sequence_missing_repo_raises_error(self):
        """Test that sequences missing repo raise ValueError."""
        sequence_data = self._create_valid_sequence_data("django", "django/django")
        del sequence_data["repo"]

        sequences_data = [sequence_data] + [
            self._create_valid_sequence_data(f"seq-{i}", f"repo{i}/repo{i}")
            for i in range(1, 8)
        ]
        curriculum_path = self._create_curriculum_file(sequences_data)

        try:
            loader = SWEBenchCLLoader(curriculum_path)
            with pytest.raises(ValueError, match="missing 'repo' field"):
                loader.load_all_sequences()
        finally:
            curriculum_path.unlink()

    def test_sequence_no_tasks_raises_error(self):
        """Test that sequences with no tasks raise ValueError."""
        sequence_data = {
            "sequence_name": "django",
            "repo": "django/django",
            "tasks": [],
        }
        sequences_data = [sequence_data] + [
            self._create_valid_sequence_data(f"seq-{i}", f"repo{i}/repo{i}")
            for i in range(1, 8)
        ]
        curriculum_path = self._create_curriculum_file(sequences_data)

        try:
            loader = SWEBenchCLLoader(curriculum_path)
            with pytest.raises(ValueError, match="has no tasks"):
                loader.load_all_sequences()
        finally:
            curriculum_path.unlink()

    def test_invalid_json_raises_error(self):
        """Test that invalid JSON raises JSONDecodeError."""
        temp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        temp_file.write("{ invalid json }")
        temp_file.close()
        curriculum_path = Path(temp_file.name)

        try:
            loader = SWEBenchCLLoader(curriculum_path)
            with pytest.raises(json.JSONDecodeError):
                loader.load_all_sequences()
        finally:
            curriculum_path.unlink()

    def test_curriculum_not_dict_raises_error(self):
        """Test that curriculum file containing non-dict raises ValueError."""
        temp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        json.dump(["not", "a", "dict"], temp_file)
        temp_file.close()
        curriculum_path = Path(temp_file.name)

        try:
            loader = SWEBenchCLLoader(curriculum_path)
            with pytest.raises(ValueError, match="must contain a JSON object"):
                loader.load_all_sequences()
        finally:
            curriculum_path.unlink()

    def test_curriculum_missing_sequences_key_raises_error(self):
        """Test that curriculum without 'sequences' key raises ValueError."""
        temp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        json.dump({"wrong_key": []}, temp_file)
        temp_file.close()
        curriculum_path = Path(temp_file.name)

        try:
            loader = SWEBenchCLLoader(curriculum_path)
            with pytest.raises(ValueError, match="must contain a 'sequences' key"):
                loader.load_all_sequences()
        finally:
            curriculum_path.unlink()

    def test_sequences_not_list_raises_error(self):
        """Test that 'sequences' value that is not a list raises ValueError."""
        temp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        json.dump({"sequences": "not a list"}, temp_file)
        temp_file.close()
        curriculum_path = Path(temp_file.name)

        try:
            loader = SWEBenchCLLoader(curriculum_path)
            with pytest.raises(ValueError, match="'sequences' must be a list"):
                loader.load_all_sequences()
        finally:
            curriculum_path.unlink()

    def test_get_sequence_by_name(self):
        """Test retrieving a specific sequence by name."""
        sequences_data = [
            self._create_valid_sequence_data("django", "django/django")
        ] + [
            self._create_valid_sequence_data(f"seq-{i}", f"repo{i}/repo{i}")
            for i in range(1, 8)
        ]
        curriculum_path = self._create_curriculum_file(sequences_data)

        try:
            loader = SWEBenchCLLoader(curriculum_path)
            sequence = loader.get_sequence_by_name("django")

            assert sequence is not None
            assert sequence.sequence_name == "django"
            assert sequence.repo == "django/django"
        finally:
            curriculum_path.unlink()

    def test_get_sequence_by_name_not_found(self):
        """Test that get_sequence_by_name returns None for nonexistent sequence."""
        sequences_data = [
            self._create_valid_sequence_data(f"seq-{i}", f"repo{i}/repo{i}")
            for i in range(8)
        ]
        curriculum_path = self._create_curriculum_file(sequences_data)

        try:
            loader = SWEBenchCLLoader(curriculum_path)
            sequence = loader.get_sequence_by_name("nonexistent")

            assert sequence is None
        finally:
            curriculum_path.unlink()

    def test_get_sequence_names(self):
        """Test retrieving all sequence names."""
        sequences_data = [
            self._create_valid_sequence_data(f"seq-{i}", f"repo{i}/repo{i}")
            for i in range(8)
        ]
        curriculum_path = self._create_curriculum_file(sequences_data)

        try:
            loader = SWEBenchCLLoader(curriculum_path)
            names = loader.get_sequence_names()

            assert len(names) == 8
            assert names == [f"seq-{i}" for i in range(8)]
        finally:
            curriculum_path.unlink()
