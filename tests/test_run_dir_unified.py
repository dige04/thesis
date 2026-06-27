"""
Tests for unified run_dir across MemoryStore and TrajectoryLogger (Task 2c).

Verifies:
1. MemoryStore(run_dir=<path>) writes memory.db, memory.faiss, snapshots under that path.
2. TrajectoryLogger(run_dir=<path>) writes trajectories under that path (not doubled run_id).
3. Neither writes to ./runs/ when run_dir is injected.
4. MemoryStore with no run_dir still defaults to Path("runs")/run_id (back-compat).
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_memory_store(tmp_path: Path, run_id: str = "t"):
    """Construct a MemoryStore with injection, patching the OpenAI client and FAISS."""
    from src.memory.store import MemoryStore

    run_dir = tmp_path / run_id
    with (
        patch("src.memory.store.OpenAI", return_value=MagicMock()),
        patch("src.memory.store.embedding_base_url", return_value="http://localhost"),
        patch("src.memory.store.embedding_api_key", return_value="x"),
        patch("src.memory.store.faiss") as mock_faiss,
    ):
        mock_faiss.IndexFlatL2.return_value = MagicMock()
        store = MemoryStore(
            run_id=run_id,
            policy_name="no_memory",
            embedding_dim=768,
            embedding_model="nomic-embed-text-v2-moe",
            run_dir=run_dir,
        )
    return store, run_dir


def _make_memory_store_default(tmp_path: Path, run_id: str = "default_t"):
    """Construct a MemoryStore WITHOUT run_dir — back-compat path."""
    from src.memory.store import MemoryStore

    with (
        patch("src.memory.store.OpenAI", return_value=MagicMock()),
        patch("src.memory.store.embedding_base_url", return_value="http://localhost"),
        patch("src.memory.store.embedding_api_key", return_value="x"),
        patch("src.memory.store.faiss") as mock_faiss,
    ):
        mock_faiss.IndexFlatL2.return_value = MagicMock()
        store = MemoryStore(
            run_id=run_id,
            policy_name="no_memory",
            embedding_dim=768,
            embedding_model="nomic-embed-text-v2-moe",
            # NOTE: no run_dir — exercises back-compat default
        )
    return store


# ---------------------------------------------------------------------------
# Test 1: MemoryStore(run_dir=...) writes everything under the injected dir
# ---------------------------------------------------------------------------

class TestMemoryStoreRunDir:
    def test_memory_db_under_injected_run_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        store, run_dir = _make_memory_store(tmp_path)

        assert store.db_path == run_dir / "memory" / "memory.db"
        assert store.db_path.exists(), "memory.db must exist under injected run_dir"

    def test_memory_faiss_under_injected_run_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        store, run_dir = _make_memory_store(tmp_path)

        assert store.faiss_path == run_dir / "memory" / "memory.faiss"

    def test_snapshots_dir_under_injected_run_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        store, run_dir = _make_memory_store(tmp_path)

        assert store.snapshot_dir == run_dir / "memory" / "snapshots"
        assert store.snapshot_dir.exists(), "snapshots dir must exist under injected run_dir"

    def test_no_runs_dir_created_when_run_dir_injected(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _make_memory_store(tmp_path)

        # ./runs/ must NOT exist (CWD is tmp_path, so Path("runs") == tmp_path/"runs")
        assert not (tmp_path / "runs").exists(), (
            "'./runs/' must not be created when run_dir is injected"
        )

    def test_run_dir_attribute_set_to_injected_path(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        run_id = "t"
        run_dir = tmp_path / run_id
        store, _ = _make_memory_store(tmp_path, run_id)

        assert store.run_dir == run_dir


# ---------------------------------------------------------------------------
# Test 2: MemoryStore default (no run_dir) → Path("runs")/run_id (back-compat)
# ---------------------------------------------------------------------------

class TestMemoryStoreDefaultBackCompat:
    def test_default_run_dir_is_runs_over_run_id(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        run_id = "default_t"
        store = _make_memory_store_default(tmp_path, run_id)

        # back-compat: relative path "runs"/{run_id}
        assert store.run_dir == Path("runs") / run_id


# ---------------------------------------------------------------------------
# Test 3: TrajectoryLogger(run_dir=...) writes under injected path, no doubling
# ---------------------------------------------------------------------------

class TestTrajectoryLoggerRunDir:
    def test_trajectory_written_under_injected_run_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from src.logging.trajectory_logger import TrajectoryLogger

        run_id = "t"
        run_dir = tmp_path / run_id
        task_id = "django__django-99999"

        logger = TrajectoryLogger(
            run_id=run_id,
            task_id=task_id,
            policy="no_memory",
            seed=1,
            run_dir=run_dir,
        )
        logger.log_step(
            step=1,
            action="search_code",
            action_input="something",
            observation_summary="nothing found",
        )
        saved_path = logger.save()

        expected = run_dir / "trajectories" / f"{task_id}.json"
        assert saved_path == expected, (
            f"Expected trajectory at {expected}, got {saved_path}"
        )
        assert expected.exists(), "Trajectory file must exist at the expected path"

    def test_no_runs_dir_created_when_run_dir_injected(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from src.logging.trajectory_logger import TrajectoryLogger

        run_id = "t"
        run_dir = tmp_path / run_id
        task_id = "django__django-00001"

        logger = TrajectoryLogger(
            run_id=run_id,
            task_id=task_id,
            policy="no_memory",
            seed=1,
            run_dir=run_dir,
        )
        logger.save()

        assert not (tmp_path / "runs").exists(), (
            "'./runs/' must not be created when run_dir is injected"
        )

    def test_no_doubled_run_id_in_path(self, tmp_path, monkeypatch):
        """
        Regression: base_dir / run_id / run_id / trajectories must NOT exist.
        The injected run_dir is already the full per-run dir, so the logger must
        NOT append run_id again.
        """
        monkeypatch.chdir(tmp_path)
        from src.logging.trajectory_logger import TrajectoryLogger

        run_id = "t"
        run_dir = tmp_path / run_id
        task_id = "django__django-11111"

        logger = TrajectoryLogger(
            run_id=run_id,
            task_id=task_id,
            policy="no_memory",
            seed=1,
            run_dir=run_dir,
        )
        logger.save()

        # Doubled path must NOT exist
        doubled = run_dir / run_id / "trajectories" / f"{task_id}.json"
        assert not doubled.exists(), (
            f"Doubled run_id path {doubled} must not exist"
        )

    def test_back_compat_base_dir_still_works(self, tmp_path, monkeypatch):
        """TrajectoryLogger without run_dir uses base_dir/run_id/trajectories."""
        monkeypatch.chdir(tmp_path)
        from src.logging.trajectory_logger import TrajectoryLogger

        run_id = "back_t"
        task_id = "django__django-22222"

        logger = TrajectoryLogger(
            run_id=run_id,
            task_id=task_id,
            policy="no_memory",
            seed=1,
            base_dir=tmp_path / "runs",  # explicit non-default to avoid repo pollution
        )
        logger.save()

        expected = tmp_path / "runs" / run_id / "trajectories" / f"{task_id}.json"
        assert expected.exists(), "Back-compat: base_dir/run_id/trajectories path must work"
