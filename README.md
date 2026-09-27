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

`reuseify annotate` and `reuseify lint` both require a
[`reuseify.toml`](#reuseifytoml-per-path-license-policy) policy file: it is
the only source of the copyright/license used to annotate and lint files.
There's no `--copyright`/`--license` CLI flag; if `reuseify.toml` doesn't
exist yet, running either command creates an empty one and tells you what to
add to it.

```bash
cat > reuseify.toml <<'EOF'
[default]
copyright = "2025 X-Men"
license = "MIT"
EOF

reuseify annotate
```

When no `reuse_annotate_authors.json` file is present, `annotate` looks up
authors from git history directly, no separate step needed.

If you want to inspect or hand-edit the author list before annotating (or
cache it for reuse across runs), use the two-step workflow instead: collect
authors → annotate files.

### Step 1 (optional): collect authors

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

Requires a [`reuseify.toml`](#reuseifytoml-per-path-license-policy); it's
created empty if missing (see above). `--copyright`/`--license` are not
accepted as CLI flags: they're always resolved per file from `reuseify.toml`,
and a file whose matched rule/`[default]` doesn't specify both just fails with
a clear message, instead of falling back to a CLI value that could disagree
with what other files in the project use.

If `--input` (or its default, `reuse_annotate_authors.json`) exists, reads
authors from that JSON file. Otherwise, looks up authors from git history
directly, the same lookup [Step 1](#step-1-optional-collect-authors) does, so
running `get-authors` first is optional. Either way, `--contributor` is
injected automatically per file, plus any extra names from `--contributor`
on the command line (see below). All unrecognised flags are forwarded
verbatim to `reuse annotate`, giving you full control over `--year`,
`--style`, `--fallback-dot-license`, `--force-dot-license`,
`--skip-unrecognised`, etc.

| Option                       | Short | Default                       | Description                                                        |
| ---------------------------- | ----- | ----------------------------- | ------------------------------------------------------------------ |
| `--input`                    | `-i`  | `reuse_annotate_authors.json` | JSON file from `get-authors`, if present; otherwise authors are read from git history directly |
| `--contributor NAME`         | `-n`  | none                          | Extra contributor(s) (repeatable). In batch mode, added on top of each file's discovered authors and also covers `NOT_IN_GIT` files. In direct-file mode, the only source of contributors |
| `--default-contributor NAME` | `-d`  | none                          | Fallback contributor for `NOT_IN_GIT` files (repeatable), used when `--contributor` isn't given |
| `--download` / `--no-download` | `-D`  | on                          | Download missing license files (`reuse download --all`) after annotating |

Output is grouped: all successes first, then skips, then failures, then finally a summary.

License downloading runs automatically after every annotate; pass
`--no-download` to skip it. A download failure is printed in red but never
fails the annotate run itself, since annotating the files is the point of the
command and a missing `LICENSES/*.txt` is a separate, recoverable problem.

Passing `--input` explicitly with a file that doesn't exist is still treated
as an error (it fails fast and points you at `get-authors`), since that's
almost always a typo rather than a request to fall back to git history.

### Examples

```bash
# basic (copyright/license come from reuseify.toml)
reuseify annotate --fallback-dot-license

# custom input + fallback contributor for untracked files
reuseify annotate \
    --input authors.json \
    --default-contributor "Charles Xavier"

# multiple default contributors
reuseify annotate \
    --default-contributor "Professor X" \
    --default-contributor "Cyclops"
```

### Check compliance: lint

```bash
reuseify lint [OPTIONS]
```

Runs `reuse lint` to find git-tracked files missing a REUSE header or
referencing a license whose text isn't in `LICENSES/`. Requires a
`reuseify.toml` (see below; created empty if missing) and also checks that
each governed file's *actual* declared license and copyright match its
assigned rule, not just that some valid header is present. Files matching no
rule and no `[default]` are still checked for a REUSE header, just not for a
*specific* license/copyright.

| Option                 | Short | Default | Description                                                            |
| ----------------------- | ----- | ------- | ------------------------------------------------------------------------ |
| `--include-not-in-git` | `-i`  | off     | Include files with no git history in the check                          |
| `--exclude PATTERN`    | `-e`  | none    | Extra glob pattern to exclude (matched per path component, repeatable)  |

Exit codes: `0` compliant, `1` REUSE or policy violations found, `2` an
underlying `reuse`/reuseify tool failure (never treated as "compliant").

## reuseify.toml: per-path license policy

`reuseify.toml` at the project root is required by `annotate`/`lint`; it's
the only source of the copyright/license used to annotate and lint files, and
it also turns `reuseify lint` into a stricter check: it verifies each
governed file has the *correct* license for its path, not just *some* valid
license. Projects with a single license across the whole tree just need a
`[default]`; use `[[rules]]` too for projects with more than one.

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

Each file is annotated with its matched rule's values automatically:

```bash
reuseify get-authors
reuseify annotate --default-contributor "Charles Xavier"
```

A file whose matched rule leaves a field unset falls through to `[default]`
for that field; if neither specifies it, that file fails with a clear message
rather than silently picking up some other value.

### Annotating specific files directly

Pass one or more file paths on the command line to annotate just those files,
skipping the `reuse lint`/git-history discovery step entirely. There's no
author auto-detection for files named this way, so use `--contributor`
(repeatable) to set one; it's optional, same as in `reuse annotate` itself,
so omitting it just annotates without a `--contributor` line.
`--copyright`/`--license` still resolve from `reuseify.toml` as above.

```bash
reuseify annotate --contributor "Sahil Jhawar" src/main.py
```

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
    rev: 1.1.0  # use the latest tag
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
