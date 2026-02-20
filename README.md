<!--
SPDX-FileCopyrightText: 2026 Sahil Jhawar
SPDX-FileContributor: Sahil Jhawar

SPDX-License-Identifier: GPL-3.0-or-later
-->

<!--
-->

# reuseify

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
`--contributor` flags are injected automatically from the JSON data.
All unrecognised flags are forwarded verbatim to `reuse annotate`, giving you
full control over `--copyright`, `--license`, `--year`, `--style`,
`--fallback-dot-license`, `--force-dot-license`, `--skip-unrecognised`, etc.

| Option                       | Short | Default                       | Description                                              |
| ---------------------------- | ----- | ----------------------------- | -------------------------------------------------------- |
| `--input`                    | `-i`  | `reuse_annotate_authors.json` | JSON file from `get-authors`                             |
| `--default-contributor NAME` | `-d`  | —                             | Fallback contributor for `NOT_IN_GIT` files (repeatable) |

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

## Disclaimer

> [!CAUTION]
> Use at your own risk. `reuse annotate` modifies files in place.

```bash
reuse annotate --help
```

This project is not affiliated with the REUSE project or its maintainers in any way.