# SPDX-FileCopyrightText: 2026 Sahil Jhawar
# SPDX-FileContributor: Sahil Jhawar
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Load and apply reuseify.toml, a per-path licensing policy for reuseify."""

import fnmatch
import re
import stat
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path

# Files the REUSE spec itself never requires licensing info on: license text
# sidecars, LICENSE/COPYING files, and REUSE.toml. Mirrors reuse.covered_files.
_NON_COVERED_FILE_PATTERNS = (
    re.compile(r"^LICEN[CS]E([-.].*)?$"),
    re.compile(r"^COPYING([-.].*)?$"),
    re.compile(r".*\.license$"),
    re.compile(r"^REUSE\.toml$"),
)


def is_covered_file(filepath: str) -> bool:
    """Return False for files REUSE does not require licensing info on."""
    path = Path(filepath)
    if "LICENSES" in path.parts:
        return False
    if any(pattern.match(path.name) for pattern in _NON_COVERED_FILE_PATTERNS):
        return False
    try:
        # lstat, not stat: a symlink (e.g. to a directory) must not be
        # resolved through to its target before checking it out.
        stat_result = path.lstat()
    except OSError:
        return True
    if stat.S_ISLNK(stat_result.st_mode):
        return False
    return stat_result.st_size != 0


@dataclass(frozen=True)
class Rule:
    """A single reuseify.toml rule (or the [default] section)."""

    paths: tuple[str, ...]
    copyright: str | None
    license: str | None


@dataclass(frozen=True)
class Policy:
    """A parsed reuseify.toml: an ordered list of path rules plus an optional default."""

    rules: tuple[Rule, ...]
    default: Rule | None


@dataclass
class DeclaredInfo:
    """A file's currently declared license identifiers and copyright text."""

    licenses: list[str]
    copyright: str = ""


@dataclass(frozen=True)
class PolicyViolation:
    """A file whose declared license/copyright does not match its assigned rule."""

    filepath: str
    expected_license: str | None
    expected_copyright: str | None
    actual_licenses: tuple[str, ...]
    actual_copyright: str


def load_policy(path: str = "reuseify.toml") -> Policy | None:
    """Load reuseify.toml from *path* if it exists, else return None."""
    config_path = Path(path)
    if not config_path.is_file():
        return None

    with config_path.open("rb") as f:
        data = tomllib.load(f)

    rules = tuple(
        Rule(
            paths=tuple([raw["paths"]] if isinstance(raw["paths"], str) else raw["paths"]),
            copyright=raw.get("copyright"),
            license=raw.get("license"),
        )
        for raw in data.get("rules", [])
    )

    default_data = data.get("default")
    default = (
        Rule(paths=(), copyright=default_data.get("copyright"), license=default_data.get("license"))
        if default_data
        else None
    )

    return Policy(rules=rules, default=default)


def _specificity(pattern: str) -> tuple[int, int]:
    """Score a glob pattern: literal (no wildcard) paths outrank wildcard ones,
    and among the same kind, longer patterns are considered more specific.
    """
    has_wildcard = any(ch in pattern for ch in "*?[")
    return (0 if has_wildcard else 1, len(pattern))


def match_rule(filepath: str, policy: Policy) -> Rule | None:
    """Return the most specific rule in *policy* whose paths match *filepath*.

    A rule matching the file's exact path (or a longer/more specific glob) takes
    precedence over one matching a broader directory. Falls back to the policy's
    [default] rule, or None if nothing matches and there is no default.
    """
    best: Rule | None = None
    best_score = (-1, -1)
    for rule in policy.rules:
        for pattern in rule.paths:
            if fnmatch.fnmatch(filepath, pattern):
                score = _specificity(pattern)
                if score >= best_score:
                    best_score = score
                    best = rule
    return best if best is not None else policy.default


def resolve_license_and_copyright(
    filepath: str,
    policy: Policy | None,
    cli_copyright: str | None,
    cli_license: str | None,
) -> tuple[str | None, str | None]:
    """Resolve the (copyright, license) to annotate *filepath* with.

    Precedence per field: the matched rule's value, then the policy default's
    value, then the CLI-supplied fallback value.
    """
    rule = match_rule(filepath, policy) if policy else None
    default = policy.default if policy else None

    copyright_ = (
        (rule.copyright if rule else None)
        or (default.copyright if default else None)
        or cli_copyright
    )
    license_ = (
        (rule.license if rule else None) or (default.license if default else None) or cli_license
    )
    return copyright_, license_


def get_declared_spdx_info() -> dict[str, DeclaredInfo]:
    """Return each file's currently declared licenses and copyright text.

    Parses the output of `reuse spdx`, which is a stable, public CLI (unlike
    reuse's internal header-parsing APIs).
    """
    result = subprocess.run(["reuse", "spdx"], capture_output=True, text=True)

    info: dict[str, DeclaredInfo] = {}
    current_file: str | None = None
    in_copyright_block = False
    copyright_lines: list[str] = []

    for line in result.stdout.splitlines():
        if in_copyright_block:
            assert current_file is not None
            if line.endswith("</text>"):
                copyright_lines.append(line[: -len("</text>")])
                info[current_file].copyright = "\n".join(copyright_lines)
                in_copyright_block = False
            else:
                copyright_lines.append(line)
            continue

        if line.startswith("FileName:"):
            current_file = line.split(":", 1)[1].strip()
            if current_file.startswith("./"):
                current_file = current_file[2:]
            info[current_file] = DeclaredInfo(licenses=[])
        elif line.startswith("LicenseInfoInFile:") and current_file:
            info[current_file].licenses.append(line.split(":", 1)[1].strip())
        elif line.startswith("FileCopyrightText:") and current_file:
            value = line.split(":", 1)[1].strip()
            # A file with no copyright notice gets the bare sentinel "NONE",
            # with no <text>...</text> wrapper.
            if value in ("NONE", "NOASSERTION"):
                info[current_file].copyright = ""
            elif value.startswith("<text>"):
                value = value[len("<text>") :]
                if value.endswith("</text>"):
                    info[current_file].copyright = value[: -len("</text>")]
                else:
                    copyright_lines = [value]
                    in_copyright_block = True
            else:
                info[current_file].copyright = value

    return info


def check_policy_violations(files: list[str], policy: Policy) -> list[PolicyViolation]:
    """Check *files* against *policy*, returning any license/copyright mismatches.

    Files that match no rule and fall outside the policy's [default] are not
    governed by the policy and are silently skipped.
    """
    declared = get_declared_spdx_info()
    violations: list[PolicyViolation] = []

    for filepath in files:
        rule = match_rule(filepath, policy)
        if rule is None:
            continue

        actual = declared.get(filepath, DeclaredInfo(licenses=[]))
        actual_licenses = tuple(actual.licenses)
        actual_copyright = actual.copyright

        license_mismatch = rule.license is not None and rule.license not in actual_licenses
        copyright_mismatch = rule.copyright is not None and rule.copyright not in actual_copyright

        if license_mismatch or copyright_mismatch:
            violations.append(
                PolicyViolation(
                    filepath=filepath,
                    expected_license=rule.license,
                    expected_copyright=rule.copyright,
                    actual_licenses=actual_licenses,
                    actual_copyright=actual_copyright,
                )
            )

    return violations
