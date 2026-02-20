"""Apply REUSE license headers to files using authors from a JSON file.

All flags not consumed by this script are forwarded verbatim to
`reuse annotate` (e.g. --copyright, --license, --year, --style,
--fallback-dot-license, --force-dot-license, --skip-unrecognised, ...).
The --contributor flags are populated automatically from the JSON file
produced by get_authors.py.
"""

import json
import os
import shutil
import subprocess
import sys
from typing import Annotated

import typer
from rich.console import Console

console = Console()


def check_reuse() -> None:
    if not shutil.which("reuse"):
        console.print(
            "[bold red]Error:[/] 'reuse' command not found. Please install it:"
        )
        console.print("  pip install reuse")
        sys.exit(1)


app = typer.Typer()


@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
def main(
    ctx: typer.Context,
    input_file: Annotated[
        str,
        typer.Option(
            "--input",
            "-i",
            help="JSON file produced by get-authors.",
            show_default=True,
        ),
    ] = "reuse_annotate_authors.json",
    default_contributor: Annotated[
        list[str] | None,
        typer.Option(
            "--default-contributor",
            "-d",
            help=(
                "Fallback contributor name(s) for files with no git history (NOT_IN_GIT). "
                "Can be repeated for multiple names. Without this flag those files are skipped."
            ),
        ),
    ] = None,
) -> None:
    """
    Apply REUSE license headers using authors from a JSON file.

    Any additional flags (not part of reuseify) are forwarded directly to `reuse annotate`.

    Example:
        reuseify annotate -i file.json --copyright-holder "John Doe"
    """
    reuse_args: list[str] = ctx.args
    _default_contributors: list[str] = default_contributor or []
    check_reuse()

    try:
        with open(input_file) as f:
            authors_map: dict[str, list[str]] = json.load(f)
    except FileNotFoundError:
        console.print(f"[bold red]Error:[/] Input file '{input_file}' not found.")
        console.print("Run [bold]reuseify get-authors[/] first to generate it.")
        sys.exit(1)
    except json.JSONDecodeError as exc:
        console.print(f"[bold red]Error:[/] Failed to parse '{input_file}': {exc}")
        sys.exit(1)

    console.print(f"Reading authors from: [bold]{input_file}[/]")

    to_annotate: list[tuple[str, list[str]]] = []
    skipped: list[tuple[str, str]] = []

    for filepath, authors in authors_map.items():
        if not authors:
            if _default_contributors and os.path.isfile(filepath):
                to_annotate.append((filepath, _default_contributors))
            else:
                reason = "NOT_IN_GIT" + (
                    "" if not _default_contributors else " (file not found)"
                )
                skipped.append((filepath, reason))
        elif not os.path.isfile(filepath):
            skipped.append((filepath, "file not found"))
        else:
            to_annotate.append((filepath, authors))

    console.print(
        f"Found [bold]{len(to_annotate)}[/] file(s) to annotate, "
        f"[bold]{len(skipped)}[/] to skip.\n"
    )

    passed: list[str] = []
    failed: list[tuple[str, str]] = []  # (filepath, stderr)

    for filepath, authors in to_annotate:
        contributor_flags: list[str] = []
        for author in authors:
            contributor_flags.extend(["--contributor", author])

        cmd = ["reuse", "annotate"] + list(reuse_args) + contributor_flags + [filepath]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            passed.append(filepath)
        else:
            failed.append((filepath, result.stderr.strip()))

    if passed:
        console.print("[bold]Annotated:[/]")
        for filepath in passed:
            authors = authors_map.get(filepath, _default_contributors)
            console.print(
                f"  [bold green]PASS[/]  {filepath}  [dim]({', '.join(authors)})[/]"
            )
        console.print()

    if skipped:
        console.print("[bold]Skipped:[/]")
        for filepath, reason in skipped:
            console.print(f"  [yellow]SKIP[/]  {filepath}  [dim]({reason})[/]")
        console.print()

    if failed:
        console.print("[bold]Failed:[/]")
        for filepath, stderr in failed:
            console.print(f"  [bold red]FAIL[/]  {filepath}")
            if stderr:
                console.print(f"         [red]{stderr}[/]")
        console.print()

    total = len(passed) + len(skipped) + len(failed)
    console.rule()
    console.print(f"Total:   {total}")
    console.print(f"[green]Success: {len(passed)}[/]")
    console.print(f"[yellow]Skipped: {len(skipped)}[/]")
    if failed:
        console.print(f"[red]Failed:  {len(failed)}[/]")
    else:
        console.print(f"Failed:  {len(failed)}")


if __name__ == "__main__":
    app()
