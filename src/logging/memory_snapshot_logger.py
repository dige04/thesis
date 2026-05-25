"""Memory snapshot logging for task boundary analysis.

This module implements memory snapshot logging that captures the complete
memory state at every task boundary (before and after). Snapshots enable
post-hoc analysis of memory evolution without re-running experiments.

Frozen Invariants (THESIS_FINAL_v5.md §11.4, §25):
- Generate before_task_n.json and after_task_n.json at EVERY task boundary
- Include: step, boundary, active_records (memory_id, importance_score, memory_type, age)
- Store in: runs/{run_id}/memory/snapshots/
- JSON format (pretty-printed for readability)
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from ..memory.record import MemoryRecord

logger = logging.getLogger(__name__)


class MemorySnapshotLogger:
    """Logger for memory state snapshots at task boundaries.

    This class captures the complete memory state before and after each task,
    enabling analysis of memory evolution, pruning decisions, and policy behavior
    over time.

    Attributes:
        snapshot_dir: Directory where snapshot JSON files are stored
        run_id: Unique identifier for the experimental run
        policy_name: Name of the memory policy being used
    """

    def __init__(self, snapshot_dir: Path, run_id: str, policy_name: str):
        """Initialize memory snapshot logger.

        Args:
            snapshot_dir: Directory for storing snapshot files
            run_id: Unique identifier for this experimental run
            policy_name: Name of the memory policy (one of 6)

        Notes:
            - Creates snapshot directory if it doesn't exist
            - Snapshots are stored as: {snapshot_dir}/{boundary}_{step}.json
        """
        self.snapshot_dir = Path(snapshot_dir)
        self.run_id = run_id
        self.policy_name = policy_name

        # Create snapshot directory
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

    def log_snapshot(
        self,
        step: int,
        boundary: str,
        active_records: list[MemoryRecord],
        archived_this_step: list[str] | None = None,
        current_step: int | None = None
    ) -> dict[str, Any]:
        """Generate and save memory snapshot at task boundary.

        This method captures the complete memory state including:
        - All active memory records with their metadata
        - Records archived at this step
        - Policy and timing information

        Args:
            step: Task sequence index (position in sequence)
            boundary: Boundary type ("before_task" or "after_task")
            active_records: List of active MemoryRecord instances
            archived_this_step: Optional list of memory_ids archived at this step
            current_step: Optional current step for age calculation (defaults to step)

        Returns:
            Dictionary containing the snapshot data (also saved to file)

        Notes:
            - Saves to: {snapshot_dir}/{boundary}_{step}.json
            - JSON is pretty-printed with indent=2 for readability
            - Age is calculated as: current_step - record.sequence_index
            - Includes importance_score for Type-Aware Decay analysis
        """
        if current_step is None:
            current_step = step

        # Build active records list with required fields
        active_records_data = []
        for record in active_records:
            # Calculate age (tasks since creation)
            age = max(0, current_step - record.sequence_index)

            active_records_data.append({
                "memory_id": record.memory_id,
                "importance_score": record.importance_score,
                "memory_type": record.memory_type,
                "age": age
            })

        # Build snapshot dictionary
        snapshot_data = {
            "step": step,
            "boundary": boundary,
            "active_records": active_records_data,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Add archived records if provided
        if archived_this_step is not None:
            snapshot_data["archived_this_step"] = archived_this_step

        # Add metadata
        snapshot_data["metadata"] = {
            "run_id": self.run_id,
            "policy_name": self.policy_name,
            "active_count": len(active_records),
            "archived_count": len(archived_this_step) if archived_this_step else 0
        }

        # Write to snapshot file
        snapshot_file = self.snapshot_dir / f"{boundary}_{step}.json"
        with open(snapshot_file, "w") as f:
            json.dump(snapshot_data, f, indent=2)

        logger.info(
            f"Saved memory snapshot: {snapshot_file.name} "
            f"(active={len(active_records)}, "
            f"archived={len(archived_this_step) if archived_this_step else 0})"
        )

        return snapshot_data

    def load_snapshot(self, step: int, boundary: str) -> dict[str, Any]:
        """Load a previously saved snapshot.

        Args:
            step: Task sequence index
            boundary: Boundary type ("before_task" or "after_task")

        Returns:
            Dictionary containing the snapshot data

        Raises:
            FileNotFoundError: If snapshot file doesn't exist

        Notes:
            - Used for post-hoc analysis and re-evaluation
            - Enables computing a_{i,j} matrix without re-running
        """
        snapshot_file = self.snapshot_dir / f"{boundary}_{step}.json"

        if not snapshot_file.exists():
            raise FileNotFoundError(
                f"Snapshot not found: {snapshot_file}"
            )

        with open(snapshot_file) as f:
            data: dict[str, Any] = json.load(f)
            return data

    def list_snapshots(self) -> list[tuple[int, str]]:
        """List all available snapshots.

        Returns:
            List of (step, boundary) tuples for all saved snapshots

        Notes:
            - Sorted by step, then boundary
            - Useful for verifying complete snapshot coverage
        """
        snapshots = []

        for snapshot_file in self.snapshot_dir.glob("*.json"):
            # Parse filename: {boundary}_{step}.json
            name = snapshot_file.stem
            parts = name.rsplit("_", 1)

            if len(parts) == 2:
                boundary = parts[0]
                try:
                    step = int(parts[1])
                    snapshots.append((step, boundary))
                except ValueError:
                    # Skip files that don't match expected format
                    continue

        # Sort by step, then boundary
        snapshots.sort(key=lambda x: (x[0], x[1]))

        return snapshots

    def verify_complete_coverage(
        self,
        num_tasks: int,
        expected_boundaries: list[str] | None = None
    ) -> tuple[bool, list[str]]:
        """Verify that snapshots exist for all task boundaries.

        Args:
            num_tasks: Total number of tasks in the sequence
            expected_boundaries: List of expected boundary types
                               (defaults to ["before_task", "after_task"])

        Returns:
            Tuple of (is_complete, missing_snapshots)
            - is_complete: True if all expected snapshots exist
            - missing_snapshots: List of missing snapshot identifiers

        Notes:
            - Used for validation after sequence execution
            - Ensures no snapshots were skipped
        """
        if expected_boundaries is None:
            expected_boundaries = ["before_task", "after_task"]

        existing = set(self.list_snapshots())
        missing = []

        for step in range(num_tasks):
            for boundary in expected_boundaries:
                if (step, boundary) not in existing:
                    missing.append(f"{boundary}_{step}")

        is_complete = len(missing) == 0

        if not is_complete:
            logger.warning(
                f"Incomplete snapshot coverage: {len(missing)} missing snapshots"
            )

        return is_complete, missing
