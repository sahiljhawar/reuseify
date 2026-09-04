# SPDX-FileCopyrightText: 2026 Sahil Jhawar
# SPDX-FileContributor: Sahil Jhawar
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for `reuseify lint`."""

# REUSE-IgnoreStart
# Some fixtures below embed literal "SPDX-License-Identifier: ..." strings as
# fake file content for temp test repos; without the markers above/below,
# `reuse` would mistake those for this file's own header when linting reuseify.

import subprocess

from conftest import HEADERED_GPL, HEADERED_MIT, UNHEADERED

import reuseify.lint as lint_module
from reuseify.lint import _match_issue_lines


def test_lint_clean_repo_exits_0(git_repo, commit_files, write_license, run_cli):
    write_license(git_repo, "GPL-3.0-or-later")
    commit_files(git_repo, {"src/main.py": HEADERED_GPL})

    result = run_cli("lint")

    assert result.exit_code == 0
    assert "compliant" in result.stdout


def test_lint_missing_license_text_reported(git_repo, commit_files, run_cli):
    commit_files(git_repo, {"src/main.py": HEADERED_GPL})

    result = run_cli("lint")

    assert result.exit_code == 1
    assert "missing license 'GPL-3.0-or-later'" in result.stdout
    assert "reuse download --all" in result.stdout


def test_lint_include_not_in_git_prints_notice(git_repo, run_cli):
    (git_repo / "untracked.py").write_text(UNHEADERED)

    result = run_cli("lint", "--include-not-in-git")

    assert result.exit_code == 1
    assert "Linting non-git-tracked files as well" in result.stdout


def test_lint_missing_header_exits_1_and_reports_file(git_repo, commit_files, run_cli):
    commit_files(git_repo, {"src/main.py": UNHEADERED})

    result = run_cli("lint")

    assert result.exit_code == 1
    assert "src/main.py" in result.stdout


def test_lint_wrong_license_under_policy_exits_1(git_repo, commit_files, write_license, run_cli):
    write_license(git_repo, "MIT")
    write_license(git_repo, "GPL-3.0-or-later")
    commit_files(
        git_repo,
        {
            "vendor/lib.py": HEADERED_MIT,
            "reuseify.toml": (
                'version = 1\n\n[default]\ncopyright = "Test User"\nlicense = "GPL-3.0-or-later"\n'
            ),
        },
    )

    result = run_cli("lint")

    assert result.exit_code == 1
    assert "Policy violations" in result.stdout
    assert "vendor/lib.py" in result.stdout
    assert "GPL-3.0-or-later" in result.stdout


def test_lint_ignores_license_sidecar_under_policy(git_repo, commit_files, write_license, run_cli):
    write_license(git_repo, "GPL-3.0-or-later")
    commit_files(
        git_repo,
        {
            "data/foo.json": '{"a": 1}\n',
            "data/foo.json.license": (
                "SPDX-FileCopyrightText: 2026 Test User\n"
                "SPDX-License-Identifier: GPL-3.0-or-later\n"
            ),
            "reuseify.toml": (
                "# SPDX-FileCopyrightText: 2026 Test User\n"
                "# SPDX-License-Identifier: GPL-3.0-or-later\n\n"
                'version = 1\n\n[default]\ncopyright = "Test User"\nlicense = "GPL-3.0-or-later"\n'
            ),
        },
    )

    result = run_cli("lint")

    assert result.exit_code == 0
    assert "data/foo.json.license" not in result.stdout


def test_lint_ignores_zero_byte_file_under_policy(git_repo, commit_files, write_license, run_cli):
    write_license(git_repo, "GPL-3.0-or-later")
    commit_files(
        git_repo,
        {
            "src/main.py": HEADERED_GPL,
            "src/empty.py": "",
            "reuseify.toml": (
                "# SPDX-FileCopyrightText: 2026 Test User\n"
                "# SPDX-License-Identifier: GPL-3.0-or-later\n\n"
                'version = 1\n\n[default]\ncopyright = "Test User"\nlicense = "GPL-3.0-or-later"\n'
            ),
        },
    )

    result = run_cli("lint")

    assert result.exit_code == 0


def test_lint_colon_in_filename_not_dropped(git_repo, commit_files, run_cli):
    commit_files(git_repo, {"weird:file.py": UNHEADERED})

    result = run_cli("lint")

    assert result.exit_code == 1
    assert "weird:file.py" in result.stdout


def test_lint_unicode_filename_not_misclassified_as_not_in_git(git_repo, commit_files, run_cli):
    commit_files(git_repo, {"café.py": UNHEADERED})

    result = run_cli("lint")

    assert result.exit_code == 1
    assert "café.py" in result.stdout
    assert "omitted" not in result.stdout


def test_lint_fails_closed_when_reuse_lint_lines_crashes(
    git_repo, commit_files, run_cli, monkeypatch
):
    commit_files(git_repo, {"src/main.py": UNHEADERED})

    real_run = subprocess.run

    def fake_run(cmd, *args, **kwargs):
        if "--lines" in cmd:
            return subprocess.CompletedProcess(cmd, returncode=2, stdout="", stderr="boom")
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(lint_module.subprocess, "run", fake_run)

    result = run_cli("lint")

    assert result.exit_code != 0
    assert result.exit_code != 1 or "reuseify" in result.stdout.lower()


def test_lint_fails_closed_when_reuse_lint_lines_output_does_not_match(
    git_repo, commit_files, run_cli, monkeypatch
):
    commit_files(git_repo, {"src/main.py": UNHEADERED})

    real_run = subprocess.run

    def fake_run(cmd, *args, **kwargs):
        if "--lines" in cmd:
            return subprocess.CompletedProcess(
                cmd, returncode=1, stdout="totally-different-format\n", stderr=""
            )
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(lint_module.subprocess, "run", fake_run)

    result = run_cli("lint")

    assert result.exit_code != 0


def test_match_issue_lines_longest_prefix_first():
    lines = [
        "src/main.py: no license identifier",
        "src/main.py.bak: no license identifier",
    ]
    files = ["src/main.py", "src/main.py.bak"]

    filtered, _, has_headers = _match_issue_lines(lines, files)

    assert len(filtered) == 2
    assert has_headers is True


def test_match_issue_lines_handles_colon_in_path():
    lines = ["weird:file.py: no license identifier"]
    files = ["weird:file.py"]

    filtered, _, has_headers = _match_issue_lines(lines, files)

    assert len(filtered) == 1
    assert has_headers is True


# REUSE-IgnoreEnd
