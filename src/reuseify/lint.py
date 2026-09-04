# SPDX-FileCopyrightText: 2026 Sahil Jhawar
# SPDX-FileContributor: Sahil Jhawar
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Lint files for REUSE license compliance."""

import re
import subprocess
import sys
from typing import Annotated

import typer
from rich.console import Console
from rich.text import Text

from .policy import PolicyViolation, check_policy_violations, is_covered_file, load_policy
from .utils import (
    DEFAULT_EXCLUDE_PATTERNS,
    check_git_repo,
    get_files_to_lint,
    get_git_tracked_files,
    is_path_excluded,
)

console = Console()


app = typer.Typer()


@app.command()
def main(
    include_not_in_git: Annotated[
        bool,
        typer.Option(
            "--include-not-in-git",
            "-i",
            help="Include files with no git history in the linting.",
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
    """Lint files for REUSE license compliance."""
    check_git_repo()

    console.print("Running [bold]reuse lint[/]...")
    files, omitted_count = get_files_to_lint(include_not_in_git, exclude)

    if include_not_in_git and files:
        console.print("[yellow]Linting non-git-tracked files as well.[/]")

    filtered_lines: list[str] = []
    has_missing_license_text = False
    has_missing_headers = False

    if files:
        console.print(f"Found [bold]{len(files)}[/] file(s) with licensing issues.")

        # Run reuse lint with --lines to get errors per line
        result = subprocess.run(
            ["reuse", "lint", "--lines"],
            capture_output=True,
            text=True,
        )

        # Filter lines to only include files in the selected list
        files_set = set(files)
        for line in result.stdout.splitlines():
            if ":" in line:
                file_path = line.split(":", 1)[0]
                if file_path in files_set:
                    if "missing license" in line:
                        line += " (license text file is missing)"
                        has_missing_license_text = True
                    elif "no license identifier" in line or "no copyright notice" in line:
                        line += " (SPDX header is missing)"
                        has_missing_headers = True
                    filtered_lines.append(line)
    else:
        console.print("[green]No files with licensing issues found by reuse lint.[/]")

    policy = load_policy()
    violations: list[PolicyViolation] = []
    if policy is not None:
        all_patterns = DEFAULT_EXCLUDE_PATTERNS + tuple(exclude or [])
        tracked = [
            f
            for f in get_git_tracked_files()
            if not is_path_excluded(f, all_patterns) and is_covered_file(f)
        ]
        violations = check_policy_violations(tracked, policy)

    for line in filtered_lines:
        text = Text(line, style="red")
        match = re.search(r"'[^']+'", line)
        if match:
            text.stylize("bold", match.start(), match.end())
        console.print(text)

    if violations:
        console.print("\n[bold]Policy violations (reuseify.toml):[/]")
        for violation in violations:
            details = []
            if (
                violation.expected_license
                and violation.expected_license not in violation.actual_licenses
            ):
                actual = ", ".join(violation.actual_licenses) or "none"
                details.append(
                    f"license should be '{violation.expected_license}', found '{actual}'"
                )
            if (
                violation.expected_copyright
                and violation.expected_copyright not in violation.actual_copyright
            ):
                details.append(f"copyright '{violation.expected_copyright}' is missing")
            console.print(f"  [red]{violation.filepath}[/]: {'; '.join(details)}")

    if omitted_count > 0:
        console.print(
            f"\n[yellow]Note:[/] {omitted_count} file(s) with no git history were omitted. "
            "Use [bold]--include-not-in-git[/] / [bold]-i[/] to include them."
        )

    if has_missing_license_text:
        console.print(
            "Run [bold]reuse download --all[/] or [bold]reuseify annotate --download/-D[/] "
            "to download missing licenses."
        )
    if has_missing_headers:
        console.print(
            "Run [bold]reuseify get-authors[/] then [bold]reuseify annotate[/] "
            "to add missing SPDX headers."
        )
    if violations:
        console.print(
            "Run [bold]reuseify annotate[/] to bring files back in line with reuseify.toml."
        )

    if filtered_lines or violations:
        sys.exit(1)

    console.print("[green]All selected files are compliant with REUSE.[/]")
    sys.exit(0)


if __name__ == "__main__":
    app()
