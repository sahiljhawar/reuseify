# SPDX-FileCopyrightText: 2026 Sahil Jhawar
# SPDX-FileContributor: Sahil Jhawar
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for reuseify.policy."""

import subprocess

import reuseify.policy as policy_module
from reuseify.policy import (
    Policy,
    Rule,
    check_policy_violations,
    get_declared_spdx_info,
    is_covered_file,
    match_rule,
    resolve_license_and_copyright,
)


def test_match_rule_exact_path_beats_directory_glob():
    policy = Policy(
        rules=(
            Rule(paths=("vendor/**",), copyright="Vendor", license="MIT"),
            Rule(
                paths=("vendor/special_file.py",),
                copyright="Sahil Jhawar",
                license="GPL-3.0-or-later",
            ),
        ),
        default=None,
    )

    rule = match_rule("vendor/special_file.py", policy)

    assert rule is not None
    assert rule.license == "GPL-3.0-or-later"


def test_match_rule_exact_path_wins_regardless_of_declaration_order():
    policy = Policy(
        rules=(
            Rule(
                paths=("vendor/special_file.py",),
                copyright="Sahil Jhawar",
                license="GPL-3.0-or-later",
            ),
            Rule(paths=("vendor/**",), copyright="Vendor", license="MIT"),
        ),
        default=None,
    )

    rule = match_rule("vendor/special_file.py", policy)

    assert rule is not None
    assert rule.license == "GPL-3.0-or-later"


def test_match_rule_longer_glob_wins_among_wildcards():
    policy = Policy(
        rules=(
            Rule(paths=("**",), copyright="Fallback", license="MIT"),
            Rule(paths=("vendor/**",), copyright="Vendor", license="Apache-2.0"),
        ),
        default=None,
    )

    rule = match_rule("vendor/lib.py", policy)

    assert rule is not None
    assert rule.license == "Apache-2.0"


def test_match_rule_falls_back_to_default():
    policy = Policy(
        rules=(Rule(paths=("src/**",), copyright="Src", license="MIT"),),
        default=Rule(paths=(), copyright="Default", license="GPL-3.0-or-later"),
    )

    rule = match_rule("other/file.py", policy)

    assert rule is not None
    assert rule.copyright == "Default"


def test_match_rule_returns_none_when_ungoverned():
    policy = Policy(rules=(Rule(paths=("src/**",), copyright="Src", license="MIT"),), default=None)

    assert match_rule("other/file.py", policy) is None


def test_resolve_license_and_copyright_precedence_rule_over_default_over_cli():
    policy = Policy(
        rules=(Rule(paths=("src/**",), copyright=None, license="MIT"),),
        default=Rule(paths=(), copyright="Default Holder", license="GPL-3.0-or-later"),
    )

    copyright_, license_ = resolve_license_and_copyright(
        "src/main.py", policy, cli_copyright="CLI Holder", cli_license="Apache-2.0"
    )

    # license comes from the matched rule; copyright falls through to default
    assert license_ == "MIT"
    assert copyright_ == "Default Holder"


def test_resolve_license_and_copyright_falls_back_to_cli():
    copyright_, license_ = resolve_license_and_copyright(
        "anything.py", policy=None, cli_copyright="CLI Holder", cli_license="Apache-2.0"
    )

    assert copyright_ == "CLI Holder"
    assert license_ == "Apache-2.0"


def test_is_covered_file_excludes_license_sidecar():
    assert not is_covered_file("data/foo.json.license")


def test_is_covered_file_excludes_licenses_dir():
    assert not is_covered_file("LICENSES/MIT.txt")


def test_is_covered_file_includes_regular_source():
    assert is_covered_file("src/main.py")


def test_is_covered_file_excludes_symlinks(git_repo):
    (git_repo / "target_dir").mkdir()
    (git_repo / "target_dir" / "file.txt").write_text("content\n")
    (git_repo / "link_to_dir").symlink_to("target_dir")

    assert not is_covered_file("link_to_dir")


def test_check_policy_violations_skips_ungoverned_files(git_repo, commit_files):
    commit_files(git_repo, {"other.py": "x = 1\n"})
    policy = Policy(rules=(Rule(paths=("src/**",), copyright="X", license="MIT"),), default=None)

    violations = check_policy_violations(["other.py"], policy)

    assert violations == []


# REUSE-IgnoreStart
# This fixture embeds literal "SPDX-FileCopyrightText: ..." lines as fake file
# content for a temp test repo; without the markers above/below, `reuse` would
# mistake them for this file's own header when linting reuseify.
def test_get_declared_spdx_info_handles_multiline_copyright(git_repo, commit_files):
    commit_files(
        git_repo,
        {
            "multi.py": (
                "# SPDX-FileCopyrightText: 2026 Alice\n"
                "# SPDX-FileCopyrightText: 2026 Bob\n"
                "# SPDX-License-Identifier: MIT\n"
                "x = 1\n"
            )
        },
    )

    info = get_declared_spdx_info()

    assert "Alice" in info["multi.py"].copyright
    assert "Bob" in info["multi.py"].copyright


def test_get_declared_spdx_info_handles_three_line_copyright_block(git_repo, commit_files):
    commit_files(
        git_repo,
        {
            "multi.py": (
                "# SPDX-FileCopyrightText: 2026 Alice\n"
                "# SPDX-FileCopyrightText: 2026 Bob\n"
                "# SPDX-FileCopyrightText: 2026 Carol\n"
                "# SPDX-License-Identifier: MIT\n"
                "x = 1\n"
            )
        },
    )

    info = get_declared_spdx_info()

    assert "Alice" in info["multi.py"].copyright
    assert "Bob" in info["multi.py"].copyright
    assert "Carol" in info["multi.py"].copyright


# REUSE-IgnoreEnd


def test_get_declared_spdx_info_handles_bare_unwrapped_copyright_value(monkeypatch):
    fake_stdout = "FileName: ./weird.py\nLicenseInfoInFile: MIT\nFileCopyrightText: Some Holder\n"

    def fake_run(cmd, *args, **kwargs):
        return subprocess.CompletedProcess(cmd, returncode=0, stdout=fake_stdout, stderr="")

    monkeypatch.setattr(policy_module.subprocess, "run", fake_run)

    info = get_declared_spdx_info()

    assert info["weird.py"].copyright == "Some Holder"
