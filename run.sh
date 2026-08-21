#!/usr/bin/env bash
#
# YouTube Downloader launcher.
#
# Safe to run directly (double-click / mark as executable):
#   - creates the virtualenv on first run
#   - installs Python dependencies with visible progress + ETA
#   - caches the large Qt wheel in .wheels/ with resume support,
#     so a dropped connection does not restart the download
#   - starts the application
#
# TWEAK: if your python3 lives elsewhere, edit PYTHON_BIN below.

set -euo pipefail
cd "$(dirname "$0")"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR=".venv"
PY="$VENV_DIR/bin/python"

# TWEAK: Qt wheel version cached locally for slow/flaky connections.
# Only used as a resumable pre-fetch on Linux x86_64; other platforms
# fall back to plain pip (which shows its own progress bar).
PYSIDE_VER="6.11.2"
PYSIDE_WHEEL_URL="https://files.pythonhosted.org/packages/0e/1a/84a84bbc75835ee88abdcb66eb875b8e1a21834af9b833bc1893f2c1bfaf/pyside6_essentials-${PYSIDE_VER}-cp310-abi3-manylinux_2_34_x86_64.whl"
WHEEL_FILE=".wheels/pyside6_essentials-${PYSIDE_VER}-cp310-abi3-manylinux_2_34_x86_64.whl"

# ── pretty stage output ──────────────────────────────────────────────────
now()  { date "+%H:%M:%S"; }
step() { printf '\n\033[1;36m==>\033[0m \033[1m[%s] %s\033[0m\n' "$(now)" "$*"; }
info() { printf '    \033[2m·\033[0m %s\n' "$*"; }

# ── 1. environment ───────────────────────────────────────────────────────
step "Environment"
info "python : $("$PYTHON_BIN" --version 2>&1)"
info "project: $(pwd)"

# ── 2. virtual environment ───────────────────────────────────────────────
step "Virtual environment"
if [ ! -x "$PY" ]; then
    info "creating $VENV_DIR (first run only)…"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
else
    info "$VENV_DIR already exists — skipping"
fi

# ── 3. dependencies ──────────────────────────────────────────────────────
NEED_QT=1; NEED_YTDLP=1
"$PY" -c "import PySide6"            2>/dev/null && NEED_QT=0
"$PY" -c "import yt_dlp"             2>/dev/null && NEED_YTDLP=0

if [ "$NEED_QT" = 0 ] && [ "$NEED_YTDLP" = 0 ]; then
    step "Dependencies"
    info "all present — skipping installs"
else
    step "Installing dependencies (download progress + ETA shown below)"
    "$PY" -m pip install --quiet --upgrade pip

    # Resumable pre-fetch of the big Qt wheel (~80 MB). Safe to interrupt:
    # re-running ./run.sh continues where it left off.
    if [ "$NEED_QT" = 1 ] && command -v wget >/dev/null 2>&1 \
       && [ "$(uname -s)-$(uname -m)" = "Linux-x86_64" ]; then
        step "Fetching Qt runtime wheel (~80 MB, resumable)"
        mkdir -p .wheels
        wget -c --show-progress --progress=bar:force:noscroll \
             --timeout=45 --tries=200 \
             "$PYSIDE_WHEEL_URL" -O "$WHEEL_FILE" || true
    fi

    if [ "$NEED_QT" = 1 ]; then
        if [ -f "$WHEEL_FILE" ] && "$PY" -m zipfile -t "$WHEEL_FILE" >/dev/null 2>&1; then
            info "installing Qt from cached wheel ✓"
            "$PY" -m pip install --timeout 60 --retries 10 "$WHEEL_FILE"
        else
            info "cached wheel unavailable — downloading via pip"
            "$PY" -m pip install --timeout 60 --retries 10 PySide6-Essentials
        fi
    fi

    if [ "$NEED_YTDLP" = 1 ]; then
        "$PY" -m pip install --timeout 60 --retries 10 yt-dlp
    fi
fi

# ── 4. project itself ────────────────────────────────────────────────────
step "Project install"
"$PY" -m pip install --quiet -e .
info "yt-downloader installed in editable mode"

# ── 5. pre-flight checks ─────────────────────────────────────────────────
step "Pre-flight checks"
QT_LIB="$("$PY" -c "import sys; sys.path.insert(0, 'src'); from yt_downloader.qt import QT_LIB; print(QT_LIB)" 2>/dev/null || echo unknown)"
info "Qt binding : $QT_LIB"
if command -v ffmpeg >/dev/null 2>&1; then
    info "ffmpeg     : found ✓"
else
    info "ffmpeg     : ⚠ NOT FOUND — video merge / MP3 conversion will fail"
fi

# ── 6. launch ────────────────────────────────────────────────────────────
step "Launching YouTube Downloader"
exec "$PY" main.py "$@"
