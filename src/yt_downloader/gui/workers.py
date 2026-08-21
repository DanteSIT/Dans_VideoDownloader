"""
Background workers — every QThread that runs core logic off the UI thread.

Pattern used everywhere: create worker, connect its Signals to slots,
call start(). The UI never blocks. Add new workers here following the
same shape.
"""

from __future__ import annotations

import urllib.request

from ..core import dependencies, downloader
from ..core.models import DownloadRequest, VideoInfo
from ..qt import QThread, Signal


# ── Fetch video info (URL -> VideoInfo) ──────────────────────────────────

class FetchWorker(QThread):
    done = Signal(object)      # emits VideoInfo
    failed = Signal(str)       # emits error message

    def __init__(self, url: str, playlist: bool, parent=None) -> None:
        super().__init__(parent)
        self.url = url
        self.playlist = playlist

    def run(self) -> None:
        try:
            self.done.emit(downloader.fetch_info(self.url, self.playlist))
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
    progress = Signal(dict)          # percent / speed / eta / downloaded
    stage = Signal(str)              # status text ("MERGING…")
    log = Signal(str)                # warning lines for the output log
    result = Signal(str, str, str)   # status ("ok"|"cancelled"|"failed"), title, quality label

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
        status, title = downloader.download(
            self.request,
            self.save_dir,
            self.is_vr,
            on_progress=self._on_progress,
            on_postprocess=self._on_postprocess,
            log=lambda msg: self.log.emit(msg),
            should_cancel=lambda: self._cancel,
        )
        self.result.emit(status, title, self.request.label)

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
    item_log = Signal(str)
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
        total = len(self.items)
        for idx, req in enumerate(self.items):
            if self._cancelled:
                break
            self.item_started.emit(idx, req.url)
            status, title = downloader.download(
                req,
                self.save_dir,
                False,
                on_progress=lambda d: self.item_progress.emit(downloader.progress_fields(d)),
                on_postprocess=self._item_postprocess,
                log=lambda msg: self.item_log.emit(msg),
                should_cancel=lambda: self._cancelled,
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
