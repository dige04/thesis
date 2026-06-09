"""
Agent tools for coding task execution.

This module provides all tools available to the coding agent:
- read_file: Read file contents
- write_file: Write content to a file
- edit_file: Apply diff-style edits to a file
- search_code: Search for code patterns in the repository
- list_files: List files in a directory
- run_command: Execute shell commands
- run_tests: Run test commands
- get_patch: Generate a git diff patch

Execution backend seam (Phase 4.8, decisions A+G)
-------------------------------------------------
``AgentTools`` keeps the tracker, validation, and diff-application logic and
delegates the raw I/O + command execution to an ``ExecutionBackend``:

- ``LocalBackend``     — subprocess + filesystem against a checked-out working
  directory (the original behavior; the default; used by unit tests).
- ``ContainerBackend`` — ``docker exec`` / ``docker cp`` against one live
  per-task container started from the swebench **arm64 instance image** (deps
  installed). Only the tool *effects* relocate into the container; the ReAct
  loop, LimitTracker, trajectory logging, and the Ollama LLM path are unchanged.

Tool call tracking is implemented for behavioral metrics (Requirement 29).
"""

import os
import shlex
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ToolCallTracker:
    """
    Tracks tool calls for behavioral metrics analysis.

    Requirement 29: Count tool calls per task for each policy to test
    whether memory accumulation induces analysis paralysis.
    """

    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    syntax_errors: int = 0

    def record_call(self, tool_name: str, args: dict[str, Any], result: Any, error: str | None = None) -> None:
        """Record a tool call with its arguments, result, and any errors."""
        self.tool_calls.append({
            "tool_name": tool_name,
            "args": args,
            "success": error is None,
            "error": error,
        })

    def record_syntax_error(self) -> None:
        """Record a syntax error occurrence."""
        self.syntax_errors += 1

    def get_stats(self) -> dict[str, Any]:
        """Get tool call statistics for logging."""
        return {
            "total_tool_calls": len(self.tool_calls),
            "syntax_errors": self.syntax_errors,
            "tool_call_breakdown": self._get_tool_breakdown(),
        }

    def _get_tool_breakdown(self) -> dict[str, int]:
        """Get count of calls per tool type."""
        breakdown: dict[str, int] = {}
        for call in self.tool_calls:
            tool_name = call["tool_name"]
            breakdown[tool_name] = breakdown.get(tool_name, 0) + 1
        return breakdown


# ─────────────────────────────────────────────────────────────────────────────
# Execution backends
# ─────────────────────────────────────────────────────────────────────────────


class ExecutionBackend(ABC):
    """Raw I/O + command execution against a repository checkout.

    All paths are RELATIVE to the repository root. Implementations relocate
    *where* the effects happen (host filesystem vs. inside a Docker container)
    without changing the agent's tool semantics.
    """

    @abstractmethod
    def exists(self, rel_path: str) -> bool: ...

    @abstractmethod
    def is_file(self, rel_path: str) -> bool: ...

    @abstractmethod
    def is_dir(self, rel_path: str) -> bool: ...

    @abstractmethod
    def read_text(self, rel_path: str) -> str: ...

    @abstractmethod
    def write_text(self, rel_path: str, content: str) -> None: ...

    @abstractmethod
    def list_files(self, rel_dir: str, pattern: str) -> list[str]:
        """Return sorted repo-relative paths of files in rel_dir matching pattern
        (non-recursive, like ``Path.glob(pattern)``)."""

    @abstractmethod
    def run(self, command: str, timeout: int) -> dict[str, Any]:
        """Run a shell command at the repo root.

        Returns {stdout, stderr, return_code}. Raises subprocess.TimeoutExpired
        on timeout (the caller maps it to a failure dict)."""

    @abstractmethod
    def search_code(self, query: str, file_pattern: str) -> list[dict[str, Any]]:
        """grep -rn -E <query> for repo-relative matches [{file, line, content}]."""

    @abstractmethod
    def git_diff(self) -> str:
        """Unified diff of all changes vs HEAD, including untracked files."""


class LocalBackend(ExecutionBackend):
    """Host filesystem + subprocess backend (original behavior; unit-test default)."""

    def __init__(self, working_dir: str | Path):
        self.working_dir = Path(working_dir)
        if not self.working_dir.exists():
            raise ValueError(f"Working directory does not exist: {working_dir}")

    def _p(self, rel_path: str) -> Path:
        return self.working_dir / rel_path

    def exists(self, rel_path: str) -> bool:
        return self._p(rel_path).exists()

    def is_file(self, rel_path: str) -> bool:
        return self._p(rel_path).is_file()

    def is_dir(self, rel_path: str) -> bool:
        return self._p(rel_path).is_dir()

    def read_text(self, rel_path: str) -> str:
        with open(self._p(rel_path), encoding="utf-8") as f:
            return f.read()

    def write_text(self, rel_path: str, content: str) -> None:
        file_path = self._p(rel_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    def list_files(self, rel_dir: str, pattern: str) -> list[str]:
        dir_path = self._p(rel_dir)
        files = []
        for file_path in dir_path.glob(pattern):
            if file_path.is_file():
                files.append(os.path.relpath(file_path, self.working_dir))
        return sorted(files)

    def run(self, command: str, timeout: int) -> dict[str, Any]:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=self.working_dir,
            timeout=timeout,
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode,
        }

    def search_code(self, query: str, file_pattern: str) -> list[dict[str, Any]]:
        cmd = ["grep", "-rn", "-E", query, str(self.working_dir)]
        if file_pattern != "*":
            cmd.extend(["--include", file_pattern])
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.working_dir)
        matches = []
        for line in result.stdout.split("\n"):
            if not line:
                continue
            parts = line.split(":", 2)
            if len(parts) >= 3:
                rel_path = os.path.relpath(parts[0], self.working_dir)
                matches.append({
                    "file": rel_path,
                    "line": int(parts[1]),
                    "content": parts[2].strip(),
                })
        return matches

    def git_diff(self) -> str:
        # Stage everything (incl. new files) then `git diff --cached HEAD` so the
        # patch carries proper `diff --git`/`new file`/`@@` headers that
        # swebench's `git apply` accepts. The previous hand-built untracked diff
        # lacked hunk headers and was rejected, silently dropping new files from
        # the evaluated patch. The checkout is throwaway, so staging is safe.
        subprocess.run(["git", "add", "-A"], capture_output=True, text=True, cwd=self.working_dir)
        result = subprocess.run(
            ["git", "diff", "--cached", "HEAD"],
            capture_output=True, text=True, cwd=self.working_dir,
        )
        return result.stdout


class ContainerBackend(ExecutionBackend):
    """``docker exec``/``docker cp`` backend against one live per-task container.

    The container is started elsewhere (the per-task lifecycle, shared with the
    eval harness — decision A) from the swebench arm64 instance image, which has
    the repo checked out at ``repo_dir`` (default ``/testbed``) with deps
    installed. This backend only *acts inside* it.

    NOTE: requires a running Docker daemon + the instance container; it cannot be
    exercised by the host-only unit tests beyond command-construction checks.
    """

    def __init__(self, container_id: str, repo_dir: str = "/testbed", docker_bin: str = "docker"):
        self.container_id = container_id
        self.repo_dir = repo_dir.rstrip("/")
        self.docker_bin = docker_bin

    # -- docker plumbing -----------------------------------------------------
    def _abs(self, rel_path: str) -> str:
        # Accept BOTH repo-relative paths and absolute container paths. The agent
        # frequently references absolute paths (e.g. "/testbed/sympy/core/basic.py")
        # because run_command output shows them; blindly prefixing repo_dir would
        # produce "/testbed//testbed/..." and break edit/read (empty-patch bug).
        if rel_path in (".", ""):
            return self.repo_dir
        if rel_path.startswith("/"):
            return rel_path.rstrip("/")
        return f"{self.repo_dir}/{rel_path}".rstrip("/")

    def _exec(self, shell_cmd: str, timeout: int | None = None, stdin: str | None = None) -> subprocess.CompletedProcess:
        """Run ``sh -c shell_cmd`` inside the container at repo_dir."""
        argv = [self.docker_bin, "exec", "-i", self.container_id, "sh", "-c",
                f"cd {shlex.quote(self.repo_dir)} && {shell_cmd}"]
        return subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout,
            input=stdin if stdin is not None else None,
        )

    def exists(self, rel_path: str) -> bool:
        return self._exec(f"test -e {shlex.quote(self._abs(rel_path))}").returncode == 0

    def is_file(self, rel_path: str) -> bool:
        return self._exec(f"test -f {shlex.quote(self._abs(rel_path))}").returncode == 0

    def is_dir(self, rel_path: str) -> bool:
        return self._exec(f"test -d {shlex.quote(self._abs(rel_path))}").returncode == 0

    def read_text(self, rel_path: str) -> str:
        proc = self._exec(f"cat {shlex.quote(self._abs(rel_path))}")
        if proc.returncode != 0:
            raise FileNotFoundError(f"File not found in container: {rel_path}")
        return proc.stdout

    def write_text(self, rel_path: str, content: str) -> None:
        abs = self._abs(rel_path)
        proc = self._exec(
            f"mkdir -p \"$(dirname {shlex.quote(abs)})\" && cat > {shlex.quote(abs)}",
            stdin=content,
        )
        if proc.returncode != 0:
            raise OSError(f"write_text failed in container: {proc.stderr}")

    def list_files(self, rel_dir: str, pattern: str) -> list[str]:
        # Non-recursive (maxdepth 1), like Path.glob(pattern). Paths are made
        # repo-relative to match LocalBackend output.
        abs_dir = self._abs(rel_dir)
        proc = self._exec(
            f"find {shlex.quote(abs_dir)} -maxdepth 1 -type f -name {shlex.quote(pattern)}"
        )
        files = []
        for line in proc.stdout.split("\n"):
            line = line.strip()
            if not line:
                continue
            rel = os.path.relpath(line, self.repo_dir)
            files.append(rel)
        return sorted(files)

    def run(self, command: str, timeout: int) -> dict[str, Any]:
        proc = self._exec(command, timeout=timeout)
        return {"stdout": proc.stdout, "stderr": proc.stderr, "return_code": proc.returncode}

    def search_code(self, query: str, file_pattern: str) -> list[dict[str, Any]]:
        include = f" --include {shlex.quote(file_pattern)}" if file_pattern != "*" else ""
        proc = self._exec(f"grep -rn -E {shlex.quote(query)}{include} .")
        matches = []
        for line in proc.stdout.split("\n"):
            if not line:
                continue
            parts = line.split(":", 2)
            if len(parts) >= 3:
                matches.append({
                    "file": parts[0].lstrip("./"),
                    "line": int(parts[1]),
                    "content": parts[2].strip(),
                })
        return matches

    def git_diff(self) -> str:
        # Same approach as LocalBackend: stage all, then diff --cached for a
        # valid, git-apply-able patch that includes new files with proper headers.
        self._exec("git add -A")
        return self._exec("git diff --cached HEAD").stdout


class ContainerSession:
    """Lifecycle for one per-task swebench instance container (decision A).

    Starts a detached container from the arm64 instance image (repo checked out
    at ``repo_dir`` with deps installed), keeps it alive (``sleep infinity``),
    hands a ``ContainerBackend`` to AgentTools, and removes it on ``stop()``.

    The local-build image name follows the swebench convention
    ``sweb.eval.{arch}.{instance_id.lower()}:{tag}`` (built by the Phase 5.0
    build-probe with ``--namespace ""``). Requires a Docker daemon + the image.
    """

    def __init__(self, image: str, repo_dir: str = "/testbed", docker_bin: str = "docker"):
        self.image = image
        self.repo_dir = repo_dir
        self.docker_bin = docker_bin
        self.container_id: str | None = None

    @staticmethod
    def image_for(
        instance_id: str,
        arch: str = "x86_64",
        tag: str = "latest",
        namespace: str | None = None,
    ) -> str:
        """Instance-image name matching swebench's ``TestSpec.instance_image_key``.

        Local build (``namespace`` falsy): ``sweb.eval.{arch}.{id.lower()}:{tag}``.
        Pulled (``namespace`` set, e.g. ``"swebench"``): the name is namespaced
        AND ``__`` is rewritten to ``_1776_`` — exactly as swebench encodes the
        published Docker Hub tag (test_spec.py:107-110). Must match so the agent
        runs the same image the eval harness pulls.
        """
        key = f"sweb.eval.{arch}.{instance_id.lower()}:{tag}"
        if namespace:
            key = f"{namespace}/{key}".replace("__", "_1776_")
        return key

    def start(self) -> str:
        proc = subprocess.run(
            [self.docker_bin, "run", "-d", "--rm", self.image, "sleep", "infinity"],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"Failed to start container from {self.image}: {proc.stderr.strip()}")
        self.container_id = proc.stdout.strip()
        return self.container_id

    def backend(self) -> "ContainerBackend":
        if self.container_id is None:
            raise RuntimeError("ContainerSession not started")
        return ContainerBackend(self.container_id, self.repo_dir, self.docker_bin)

    def stop(self) -> None:
        if self.container_id:
            subprocess.run(
                [self.docker_bin, "rm", "-f", self.container_id],
                capture_output=True, text=True,
            )
            self.container_id = None

    def __enter__(self) -> "ContainerSession":
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()


class AgentTools:
    """
    Collection of tools available to the coding agent.

    Tool semantics are backend-agnostic: validation, tracking, and diff
    application live here, while raw I/O + command execution are delegated to an
    ``ExecutionBackend``. Pass ``working_dir`` for the default ``LocalBackend``,
    or an explicit ``backend`` (e.g. ``ContainerBackend``) for in-container runs.
    """

    def __init__(
        self,
        working_dir: str | None = None,
        tracker: ToolCallTracker | None = None,
        backend: ExecutionBackend | None = None,
    ):
        """
        Initialize agent tools.

        Args:
            working_dir: Repository working directory (used to build a default
                LocalBackend when ``backend`` is not provided).
            tracker: Optional tool call tracker for behavioral metrics.
            backend: Optional explicit execution backend (overrides working_dir).
        """
        if backend is None:
            if working_dir is None:
                raise ValueError("AgentTools requires either working_dir or backend")
            backend = LocalBackend(working_dir)
        self.backend = backend
        # Preserve the original attribute for callers/tests that read it.
        self.working_dir = getattr(backend, "working_dir", None)
        self.tracker = tracker or ToolCallTracker()

    def read_file(self, path: str) -> str:
        """Read the contents of a file (relative to the repo root)."""
        args = {"path": path}

        if not self.backend.exists(path):
            error = f"File not found: {path}"
            self.tracker.record_call("read_file", args, None, error)
            raise FileNotFoundError(error)

        if not self.backend.is_file(path):
            error = f"Path is not a file: {path}"
            self.tracker.record_call("read_file", args, None, error)
            raise ValueError(error)

        try:
            content = self.backend.read_text(path)
            self.tracker.record_call("read_file", args, len(content))
            return content
        except Exception as e:
            self.tracker.record_call("read_file", args, None, str(e))
            raise

    def write_file(self, path: str, content: str) -> None:
        """Write content to a file, creating parents if needed."""
        args = {"path": path, "content_length": len(content)}
        try:
            self.backend.write_text(path, content)
            self.tracker.record_call("write_file", args, "success")
        except Exception as e:
            self.tracker.record_call("write_file", args, None, str(e))
            raise

    def edit_file(self, path: str, diff: str) -> None:
        """Apply simplified diff-style edits to a file."""
        args = {"path": path, "diff_length": len(diff)}

        if not self.backend.exists(path):
            error = f"File not found: {path}"
            self.tracker.record_call("edit_file", args, None, error)
            raise FileNotFoundError(error)

        try:
            lines = self.backend.read_text(path).splitlines(keepends=True)
            new_lines = self._apply_diff(lines, diff)
            self.backend.write_text(path, "".join(new_lines))
            self.tracker.record_call("edit_file", args, "success")
        except Exception as e:
            self.tracker.record_call("edit_file", args, None, str(e))
            raise

    def _apply_diff(self, lines: list[str], diff: str) -> list[str]:
        """
        Apply a simplified diff to a list of lines.

        - Lines starting with ' ' are context (kept).
        - Lines starting with '-' are removed.
        - Lines starting with '+' are added.
        """
        diff_lines = diff.split("\n")
        result = []
        line_idx = 0

        for diff_line in diff_lines:
            if not diff_line:
                continue
            if diff_line.startswith(" "):
                if line_idx < len(lines):
                    result.append(lines[line_idx])
                    line_idx += 1
            elif diff_line.startswith("-"):
                line_idx += 1
            elif diff_line.startswith("+"):
                result.append(diff_line[1:] + "\n")

        result.extend(lines[line_idx:])
        return result

    def search_code(self, query: str, file_pattern: str = "*") -> list[dict[str, Any]]:
        """Search for code patterns in the repository using grep."""
        args = {"query": query, "file_pattern": file_pattern}
        try:
            matches = self.backend.search_code(query, file_pattern)
            self.tracker.record_call("search_code", args, len(matches))
            return matches
        except Exception as e:
            self.tracker.record_call("search_code", args, None, str(e))
            raise

    def list_files(self, path: str = ".", pattern: str = "*") -> list[str]:
        """List files in a directory (non-recursive glob)."""
        args = {"path": path, "pattern": pattern}

        if not self.backend.exists(path):
            error = f"Directory not found: {path}"
            self.tracker.record_call("list_files", args, None, error)
            raise FileNotFoundError(error)

        if not self.backend.is_dir(path):
            error = f"Path is not a directory: {path}"
            self.tracker.record_call("list_files", args, None, error)
            raise ValueError(error)

        try:
            files = self.backend.list_files(path, pattern)
            self.tracker.record_call("list_files", args, len(files))
            return files
        except Exception as e:
            self.tracker.record_call("list_files", args, None, str(e))
            raise

    def run_command(self, command: str, timeout: int = 60) -> dict[str, Any]:
        """Execute a shell command at the repo root."""
        args = {"command": command, "timeout": timeout}
        try:
            output = self.backend.run(command, timeout)
            output["success"] = output["return_code"] == 0

            if "SyntaxError" in output["stderr"] or "syntax error" in output["stderr"].lower():
                self.tracker.record_syntax_error()

            self.tracker.record_call("run_command", args, output)
            return output

        except subprocess.TimeoutExpired:
            error = f"Command timed out after {timeout} seconds"
            self.tracker.record_call("run_command", args, None, error)
            return {"stdout": "", "stderr": error, "return_code": -1, "success": False}
        except Exception as e:
            self.tracker.record_call("run_command", args, None, str(e))
            raise

    def run_tests(self, test_command: str, timeout: int = 300) -> dict[str, Any]:
        """Run a test command (longer default timeout, tests_passed flag)."""
        args = {"test_command": test_command, "timeout": timeout}
        try:
            output = self.backend.run(test_command, timeout)
            output["success"] = output["return_code"] == 0
            output["tests_passed"] = output["return_code"] == 0

            if "SyntaxError" in output["stderr"] or "syntax error" in output["stderr"].lower():
                self.tracker.record_syntax_error()

            self.tracker.record_call("run_tests", args, output)
            return output

        except subprocess.TimeoutExpired:
            error = f"Tests timed out after {timeout} seconds"
            self.tracker.record_call("run_tests", args, None, error)
            return {
                "stdout": "", "stderr": error, "return_code": -1,
                "success": False, "tests_passed": False,
            }
        except Exception as e:
            self.tracker.record_call("run_tests", args, None, str(e))
            raise

    def get_patch(self) -> str:
        """Generate a git diff patch of all changes (incl. untracked files)."""
        args: dict[str, Any] = {}
        try:
            patch = self.backend.git_diff()
            self.tracker.record_call("get_patch", args, len(patch))
            return patch
        except Exception as e:
            self.tracker.record_call("get_patch", args, None, str(e))
            raise

    def get_tracker_stats(self) -> dict[str, Any]:
        """Get tool call statistics for behavioral metrics."""
        return self.tracker.get_stats()
