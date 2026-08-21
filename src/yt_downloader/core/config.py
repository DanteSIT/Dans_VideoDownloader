"""
App-wide constants: window size, quality presets, paths.

START HERE if you want to change default behaviour — everything in this
file is safe to tweak and affects the whole app.
"""

import os
from pathlib import Path

APP_NAME = "YouTube Downloader"
# TWEAK: text shown in the red header bar
APP_HEADER = "▶  YOUTUBE DOWNLOADER"
APP_AUTHOR = "by Dante Lespoir"

# TWEAK: maximum entries kept in download_history.json
MAX_HISTORY_ENTRIES = 200

# TWEAK: thumbnail preview size (width, height) in pixels
THUMBNAIL_SIZE = (176, 99)

# TWEAK: window size / minimum size
WINDOW_MIN = (560, 640)
WINDOW_DEFAULT = (680, 800)

# TWEAK: resolutions scanned when building the quality dropdown 240p ~ 8k
RESOLUTIONS = [4320, 2160, 1440, 1080, 720, 480, 360, 240]

# TWEAK: qualities offered for playlists (no per-video formats there)
DEFAULT_QUALITIES = ["Best Available", "1080p", "720p", "480p", "360p"]


def default_save_dir() -> str:
    """Default download folder — TWEAK this to change where files go."""
    return str(Path(os.path.expanduser("~")) / "home/dante/Videos/")


def config_dir() -> Path:
    base = os.environ.get("YT_DOWNLOADER_CONFIG_DIR")
    if base:
        return Path(base)
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", str(Path.home()))) / APP_NAME.replace(" ", "")
    return Path.home() / ".config" / "youtube-downloader"


def history_file() -> Path:
    return config_dir() / "download_history.json"
