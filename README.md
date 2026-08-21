# Video Downloader (Qt)

Modern rebuild of the original single-file Tkinter app, split into a Qt-free
core and a PySide6 GUI. Renamed from "YouTube Downloader" because it works
with any site yt-dlp supports.

## Features

- Works with any site yt-dlp supports — YouTube, Facebook, Twitter/X,
  TikTok, Instagram, Vimeo, Twitch and 1000+ more (see yt-dlp's
  supported-sites list). Quality detection depends on what each site exposes.
- URL input with clipboard paste and thumbnail preview
- Quality picker built from real available formats (with sizes)
- Audio-only extraction (320 kbps MP3)
- Playlist support
- VR / 360° video detection
- Batch queue with sequential processing
- Download history (capped at 200 entries)
- Progress bar with speed / ETA / downloaded bytes
- Terminal-style output log: measured DNS/TCP/TLS handshake stats,
  yt-dlp's own messages, live speed/ETA/bytes line
- Automatic fallback format retry on failure
- Missing dependency check for `ffmpeg`

### Where files end up

```
Downloads/
├── My Video Title/
│   ├── My Video Title [1080p].mp4
│   └── My Video Title.txt        <- title, URL, length, views, description
├── Some Song/
│   ├── Some Song.mp3
│   └── Some Song.txt
└── Cool Playlist/
    ├── 001 - First Video.mp4
    ├── 002 - Second Video.mp4
    └── Cool Playlist.txt         <- one file for the whole playlist
```

## Project layout

```
src/video_downloader/
├── app.py               # QApplication bootstrap + dependency prompt
├── core/                # Pure logic — no Qt imports allowed here
│   ├── config.py        # Paths & constants
│   ├── models.py        # DownloadRequest / QueueItem / HistoryEntry dataclasses
│   ├── utils.py         # Formatting helpers, folder opener
│   ├── history.py       # HistoryStore (JSON persistence)
│   ├── dependencies.py  # System tool checks + installers
│   └── downloader.py    # yt-dlp wrapper: fetch info, build opts, download
└── gui/
    ├── theme.py         # Dark palette + global QSS stylesheet
    ├── workers.py       # QThread workers bridging core -> signals
    ├── main_window.py   # QMainWindow with the three tabs
    └── tabs/
        ├── download_tab.py
        ├── queue_tab.py
        └── history_tab.py
```

The rule that keeps this maintainable: **`gui` may import from `core`, but
`core` never imports from `gui`**. All cross-thread communication happens
through Qt signals defined in `gui/workers.py`.

## Run

### Easiest — the launcher script

```bash
./run.sh
```

Creates the virtualenv and installs dependencies automatically on first
run, then starts the app. Mark it executable once (`chmod +x run.sh`) or
point your desktop launcher / file manager at it.

### Manual

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e .
python main.py                 # or: video-downloader  /  python -m video_downloader
```

System requirement: `ffmpeg` on PATH (merge/MP3 conversion).

### Qt binding

The GUI prefers **PySide6** but automatically falls back to **PyQt5**
if PySide6 isn't installed (see `src/video_downloader/qt.py`), so it runs
on machines that already have either binding.

## Build an executable

PyInstaller cannot cross-compile — build on the OS you target.

### Linux

```bash
./build_linux.sh          # → dist/VideoDownloader
```

### Windows (on a Windows machine)

```bat
py -m venv .venv
.venv\Scripts\activate
pip install . pyinstaller
pyinstaller --onefile --windowed --name VideoDownloader --collect-submodules yt_dlp main.py
:: → dist\VideoDownloader.exe
```

### Both at once (GitHub Actions)

Push a version tag and the included workflow builds both binaries:

```bash
git tag v2.1.0 && git push --tags
```

Artifacts (`VideoDownloader-linux`, `VideoDownloader-windows.exe`) appear
under the workflow run. ffmpeg is bundled next to the executable so end
users don't need to install anything.
