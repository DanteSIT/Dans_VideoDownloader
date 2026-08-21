"""
Launcher for the YouTube Downloader.

Run from the project root with:  python main.py
Works whether or not the package is pip-installed (it adds src/ to the
path automatically). This is also the file PyInstaller uses to build
the executable — see README.md.
"""

import sys
from pathlib import Path

# Make `src/` importable so the app runs even without `pip install -e .`
SRC_DIR = Path(__file__).resolve().parent / "src"
if SRC_DIR.is_dir() and str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from yt_downloader.app import main

if __name__ == "__main__":
    raise SystemExit(main())
