"""
yt-dlp wrapper — the actual download engine, no GUI code here.

Everything yt-dlp related lives in this file:
  - fetch_info()      : URL -> VideoInfo (formats, VR flag, qualities)
  - build_opts()      : turns a DownloadRequest into yt-dlp options
  - download()        : runs the download with fallback retry

TWEAK points: MP3 bitrate, output filename template, format selectors.
"""

from __future__ import annotations

import os
from typing import Callable

import yt_dlp

from .config import RESOLUTIONS
from .models import DownloadRequest, VideoInfo
from .utils import strip_ansi

FetchLog = Callable[[str], None]


class DownloadError(Exception):
    pass


def fetch_info(url: str, playlist: bool) -> VideoInfo:
    opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": not playlist,
        "nocheckcertificate": True,
        "extract_flat": playlist,
    }
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
        return {
            "outtmpl": os.path.join(save_dir, "%(title)s.%(ext)s"),
            "format": "bestaudio/best",
            "merge_output_format": "mp4",
            "nocolor": True,
            "nocheckcertificate": True,
            "noplaylist": not request.playlist,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    # TWEAK: MP3 bitrate (kbps)
                    "preferredquality": "320",
                }
            ],
        }

    # TWEAK: output filename template (yt-dlp outtmpl syntax)
    name = (
        "%(playlist_index)s-%(title)s [%(height)sp].%(ext)s"
        if request.playlist
        else "%(title)s [%(height)sp].%(ext)s"
    )
    opts: dict = {
        "outtmpl": os.path.join(save_dir, name),
        "merge_output_format": "mp4",
        "nocolor": True,
        "nocheckcertificate": True,
        "noplaylist": not request.playlist,
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


def download(
    request: DownloadRequest,
    save_dir: str,
    is_vr: bool,
    on_progress: Callable[[dict], None] | None = None,
    on_postprocess: Callable[[dict], None] | None = None,
    log: FetchLog | None = None,
) -> tuple[bool, str]:
    title = "Unknown"

    def run(opts: dict) -> str | None:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(request.url)
            return info.get("title") if info else None

    opts = build_opts(request, save_dir, is_vr)
    hooks = {
        "progress_hooks": ([on_progress] if on_progress else []),
        "postprocessor_hooks": ([on_postprocess] if on_postprocess else []),
    }
    opts.update(hooks)
    try:
        found = run(opts)
        if found:
            title = found
        return True, title
    except Exception:
        if log:
            log("⚠ Primary failed, trying fallback…")
        height = request.height
        fallback = "best" if height is None else f"best[height<={height}][ext=mp4]/best"
        retry = DownloadRequest(
            url=request.url,
            quality="Best Available" if height is None else f"{height}p",
            audio_only=request.audio_only,
            playlist=request.playlist,
        )
        opts2 = build_opts(retry, save_dir, is_vr=False)
        opts2.update(hooks)
        try:
            found = run(opts2)
            if found:
                title = found
            return True, title
        except Exception as exc:
            if log:
                log(f"ERROR: {exc}")
            return False, title


def progress_fields(d: dict) -> dict:
    raw_p = strip_ansi(d.get("_percent_str", "0%")).replace("%", "").strip()
    try:
        pct = float(raw_p)
    except ValueError:
        pct = 0.0
    return {
        "status": d.get("status"),
        "percent": pct,
        "speed": strip_ansi(d.get("_speed_str", "—")),
        "eta": strip_ansi(d.get("_eta_str", "—")),
        "downloaded": strip_ansi(d.get("_downloaded_bytes_str", "—")),
    }
