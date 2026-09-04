# SPDX-FileCopyrightText: 2026 Sahil Jhawar
# SPDX-FileContributor: Sahil Jhawar
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Shared fixtures for the reuseify test suite."""

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from reuseify.cli import app

# REUSE-IgnoreStart
# These constants embed literal SPDX tags as fixture data for temp test
# repos; without the markers above/below, `reuse` would mistake them for
# this file's own header when linting the reuseify project itself.
HEADERED_GPL = (
    "# SPDX-FileCopyrightText: 2026 Test User\n"
    "# SPDX-License-Identifier: GPL-3.0-or-later\n"
    "\n"
    "x = 1\n"
)

HEADERED_MIT = "# SPDX-FileCopyrightText: 2026 Test User\n# SPDX-License-Identifier: MIT\n\nx = 1\n"
# REUSE-IgnoreEnd

UNHEADERED = "x = 1\n"


@pytest.fixture
def git_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fresh, empty git repository with a test identity, as the cwd."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def commit_files():
    """Write and commit a dict of {relative_path: content} to a repo."""

    def _commit(repo: Path, files: dict[str, str], message: str = "add files") -> None:
        for relpath, content in files.items():
            path = repo / relpath
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", message], cwd=repo, check=True)

    return _commit


@pytest.fixture
def write_license():
    """Write a placeholder LICENSES/<name>.txt so `reuse` recognizes the id as available."""

    def _write(repo: Path, name: str) -> None:
        licenses_dir = repo / "LICENSES"
        licenses_dir.mkdir(exist_ok=True)
        (licenses_dir / f"{name}.txt").write_text(f"Placeholder {name} license text.\n")

    return _write


@pytest.fixture
def run_cli():
    """Invoke the reuseify Typer app in-process, returning a click Result."""
    runner = CliRunner()

    def _run(*args: str):
        return runner.invoke(app, list(args))

    return _run
