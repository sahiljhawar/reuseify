"""reuseify — top-level CLI entry point."""

import typer

from reuseify.get_authors import main as _get_authors_cmd
from reuseify.annotate import main as _annotate_cmd

app = typer.Typer(
    name="reuseify",
    help="Automate REUSE license annotation from git history.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

app.command("get-authors")(_get_authors_cmd)
app.command("annotate", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})(_annotate_cmd)


if __name__ == "__main__":
    app()
