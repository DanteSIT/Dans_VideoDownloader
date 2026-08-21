#!/usr/bin/env bash
#
# YouTube Downloader launcher.
#
# Safe to run directly (double-click / mark as executable):
#   - creates the virtualenv on first run
#   - installs Python dependencies if they are missing
#   - starts the application
#
# TWEAK: if your python3 is elsewhere, edit the PYTHON_BIN line below.

set -euo pipefail
cd "$(dirname "$0")"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR=".venv"
PY="$VENV_DIR/bin/python"

# ── 1. virtual environment ───────────────────────────────────────────────
if [ ! -x "$PY" ]; then
    echo "==> Creating virtual environment…"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# ── 2. dependencies (skipped when already installed) ─────────────────────
if ! "$PY" -c "import PySide6, yt_dlp" >/dev/null 2>&1; then
    echo "==> Installing dependencies…"
    "$PY" -m pip install --quiet --upgrade pip
    "$PY" -m pip install --quiet -e .
fi

# ── 3. launch ────────────────────────────────────────────────────────────
exec "$PY" main.py "$@"
