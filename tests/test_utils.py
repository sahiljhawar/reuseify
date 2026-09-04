# SPDX-FileCopyrightText: 2026 Sahil Jhawar
# SPDX-FileContributor: Sahil Jhawar
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for reuseify.utils."""

import subprocess

import pytest
from conftest import UNHEADERED

import reuseify.utils as utils_module
from reuseify.utils import (
    check_git_repo,
    check_reuse,
    filter_git_ignored,
    get_files_to_lint,
    get_git_tracked_files,
    is_path_excluded,
)


def test_get_missing_license_files_fails_closed_on_reuse_crash(monkeypatch):
    def fake_run(cmd, *args, **kwargs):
        return subprocess.CompletedProcess(cmd, returncode=2, stdout="", stderr="boom")

    monkeypatch.setattr(utils_module.subprocess, "run", fake_run)

    with pytest.raises(SystemExit) as exc_info:
        utils_module.get_missing_license_files()

    assert exc_info.value.code != 0


def test_get_git_tracked_files_handles_unicode_without_quoting(git_repo, commit_files):
    commit_files(git_repo, {"café.py": UNHEADERED})

    tracked = get_git_tracked_files()

    assert "café.py" in tracked


def test_is_path_excluded_matches_default_patterns():
    assert is_path_excluded("src/__pycache__/foo.pyc", ("__pycache__", "*.pyc"))
    assert not is_path_excluded("src/main.py", ("__pycache__", "*.pyc"))


def test_get_files_to_lint_omits_untracked_by_default(git_repo, commit_files):
    commit_files(git_repo, {"tracked.py": UNHEADERED})
    (git_repo / "untracked.py").write_text(UNHEADERED)

    files, omitted = get_files_to_lint(include_not_in_git=False, exclude=None)

    assert "tracked.py" in files
    assert "untracked.py" not in files
    assert omitted == 1


def test_get_files_to_lint_includes_untracked_with_flag(git_repo, commit_files):
    commit_files(git_repo, {"tracked.py": UNHEADERED})
    (git_repo / "untracked.py").write_text(UNHEADERED)

    files, omitted = get_files_to_lint(include_not_in_git=True, exclude=None)

    assert "tracked.py" in files
    assert "untracked.py" in files
    assert omitted == 0


def test_filter_git_ignored_empty_input_returns_empty():
    assert filter_git_ignored([]) == []


def test_check_git_repo_exits_when_not_a_repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        check_git_repo()

    assert exc_info.value.code != 0


def test_check_reuse_exits_when_not_installed(monkeypatch):
    monkeypatch.setattr(utils_module.shutil, "which", lambda _: None)

    with pytest.raises(SystemExit) as exc_info:
        check_reuse()

    assert exc_info.value.code != 0


def test_get_git_tracked_files_returns_empty_on_git_failure(monkeypatch):
    def fake_run(cmd, *args, **kwargs):
        return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr="not a repo")

    monkeypatch.setattr(utils_module.subprocess, "run", fake_run)

    assert get_git_tracked_files() == []
