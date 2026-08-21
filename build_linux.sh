#!/usr/bin/env bash
# Build a standalone Linux executable with PyInstaller.
# Output: dist/VideoDownloader (single file)
set -euo pipefail

cd "$(dirname "$0")"

PY=".venv/bin/python"

if [ ! -x "$PY" ]; then
    echo "No .venv found — run ./run.sh once first."
    exit 1
fi

"$PY" -m pip install --quiet pyinstaller

echo "Building Linux binary…"
"$PY" -m PyInstaller \
    --onefile \
    --windowed \
    --name VideoDownloader \
    --collect-submodules yt_dlp \
    main.py

echo ""
echo "Done → $(pwd)/dist/VideoDownloader"
