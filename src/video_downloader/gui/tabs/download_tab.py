"""
Download tab — URL input, video preview, quality picker, progress and
the main Download / Queue buttons. This is the tab users see first.

Most visual tweaks live in gui/theme.py; behaviour tweaks are marked
with `# TWEAK:` below.
"""

from __future__ import annotations

import time

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
    QTextCursor,
    QTextEdit,
    QTimer,
    QVBoxLayout,
    QWidget,
    Signal,
)
from ..theme import COLORS, FONT_CODE, SECTION_LABEL_QSS
from ..workers import DownloadWorker, FetchWorker, ThumbWorker

# TWEAK: log message colors (level -> hex color)
# TWEAK: connect-animation look (terminal spinner frames + stage messages)
SPIN_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
CONNECT_STAGES = [
    (0.0, "Resolving hostname…"),
    (2.0, "Establishing secure channel…"),
    (5.0, "Negotiating stream formats…"),
]

# TWEAK: minimum seconds between live terminal line repaints (throttle)
LIVE_REFRESH = 0.1

LOG_COLORS = {
    "info": COLORS["info"],
    "ok": COLORS["success"],
    "warn": COLORS["warning"],
    "err": COLORS["accent"],
    "vr": COLORS["info"],
    # TWEAK: gray used for yt-dlp's own terminal chatter
    "debug": "#8a8f98",
}


def _ts() -> str:
    return time.strftime("%H:%M:%S")


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
        self._anim_timer: QTimer | None = None
        self._anim_frame = 0
        self._anim_t0 = 0.0
        self._live_active = False      # a live download line is in the log
        self._last_live = 0.0          # throttle timestamp for live line
        self._last_live_text = ""      # last rendered live line (for freeze)
        self._dl_t0 = 0.0              # download start time (elapsed stat)
        self._thumb_worker: ThumbWorker | None = None
        self._download_worker: DownloadWorker | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(4)

        self._build_url_section(root)
        root.addWidget(_separator())
        self._build_preview_section(root)
        self._build_path_section(root)
        root.addWidget(_separator())
        self._build_quality_section(root)
        root.addWidget(_separator())
        # the log is the flexible element — it grows/shrinks with the
        # window while progress + buttons stay pinned at the bottom
        self._build_log_section(root)
        root.addWidget(_separator())
        self._build_progress_section(root)
        self._build_action_buttons(root)

    # ── UI construction ──────────────────────────────────────────────

    def _build_url_section(self, root: QVBoxLayout) -> None:
        root.addWidget(_section_label("VIDEO URL"))

        url_row = QHBoxLayout()
        self.url_entry = QLineEdit()
        # TWEAK: works with any yt-dlp supported site (YouTube, FB, X, TikTok…)
        self.url_entry.setPlaceholderText(
            "Paste any video URL — YouTube, Facebook, Twitter/X, TikTok…"
        )
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

        # TWEAK: description snippet shown under title/time (set max chars below)
        self.desc_lbl = QLabel("")
        self.desc_lbl.setWordWrap(True)
        self.desc_lbl.setStyleSheet(
            f"color: {COLORS['muted']}; font-size: 11px; background: transparent;"
        )
        self.desc_lbl.setVisible(False)
        info_col.addWidget(self.desc_lbl)

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
        q_row.setSpacing(8)
        q_row.addWidget(_section_label("QUALITY"))

        self.quality_combo = QComboBox()
        self.quality_combo.addItem("Fetch Info First")
        q_row.addWidget(self.quality_combo, stretch=1)

        self.fetch_btn = QPushButton("🔍  FETCH INFO")
        self.fetch_btn.setProperty("variant", "accent")
        self.fetch_btn.clicked.connect(self._fetch_info)
        q_row.addWidget(self.fetch_btn)

        root.addLayout(q_row)

    def _build_log_section(self, root: QVBoxLayout) -> None:
        root.addWidget(_section_label("OUTPUT LOG"))
        self.log_view = QTextEdit()
        self.log_view.setObjectName("log")
        self.log_view.setReadOnly(True)
        # TWEAK: minimum log height — it stretches to fill leftover space
        self.log_view.setMinimumHeight(96)
        root.addWidget(self.log_view, stretch=1)

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
        # TWEAK: while downloading this button becomes the STOP button
        self.download_btn.clicked.connect(self._on_download_clicked)
        btn_row.addWidget(self.download_btn, stretch=1)

        self.queue_btn = QPushButton("+ QUEUE")
        self.queue_btn.setToolTip("Add to batch queue instead of downloading now")
        self.queue_btn.setEnabled(False)
        self.queue_btn.clicked.connect(self._emit_queue)
        btn_row.addWidget(self.queue_btn)

        root.addLayout(btn_row)

    # ── helpers ──────────────────────────────────────────────────────

    def _log(self, msg: str, level: str = "info") -> None:
        # if a live stats line sits at the bottom, freeze it into history
        # first so normal output always lands BELOW the last stats frame
        if self._live_active:
            self._freeze_live_line()
            self._live_active = False
        color = LOG_COLORS.get(level, COLORS["info"])
        safe = (
            msg.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>")
        )
        self.log_view.append(f'<span style="color:{color}; white-space:pre-wrap;">{safe}</span>')

    def _on_ydl_log(self, msg: str, level: str = "info") -> None:
        """Real output from yt-dlp — replaces the spinner animation the
        moment the server starts talking."""
        if self._anim_timer is not None:
            self._stop_connect_animation()
        if msg.strip():
            self._log(msg, level)

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
                Qt.AspectRatioMode.IgnoreAspectRatio,
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
        self.desc_lbl.setText("")
        self.desc_lbl.setVisible(False)
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
        self.fetch_btn.setEnabled(False)
        self._set_status("FETCHING…", COLORS["warning"])
        self._start_connect_animation(url)

        self._fetch_worker = FetchWorker(url, self.playlist_cb.isChecked(), self)
        self._fetch_worker.done.connect(self._on_fetched)
        self._fetch_worker.failed.connect(self._on_fetch_failed)
        # mirror yt-dlp's own terminal lines (connecting, checking, formats…)
        self._fetch_worker.log.connect(self._on_ydl_log)
        # real measured connection stats for the terminal intro
        self._fetch_worker.netstat.connect(self._on_netstat)
        self._fetch_worker.start()

    # ── connect animation (hacker-movie style, real data only) ───────
    def _start_connect_animation(self, url: str) -> None:
        self._anim_frame = 0
        self._anim_t0 = time.time()
        self._log(f"▶ TARGET: {url}", "info")
        self._log_view_placeholder_line()

    def _log_view_placeholder_line(self) -> None:
        """Append an empty line that later gets rewritten in place."""
        self.log_view.append("")
        if self._anim_timer is None:
            self._anim_timer = QTimer(self)
            self._anim_timer.timeout.connect(self._tick_connect_animation)
            self._anim_timer.start(120)

    def _tick_connect_animation(self) -> None:
        elapsed = time.time() - self._anim_t0
        frame = SPIN_FRAMES[self._anim_frame % len(SPIN_FRAMES)]
        self._anim_frame += 1
        stage = CONNECT_STAGES[0][1]
        for start_at, msg in CONNECT_STAGES:
            if elapsed >= start_at:
                stage = msg
        line = f"[{_ts()}] {frame} {stage} ({elapsed:.1f}s)"
        self._replace_last_log_line(line)

    def _on_netstat(self, ns: dict) -> None:
        """Print the measured handshake — DNS / TCP / TLS with real ms."""
        if not ns:
            return
        self._stop_connect_animation()
        self._log(
            f"  resolving {ns['host']} … {ns['ip']}  ({ns['dns_ms']:.0f} ms)", "debug"
        )
        self._log(
            f"  tcp connect {ns['ip']}:443  ({ns['tcp_ms']:.0f} ms)", "debug"
        )
        self._log(
            f"  {ns['proto']} handshake ok — {ns['cipher']}  ({ns['tls_ms']:.0f} ms)",
            "ok",
        )
        self._log_view_placeholder_line()

    def _replace_last_log_line(self, text: str, color: str | None = None) -> None:
        cursor = QTextCursor(self.log_view.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        c = color or COLORS["info"]
        safe = (
            text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )
        cursor.insertHtml(f'<span style="color:{c}; white-space:pre-wrap;">{safe}</span>')

    def _stop_connect_animation(self) -> None:
        if self._anim_timer is not None:
            self._anim_timer.stop()
            self._anim_timer.deleteLater()
            self._anim_timer = None
        # clear the spinner line so results start on a clean slate
        cursor = QTextCursor(self.log_view.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()

    def _on_fetched(self, vi: VideoInfo) -> None:
        self._stop_connect_animation()
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

        desc = (raw.get("description") or "").strip()
        if desc:
            # TWEAK: how many characters of the description to preview
            limit = 220
            snippet = desc[:limit].replace("\n", " ")
            self.desc_lbl.setText(f"📝 {snippet}{'…' if len(desc) > limit else ''}")
            self.desc_lbl.setVisible(True)

        if vi.is_vr:
            self.vr_badge.setText("🔮  360° / VR Video")

        self.quality_combo.clear()
        self.quality_combo.addItems(["Best Available"] + vi.qualities)
        self.download_btn.setEnabled(True)
        self.queue_btn.setEnabled(True)
        self.fetch_btn.setEnabled(True)
        self._set_status("READY", COLORS["success"])

    def _on_fetch_failed(self, msg: str) -> None:
        self._stop_connect_animation()
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

    def _on_download_clicked(self) -> None:
        if self._download_worker is not None:
            self._download_worker.cancel()
            self.download_btn.setEnabled(False)
            self._set_status("STOPPING…", COLORS["warning"])
            return
        self._start_download()

    def _start_download(self) -> None:
        req = self._current_request()
        if req is None or self._download_worker is not None:
            return
        self.queue_btn.setEnabled(False)
        self.download_btn.setText("⏹  STOP")
        self._set_status("STARTING…", COLORS["warning"])

        self._download_worker = DownloadWorker(req, self.save_dir, bool(self.info.is_vr), self)
        worker = self._download_worker
        worker.progress.connect(self._on_progress)
        worker.stage.connect(lambda s: self._set_status(s, COLORS["info"]))
        worker.log.connect(self._on_ydl_log)
        worker.netstat.connect(self._on_netstat)
        worker.result.connect(self._on_download_result)
        self._live_active = False
        self._last_live = 0.0
        self._dl_t0 = time.time()
        worker.start()

    def _on_progress(self, d: dict) -> None:
        if d["status"] == "downloading":
            pct = d.get("percent", 0.0)
            self.progress.setValue(int(pct))
            speed = d.get("speed", "—")
            eta = d.get("eta", "—")
            got_bytes = d.get("downloaded_bytes") or 0
            got_txt = utils.format_file_size(got_bytes) if got_bytes else d.get("downloaded", "—")
            total_txt = d.get("total", "Unknown")
            size_txt = (
                f"Got: {got_txt} of {total_txt}"
                if total_txt != "Unknown"
                else f"Got: {got_txt}"
            )
            self.speed_lbl.setText(f"Speed: {speed}")
            self.eta_lbl.setText(f"ETA: {eta}")
            self.got_lbl.setText(size_txt)
            self._set_status(f"DOWNLOADING {pct:.0f}%", COLORS["warning"])
            self._update_live_line(pct, got_txt, total_txt, speed, eta)
        elif d["status"] == "finished":
            self._set_status("PROCESSING…", COLORS["info"])
            self._live_active = False
            self._log("✔ stream complete — merging tracks…", "ok")

    # ── live terminal line (real stats, rewritten in place) ──────────

    def _update_live_line(self, pct: float, got: str, total: str, speed: str, eta: str) -> None:
        now = time.time()
        if not self._live_active:
            self._log_view_placeholder_line()
            self._live_active = True
        elif now - self._last_live < LIVE_REFRESH:
            return
        self._last_live = now
        frame = SPIN_FRAMES[self._anim_frame % len(SPIN_FRAMES)]
        self._anim_frame += 1
        elapsed = now - self._dl_t0
        total_part = f" / {total}" if total != "Unknown" else ""
        line = (
            f"[{_ts()}] {frame} {pct:5.1f}% │ {got}{total_part}"
            f" │ {speed}/s │ ETA {eta} │ {elapsed:.0f}s elapsed"
        )
        self._last_live_text = line
        self._replace_last_log_line(line, COLORS["success"])

    def _freeze_live_line(self) -> None:
        """Pin the last live stats frame into the log history."""
        if self._last_live_text:
            self._replace_last_log_line(self._last_live_text, COLORS["success"])

    def _on_download_result(
        self, status: str, title: str, _label: str = "", folder: str = ""
    ) -> None:
        worker = self._download_worker
        self._download_worker = None
        req = worker.request if worker else None
        self._live_active = False

        self.download_btn.setEnabled(True)
        self.download_btn.setText("⬇  DOWNLOAD")
        self.queue_btn.setEnabled(True)

        if status == "cancelled":
            self.progress.setValue(0)
            self.speed_lbl.setText("Speed: —")
            self.eta_lbl.setText("ETA: —")
            self.got_lbl.setText("Got: —")
            self._set_status("CANCELLED", COLORS["muted"])
            return

        ok = status == "ok"
        # files live inside their own title/ subfolder now
        target = folder or self.save_dir
        if ok:
            self._set_status("COMPLETE ✓", COLORS["success"])
            self.progress.setValue(100)
            self._log(f"✔ Done: {title}", "ok")
            quality = req.label if req else ""
            self.download_completed.emit(title, quality, target, True)
            answer = QMessageBox.question(
                self,
                "Done ✓",
                f"'{title}' downloaded!\n\nOpen folder?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                utils.open_folder(target)
        else:
            self._set_status("FAILED", COLORS["accent"])
            self.download_completed.emit(title or "", "", self.save_dir, False)
            QMessageBox.critical(
                self,
                "Download Failed",
                "All attempts failed.\nCheck your internet connection and FFmpeg install.",
            )
