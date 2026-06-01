"""SWE-Bench-CL dataset loader.

This module loads all 8 official SWE-Bench-CL sequences from the curriculum JSON file,
preserving chronological ordering and validating data integrity.

Frozen Decision #1 (THESIS_FINAL_v5.md §0.1):
- All 8 official sequences, no self-generated, no re-ordering
- Minimum 15 tasks per sequence
- Chronological ordering preserved within each sequence
"""

import json
from pathlib import Path
from typing import Any

from src.benchmark.models import Sequence, Task


class SWEBenchCLLoader:
    """Loader for SWE-Bench-CL curriculum data.

    Loads all 8 official sequences from the SWE-Bench-CL-Curriculum.json file,
    validates data integrity, and constructs Sequence objects with ordered tasks.
    """

    def __init__(self, curriculum_path: str | Path):
        """Initialize the loader with path to curriculum JSON file.

        Args:
            curriculum_path: Path to SWE-Bench-CL-Curriculum.json file

        Raises:
            FileNotFoundError: If curriculum file does not exist
            ValueError: If curriculum_path is empty
        """
        if not curriculum_path:
            raise ValueError("curriculum_path cannot be empty")

        self.curriculum_path = Path(curriculum_path)

        if not self.curriculum_path.exists():
            raise FileNotFoundError(
                f"Curriculum file not found: {self.curriculum_path}"
            )

    def load_all_sequences(self) -> list[Sequence]:
        """Load all 8 official SWE-Bench-CL sequences.

        Requirement 1: Load all 8 sequences without subsetting or filtering,
        preserving chronological ordering within each sequence.

        Returns:
            List of 8 Sequence objects, each containing ordered tasks

        Raises:
            ValueError: If curriculum does not contain exactly 8 sequences
            ValueError: If any sequence has fewer than 15 tasks
            json.JSONDecodeError: If curriculum file is not valid JSON
        """
        with open(self.curriculum_path, encoding="utf-8") as f:
            curriculum_data = json.load(f)

        # Validate curriculum structure
        if not isinstance(curriculum_data, dict):
            raise ValueError(
                f"Curriculum file must contain a JSON object, got {type(curriculum_data)}"
            )

        if "sequences" not in curriculum_data:
            raise ValueError(
                "Curriculum file must contain a 'sequences' key"
            )

        sequences_data = curriculum_data["sequences"]

        if not isinstance(sequences_data, list):
            raise ValueError(
                f"'sequences' must be a list, got {type(sequences_data)}"
            )

        # Frozen Decision #1: Must have exactly 8 sequences
        if len(sequences_data) != 8:
            raise ValueError(
                f"Curriculum must contain exactly 8 sequences, got {len(sequences_data)}"
            )

        sequences = []
        for seq_data in sequences_data:
            sequence = self._parse_sequence(seq_data)
            sequences.append(sequence)

        return sequences

    def _parse_sequence(self, seq_data: dict[str, Any]) -> Sequence:
        """Parse a single sequence from curriculum data.

        Args:
            seq_data: Dictionary containing sequence data

        Returns:
            Sequence object with ordered tasks

        Raises:
            ValueError: If required fields are missing or invalid
        """
        # Extract sequence metadata
        sequence_name = seq_data.get("sequence_name")
        repo = seq_data.get("repo")
        tasks_data = seq_data.get("tasks", [])

        if not sequence_name:
            raise ValueError("Sequence missing 'sequence_name' field")
        if not repo:
            raise ValueError(f"Sequence '{sequence_name}' missing 'repo' field")
        if not tasks_data:
            raise ValueError(f"Sequence '{sequence_name}' has no tasks")

        # Parse tasks
        tasks = []
        for task_data in tasks_data:
            task = self._parse_task(task_data)
            tasks.append(task)

        # Frozen Decision #1: Preserve chronological ordering.
        # Official SWE-Bench-CL data must already be ordered by sequence_index.
        # Refuse to silently reorder it; raise instead.
        sequence_indices = [task.sequence_index for task in tasks]
        if sequence_indices != sorted(sequence_indices):
            raise ValueError(
                f"Tasks in sequence '{sequence_name}' must already be ordered by "
                "sequence_index. Refusing to reorder official SWE-Bench-CL data."
            )

        # Construct Sequence object (validation happens in __post_init__)
        sequence = Sequence(
            sequence_name=sequence_name,
            repo=repo,
            tasks=tasks,
            task_count=len(tasks),
        )

        return sequence

    def _parse_task(self, task_data: dict[str, Any]) -> Task:
        """Parse a single task from curriculum data.

        Requirement 1: Extract task_id, repo, base_commit, issue_text,
        test_patch, gold_patch, created_at, sequence_index, and difficulty_label.

        Args:
            task_data: Dictionary containing task data

        Returns:
            Task object with all required fields

        Raises:
            ValueError: If required fields are missing
        """
        # Extract required fields
        task_id = task_data.get("task_id")
        repo = task_data.get("repo")
        base_commit = task_data.get("base_commit")
        issue_text = task_data.get("issue_text")
        test_patch = task_data.get("test_patch")
        gold_patch = task_data.get("gold_patch")
        created_at = task_data.get("created_at")
        sequence_index = task_data.get("sequence_index")
        difficulty_label = task_data.get("difficulty_label")

        # Validate required fields are present
        missing_fields = []
        if task_id is None:
            missing_fields.append("task_id")
        if repo is None:
            missing_fields.append("repo")
        if base_commit is None:
            missing_fields.append("base_commit")
        if issue_text is None:
            missing_fields.append("issue_text")
        if test_patch is None:
            missing_fields.append("test_patch")
        if gold_patch is None:
            missing_fields.append("gold_patch")
        if created_at is None:
            missing_fields.append("created_at")
        if sequence_index is None:
            missing_fields.append("sequence_index")
        if difficulty_label is None:
            missing_fields.append("difficulty_label")

        if missing_fields:
            raise ValueError(
                f"Task missing required fields: {', '.join(missing_fields)}"
            )

        # Type assertions for mypy
        assert isinstance(task_id, str)
        assert isinstance(repo, str)
        assert isinstance(base_commit, str)
        assert isinstance(issue_text, str)
        assert isinstance(test_patch, str)
        assert isinstance(gold_patch, str)
        assert isinstance(created_at, str)
        assert isinstance(sequence_index, int)
        assert isinstance(difficulty_label, str)

        # Construct Task object (validation happens in __post_init__)
        task = Task(
            task_id=task_id,
            repo=repo,
            base_commit=base_commit,
            issue_text=issue_text,
            test_patch=test_patch,
            gold_patch=gold_patch,
            created_at=created_at,
            sequence_index=sequence_index,
            difficulty_label=difficulty_label,
        )

        return task

    def get_sequence_by_name(self, sequence_name: str) -> Sequence | None:
        """Get a specific sequence by name.

        Args:
            sequence_name: Name of the sequence to retrieve

        Returns:
            Sequence object if found, None otherwise
        """
        sequences = self.load_all_sequences()
        for sequence in sequences:
            if sequence.sequence_name == sequence_name:
                return sequence
        return None

    def get_sequence_names(self) -> list[str]:
        """Get names of all sequences in the curriculum.

        Returns:
            List of sequence names
        """
        sequences = self.load_all_sequences()
        return [seq.sequence_name for seq in sequences]
