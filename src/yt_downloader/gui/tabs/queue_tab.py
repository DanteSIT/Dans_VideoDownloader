"""
Queue tab — batch download list. Items are added from the Download tab
("+ QUEUE" button), then processed one-by-one with "RUN ALL".
"""

from __future__ import annotations

from ...core.models import DownloadRequest, QueueItem
from ...qt import QHBoxLayout, QLabel, QListWidget, QMessageBox, QProgressBar, QPushButton, QVBoxLayout, Signal, QWidget
from ..theme import COLORS
from ..workers import QueueWorker


class QueueTab(QWidget):
    """Batch queue screen."""

    # emitted per finished item so the main window can record history
    item_completed = Signal(str, str, str)  # title, quality label, ok

    def __init__(self, save_dir: str, parent=None) -> None:
        super().__init__(parent)
        self.save_dir = save_dir
        self.items: list[QueueItem] = []
        self._worker: QueueWorker | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(4)

        header = QLabel("DOWNLOAD QUEUE")
        hint = QLabel("Add items from the Download tab, then press Run All.")
        hint.setStyleSheet(f"color: {COLORS['muted']}; font-family: monospace;")
        root.addWidget(header)
        root.addWidget(hint)

        self.queue_list = QListWidget()
        root.addWidget(self.queue_list, stretch=1)

        btn_row = QHBoxLayout()

        # TWEAK: while running this button becomes the STOP button
        self.run_btn = QPushButton("▶  RUN ALL")
        self.run_btn.setProperty("variant", "success")
        self.run_btn.clicked.connect(self._on_run_clicked)
        btn_row.addWidget(self.run_btn)

        remove_btn = QPushButton("✕  Remove")
        remove_btn.clicked.connect(self._remove_selected)
        btn_row.addWidget(remove_btn)

        btn_row.addStretch(1)

        clear_btn = QPushButton("Clear All")
        clear_btn.setProperty("variant", "danger")
        clear_btn.clicked.connect(self._clear_all)
        btn_row.addWidget(clear_btn)

        root.addLayout(btn_row)

        self.progress_lbl = QLabel("")
        self.progress_lbl.setStyleSheet(f"color: {COLORS['muted']}; font-family: monospace;")
        root.addWidget(self.progress_lbl)

        bar = QProgressBar()
        bar.setProperty("variant", "queue")
        bar.setRange(0, 100)
        bar.setValue(0)
        self.queue_bar = bar
        root.addWidget(bar)

    # ── public API (used by MainWindow) ──────────────────────────────

    def add_item(self, request: DownloadRequest, title: str) -> None:
        self.items.append(QueueItem(request=request, title=title))
        self._refresh_list()

    # ── list helpers ─────────────────────────────────────────────────

    def _refresh_list(self) -> None:
        self.queue_list.clear()
        for item in self.items:
            self.queue_list.addItem(item.display())

    def _remove_selected(self) -> None:
        row = self.queue_list.currentRow()
        if row >= 0:
            del self.items[row]
            self._refresh_list()

    def _clear_all(self) -> None:
        if not self.items:
            return
        answer = QMessageBox.question(
            self,
            "Clear Queue",
            "Remove all queued items?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.items.clear()
            self._refresh_list()

    # ── queue execution ──────────────────────────────────────────────

    def _on_run_clicked(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.run_btn.setEnabled(False)
            self.progress_lbl.setText("Stopping after current item…")
            return
        self._run_all()

    def _run_all(self) -> None:
        if not self.items:
            QMessageBox.information(self, "Queue Empty", "Add items to the queue first.")
            return

        pending = [it.request for it in self.items if it.status != "Done"]
        if not pending:
            QMessageBox.information(self, "Nothing To Do", "All items are already done.")
            return

        self.run_btn.setText("⏹  STOP")
        self.queue_bar.setValue(0)

        worker = QueueWorker(pending, self.save_dir, self)
        worker.item_started.connect(self._on_item_started)
        worker.item_finished.connect(self._on_item_finished)
        worker.all_finished.connect(self._on_all_finished)
        worker.start()
        self._worker = worker

    def _pending_items(self) -> list[QueueItem]:
        return [it for it in self.items if it.status != "Done"]

    def _on_item_started(self, index: int, url: str) -> None:
        pending = self._pending_items()
        total = len(pending) or len(self.items)
        item = pending[index] if index < len(pending) else None
        if item:
            item.status = "Working"
        title = (item.title or url)[:50] if item else url[:50]
        self.progress_lbl.setText(f"Processing {index + 1} / {total}  —  {title}")
        self.queue_bar.setValue(int((index / max(total, 1)) * 100))
        self._refresh_list()

    def _on_item_finished(self, index: int, status: str, title: str, quality: str) -> None:
        pending = [it for it in self.items if it.status != "Done" and it.status != "Cancelled"]
        item = pending[index] if index < len(pending) else None
        if item is None:
            # fallback: mark first working item
            for it in self.items:
                if it.status == "Working":
                    item = it
                    break
        if item:
            item.status = {"ok": "Done", "cancelled": "Cancelled"}.get(status, "Failed")
        self._refresh_list()
        if status == "ok":
            self.item_completed.emit(title or (item.title if item else ""), quality, True)

    def _on_all_finished(self, _total: int) -> None:
        cancelled = any(it.status == "Cancelled" for it in self.items)
        self.queue_bar.setValue(0 if cancelled else 100)
        self.progress_lbl.setText("Queue stopped ⏹" if cancelled else "Queue complete ✓")
        self.run_btn.setText("▶  RUN ALL")
        self.run_btn.setEnabled(True)
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
        if not cancelled:
            QMessageBox.information(self, "Queue Done", "Finished processing the queue.")
