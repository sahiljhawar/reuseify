# SPDX-FileCopyrightText: 2026 Sahil Jhawar
# SPDX-FileContributor: Sahil Jhawar
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Apply REUSE license headers to files using authors from git or a JSON file.

All flags not consumed by this script are forwarded verbatim to
`reuse annotate` (e.g. --year, --style, --fallback-dot-license,
--force-dot-license, --skip-unrecognised, ...).

A reuseify.toml policy file is required: it is the only source of the
--copyright/--license used to annotate each file, resolved per file from its
path-based rules (or [default]). --copyright/--license are not accepted as
CLI flags here; this keeps a project's licensing consistent regardless of
what any one invocation happens to pass, which is the whole point of having
a policy file. See README for reuseify.toml's format.

Contributors always start from git history (per file, whether discovered via
--input/git-history batch mode, or looked up directly for file path(s) given
explicitly on the command line). --contributor adds extra name(s) on top of
that for every file, and also covers files with no git history at all (in
batch mode, in place of --default-contributor; in direct-file mode, it's then
the only source of contributors, and can be omitted entirely since it isn't
required by `reuse annotate` either).
"""

import json
import os
import subprocess
import sys
from typing import Annotated

import typer
from rich.console import Console
from richpool import JoblibPool

from reuseify.get_authors import build_authors_map, get_git_authors
from reuseify.policy import require_policy, resolve_license_and_copyright
from reuseify.utils import check_git_repo, check_reuse

console = Console()

DEFAULT_INPUT_FILE = "reuse_annotate_authors.json"


# reuse annotate's own flags that consume a following value (from `reuse
# annotate --help`).
_REUSE_VALUE_FLAGS = frozenset(
    {"-y", "--year", "-s", "--style", "--copyright-prefix", "-t", "--template"}
)

# Rejected outright in main() rather than handled here: reuseify.toml is now
# the only source of copyright/license.
_REJECTED_FLAGS = ("-c", "--copyright", "-l", "--license")


def _extract_annotate_args(args: list[str]) -> tuple[list[str], list[str]]:
    """Split reuseify's own positional file arguments out of *args* (forwarded CLI args).

    Returns (files, remaining_args):
    - files: positional file paths, for annotating specific files directly instead
      of discovering them via --input / git history.
    - remaining_args: everything else, forwarded verbatim to `reuse annotate`.
    """
    files: list[str] = []
    remainder: list[str] = []

    i = 0
    while i < len(args):
        token = args[i]
        has_value = i + 1 < len(args)

        if token in _REUSE_VALUE_FLAGS:
            remainder.append(token)
            if has_value:
                remainder.append(args[i + 1])
                i += 2
            else:
                i += 1
        elif token.startswith("-"):
            remainder.append(token)
            i += 1
        else:
            files.append(token)
            i += 1

    return files, remainder


app = typer.Typer()


def main(
    ctx: typer.Context,
    input_file: Annotated[
        str,
        typer.Option(
            "--input",
            "-i",
            help=(
                "JSON file produced by get-authors. If this is left at its default "
                "and the file doesn't exist, authors are looked up directly from "
                "git history instead."
            ),
            show_default=True,
        ),
    ] = DEFAULT_INPUT_FILE,
    contributor: Annotated[
        list[str] | None,
        typer.Option(
            "--contributor",
            "-n",
            help=(
                "Extra contributor name(s), can be repeated. Added on top of each file's "
                "git-history authors (looked up directly for file(s) given on the command "
                "line, or discovered via --input/git history otherwise), and also covers "
                "files with no git history at all that would otherwise need "
                "--default-contributor (or, in direct-file mode, have no --contributor)."
            ),
        ),
    ] = None,
    default_contributor: Annotated[
        list[str] | None,
        typer.Option(
            "--default-contributor",
            "-d",
            help=(
                "Fallback contributor name(s) for files with no git history (NOT_IN_GIT), "
                "used when --contributor isn't given. Can be repeated. Without either flag "
                "those files are skipped."
            ),
        ),
    ] = None,
    download: Annotated[
        bool,
        typer.Option(
            "--download/--no-download",
            "-D",
            help=(
                "Download missing license files after annotating. On by default; a "
                "download failure is reported but never fails the annotate run itself."
            ),
        ),
    ] = True,
) -> None:
    """
    Apply REUSE license headers using authors from git history or a JSON file.

    Requires a reuseify.toml: it's the only source of --copyright/--license,
    resolved per file from its path-based rules (or [default]). --copyright/
    --license are not accepted as CLI flags.

    With no --input, or when the default input file doesn't exist, authors are
    looked up directly from git history, same as running `reuseify get-authors`
    first would produce. Pass --input to reuse a JSON file from a prior
    get-authors run instead (e.g. one you've hand-edited).

    Passing specific file path(s) directly skips that discovery entirely and
    annotates just those files, with contributors looked up directly from git
    history for each one; --contributor adds extra names on top of that (and
    is the only source of contributors for a file with no git history):

        reuseify annotate --contributor "Sahil Jhawar" src/main.py

    Any additional flags (not part of reuseify) are forwarded directly to `reuse annotate`.
    """
    reuse_args: list[str] = ctx.args
    cli_contributors: list[str] = contributor or []
    _default_contributors: list[str] = default_contributor or []
    check_reuse()

    if any(token in _REJECTED_FLAGS for token in reuse_args):
        console.print(
            "[bold red]Error:[/] [bold]--copyright[/]/[bold]--license[/] are no longer "
            "accepted here; configure them in [bold]reuseify.toml[/] instead (see README)."
        )
        sys.exit(1)

    policy = require_policy()
    direct_files, remainder_args = _extract_annotate_args(reuse_args)

    to_annotate: list[tuple[str, list[str]]] = []
    skipped: list[tuple[str, str]] = []

    if direct_files:
        check_git_repo()
        authors_map: dict[str, list[str]] = {}
        for filepath in direct_files:
            if not os.path.isfile(filepath):
                skipped.append((filepath, "file not found"))
                continue
            git_authors = get_git_authors(filepath)
            combined = git_authors + [c for c in cli_contributors if c not in git_authors]
            authors_map[filepath] = combined
            to_annotate.append((filepath, combined))
    else:
        try:
            with open(input_file) as f:
                authors_map = json.load(f)
            console.print(f"Reading authors from: [bold]{input_file}[/]")
        except FileNotFoundError:
            if input_file != DEFAULT_INPUT_FILE:
                console.print(f"[bold red]Error:[/] Input file '{input_file}' not found.")
                console.print("Run [bold]reuseify get-authors[/] first to generate it.")
                sys.exit(1)
            check_git_repo()
            console.print(
                f"[dim]No '{input_file}' found; looking up authors from git history "
                "directly (run [bold]reuseify get-authors[/] first to cache/edit them "
                "instead).[/]"
            )
            authors_map = build_authors_map()
        except json.JSONDecodeError as exc:
            console.print(f"[bold red]Error:[/] Failed to parse '{input_file}': {exc}")
            sys.exit(1)

        for filepath, authors in authors_map.items():
            if not authors:
                fallback = cli_contributors or _default_contributors
                if fallback and os.path.isfile(filepath):
                    authors_map[filepath] = fallback
                    to_annotate.append((filepath, fallback))
                else:
                    reason = "NOT_IN_GIT" + ("" if not fallback else " (file not found)")
                    skipped.append((filepath, reason))
            elif not os.path.isfile(filepath):
                skipped.append((filepath, "file not found"))
            else:
                combined = authors + [c for c in cli_contributors if c not in authors]
                authors_map[filepath] = combined
                to_annotate.append((filepath, combined))

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

        copyright_, license_ = resolve_license_and_copyright(filepath, policy)
        if not (copyright_ and license_):
            return (
                filepath,
                "no --copyright/--license resolved from reuseify.toml "
                r"(add a matching rule or \[default])",
            )

        copyright_license_flags = ["--copyright", copyright_, "--license", license_]

        cmd = (
            ["reuse", "annotate"]
            + remainder_args
            + copyright_license_flags
            + contributor_flags
            + [filepath]
        )

        result = subprocess.run(cmd, capture_output=True, text=True)
        return (filepath, None if result.returncode == 0 else result.stderr.strip())

    max_workers = min(32, (os.cpu_count() or 4) * 4)
    pool = JoblibPool(processes=max_workers, backend="threading")
    results = pool.map(_annotate_one, to_annotate, desc="Annotating", total=len(to_annotate))

    for filepath, error in results:
        if error is None:
            passed.append(filepath)
        else:
            failed.append((filepath, error))

    if passed:
        console.print("[bold]Annotated:[/]")
        for filepath in passed:
            authors = authors_map.get(filepath) or _default_contributors
            suffix = f"  [dim]({', '.join(authors)})[/]" if authors else ""
            console.print(f"  [bold green]PASS[/]  {filepath}{suffix}")
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
        try:
            result = subprocess.run(["reuse", "download", "--all"], capture_output=True, text=True)
        except OSError as exc:
            console.print(f"[bold red]Error downloading licenses:[/] {exc}")
        else:
            if result.returncode != 0:
                # `reuse download` writes its own errors to stdout, not stderr.
                message = result.stderr.strip() or result.stdout.strip()
                console.print(f"[bold red]Error downloading licenses:[/] {message}")
            else:
                console.print(f"[green]{result.stdout.strip()}[/]")


if __name__ == "__main__":
    app()
