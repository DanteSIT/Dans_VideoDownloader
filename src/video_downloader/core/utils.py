"""
Small pure helpers — string formatting and "open folder in file
manager". No yt-dlp or Qt logic here.
"""

import os
import re
import subprocess
import sys
import webbrowser

ANSI_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", str(text))


def format_file_size(size_bytes: int | float | None) -> str:
    if not size_bytes:
        return "Unknown"
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def format_duration(duration: int | float | None) -> str:
    if not duration:
        return "—"
    total = int(duration)
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"


def open_folder(path: str) -> None:
    path = os.path.realpath(path)
    if not os.path.isdir(path):
        return
    if sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def open_url(url: str) -> None:
    webbrowser.open(url)
