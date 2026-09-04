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

import reuseify.annotate as annotate_module


def test_annotate_download_failure_is_reported(git_repo, commit_files, run_cli, monkeypatch):
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

    result = run_cli("annotate", "--copyright", "Test", "--license", "MIT", "--download")

    assert result.exit_code == 0
    assert "Error downloading licenses" in result.stdout
    assert "network down" in result.stdout


def test_annotate_input_file_not_found(git_repo, run_cli):
    result = run_cli("annotate", "--copyright", "Test", "--license", "MIT", "-i", "missing.json")

    assert result.exit_code == 1
    assert "not found" in result.stdout
    assert "get-authors" in result.stdout


def test_annotate_input_file_invalid_json(git_repo, run_cli):
    (git_repo / "bad.json").write_text("{not valid json")

    result = run_cli("annotate", "--copyright", "Test", "--license", "MIT", "-i", "bad.json")

    assert result.exit_code == 1
    assert "Failed to parse" in result.stdout


def test_annotate_skips_file_with_authors_but_missing_on_disk(git_repo, run_cli):
    (git_repo / "reuse_annotate_authors.json").write_text(json.dumps({"gone.py": ["Some Author"]}))

    result = run_cli("annotate", "--copyright", "Test", "--license", "MIT")

    assert result.exit_code == 0
    assert "SKIP" in result.stdout
    assert "file not found" in result.stdout


def test_annotate_governed_file_with_no_resolvable_license_fails(git_repo, commit_files, run_cli):
    commit_files(git_repo, {"src/main.py": "x = 1\n"})
    (git_repo / "reuseify.toml").write_text('version = 1\n\n[[rules]]\npaths = ["src/**"]\n')
    (git_repo / "reuse_annotate_authors.json").write_text(
        json.dumps({"src/main.py": ["Test User"]})
    )

    result = run_cli("annotate")

    assert result.exit_code == 0
    assert "FAIL" in result.stdout
    assert "no --copyright/--license resolved" in result.stdout


def test_annotate_reports_failed_reuse_invocation(git_repo, run_cli):
    (git_repo / "weird.xyzext").write_text("data\n")
    (git_repo / "reuse_annotate_authors.json").write_text(
        json.dumps({"weird.xyzext": ["Test User"]})
    )

    result = run_cli("annotate", "--copyright", "Test", "--license", "MIT")

    assert result.exit_code == 0
    assert "FAIL" in result.stdout
    assert "weird.xyzext" in result.stdout
    assert "Failed:  1" in result.stdout


def test_annotate_download_flag_runs_reuse_download(git_repo, commit_files, run_cli):
    commit_files(git_repo, {"src/main.py": "x = 1\n"})
    (git_repo / "reuse_annotate_authors.json").write_text(
        json.dumps({"src/main.py": ["Test User"]})
    )

    result = run_cli("annotate", "--copyright", "Test", "--license", "MIT", "--download")

    assert result.exit_code == 0
    assert "Downloading missing licenses" in result.stdout
    assert (git_repo / "LICENSES" / "MIT.txt").is_file()


def test_annotate_requires_both_copyright_and_license_without_policy(git_repo, run_cli):
    (git_repo / "reuse_annotate_authors.json").write_text("{}")

    result = run_cli("annotate")

    assert result.exit_code == 1
    assert "--copyright" in result.stdout
    assert "--license" in result.stdout


def test_annotate_resolves_from_policy_with_no_cli_flags(git_repo, commit_files, run_cli):
    commit_files(git_repo, {"src/main.py": "x = 1\n"})
    (git_repo / "reuseify.toml").write_text(
        'version = 1\n\n[default]\ncopyright = "Test User"\nlicense = "MIT"\n'
    )
    (git_repo / "reuse_annotate_authors.json").write_text(
        json.dumps({"src/main.py": ["Test User"]})
    )

    result = run_cli("annotate")

    assert result.exit_code == 0
    content = (git_repo / "src/main.py").read_text()
    assert "SPDX-License-Identifier: MIT" in content
    assert "Test User" in content


def test_annotate_cli_flags_used_as_fallback_for_unmatched_fields(git_repo, commit_files, run_cli):
    commit_files(git_repo, {"src/main.py": "x = 1\n"})
    (git_repo / "reuseify.toml").write_text(
        'version = 1\n\n[[rules]]\npaths = ["src/**"]\nlicense = "MIT"\n'
    )
    (git_repo / "reuse_annotate_authors.json").write_text(
        json.dumps({"src/main.py": ["Test User"]})
    )

    result = run_cli("annotate", "--copyright", "CLI Holder")

    assert result.exit_code == 0
    content = (git_repo / "src/main.py").read_text()
    assert "SPDX-License-Identifier: MIT" in content
    assert "CLI Holder" in content


def test_annotate_skips_not_in_git_without_default_contributor(git_repo, run_cli):
    (git_repo / "untracked.py").write_text("x = 1\n")
    (git_repo / "reuse_annotate_authors.json").write_text(json.dumps({"untracked.py": []}))

    result = run_cli("annotate", "--copyright", "Test", "--license", "MIT")

    assert result.exit_code == 0
    assert "SKIP" in result.stdout
    content = (git_repo / "untracked.py").read_text()
    assert "SPDX-License-Identifier" not in content


def test_annotate_includes_not_in_git_with_default_contributor(git_repo, run_cli):
    (git_repo / "untracked.py").write_text("x = 1\n")
    (git_repo / "reuse_annotate_authors.json").write_text(json.dumps({"untracked.py": []}))

    result = run_cli(
        "annotate",
        "--copyright",
        "Test",
        "--license",
        "MIT",
        "--default-contributor",
        "Fallback Author",
    )

    assert result.exit_code == 0
    content = (git_repo / "untracked.py").read_text()
    assert "SPDX-License-Identifier: MIT" in content
    assert "Fallback Author" in content


# REUSE-IgnoreEnd
