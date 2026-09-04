# SPDX-FileCopyrightText: 2026 Sahil Jhawar
# SPDX-FileContributor: Sahil Jhawar
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Get authors for files with missing REUSE licenses and save to a JSON file."""

import json
import subprocess
import sys
from typing import Annotated

import typer
from rich.console import Console

from .utils import (
    DEFAULT_EXCLUDE_PATTERNS,
    check_git_repo,
    filter_git_ignored,
    get_missing_license_files,
    is_path_excluded,
)

console = Console()


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
        console.print(f"[dim]Excluded {excluded_count} file(s) via path patterns / .gitignore.[/]")
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
