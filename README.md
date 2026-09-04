<!--
SPDX-FileCopyrightText: 2026 Sahil Jhawar
SPDX-FileContributor: Sahil Jhawar

SPDX-License-Identifier: GPL-3.0-or-later
-->

<!--
-->

# reuseify
[![PyPi](https://badge.fury.io/py/reuseify.svg)](https://badge.fury.io/py/reuseify)
[![Python version](https://img.shields.io/pypi/pyversions/reuseify.svg)](https://badge.fury.io/py/reuseify)
[![REUSE status](https://api.reuse.software/badge/github.com/sahiljhawar/reuseify)](https://api.reuse.software/info/github.com/sahiljhawar/reuseify)
[![Coverage Status](https://coveralls.io/repos/github/sahiljhawar/reuseify/badge.svg?branch=main)](https://coveralls.io/github/sahiljhawar/reuseify?branch=main)


Automate [REUSE](https://reuse.software/) license annotation from git history.

`reuseify` inspects which files are missing license headers (via `reuse lint`),
looks up their git commit authors, and applies `reuse annotate`, all from a single CLI.

## Installation

```bash
uv pip install .
```

## Usage

The workflow is two steps: collect authors → annotate files.

### Step 1: collect authors

```bash
reuseify get-authors [OPTIONS]
```

Runs `reuse lint`, finds every file missing a license header, looks up its git
commit authors, and writes a JSON file:

```json
{
  "src/foo.py": ["Alice", "Bob"],
  "src/bar.c":  ["Alice"],
  "src/new.py": [] #NOT_IN_GIT
}
```

| Option                 | Short | Default                       | Description                                                            |
| ---------------------- | ----- | ----------------------------- | ---------------------------------------------------------------------- |
| `--output`             | `-o`  | `reuse_annotate_authors.json` | Output JSON file                                                       |
| `--include-not-in-git` | `-i`  | off                           | Include files with no git history (empty author list)                  |
| `--exclude PATTERN`    | `-e`  |                               | Extra glob pattern to exclude (matched per path component, repeatable) |

Files matching built-in patterns are always excluded:
`__pycache__`, `.venv`, `venv`, `.env`, `env`, `.git`, `.vscode`, `.idea`,
`*.egg-info`, `*.pyc`, `dist`, `build`, `node_modules`, `.tox`,
`.mypy_cache`, `.pytest_cache`, `.ruff_cache`.

Files ignored by `.gitignore` are also excluded
automatically.

**Examples**

```bash
# defaults
reuseify get-authors

# custom output path + include untracked files
reuseify get-authors --output authors.json --include-not-in-git

# add an extra exclusion pattern
reuseify get-authors --exclude reports --exclude "*.tmp"
```

---

### Step 2: annotate files

```bash
reuseify annotate [OPTIONS] [REUSE ANNOTATE FLAGS...]
```

Reads the JSON file from [Step 1](#step-1-collect-authors) and calls `reuse annotate` for every file.
`--contributor` flags are injected automatically from the JSON data. Both `--copyright` and
`--license` must still be passed, otherwise the command fails fast, since `reuse lint`
requires both a copyright notice and a license identifier (contributor alone isn't enough).
All unrecognised flags are forwarded verbatim to `reuse annotate`, giving you
full control over `--copyright`, `--license`, `--year`, `--style`,
`--fallback-dot-license`, `--force-dot-license`, `--skip-unrecognised`, etc.

| Option                       | Short | Default                       | Description                                                        |
| ---------------------------- | ----- | ----------------------------- | ------------------------------------------------------------------ |
| `--input`                    | `-i`  | `reuse_annotate_authors.json` | JSON file from `get-authors`                                       |
| `--default-contributor NAME` | `-d`  | none                          | Fallback contributor for `NOT_IN_GIT` files (repeatable)            |
| `--download`                 | `-D`  | off                           | Download missing license files (`reuse download --all`) after annotating |

Output is grouped: all successes first, then skips, then failures, then finally a summary.

### Examples

```bash
# basic
reuseify annotate \
    --copyright "2025 X-Men" \
    --license Apache-2.0 \
    --fallback-dot-license

# custom input + fallback contributor for untracked files
reuseify annotate \
    --input authors.json \
    --default-contributor "Charles Xavier" \
    --copyright "2025 X-Men" \
    --license Apache-2.0

# multiple default contributors
reuseify annotate \
    --default-contributor "Professor X" \
    --default-contributor "Cyclops" \
    --copyright "2025 X-Men" \
    --license MIT
```

### Check compliance: lint

```bash
reuseify lint [OPTIONS]
```

Runs `reuse lint` to find git-tracked files missing a REUSE header or
referencing a license whose text isn't in `LICENSES/`. If a `reuseify.toml`
policy file exists (see below), it also checks that each governed file's
*actual* declared license and copyright match its assigned rule, not just
that some valid header is present.

| Option                 | Short | Default | Description                                                            |
| ----------------------- | ----- | ------- | ------------------------------------------------------------------------ |
| `--include-not-in-git` | `-i`  | off     | Include files with no git history in the check                          |
| `--exclude PATTERN`    | `-e`  | none    | Extra glob pattern to exclude (matched per path component, repeatable)  |

Exit codes: `0` compliant, `1` REUSE or policy violations found, `2` an
underlying `reuse`/reuseify tool failure (never treated as "compliant").

## reuseify.toml: per-path license policy

For projects that use more than one license across different directories,
add a `reuseify.toml` at the project root. It replaces the need to pass
`--copyright`/`--license` on the command line, and turns `reuseify lint` into
a stricter check: it verifies each governed file has the *correct* license
for its path, not just *some* valid license.

```toml

[[rules]]
paths = ["src/**"]
copyright = "Sahil Jhawar"
license = "GPL-3.0-or-later"

[[rules]]
paths = ["vendor/**", "third_party/**"]
copyright = "Some Vendor"
license = "MIT"

# a rule matching an exact file always wins over a directory glob
[[rules]]
paths = ["vendor/special_file.py"]
copyright = "Sahil Jhawar"
license = "GPL-3.0-or-later"

[default]
copyright = "Sahil Jhawar"
license = "GPL-3.0-or-later"
```

- **`[[rules]]`**: `paths` is a glob (or list of globs) matched against the
  file's git-relative path. When a file matches more than one rule, the most
  specific one wins: an exact file path beats a directory glob, and among
  glob patterns, the longer one wins.
- **`[default]`**: used for any tracked file that matches no rule. Files
  matching neither a rule nor `[default]` are not governed by the policy and
  are ignored by both `lint` and `annotate`.
- Leave the year out of `copyright` (`"Sahil Jhawar"`, not `"2026 Sahil
  Jhawar"`): `reuse annotate` always prepends the current year itself, so
  including one produces a duplicated year in the header.

With a `reuseify.toml` in place, `reuseify annotate` no longer requires
`--copyright`/`--license` on the command line; each file is annotated with
its matched rule's values automatically:

```bash
reuseify get-authors
reuseify annotate --default-contributor "Charles Xavier"
```

Any `--copyright`/`--license` still passed on the command line is used only
as a fallback, for fields a matched rule or `[default]` leaves unset.

`paths` glob matching uses `fnmatch`, which is case-sensitive on POSIX/macOS
and case-insensitive on Windows. reuseify only targets POSIX/Unix/macOS
(see the classifiers in `pyproject.toml`), so write patterns case-exact with
forward slashes.

## Pre-commit hook

`reuseify` ships a [pre-commit](https://pre-commit.com) hook that runs `reuseify lint`
and fails the commit if any git-tracked file is missing a REUSE license header.

Add this to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/sahiljhawar/reuseify
    rev: 1.0.0  # use the latest tag
    hooks:
      - id: reuseify-lint
```

Then install it once per clone:

```bash
pre-commit install
```

## Disclaimer

> [!CAUTION]
> Use at your own risk. `reuse annotate` modifies files in place.

```bash
reuse annotate --help
```

This project is not affiliated with the REUSE project or its maintainers in any way.