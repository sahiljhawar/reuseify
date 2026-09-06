#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Sahil Jhawar
# SPDX-FileContributor: Sahil Jhawar
#
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

uv lock
git add uv.lock
