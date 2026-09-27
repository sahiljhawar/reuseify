# SPDX-FileCopyrightText: 2026 Sahil Jhawar
# SPDX-FileContributor: Sahil Jhawar
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for `reuseify annotate`."""

# REUSE-IgnoreStart
# These tests assert on literal "SPDX-License-Identifier: ..." substrings in
# annotated file content; without the markers above/below, `reuse` would
# mistake those assertions for this file's own header when linting reuseify.

import json
import subprocess

import pytest

import reuseify.annotate as annotate_module


def test_annotate_creates_reuseify_toml_when_missing(git_repo, commit_files, run_cli):
    commit_files(git_repo, {"src/main.py": "x = 1\n"})

    result = run_cli("annotate", "--no-download")

    assert result.exit_code == 0
    assert "created an empty one" in result.stdout
    assert (git_repo / "reuseify.toml").is_file()
    assert "FAIL" in result.stdout
    assert "no --copyright/--license resolved" in result.stdout


def test_annotate_rejects_copyright_and_license_cli_flags(git_repo, default_policy, run_cli):
    default_policy(git_repo)

    result = run_cli("annotate", "--copyright", "CLI Holder", "--license", "MIT")

    assert result.exit_code == 1
    assert "--copyright" in result.stdout
    assert "--license" in result.stdout
    assert "reuseify.toml" in result.stdout


def test_annotate_download_failure_is_reported(
    git_repo, commit_files, default_policy, run_cli, monkeypatch
):
    default_policy(git_repo)
    commit_files(git_repo, {"src/main.py": "x = 1\n"})
    (git_repo / "reuse_annotate_authors.json").write_text(
        json.dumps({"src/main.py": ["Test User"]})
    )

    real_run = subprocess.run

    def fake_run(cmd, *args, **kwargs):
        if "download" in cmd:
            return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr="network down")
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(annotate_module.subprocess, "run", fake_run)

    result = run_cli("annotate", "--download")

    assert result.exit_code == 0
    assert "Error downloading licenses" in result.stdout
    assert "network down" in result.stdout


def test_annotate_input_file_not_found(git_repo, default_policy, run_cli):
    default_policy(git_repo)

    result = run_cli("annotate", "-i", "missing.json")

    assert result.exit_code == 1
    assert "not found" in result.stdout
    assert "get-authors" in result.stdout


def test_annotate_direct_files_with_contributor_adds_to_git_contributor(
    git_repo, commit_files, run_cli
):
    commit_files(git_repo, {"src/main.py": "x = 1\n", "src/other.py": "y = 2\n"})
    (git_repo / "reuseify.toml").write_text(
        'version = 1\n\n[default]\ncopyright = "Sahil Jhawar"\nlicense = "MIT"\n'
    )

    result = run_cli("annotate", "--no-download", "--contributor", "Sahil Jhawar", "src/main.py")

    assert result.exit_code == 0
    content = (git_repo / "src/main.py").read_text()
    assert "SPDX-License-Identifier: MIT" in content
    assert "SPDX-FileContributor: Sahil Jhawar" in content
    assert "SPDX-FileContributor: Test User" in content
    assert "SPDX-License-Identifier" not in (git_repo / "src/other.py").read_text()


def test_annotate_direct_files_falls_back_to_git_contributor(git_repo, commit_files, run_cli):
    commit_files(git_repo, {"src/main.py": "x = 1\n"})
    (git_repo / "reuseify.toml").write_text(
        'version = 1\n\n[default]\ncopyright = "Sahil Jhawar"\nlicense = "MIT"\n'
    )

    result = run_cli("annotate", "--no-download", "src/main.py")

    assert result.exit_code == 0
    content = (git_repo / "src/main.py").read_text()
    assert "SPDX-License-Identifier: MIT" in content
    assert "SPDX-FileContributor: Test User" in content


def test_annotate_direct_files_without_contributor_is_optional_with_no_git_history(
    git_repo, run_cli
):
    (git_repo / "untracked.py").write_text("x = 1\n")
    (git_repo / "reuseify.toml").write_text(
        'version = 1\n\n[default]\ncopyright = "Sahil Jhawar"\nlicense = "MIT"\n'
    )

    result = run_cli("annotate", "--no-download", "untracked.py")

    assert result.exit_code == 0
    content = (git_repo / "untracked.py").read_text()
    assert "SPDX-License-Identifier: MIT" in content
    assert "SPDX-FileContributor" not in content


def test_annotate_direct_files_multiple_contributors(
    git_repo, commit_files, default_policy, run_cli
):
    default_policy(git_repo)
    commit_files(git_repo, {"src/main.py": "x = 1\n"})

    result = run_cli(
        "annotate",
        "--no-download",
        "--contributor",
        "Alice",
        "--contributor",
        "Bob",
        "src/main.py",
    )

    assert result.exit_code == 0
    content = (git_repo / "src/main.py").read_text()
    assert "SPDX-FileContributor: Alice" in content
    assert "SPDX-FileContributor: Bob" in content


def test_annotate_without_get_authors_uses_git_history_directly(
    git_repo, commit_files, default_policy, run_cli
):
    default_policy(git_repo, license="MIT")
    commit_files(git_repo, {"src/main.py": "x = 1\n"})

    result = run_cli("annotate", "--no-download")

    assert result.exit_code == 0
    assert "looking up authors from git history" in result.stdout
    content = (git_repo / "src/main.py").read_text()
    assert "SPDX-License-Identifier: MIT" in content
    assert "Test User" in content


def test_annotate_input_file_invalid_json(git_repo, default_policy, run_cli):
    default_policy(git_repo)
    (git_repo / "bad.json").write_text("{not valid json")

    result = run_cli("annotate", "-i", "bad.json")

    assert result.exit_code == 1
    assert "Failed to parse" in result.stdout


def test_annotate_skips_file_with_authors_but_missing_on_disk(git_repo, default_policy, run_cli):
    default_policy(git_repo)
    (git_repo / "reuse_annotate_authors.json").write_text(json.dumps({"gone.py": ["Some Author"]}))

    result = run_cli("annotate", "--no-download")

    assert result.exit_code == 0
    assert "SKIP" in result.stdout
    assert "file not found" in result.stdout


def test_annotate_governed_file_with_no_resolvable_license_fails(git_repo, commit_files, run_cli):
    commit_files(git_repo, {"src/main.py": "x = 1\n"})
    (git_repo / "reuseify.toml").write_text('version = 1\n\n[[rules]]\npaths = ["src/**"]\n')
    (git_repo / "reuse_annotate_authors.json").write_text(
        json.dumps({"src/main.py": ["Test User"]})
    )

    result = run_cli("annotate", "--no-download")

    assert result.exit_code == 0
    assert "FAIL" in result.stdout
    assert "no --copyright/--license resolved" in result.stdout


def test_annotate_reports_failed_reuse_invocation(git_repo, default_policy, run_cli):
    default_policy(git_repo)
    (git_repo / "weird.xyzext").write_text("data\n")
    (git_repo / "reuse_annotate_authors.json").write_text(
        json.dumps({"weird.xyzext": ["Test User"]})
    )

    result = run_cli("annotate", "--no-download")

    assert result.exit_code == 0
    assert "FAIL" in result.stdout
    assert "weird.xyzext" in result.stdout
    assert "Failed:  1" in result.stdout


@pytest.mark.skip(reason="SPDX renamed branch from master to main, hence download fails.")
def test_annotate_download_flag_runs_reuse_download(
    git_repo, commit_files, default_policy, run_cli
):
    default_policy(git_repo, license="MIT")
    commit_files(git_repo, {"src/main.py": "x = 1\n"})
    (git_repo / "reuse_annotate_authors.json").write_text(
        json.dumps({"src/main.py": ["Test User"]})
    )

    result = run_cli("annotate", "--download")

    assert result.exit_code == 0
    assert "Downloading missing licenses" in result.stdout
    assert (git_repo / "LICENSES" / "MIT.txt").is_file()


def test_annotate_resolves_from_policy_with_no_cli_flags(git_repo, commit_files, run_cli):
    commit_files(git_repo, {"src/main.py": "x = 1\n"})
    (git_repo / "reuseify.toml").write_text(
        'version = 1\n\n[default]\ncopyright = "Test User"\nlicense = "MIT"\n'
    )
    (git_repo / "reuse_annotate_authors.json").write_text(
        json.dumps({"src/main.py": ["Test User"]})
    )

    result = run_cli("annotate", "--no-download")

    assert result.exit_code == 0
    content = (git_repo / "src/main.py").read_text()
    assert "SPDX-License-Identifier: MIT" in content
    assert "Test User" in content


def test_annotate_skips_not_in_git_without_default_contributor(git_repo, default_policy, run_cli):
    default_policy(git_repo)
    (git_repo / "untracked.py").write_text("x = 1\n")
    (git_repo / "reuse_annotate_authors.json").write_text(json.dumps({"untracked.py": []}))

    result = run_cli("annotate", "--no-download")

    assert result.exit_code == 0
    assert "SKIP" in result.stdout
    content = (git_repo / "untracked.py").read_text()
    assert "SPDX-License-Identifier" not in content


def test_annotate_includes_not_in_git_with_default_contributor(git_repo, default_policy, run_cli):
    default_policy(git_repo, license="MIT")
    (git_repo / "untracked.py").write_text("x = 1\n")
    (git_repo / "reuse_annotate_authors.json").write_text(json.dumps({"untracked.py": []}))

    result = run_cli(
        "annotate",
        "--no-download",
        "--default-contributor",
        "Fallback Author",
    )

    assert result.exit_code == 0
    content = (git_repo / "untracked.py").read_text()
    assert "SPDX-License-Identifier: MIT" in content
    assert "Fallback Author" in content


def test_annotate_contributor_adds_to_batch_mode_git_authors(
    git_repo, commit_files, default_policy, run_cli
):
    default_policy(git_repo)
    commit_files(git_repo, {"src/main.py": "x = 1\n"})

    result = run_cli("annotate", "--no-download", "--contributor", "Extra Person")

    assert result.exit_code == 0
    content = (git_repo / "src/main.py").read_text()
    assert "SPDX-FileContributor: Test User" in content
    assert "SPDX-FileContributor: Extra Person" in content


def test_annotate_contributor_covers_not_in_git_without_default_contributor(
    git_repo, default_policy, run_cli
):
    default_policy(git_repo, license="MIT")
    (git_repo / "untracked.py").write_text("x = 1\n")
    (git_repo / "reuse_annotate_authors.json").write_text(json.dumps({"untracked.py": []}))

    result = run_cli("annotate", "--no-download", "--contributor", "Fallback Author")

    assert result.exit_code == 0
    content = (git_repo / "untracked.py").read_text()
    assert "SPDX-License-Identifier: MIT" in content
    assert "Fallback Author" in content


# REUSE-IgnoreEnd
