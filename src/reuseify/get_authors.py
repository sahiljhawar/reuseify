# SPDX-FileCopyrightText: 2026 Sahil Jhawar
# SPDX-FileContributor: Sahil Jhawar
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Get authors for files with missing REUSE licenses and save to a JSON file."""

import fnmatch
import json
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer
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
    """Return True if any component of *filepath* matches any glob *pattern*."""
    return any(
        fnmatch.fnmatch(part, pattern)
        for part in Path(filepath).parts
        for pattern in patterns
    )


def filter_git_ignored(files: list[str]) -> list[str]:
    """Remove files that are ignored by git (.gitignore et al.)."""
    if not files:
        return []
    result = subprocess.run(
        ["git", "check-ignore", "--stdin"],
        input="\n".join(files),
        capture_output=True,
        text=True,
    )
    ignored = set(result.stdout.splitlines())
    return [f for f in files if f not in ignored]


def check_git_repo() -> None:
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        console.print("[bold red]Error:[/] Not in a git repository.")
        sys.exit(1)


def get_missing_license_files() -> list[str]:
    result = subprocess.run(
        ["reuse", "lint"],
        capture_output=True,
        text=True,
    )
    files: list[str] = []
    for line in (result.stdout + result.stderr).splitlines():
        if line.strip().startswith("# SUMMARY"):
            break
        stripped = line.strip()
        if stripped.startswith("* "):
            files.append(stripped[2:])
    return files


def get_git_authors(filepath: str) -> list[str]:
    result = subprocess.run(
        ["git", "log", "--format=%an", "--", filepath],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []
    return sorted(set(result.stdout.strip().splitlines()))


app = typer.Typer()


@app.command()
def main(
    output: Annotated[
        str,
        typer.Option("--output", "-o", help="Output JSON file.", show_default=True),
    ] = "reuse_annotate_authors.json",
    include_not_in_git: Annotated[
        bool,
        typer.Option(
            "--include-not-in-git",
            "-i",
            help="Include files with no git history in the JSON output (empty author list).",
        ),
    ] = False,
    exclude: Annotated[
        list[str] | None,
        typer.Option(
            "--exclude",
            "-e",
            help=(
                "Glob pattern to exclude (matched against each path component). "
                "Can be repeated. Default patterns always apply: "
                + ", ".join(DEFAULT_EXCLUDE_PATTERNS)
            ),
        ),
    ] = None,
) -> None:
    """Get git authors for files missing REUSE license headers."""
    _exclude: tuple[str, ...] = tuple(exclude or [])
    check_git_repo()

    console.print("Running [bold]reuse lint[/]...")
    files = get_missing_license_files()

    if not files:
        console.print("[green]No files with licensing issues found by reuse lint.[/]")
        sys.exit(0)

    console.print(f"Found [bold]{len(files)}[/] file(s) with licensing issues.")

    all_patterns = DEFAULT_EXCLUDE_PATTERNS + _exclude
    before = len(files)
    files = [f for f in files if not is_path_excluded(f, all_patterns)]
    files = filter_git_ignored(files)
    excluded_count = before - len(files)
    if excluded_count:
        console.print(
            f"[dim]Excluded {excluded_count} file(s) via path patterns / .gitignore.[/]"
        )
    if not files:
        console.print("[green]All remaining files were excluded.[/]")
        sys.exit(0)

    console.print("Fetching git authors...\n")

    authors_map: dict[str, list[str]] = {}
    not_in_git: list[str] = []
    for filepath in files:
        authors = get_git_authors(filepath)
        if not authors:
            not_in_git.append(filepath)
            if include_not_in_git:
                authors_map[filepath] = []
                console.print(f"  [yellow]{filepath}[/]: NOT_IN_GIT (included)")
            else:
                console.print(f"  [dim]{filepath}[/]: NOT_IN_GIT (omitted)")
        else:
            authors_map[filepath] = authors
            console.print(f"  [cyan]{filepath}[/]: {', '.join(authors)}")

    if not_in_git and not include_not_in_git:
        console.print(
            f"\n[yellow]Note:[/] {len(not_in_git)} file(s) with no git history were omitted. "
            "Use [bold]--include-not-in-git[/] / [bold]-i[/] to include them."
        )

    with open(output, "w") as f:
        json.dump(authors_map, f, indent=2)

    console.print(f"\n[green]JSON written to:[/] {output}")
    console.print(f"Total entries:  {len(authors_map)}")


if __name__ == "__main__":
    app()
