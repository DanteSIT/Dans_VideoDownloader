"""
yt-dlp wrapper — the actual download engine, no GUI code here.

Everything yt-dlp related lives in this file:
  - fetch_info()      : URL -> VideoInfo (formats, VR flag, qualities)
  - build_opts()      : turns a DownloadRequest into yt-dlp options
  - download()        : runs the download with fallback retry, then
                        writes a "<title>.txt" info file next to it

Layout on disk:
  single video/audio -> <save>/<Video Title>/<file>
  playlist           -> <save>/<Playlist Title>/ (one .txt for the whole
                        playlist, not per video)

TWEAK points: MP3 bitrate, filename templates (_outtmpl), format selectors.
"""

from __future__ import annotations

import os
import re
import shutil
from collections.abc import Callable

import yt_dlp

from .config import RESOLUTIONS
from .models import DownloadRequest, VideoInfo
from .utils import format_duration, format_file_size, strip_ansi

FetchLog = Callable[[str], None]
CancelCheck = Callable[[], bool]


def find_js_runtime() -> str | None:
    """YouTube needs a JavaScript runtime for its challenges.
    yt-dlp only enables deno by default — pick whichever we can find."""
    # TWEAK: order of preferred JS runtimes
    for name in ("deno", "node", "bun", "quickjs"):
        if shutil.which(name):
            return name
    return None


def _apply_js_runtime(opts: dict) -> None:
    runtime = find_js_runtime()
    if runtime:
        opts["js_runtimes"] = {runtime: {}}


class _SignalLogger:
    """Routes yt-dlp's own terminal messages into the GUI log.

    Pass any object with debug/info/warning/error methods as the
    "logger" yt-dlp option — that is what makes the app behave like a
    real terminal during extraction. ANSI color codes are stripped so
    the QTextEdit doesn't show raw escape sequences.
    """

    def __init__(self, emit: Callable[[str, str], None]) -> None:
        self._emit = emit

    def debug(self, msg: str) -> None:
        msg = strip_ansi(msg)
        if msg.startswith("[debug]"):
            return
        self._emit(msg, "debug")

    def info(self, msg: str) -> None:
        self._emit(strip_ansi(msg), "info")

    def warning(self, msg: str) -> None:
        msg = strip_ansi(msg)
        self._emit(msg, "warn")
        if "JavaScript runtime" in msg:
            self._emit(
                "  ↳ tip: install Deno (docs.deno.com) or Node.js so all"
                " YouTube formats stay available",
                "info",
            )

    def error(self, msg: str) -> None:
        self._emit(strip_ansi(msg), "err")


class DownloadError(Exception):
    pass


def fetch_info(url: str, playlist: bool, ydl_logger=None) -> VideoInfo:
    opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": not playlist,
        "nocheckcertificate": True,
        "extract_flat": playlist,
    }
    if ydl_logger is not None:
        opts["logger"] = ydl_logger
    _apply_js_runtime(opts)
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if info is None:
        raise DownloadError("Could not extract video info.")
    return analyze_info(info)


def analyze_info(info: dict) -> VideoInfo:
    is_playlist = info.get("_type") == "playlist"
    vi = VideoInfo(raw=info, is_playlist=is_playlist)
    if not is_playlist:
        vi.is_vr = _detect_vr(info)
        vi.qualities, vi.sizes = _available_qualities(info)
    return vi


def _detect_vr(info: dict) -> bool:
    tags = info.get("tags") or []
    title = info.get("title", "").lower()
    projection = str(info.get("projection", "")).lower()
    formats = info.get("formats") or []
    return bool(
        info.get("spherical")
        or projection in ("equirectangular", "360", "vr180")
        or any("360" in str(t).lower() or "vr" in str(t).lower() for t in tags)
        or "360" in title
        or any(
            str(f.get("format_note", "")).lower() in ("360", "vr", "equirectangular")
            for f in formats
        )
    )


def _available_qualities(info: dict) -> tuple[list[str], dict[str, int]]:
    qualities: list[str] = []
    sizes: dict[str, int] = {}
    formats = info.get("formats") or []
    for res in RESOLUTIONS:
        matching = [f for f in formats if f.get("height") == res]
        if matching:
            label = f"{res}p"
            qualities.append(label)
            sizes[label] = max(f.get("filesize") or 0 for f in matching)
    qualities.sort(key=lambda q: int(q[:-1]), reverse=True)
    return qualities, sizes


def format_table(vi: VideoInfo) -> str:
    lines = [f"TITLE : {vi.title}", "─" * 60]
    if vi.is_vr:
        lines.append("⚠  VR / 360° video detected")
    for res in RESOLUTIONS:
        label = f"{res}p"
        if label in vi.sizes:
            size = vi.sizes[label]
            size_str = f"{size / 1048576:.1f} MB" if size else "size N/A"
            lines.append(f"  ✔  {label}  —  {size_str}")
    return "\n".join(lines)


def build_opts(request: DownloadRequest, save_dir: str, is_vr: bool) -> dict:
    save_dir = os.path.abspath(save_dir)

    if request.audio_only:
        # music gets its own folder too: <save>/<Title>/<file>
        return {
            "outtmpl": os.path.join(save_dir, "%(title)s", "%(title)s.%(ext)s"),
            "format": "bestaudio/best",
            "merge_output_format": "mp4",
            "nocolor": True,
            "nocheckcertificate": True,
            "noplaylist": not request.playlist,
            "noprogress": True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    # TWEAK: MP3 bitrate (kbps)
                    "preferredquality": "320",
                }
            ],
        }

    # TWEAK: output filename template (yt-dlp outtmpl syntax).
    # single   -> <save>/<Video Title>/<Video Title> [<quality>].<ext>
    # playlist -> <save>/<Playlist Title>/<nnn> - <Title>.<ext>
    if request.playlist:
        name = "%(playlist_title)s/%(playlist_index)03d - %(title)s.%(ext)s"
    else:
        name = "%(title)s/%(title)s [%(height)sp].%(ext)s"
    opts: dict = {
        "outtmpl": os.path.join(save_dir, name),
        "merge_output_format": "mp4",
        "nocolor": True,
        "nocheckcertificate": True,
        "noplaylist": not request.playlist,
        "noprogress": True,
    }

    height = request.height
    # TWEAK: video+audio format selector (yt-dlp -f syntax)
    if height is None:
        opts["format"] = "bestvideo+bestaudio/best"
    else:
        opts["format"] = f"bestvideo[height<={height}]+bestaudio/best[height<={height}]"

    if is_vr:
        opts["postprocessor_args"] = {
            "ffmpeg": ["-c", "copy", "-map_metadata", "0", "-movflags", "use_metadata_tags"]
        }
    return opts


def _write_video_info_txt(folder: str, info: dict, url: str) -> None:
    """Write a readable .txt (title/length/views/description) next to the file."""
    try:
        title = info.get("title", "Unknown")
        desc = (info.get("description") or "").strip()
        duration = format_duration(info.get("duration"))
        views = f"{info.get('view_count', 0):,}" if info.get("view_count") else "—"
        lines = [
            f"Title   : {title}",
            f"URL     : {url}",
            f"Length  : {duration}",
            f"Views   : {views}",
            "",
            "Description:",
            desc if desc else "(no description)",
        ]
        name = yt_dlp.utils.sanitize_filename(title)[:120] or "info"
        path = os.path.join(folder, f"{name}.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    except OSError:
        pass


def _write_playlist_info_txt(folder: str, info: dict, url: str) -> None:
    """One .txt for the whole playlist: title + description (+ count)."""
    try:
        title = info.get("title", "Playlist")
        desc = (info.get("description") or "").strip()
        count = len(info.get("entries") or [])
        lines = [
            f"Playlist : {title}",
            f"URL      : {url}",
            f"Videos   : {count}",
            "",
            "Description:",
            desc if desc else "(no description)",
        ]
        name = yt_dlp.utils.sanitize_filename(title)[:120] or "playlist"
        path = os.path.join(folder, f"{name}.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    except OSError:
        pass


def _cleanup_leftovers(folder: str, base_title: str | None = None) -> None:
    """Remove half-downloaded streams from failed attempts, e.g.
    'Title [240p].f395.mp4', '.part' and '.ytdl' temp files.
    If base_title is given only files starting with it are removed."""
    pattern = re.compile(r"\.f\d+\.(?:mp4|webm|m4a|ogg|opus)$|\.part$|\.ytdl$")
    try:
        prefix = (
            yt_dlp.utils.sanitize_filename(base_title) if base_title else ""
        )
        for name in os.listdir(folder):
            if base_title and not name.startswith(prefix):
                continue
            if pattern.search(name):
                path = os.path.join(folder, name)
                if os.path.isfile(path):
                    os.unlink(path)
    except OSError:
        pass


def download(
    request: DownloadRequest,
    save_dir: str,
    is_vr: bool,
    on_progress: Callable[[dict], None] | None = None,
    on_postprocess: Callable[[dict], None] | None = None,
    log: FetchLog | None = None,
    should_cancel: CancelCheck | None = None,
    ydl_logger=None,
) -> tuple[str, str, str]:
    """Run a download. Returns (status, title, folder) with status one of
    "ok" | "cancelled" | "failed"; folder is where the files landed.
    Set should_cancel to a callable that returns True when the user
    wants to stop. Pass ydl_logger (debug/info/warning/error methods)
    to mirror yt-dlp's terminal output."""
    title = "Unknown"

    def _guard(hook):
        def inner(d: dict) -> None:
            if should_cancel and should_cancel():
                raise yt_dlp.utils.DownloadCancelled()
            if hook:
                hook(d)
        return inner

    def run(opts: dict) -> dict | None:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(request.url)

    def finalize(info: dict) -> tuple[str, str, str]:
        # figure out which folder the files went into and drop the .txt
        nonlocal title
        if not info:
            return "ok", title, save_dir
        if info.get("_type") == "playlist":
            ptitle = info.get("title") or "Playlist"
            title = ptitle
            folder = os.path.join(save_dir, yt_dlp.utils.sanitize_filename(ptitle))
            os.makedirs(folder, exist_ok=True)
            _write_playlist_info_txt(folder, info, request.url)
        else:
            title = info.get("title", title)
            folder = os.path.join(save_dir, yt_dlp.utils.sanitize_filename(title))
            _write_video_info_txt(folder, info, request.url)
        # sweep partial streams from earlier failed attempts
        # (playlists: scan whole folder; singles: only this title's files)
        is_playlist = info.get("_type") == "playlist"
        _cleanup_leftovers(folder, None if is_playlist else title)
        return "ok", title, folder

    opts = build_opts(request, save_dir, is_vr)
    hooks = {
        "progress_hooks": ([_guard(on_progress)] if on_progress or should_cancel else []),
        "postprocessor_hooks": (
            [_guard(on_postprocess)] if on_postprocess or should_cancel else []
        ),
    }
    opts.update(hooks)
    _apply_js_runtime(opts)
    if ydl_logger is not None:
        opts["logger"] = ydl_logger

    try:
        return finalize(run(opts))
    except yt_dlp.utils.DownloadCancelled:
        if log:
            log("⏹ Cancelled by user")
        return "cancelled", title, save_dir
    except Exception:
        if log:
            log("⚠ Primary failed, trying fallback…")
        height = request.height
        retry = DownloadRequest(
            url=request.url,
            quality="Best Available" if height is None else f"{height}p",
            audio_only=request.audio_only,
            playlist=request.playlist,
        )
        opts2 = build_opts(retry, save_dir, is_vr=False)
        opts2.update(hooks)
        try:
            return finalize(run(opts2))
        except yt_dlp.utils.DownloadCancelled:
            if log:
                log("⏹ Cancelled by user")
            return "cancelled", title, save_dir
        except Exception as exc:
            if log:
                log(f"ERROR: {exc}")
            return "failed", title, save_dir


def progress_fields(d: dict) -> dict:
    raw_p = strip_ansi(d.get("_percent_str", "0%")).replace("%", "").strip()
    try:
        pct = float(raw_p)
    except ValueError:
        pct = 0.0
    total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
    return {
        "status": d.get("status"),
        "percent": pct,
        "speed": strip_ansi(d.get("_speed_str", "—")),
        "eta": strip_ansi(d.get("_eta_str", "—")),
        "downloaded": strip_ansi(d.get("_downloaded_bytes_str", "—")),
        "downloaded_bytes": d.get("downloaded_bytes") or 0,
        "total_bytes": total_bytes,
        "total": format_file_size(total_bytes),
    }
