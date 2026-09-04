# SPDX-FileCopyrightText: 2026 Sahil Jhawar
# SPDX-FileContributor: Sahil Jhawar
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Smoke test for the installed `reuseify` console-script entry point."""

import subprocess
import sys


def test_installed_console_script_runs():
    result = subprocess.run(["reuseify", "--help"], capture_output=True, text=True, check=False)
    assert result.returncode == 0
    assert "reuseify" in result.stdout.lower() or "Usage" in result.stdout


def test_module_entrypoint_runs():
    result = subprocess.run(
        [sys.executable, "-m", "reuseify.cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
