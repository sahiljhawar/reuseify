# SPDX-FileCopyrightText: 2026 Sahil Jhawar
# SPDX-FileContributor: Sahil Jhawar
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Apply REUSE license headers to files using authors from a JSON file.

All flags not consumed by this script are forwarded verbatim to
`reuse annotate` (e.g. --copyright, --license, --year, --style,
--fallback-dot-license, --force-dot-license, --skip-unrecognised, ...).
The --contributor flags are populated automatically from the JSON file
produced by get_authors.py.

If a reuseify.toml policy file is present, --copyright and --license are
resolved per file from its path-based rules instead of being required on
the command line; CLI-supplied values are used as a fallback for fields a
rule/default does not specify.
"""

import argparse
import json
import os
import subprocess
import sys
from typing import Annotated

import typer
from rich.console import Console
from richpool import JoblibPool

from reuseify.policy import load_policy, match_rule, resolve_license_and_copyright
from reuseify.utils import check_reuse

console = Console()


def _extract_copyright_license(
    args: list[str],
) -> tuple[str | None, str | None, list[str]]:
    """Pull the last --copyright/--license value out of *args*.

    Returns (copyright, license, remaining_args), where remaining_args has the
    recognised --copyright/--license flags and their values removed so they can
    be re-added per file with a resolved value instead of duplicated.
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-c", "--copyright", action="append", default=[])
    parser.add_argument("-l", "--license", action="append", default=[])
    known, remainder = parser.parse_known_args(args)
    copyright_ = known.copyright[-1] if known.copyright else None
    license_ = known.license[-1] if known.license else None
    return copyright_, license_, remainder


app = typer.Typer()


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
    download: Annotated[
        bool,
        typer.Option(
            "--download",
            "-D",
            help="Download missing license files.",
        ),
    ] = False,
) -> None:
    """
    Apply REUSE license headers using authors from a JSON file.

    Any additional flags (not part of reuseify) are forwarded directly to `reuse annotate`.

    Example:
        reuseify annotate -i file.json --copyright "John Doe" --license MIT
    """
    reuse_args: list[str] = ctx.args
    _default_contributors: list[str] = default_contributor or []
    check_reuse()

    policy = load_policy()
    cli_copyright, cli_license, remainder_args = _extract_copyright_license(reuse_args)

    if policy is None and not (cli_copyright and cli_license):
        console.print(
            "[bold red]Error:[/] Both [bold]--copyright[/] and [bold]--license[/] are required."
        )
        console.print(
            "reuse lint requires a copyright notice and a license identifier on every file; "
            "reuseify's automatic [bold]--contributor[/] alone will not satisfy it. "
            "Add a reuseify.toml to resolve these per file instead."
        )
        sys.exit(1)

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
        f"Found [bold]{len(to_annotate)}[/] file(s) to annotate, [bold]{len(skipped)}[/] to skip.\n"
    )

    passed: list[str] = []
    failed: list[tuple[str, str]] = []  # (filepath, stderr)

    def _annotate_one(
        item: tuple[str, list[str]],
    ) -> tuple[str, str | None]:
        """Run `reuse annotate` for a single file.

        Returns (filepath, stderr) on failure, or (filepath, None) on success.
        """
        filepath, authors = item
        contributor_flags: list[str] = []
        for author in authors:
            contributor_flags.extend(["--contributor", author])

        governed = policy is not None and match_rule(filepath, policy) is not None
        if governed:
            copyright_, license_ = resolve_license_and_copyright(
                filepath, policy, cli_copyright, cli_license
            )
            if not (copyright_ and license_):
                return (
                    filepath,
                    "no --copyright/--license resolved from reuseify.toml or CLI flags",
                )
            cmd = (
                ["reuse", "annotate"]
                + remainder_args
                + ["--copyright", copyright_, "--license", license_]
                + contributor_flags
                + [filepath]
            )
        else:
            cmd = (
                ["reuse", "annotate"]
                + list(reuse_args)
                + contributor_flags
                + [filepath]
            )

        result = subprocess.run(cmd, capture_output=True, text=True)
        return (filepath, None if result.returncode == 0 else result.stderr.strip())

    max_workers = min(32, (os.cpu_count() or 4) * 4)
    pool = JoblibPool(processes=max_workers, backend="threading")
    results = pool.map(
        _annotate_one, to_annotate, desc="Annotating", total=len(to_annotate)
    )

    for filepath, error in results:
        if error is None:
            passed.append(filepath)
        else:
            failed.append((filepath, error))

    if passed:
        console.print("[bold]Annotated:[/]")
        for filepath in passed:
            authors = authors_map.get(filepath) or _default_contributors
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

    if download:
        console.print("\n[bold]Downloading missing licenses to LICENSES/...[/]")
        cmd = ["reuse", "download", "--all"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            console.print(
                f"[bold red]Error downloading licenses:[/] {result.stderr.strip()}"
            )
        else:
            console.print(f"[green]{result.stdout.strip()}[/]")


if __name__ == "__main__":
    app()
