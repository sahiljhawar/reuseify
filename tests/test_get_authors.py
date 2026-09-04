# SPDX-FileCopyrightText: 2026 Sahil Jhawar
# SPDX-FileContributor: Sahil Jhawar
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for `reuseify get-authors`."""

import json

from conftest import HEADERED_GPL, UNHEADERED


def test_get_authors_no_issues_exits_0(git_repo, commit_files, write_license, run_cli):
    write_license(git_repo, "GPL-3.0-or-later")
    commit_files(git_repo, {"src/main.py": HEADERED_GPL})

    result = run_cli("get-authors", "-o", "out.json")

    assert result.exit_code == 0
    assert "No files with licensing issues" in result.stdout


def test_get_authors_reports_excluded_count(git_repo, commit_files, run_cli):
    commit_files(git_repo, {"keep.py": UNHEADERED, "reports/skip.py": UNHEADERED})

    result = run_cli("get-authors", "-o", "out.json", "--exclude", "reports")

    assert result.exit_code == 0
    assert "Excluded 1 file(s)" in result.stdout
    data = json.loads((git_repo / "out.json").read_text())
    assert "keep.py" in data
    assert "reports/skip.py" not in data


def test_get_authors_all_files_excluded_exits_0(git_repo, commit_files, run_cli):
    commit_files(git_repo, {"reports/skip.py": UNHEADERED})

    result = run_cli("get-authors", "-o", "out.json", "--exclude", "reports")

    assert result.exit_code == 0
    assert "All remaining files were excluded" in result.stdout


def test_get_authors_separates_tracked_and_not_in_git(git_repo, commit_files, run_cli):
    commit_files(git_repo, {"tracked.py": UNHEADERED})
    (git_repo / "untracked.py").write_text(UNHEADERED)

    result = run_cli("get-authors", "-o", "out.json")

    assert result.exit_code == 0
    data = json.loads((git_repo / "out.json").read_text())
    assert data["tracked.py"] == ["Test User"]
    assert "untracked.py" not in data
    assert "omitted" in result.stdout


def test_get_authors_includes_not_in_git_with_flag(git_repo, commit_files, run_cli):
    commit_files(git_repo, {"tracked.py": UNHEADERED})
    (git_repo / "untracked.py").write_text(UNHEADERED)

    result = run_cli("get-authors", "-o", "out.json", "--include-not-in-git")

    assert result.exit_code == 0
    data = json.loads((git_repo / "out.json").read_text())
    assert data["tracked.py"] == ["Test User"]
    assert data["untracked.py"] == []


def test_get_authors_excludes_gitignored_files(git_repo, commit_files, run_cli):
    commit_files(git_repo, {"tracked.py": UNHEADERED, ".gitignore": "ignored.py\n"})
    (git_repo / "ignored.py").write_text(UNHEADERED)

    run_cli("get-authors", "-o", "out.json", "--include-not-in-git")

    data = json.loads((git_repo / "out.json").read_text())
    assert "ignored.py" not in data
