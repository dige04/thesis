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

Tool call tracking is implemented for behavioral metrics (Requirement 29).
"""

import os
import subprocess
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


class AgentTools:
    """
    Collection of tools available to the coding agent.

    All tools operate within a working directory (repository checkout).
    Tool calls are tracked for behavioral metrics analysis.
    """

    def __init__(self, working_dir: str, tracker: ToolCallTracker | None = None):
        """
        Initialize agent tools.

        Args:
            working_dir: Path to the repository working directory
            tracker: Optional tool call tracker for behavioral metrics
        """
        self.working_dir = Path(working_dir)
        self.tracker = tracker or ToolCallTracker()

        # Ensure working directory exists
        if not self.working_dir.exists():
            raise ValueError(f"Working directory does not exist: {working_dir}")

    def read_file(self, path: str) -> str:
        """
        Read the contents of a file.

        Args:
            path: Relative path to the file within the working directory

        Returns:
            File contents as a string

        Raises:
            FileNotFoundError: If the file does not exist
            PermissionError: If the file cannot be read
        """
        args = {"path": path}
        file_path = self.working_dir / path

        if not file_path.exists():
            error = f"File not found: {path}"
            self.tracker.record_call("read_file", args, None, error)
            raise FileNotFoundError(error)

        if not file_path.is_file():
            error = f"Path is not a file: {path}"
            self.tracker.record_call("read_file", args, None, error)
            raise ValueError(error)

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            self.tracker.record_call("read_file", args, len(content))
            return content

        except Exception as e:
            # Only track unexpected errors (file system errors, encoding errors, etc.)
            self.tracker.record_call("read_file", args, None, str(e))
            raise

    def write_file(self, path: str, content: str) -> None:
        """
        Write content to a file, creating it if it doesn't exist.

        Args:
            path: Relative path to the file within the working directory
            content: Content to write to the file

        Raises:
            PermissionError: If the file cannot be written
        """
        args = {"path": path, "content_length": len(content)}
        try:
            file_path = self.working_dir / path

            # Create parent directories if they don't exist
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            self.tracker.record_call("write_file", args, "success")

        except Exception as e:
            self.tracker.record_call("write_file", args, None, str(e))
            raise

    def edit_file(self, path: str, diff: str) -> None:
        """
        Apply diff-style edits to a file.

        The diff format is a simplified unified diff:
        - Lines starting with '-' are removed
        - Lines starting with '+' are added
        - Lines starting with ' ' (space) are context lines

        Args:
            path: Relative path to the file within the working directory
            diff: Diff string to apply

        Raises:
            FileNotFoundError: If the file does not exist
            ValueError: If the diff cannot be applied
        """
        args = {"path": path, "diff_length": len(diff)}
        file_path = self.working_dir / path

        if not file_path.exists():
            error = f"File not found: {path}"
            self.tracker.record_call("edit_file", args, None, error)
            raise FileNotFoundError(error)

        try:
            # Read current content
            with open(file_path, encoding="utf-8") as f:
                lines = f.readlines()

            # Apply diff
            new_lines = self._apply_diff(lines, diff)

            # Write modified content
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)

            self.tracker.record_call("edit_file", args, "success")

        except Exception as e:
            self.tracker.record_call("edit_file", args, None, str(e))
            raise

    def _apply_diff(self, lines: list[str], diff: str) -> list[str]:
        """
        Apply a simplified diff to a list of lines.

        This is a basic implementation that processes the diff line by line.
        For production use, consider using a proper diff library.
        """
        diff_lines = diff.split("\n")
        result = []
        line_idx = 0

        for diff_line in diff_lines:
            if not diff_line:
                continue

            if diff_line.startswith(" "):
                # Context line - keep original
                if line_idx < len(lines):
                    result.append(lines[line_idx])
                    line_idx += 1
            elif diff_line.startswith("-"):
                # Remove line
                line_idx += 1
            elif diff_line.startswith("+"):
                # Add line
                result.append(diff_line[1:] + "\n")

        # Append remaining lines
        result.extend(lines[line_idx:])

        return result

    def search_code(self, query: str, file_pattern: str = "*") -> list[dict[str, Any]]:
        """
        Search for code patterns in the repository using grep.

        Args:
            query: Search query (regex pattern)
            file_pattern: Optional file pattern to limit search (e.g., "*.py")

        Returns:
            List of matches with file path, line number, and content
        """
        args = {"query": query, "file_pattern": file_pattern}
        try:
            # Use grep for searching
            cmd = [
                "grep",
                "-rn",  # recursive, with line numbers
                "-E",   # extended regex
                query,
                str(self.working_dir),
            ]

            if file_pattern != "*":
                cmd.extend(["--include", file_pattern])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.working_dir,
            )

            # Parse grep output
            matches = []
            for line in result.stdout.split("\n"):
                if not line:
                    continue

                parts = line.split(":", 2)
                if len(parts) >= 3:
                    file_path = parts[0]
                    line_num = parts[1]
                    content = parts[2]

                    # Make path relative to working_dir
                    rel_path = os.path.relpath(file_path, self.working_dir)

                    matches.append({
                        "file": rel_path,
                        "line": int(line_num),
                        "content": content.strip(),
                    })

            self.tracker.record_call("search_code", args, len(matches))
            return matches

        except Exception as e:
            self.tracker.record_call("search_code", args, None, str(e))
            raise

    def list_files(self, path: str = ".", pattern: str = "*") -> list[str]:
        """
        List files in a directory.

        Args:
            path: Relative path to the directory (default: current directory)
            pattern: Optional glob pattern to filter files (e.g., "*.py")

        Returns:
            List of relative file paths
        """
        args = {"path": path, "pattern": pattern}
        dir_path = self.working_dir / path

        if not dir_path.exists():
            error = f"Directory not found: {path}"
            self.tracker.record_call("list_files", args, None, error)
            raise FileNotFoundError(error)

        if not dir_path.is_dir():
            error = f"Path is not a directory: {path}"
            self.tracker.record_call("list_files", args, None, error)
            raise ValueError(error)

        try:
            # Use glob to find matching files
            files = []
            for file_path in dir_path.glob(pattern):
                if file_path.is_file():
                    rel_path = os.path.relpath(file_path, self.working_dir)
                    files.append(rel_path)

            self.tracker.record_call("list_files", args, len(files))
            return sorted(files)

        except Exception as e:
            self.tracker.record_call("list_files", args, None, str(e))
            raise

    def run_command(self, command: str, timeout: int = 60) -> dict[str, Any]:
        """
        Execute a shell command in the working directory.

        Args:
            command: Shell command to execute
            timeout: Maximum execution time in seconds (default: 60)

        Returns:
            Dictionary with stdout, stderr, return_code, and success status
        """
        args = {"command": command, "timeout": timeout}
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=self.working_dir,
                timeout=timeout,
            )

            output = {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode,
                "success": result.returncode == 0,
            }

            # Check for syntax errors in stderr
            if "SyntaxError" in result.stderr or "syntax error" in result.stderr.lower():
                self.tracker.record_syntax_error()

            self.tracker.record_call("run_command", args, output)
            return output

        except subprocess.TimeoutExpired:
            error = f"Command timed out after {timeout} seconds"
            self.tracker.record_call("run_command", args, None, error)
            return {
                "stdout": "",
                "stderr": error,
                "return_code": -1,
                "success": False,
            }
        except Exception as e:
            self.tracker.record_call("run_command", args, None, str(e))
            raise

    def run_tests(self, test_command: str, timeout: int = 300) -> dict[str, Any]:
        """
        Run test commands with extended timeout.

        This is a specialized version of run_command for test execution,
        with a longer default timeout and test-specific result parsing.

        Args:
            test_command: Test command to execute (e.g., "pytest tests/")
            timeout: Maximum execution time in seconds (default: 300)

        Returns:
            Dictionary with test results including pass/fail status
        """
        args = {"test_command": test_command, "timeout": timeout}
        try:
            result = subprocess.run(
                test_command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=self.working_dir,
                timeout=timeout,
            )

            output = {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode,
                "success": result.returncode == 0,
                "tests_passed": result.returncode == 0,
            }

            # Check for syntax errors in test output
            if "SyntaxError" in result.stderr or "syntax error" in result.stderr.lower():
                self.tracker.record_syntax_error()

            self.tracker.record_call("run_tests", args, output)
            return output

        except subprocess.TimeoutExpired:
            error = f"Tests timed out after {timeout} seconds"
            self.tracker.record_call("run_tests", args, None, error)
            return {
                "stdout": "",
                "stderr": error,
                "return_code": -1,
                "success": False,
                "tests_passed": False,
            }
        except Exception as e:
            self.tracker.record_call("run_tests", args, None, str(e))
            raise

    def get_patch(self) -> str:
        """
        Generate a git diff patch of all changes in the working directory.

        Returns:
            Git diff output as a string
        """
        args: dict[str, Any] = {}
        try:
            # Get git diff including untracked files
            result = subprocess.run(
                ["git", "diff", "HEAD"],
                capture_output=True,
                text=True,
                cwd=self.working_dir,
            )

            patch = result.stdout

            # Also include untracked files
            untracked_result = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard"],
                capture_output=True,
                text=True,
                cwd=self.working_dir,
            )

            if untracked_result.stdout:
                # Add untracked files to patch
                for file_path in untracked_result.stdout.strip().split("\n"):
                    if file_path:
                        try:
                            with open(self.working_dir / file_path, encoding="utf-8") as f:
                                content = f.read()
                            patch += f"\n--- /dev/null\n+++ b/{file_path}\n"
                            for line in content.split("\n"):
                                patch += f"+{line}\n"
                        except Exception:
                            # Skip files that can't be read
                            pass

            self.tracker.record_call("get_patch", args, len(patch))
            return patch

        except Exception as e:
            self.tracker.record_call("get_patch", args, None, str(e))
            raise

    def get_tracker_stats(self) -> dict[str, Any]:
        """
        Get tool call statistics for behavioral metrics.

        Returns:
            Dictionary with tool call counts and syntax error counts
        """
        return self.tracker.get_stats()
