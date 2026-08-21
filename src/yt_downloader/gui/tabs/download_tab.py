"""
Download tab — URL input, video preview, quality picker, progress and
the main Download / Queue buttons. This is the tab users see first.

Most visual tweaks live in gui/theme.py; behaviour tweaks are marked
with `# TWEAK:` below.
"""

from __future__ import annotations

from ...core import config, downloader, utils
from ...core.models import DownloadRequest, VideoInfo
from ...qt import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGuiApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPixmap,
    QProgressBar,
    QPushButton,
    Qt,
    QTextEdit,
    QVBoxLayout,
    Signal,
    QWidget,
)
from ..theme import COLORS, FONT_CODE, SECTION_LABEL_QSS
from ..workers import DownloadWorker, FetchWorker, ThumbWorker

# TWEAK: log message colors (level -> hex color)
LOG_COLORS = {
    "info": COLORS["info"],
    "ok": COLORS["success"],
    "warn": COLORS["warning"],
    "err": COLORS["accent"],
    "vr": COLORS["info"],
}


# ── Small UI helpers ─────────────────────────────────────────────────────

def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(SECTION_LABEL_QSS)
    return lbl


def _separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"background-color: {COLORS['border']}; max-height: 1px; border: none;")
    return line


class DownloadTab(QWidget):
    """Main download screen."""

    # emitted when the user queues an item (request, display title)
    add_to_queue = Signal(DownloadRequest, str)
    # emitted when a direct download ends (title, quality label, save dir, ok)
    download_completed = Signal(str, str, str, bool)

    def __init__(self, save_dir: str, parent=None) -> None:
        super().__init__(parent)
        self.save_dir = save_dir
        self.info: VideoInfo | None = None
        self._fetch_worker: FetchWorker | None = None
        self._thumb_worker: ThumbWorker | None = None
        self._download_worker: DownloadWorker | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(6)

        self._build_url_section(root)
        root.addWidget(_separator())
        self._build_preview_section(root)
        self._build_path_section(root)
        root.addWidget(_separator())
        self._build_quality_section(root)
        root.addWidget(_separator())
        self._build_log_section(root)
        root.addWidget(_separator())
        self._build_progress_section(root)
        self._build_action_buttons(root)

        root.addStretch(1)

    # ── UI construction ──────────────────────────────────────────────

    def _build_url_section(self, root: QVBoxLayout) -> None:
        root.addWidget(_section_label("VIDEO URL"))

        url_row = QHBoxLayout()
        self.url_entry = QLineEdit()
        self.url_entry.setPlaceholderText("https://www.youtube.com/watch?v=…")
        self.url_entry.textChanged.connect(self._reset_preview)
        url_row.addWidget(self.url_entry, stretch=1)

        paste_btn = QPushButton("📋")
        paste_btn.setToolTip("Paste from clipboard")
        paste_btn.setFixedWidth(44)
        paste_btn.clicked.connect(self._paste_url)
        url_row.addWidget(paste_btn)
        root.addLayout(url_row)

        cb_row = QHBoxLayout()
        self.playlist_cb = QCheckBox("Download entire playlist")
        self.playlist_cb.setToolTip("If URL is a playlist, download all videos")
        cb_row.addWidget(self.playlist_cb)
        cb_row.addStretch(1)
        self.audio_cb = QCheckBox("Audio only (MP3)")
        self.audio_cb.setToolTip("Extract audio as 320kbps MP3")
        self.audio_cb.toggled.connect(self._on_audio_toggle)
        cb_row.addWidget(self.audio_cb)
        root.addLayout(cb_row)

    def _build_preview_section(self, root: QVBoxLayout) -> None:
        thumb_row = QHBoxLayout()

        # TWEAK: thumbnail size comes from config.THUMBNAIL_SIZE
        self.thumb_label = QLabel("No Preview")
        self.thumb_label.setFixedSize(*config.THUMBNAIL_SIZE)
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setStyleSheet(
            f"background-color: {COLORS['card']};"
            f"border: 1px solid {COLORS['border']}; color: {COLORS['muted']}; font-size: 11px;"
        )
        thumb_row.addWidget(self.thumb_label)

        info_col = QVBoxLayout()
        info_col.setSpacing(4)

        self.title_lbl = QLabel("—")
        self.title_lbl.setWordWrap(True)
        title_font = self.title_lbl.font()
        title_font.setBold(True)
        self.title_lbl.setFont(title_font)
        info_col.addWidget(self.title_lbl)

        self.meta_lbl = QLabel("")
        self.meta_lbl.setStyleSheet(f"color: {COLORS['muted']}; font-family: {FONT_CODE};")
        info_col.addWidget(self.meta_lbl)

        self.vr_badge = QLabel("")
        self.vr_badge.setStyleSheet(f"color: {COLORS['info']}; font-weight: 700;")
        info_col.addWidget(self.vr_badge)
        info_col.addStretch(1)

        thumb_row.addLayout(info_col, stretch=1)
        root.addLayout(thumb_row)

    def _build_path_section(self, root: QVBoxLayout) -> None:
        root.addWidget(_section_label("SAVE TO"))
        path_row = QHBoxLayout()
        self.path_entry = QLineEdit(self.save_dir)
        self.path_entry.setReadOnly(True)
        path_row.addWidget(self.path_entry, stretch=1)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_folder)
        path_row.addWidget(browse_btn)
        root.addLayout(path_row)

    def _build_quality_section(self, root: QVBoxLayout) -> None:
        q_row = QHBoxLayout()
        q_row.addWidget(_section_label("QUALITY"))
        q_row.addStretch(1)

        self.fetch_btn = QPushButton("🔍  FETCH INFO")
        self.fetch_btn.setProperty("variant", "accent")
        self.fetch_btn.clicked.connect(self._fetch_info)
        q_row.addWidget(self.fetch_btn)
        root.addLayout(q_row)

        self.quality_combo = QComboBox()
        self.quality_combo.addItem("Fetch Info First")
        root.addWidget(self.quality_combo)

    def _build_log_section(self, root: QVBoxLayout) -> None:
        root.addWidget(_section_label("OUTPUT LOG"))
        self.log_view = QTextEdit()
        self.log_view.setObjectName("log")
        self.log_view.setReadOnly(True)
        # TWEAK: height of the output log box
        self.log_view.setFixedHeight(110)
        root.addWidget(self.log_view)

    def _build_progress_section(self, root: QVBoxLayout) -> None:
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        root.addWidget(self.progress)

        stat_row = QHBoxLayout()

        self.speed_lbl = QLabel("Speed: —")
        self.speed_lbl.setStyleSheet(f"color: {COLORS['success']};")
        stat_row.addWidget(self.speed_lbl)

        self.eta_lbl = QLabel("ETA: —")
        self.eta_lbl.setStyleSheet(f"color: {COLORS['warning']};")
        stat_row.addWidget(self.eta_lbl)

        self.got_lbl = QLabel("Got: —")
        self.got_lbl.setStyleSheet(f"color: {COLORS['info']};")
        stat_row.addWidget(self.got_lbl)

        stat_row.addStretch(1)

        self.status_lbl = QLabel("IDLE")
        self.status_lbl.setStyleSheet(f"color: {COLORS['muted']}; font-weight: 700;")
        stat_row.addWidget(self.status_lbl)
        root.addLayout(stat_row)

    def _build_action_buttons(self, root: QVBoxLayout) -> None:
        btn_row = QHBoxLayout()

        self.download_btn = QPushButton("⬇  DOWNLOAD")
        self.download_btn.setProperty("variant", "success")
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self._start_download)
        btn_row.addWidget(self.download_btn, stretch=1)

        self.queue_btn = QPushButton("+ QUEUE")
        self.queue_btn.setToolTip("Add to batch queue instead of downloading now")
        self.queue_btn.setEnabled(False)
        self.queue_btn.clicked.connect(self._emit_queue)
        btn_row.addWidget(self.queue_btn)

        root.addLayout(btn_row)

    # ── helpers ──────────────────────────────────────────────────────

    def _log(self, msg: str, level: str = "info") -> None:
        color = LOG_COLORS.get(level, COLORS["info"])
        safe = (
            msg.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>")
        )
        self.log_view.append(f'<span style="color:{color}; white-space:pre-wrap;">{safe}</span>')

    def _set_status(self, text: str, color: str) -> None:
        self.status_lbl.setText(text)
        self.status_lbl.setStyleSheet(f"color: {color}; font-weight: 700;")

    def _set_thumb_placeholder(self) -> None:
        self.thumb_label.setPixmap(QPixmap())
        self.thumb_label.setText("No Preview")

    def _set_thumb(self, data: bytes) -> None:
        pix = QPixmap()
        if not pix.loadFromData(data):
            return
        self.thumb_label.setText("")
        self.thumb_label.setPixmap(
            pix.scaled(
                self.thumb_label.size(),
                Qt.AspectRatioMode.IgnoreAspect,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    # ── small event handlers ─────────────────────────────────────────

    def _paste_url(self) -> None:
        clip = QGuiApplication.clipboard().text().strip()
        if clip:
            self.url_entry.setText(clip)

    def _on_audio_toggle(self, checked: bool) -> None:
        if checked:
            self.quality_combo.setEnabled(False)
            self.quality_combo.setCurrentText("Audio Only (MP3)")
        else:
            self.quality_combo.setEnabled(True)
            if self.quality_combo.count() and self.quality_combo.itemText(0) != "Fetch Info First":
                self.quality_combo.setCurrentIndex(0)

    def _reset_preview(self) -> None:
        self._set_thumb_placeholder()
        self.title_lbl.setText("—")
        self.meta_lbl.setText("")
        self.vr_badge.setText("")
        self.quality_combo.clear()
        self.quality_combo.addItem("Fetch Info First")
        self.download_btn.setEnabled(False)
        self.queue_btn.setEnabled(False)
        self.info = None

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select folder", self.save_dir)
        if folder:
            self.save_dir = folder
            self.path_entry.setText(folder)

    # ── fetch info flow ──────────────────────────────────────────────

    def _fetch_info(self) -> None:
        url = self.url_entry.text().strip()
        if not url:
            QMessageBox.warning(self, "No URL", "Please enter a video URL first.")
            return
        self.log_view.clear()
        self._log("@ Fetching info…")
        self.fetch_btn.setEnabled(False)
        self._set_status("FETCHING…", COLORS["warning"])

        self._fetch_worker = FetchWorker(url, self.playlist_cb.isChecked(), self)
        self._fetch_worker.done.connect(self._on_fetched)
        self._fetch_worker.failed.connect(self._on_fetch_failed)
        self._fetch_worker.start()

    def _on_fetched(self, vi: VideoInfo) -> None:
        self.info = vi
        if vi.is_playlist:
            self._show_playlist(vi)
        else:
            self._show_video(vi)
            thumbnail_url = vi.raw.get("thumbnail")
            if thumbnail_url:
                self._thumb_worker = ThumbWorker(thumbnail_url, self)
                self._thumb_worker.loaded.connect(self._set_thumb)
                self._thumb_worker.start()

    def _show_playlist(self, vi: VideoInfo) -> None:
        self._log(f"PLAYLIST: {vi.title}", "ok")
        self._log(f"{vi.entry_count} video(s) found.")
        self.title_lbl.setText(f"📋  {vi.title}")
        self.meta_lbl.setText(f"{vi.entry_count} videos")
        self.quality_combo.clear()
        self.quality_combo.addItems(config.DEFAULT_QUALITIES)
        self.download_btn.setEnabled(True)
        self.queue_btn.setEnabled(True)
        self.fetch_btn.setEnabled(True)
        self._set_status("READY", COLORS["success"])

    def _show_video(self, vi: VideoInfo) -> None:
        raw = vi.raw
        duration = utils.format_duration(raw.get("duration"))
        views = f"{raw.get('view_count', 0):,}" if raw.get("view_count") else "—"
        uploader = raw.get("uploader", "")

        self._log(downloader.format_table(vi), "vr" if vi.is_vr else "")
        self.title_lbl.setText(vi.title)
        self.meta_lbl.setText(f"⏱ {duration}   👁 {views} views   ↑ {uploader}")
        if vi.is_vr:
            self.vr_badge.setText("🔮  360° / VR Video")

        self.quality_combo.clear()
        self.quality_combo.addItems(["Best Available"] + vi.qualities)
        self.download_btn.setEnabled(True)
        self.queue_btn.setEnabled(True)
        self.fetch_btn.setEnabled(True)
        self._set_status("READY", COLORS["success"])

    def _on_fetch_failed(self, msg: str) -> None:
        self._log(f"ERROR: {msg}", "err")
        self._set_status("ERROR", COLORS["accent"])
        self.fetch_btn.setEnabled(True)

    # ── queue / download actions ─────────────────────────────────────

    def _current_request(self) -> DownloadRequest | None:
        url = self.url_entry.text().strip()
        if not url or not self.info:
            return None
        return DownloadRequest(
            url=url,
            quality=self.quality_combo.currentText(),
            audio_only=self.audio_cb.isChecked(),
            playlist=self.playlist_cb.isChecked(),
        )

    def _emit_queue(self) -> None:
        req = self._current_request()
        if req is None:
            return
        title = self.info.title[:70] if self.info else ""
        self.add_to_queue.emit(req, title)
        self._log(f"+ Queued: {title}", "ok")

    def _start_download(self) -> None:
        req = self._current_request()
        if req is None or self._download_worker is not None:
            return
        self.download_btn.setEnabled(False)
        self.queue_btn.setEnabled(False)
        self._set_status("STARTING…", COLORS["warning"])

        self._download_worker = DownloadWorker(req, self.save_dir, bool(self.info.is_vr), self)
        worker = self._download_worker
        worker.progress.connect(self._on_progress)
        worker.stage.connect(lambda s: self._set_status(s, COLORS["info"]))
        worker.log.connect(lambda m: self._log(m, "warn"))
        worker.result.connect(lambda ok, title, _label: self._on_download_result(ok, title))
        worker.start()

    def _on_progress(self, d: dict) -> None:
        if d["status"] == "downloading":
            pct = d.get("percent", 0.0)
            self.progress.setValue(int(pct))
            self.speed_lbl.setText(f"Speed: {d.get('speed', '—')}")
            self.eta_lbl.setText(f"ETA: {d.get('eta', '—')}")
            self.got_lbl.setText(f"Got: {d.get('downloaded', '—')}")
            self._set_status(f"DOWNLOADING {pct:.0f}%", COLORS["warning"])
        elif d["status"] == "finished":
            self._set_status("PROCESSING…", COLORS["info"])

    def _on_download_result(self, ok: bool, title: str) -> None:
        worker = self._download_worker
        self._download_worker = None
        req = worker.request if worker else None

        self.download_btn.setEnabled(True)
        self.queue_btn.setEnabled(True)

        if ok:
            self._set_status("COMPLETE ✓", COLORS["success"])
            self.progress.setValue(100)
            self._log(f"✔ Done: {title}", "ok")
            quality = req.label if req else ""
            self.download_completed.emit(title, quality, self.save_dir, True)
            answer = QMessageBox.question(
                self,
                "Done ✓",
                f"'{title}' downloaded!\n\nOpen folder?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                utils.open_folder(self.save_dir)
        else:
            self._set_status("FAILED", COLORS["accent"])
            self.download_completed.emit(title or "", "", self.save_dir, False)
            QMessageBox.critical(
                self,
                "Download Failed",
                "All attempts failed.\nCheck your internet connection and FFmpeg install.",
            )
