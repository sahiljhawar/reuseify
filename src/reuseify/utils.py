# SPDX-FileCopyrightText: 2026 Sahil Jhawar
# SPDX-FileContributor: Sahil Jhawar
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Utility functions for reuseify."""

import fnmatch
import shutil
import subprocess
import sys
from pathlib import Path

from rich.console import Console

console = Console()

DEFAULT_EXCLUDE_PATTERNS: tuple[str, ...] = (
    "__pycache__",
    ".venv",
    "venv",
    ".env",
    "env",
    ".git",
    ".vscode",
    ".idea",
    "*.egg-info",
    "*.pyc",
    "dist",
    "build",
    "node_modules",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
)


def is_path_excluded(filepath: str, patterns: tuple[str, ...]) -> bool:
    """Return True if any component of *filepath* matches any glob *pattern*.

    Parameters
    ----------
    filepath : str
        File path to check.
    patterns : Tuple[str, ...]
        Glob patterns to exclude.

    Returns
    -------
    bool
        True if the filepath matches any pattern, False otherwise.

    """
    return any(
        fnmatch.fnmatch(part, pattern) for part in Path(filepath).parts for pattern in patterns
    )


def filter_git_ignored(files: list[str]) -> list[str]:
    """Remove files that are ignored by git (.gitignore et al.).

    Parameters
    ----------
    files : List[str]
        List of file paths to filter.

    Returns
    -------
    List[str]
        List of file paths that are not ignored by git.
    """
    if not files:
        return []
    # NUL-delimited in and out: bypasses core.quotePath, so filenames with
    # unicode/special characters round-trip exactly instead of being quoted.
    result = subprocess.run(
        ["git", "check-ignore", "-z", "--stdin"],
        input="\0".join(files) + "\0",
        capture_output=True,
        text=True,
    )
    ignored = {f for f in result.stdout.split("\0") if f}
    return [f for f in files if f not in ignored]


def check_git_repo() -> None:
    """Check if the current directory is inside a git repository.
    If not, print an error message and exit.
    """
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        console.print("[bold red]Error:[/] Not in a git repository.")
        sys.exit(1)


def check_reuse() -> None:
    """Check that the `reuse` CLI is installed. If not, print an error and exit."""
    if not shutil.which("reuse"):
        console.print("[bold red]Error:[/] 'reuse' command not found. Please install it:")
        console.print("  pip install reuse")
        sys.exit(1)


def get_missing_license_files() -> list[str]:
    """Get files in which licenses are missing

    Returns
    -------
    List[str]
        List of files with missing licenses as reported by reuse lint. This include files that
        are excluded by git or by patterns, so further filtering may be needed.
    """
    result = subprocess.run(
        ["reuse", "lint"],
        capture_output=True,
        text=True,
    )
    # `reuse lint` returns 0 (compliant) or 1 (violations found) on a normal
    # run; anything else means the tool itself failed. Never silently treat
    # that as "no issues found" — a pre-commit hook must not fail open.
    if result.returncode not in (0, 1):
        console.print(
            f"[bold red]Error:[/] 'reuse lint' failed unexpectedly (exit code {result.returncode})."
        )
        if result.stderr.strip():
            console.print(f"[red]{result.stderr.strip()}[/]")
        sys.exit(2)
    files: list[str] = []
    for line in (result.stdout + result.stderr).splitlines():
        if line.strip().startswith("# SUMMARY"):
            break
        stripped = line.strip()
        if stripped.startswith("* "):
            files.append(stripped[2:])
    return files


def get_git_tracked_files() -> list[str]:
    """Get List of files tracked by git.

    Returns
    -------
    List[str]
        List of file paths tracked by git.
    """
    # -z: NUL-delimited, bypasses core.quotePath so unicode/special-character
    # filenames come back exactly as reuse itself would print them.
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [f for f in result.stdout.split("\0") if f]


def get_files_to_lint(include_not_in_git: bool, exclude: list[str] | None) -> tuple[list[str], int]:
    """Get files to lint based on options, and count of omitted untracked files.

    Parameters
    ----------
    include_not_in_git : bool
        Whether to include files with no git history in the List of files to lint. If False
        (default), such files will be omitted and counted in the returned omitted_count.
    exclude : List[str] | None
        Additional glob patterns to exclude (matched against each path component). Default
        patterns are always applied.

    Returns
    -------
    Tuple[List[str], int]
        A tuple containing:
        - List of file paths to lint (with missing licenses, not excluded by patterns, and
            if `include_not_in_git` is False, only those that are tracked by git).
        - Count of files that were omitted because they have no git history (only relevant
            if `include_not_in_git` is False).

    """
    missing = get_missing_license_files()
    all_patterns = DEFAULT_EXCLUDE_PATTERNS + tuple(exclude or [])
    missing = [f for f in missing if not is_path_excluded(f, all_patterns)]
    if not include_not_in_git:
        tracked = get_git_tracked_files()
        tracked_set = set(tracked)
        omitted = [f for f in missing if f not in tracked_set]
        omitted_count = len(omitted)
        missing = [f for f in missing if f in tracked_set]
    else:
        omitted_count = 0
    return missing, omitted_count
