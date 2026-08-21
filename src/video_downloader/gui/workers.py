"""
Background workers — every QThread that runs core logic off the UI thread.

Pattern used everywhere: create worker, connect its Signals to slots,
call start(). The UI never blocks. Add new workers here following the
same shape.
"""

from __future__ import annotations

import socket
import ssl
import time
import urllib.parse
import urllib.request

from ..core import dependencies, downloader
from ..core.models import DownloadRequest
from ..qt import QThread, Signal

# ── Fetch video info (URL -> VideoInfo) ──────────────────────────────────

def measure_connection(url: str) -> dict:
    """Real network probe for the terminal animation: DNS lookup,
    TCP connect and TLS handshake timings against the target host."""
    out: dict = {}
    try:
        host = urllib.parse.urlparse(url).hostname or ""
        if not host:
            return out
        t0 = time.perf_counter()
        ip = socket.gethostbyname(host)
        dns_ms = (time.perf_counter() - t0) * 1000
        t1 = time.perf_counter()
        raw = socket.create_connection((ip, 443), timeout=8)
        tcp_ms = (time.perf_counter() - t1) * 1000
        t2 = time.perf_counter()
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE  # we only probe latency here
        with ctx.wrap_socket(raw, server_hostname=host) as tls:
            cipher = (tls.cipher() or ("?", 0, "?"))[0]
            proto = tls.version() or "?"
        tls_ms = (time.perf_counter() - t2) * 1000
        out = {
            "host": host, "ip": ip,
            "dns_ms": dns_ms, "tcp_ms": tcp_ms, "tls_ms": tls_ms,
            "cipher": cipher, "proto": proto,
        }
    except Exception:
        pass  # probe is cosmetic — real work happens in yt-dlp
    return out


class FetchWorker(QThread):
    done = Signal(object)          # emits VideoInfo
    failed = Signal(str)           # emits error message
    log = Signal(str, str)         # yt-dlp terminal lines (msg, level)
    netstat = Signal(dict)         # measured DNS/TCP/TLS stats

    def __init__(self, url: str, playlist: bool, parent=None) -> None:
        super().__init__(parent)
        self.url = url
        self.playlist = playlist

    def run(self) -> None:
        self.netstat.emit(measure_connection(self.url))
        try:
            logger = downloader._SignalLogger(self.log.emit)
            self.done.emit(
                downloader.fetch_info(self.url, self.playlist, ydl_logger=logger)
            )
        except Exception as exc:
            self.failed.emit(str(exc))


# ── Download thumbnail image (URL -> raw bytes) ──────────────────────────

class ThumbWorker(QThread):
    loaded = Signal(bytes)

    def __init__(self, url: str, parent=None) -> None:
        super().__init__(parent)
        self.url = url

    def run(self) -> None:
        try:
            req = urllib.request.Request(self.url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                self.loaded.emit(resp.read())
        except Exception:
            pass  # thumbnail is cosmetic; silently ignore failures


# ── Single download ──────────────────────────────────────────────────────

class DownloadWorker(QThread):
    progress = Signal(dict)             # percent / speed / eta / downloaded
    stage = Signal(str)                 # status text ("MERGING…")
    log = Signal(str, str)              # yt-dlp terminal lines (msg, level)
    netstat = Signal(dict)              # measured DNS/TCP/TLS stats
    # status ("ok"|"cancelled"|"failed"), title, quality label, folder
    result = Signal(str, str, str, str)

    def __init__(self, request: DownloadRequest, save_dir: str, is_vr: bool, parent=None) -> None:
        super().__init__(parent)
        self.request = request
        self.save_dir = save_dir
        self.is_vr = is_vr
        self._cancel = False

    # TWEAK: call cancel() to stop the current download
    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        self.netstat.emit(measure_connection(self.request.url))
        logger = downloader._SignalLogger(self.log.emit)
        status, title, folder = downloader.download(
            self.request,
            self.save_dir,
            self.is_vr,
            on_progress=self._on_progress,
            on_postprocess=self._on_postprocess,
            log=lambda msg: self.log.emit(msg, "warn"),
            should_cancel=lambda: self._cancel,
            ydl_logger=logger,
        )
        self.result.emit(status, title, self.request.label, folder)

    def _on_progress(self, d: dict) -> None:
        self.progress.emit(downloader.progress_fields(d))

    def _on_postprocess(self, d: dict) -> None:
        if d.get("status") == "started":
            self.stage.emit("⚙  MERGING…")


# ── Batch queue runner ───────────────────────────────────────────────────

class QueueWorker(QThread):
    item_started = Signal(int, str)              # index, url
    item_progress = Signal(dict)
    item_stage = Signal(str)
    item_log = Signal(str, str)                  # yt-dlp terminal lines (msg, level)
    item_finished = Signal(int, str, str, str)   # index, status, title, quality
    all_finished = Signal(int)

    def __init__(self, items: list[DownloadRequest], save_dir: str, parent=None) -> None:
        super().__init__(parent)
        self.items = items
        self.save_dir = save_dir
        self._cancelled = False

    # TWEAK: call cancel() to stop after (or during) the current item
    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        logger = downloader._SignalLogger(self.item_log.emit)
        total = len(self.items)
        for idx, req in enumerate(self.items):
            if self._cancelled:
                break
            self.item_started.emit(idx, req.url)
            status, title, _folder = downloader.download(
                req,
                self.save_dir,
                False,
                on_progress=lambda d: self.item_progress.emit(downloader.progress_fields(d)),
                on_postprocess=self._item_postprocess,
                log=lambda msg: self.item_log.emit(msg, "warn"),
                should_cancel=lambda: self._cancelled,
                ydl_logger=logger,
            )
            self.item_finished.emit(idx, status, title, req.label)
            if status == "cancelled":
                break
        self.all_finished.emit(total)

    def _item_postprocess(self, d: dict) -> None:
        if d.get("status") == "started":
            self.item_stage.emit("⚙  MERGING…")


# ── Missing dependency installer ─────────────────────────────────────────

class DependencyInstallWorker(QThread):
    done = Signal(int, list)  # installed count, failed labels

    def __init__(self, tools: list[str], packages: list[str] | None = None, parent=None) -> None:
        super().__init__(parent)
        self.tools = tools
        # Pillow is no longer needed (Qt renders thumbnails natively)
        self.packages = [p for p in (packages or []) if p != "pillow"]

    def run(self) -> None:
        installed = 0
        failed: list[str] = []
        for pkg in self.packages:
            if dependencies.pip_install(pkg):
                installed += 1
            else:
                failed.append(f"Python: {pkg}")
        tool_ok, tool_failed = dependencies.install_tools(self.tools)
        installed += tool_ok
        failed.extend(tool_failed)
        self.done.emit(installed, failed)
