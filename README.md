# YouTube Downloader (Qt)

Modern rebuild of the original single-file Tkinter app, split into a Qt-free
core and a PySide6 GUI.

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
- Automatic fallback format retry on failure
- Missing dependency check for `ffmpeg` / `atomicparsley`

## Project layout

```
src/yt_downloader/
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
python main.py                 # or: yt-downloader  /  python -m yt_downloader
```

System requirement: `ffmpeg` on PATH (merge/MP3 conversion).

### Qt binding

The GUI prefers **PySide6** but automatically falls back to **PyQt5**
if PySide6 isn't installed (see `src/yt_downloader/qt.py`), so it runs
on machines that already have either binding.

## Build an executable (PyInstaller)

```bash
source .venv/bin/activate
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name YouTubeDownloader main.py
```

The single-file binary ends up at `dist/YouTubeDownloader`
(`dist/YouTubeDownloader.exe` on Windows). Distribute that file; users
still need `ffmpeg` installed on their system.
