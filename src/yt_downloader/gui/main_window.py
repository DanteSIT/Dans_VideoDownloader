"""
Main window — header bar, the three tabs, and all the wiring between
them. Shared state (history store) lives here.

To add a new tab: create the widget in gui/tabs/, import it below and
add it to `self.tabs.addTab(...)`, then wire any signals in `_wire()`.
"""

from __future__ import annotations

from ..core import config
from ..core.history import HistoryStore
from ..qt import QFrame, QHBoxLayout, QLabel, QMainWindow, QTabWidget, QVBoxLayout
from .tabs.download_tab import DownloadTab
from .tabs.history_tab import HistoryTab
from .tabs.queue_tab import QueueTab


class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(config.APP_NAME)
        self.resize(*config.WINDOW_DEFAULT)
        self.setMinimumSize(*config.WINDOW_MIN)

        # shared state
        self.history = HistoryStore()
        save_dir = config.default_save_dir()

        # tabs
        self.download_tab = DownloadTab(save_dir)
        self.queue_tab = QueueTab(save_dir)
        self.history_tab = HistoryTab()

        central = QFrame()
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_header())

        self.tabs = QTabWidget()
        # TWEAK: tab labels shown at the top of the window
        self.tabs.addTab(self.download_tab, "  ⬇  Download  ")
        self.tabs.addTab(self.queue_tab, "  ☰  Queue  ")
        self.tabs.addTab(self.history_tab, "  🕘  History  ")
        root_layout.addWidget(self.tabs)

        self._wire()
        self.history_tab.refresh(self.history.entries)

    # ── UI construction ──────────────────────────────────────────────

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(50)

        row = QHBoxLayout(header)
        row.setContentsMargins(20, 8, 20, 8)

        title = QLabel(config.APP_HEADER)
        title.setStyleSheet("font-size: 17px; font-weight: 800;")
        row.addWidget(title)

        row.addStretch(1)

        author = QLabel(config.APP_AUTHOR)
        author.setStyleSheet("font-size: 11px; color: #ffcccc;")
        row.addWidget(author)

        return header

    # ── signal wiring ────────────────────────────────────────────────

    def _wire(self) -> None:
        dt, qt_, ht = self.download_tab, self.queue_tab, self.history_tab

        # "+ QUEUE" on the download tab -> append to queue and show it
        dt.add_to_queue.connect(self._on_add_to_queue)

        # direct downloads -> record history when successful
        dt.download_completed.connect(self._on_download_completed)

        # queue items -> record history when each one succeeds
        qt_.item_completed.connect(self._on_queue_item_completed)

        # history clear button -> wipe the store
        ht.clear_requested.connect(self._on_clear_history)

    # ── slots ────────────────────────────────────────────────────────

    def _on_add_to_queue(self, request, title: str) -> None:
        self.queue_tab.add_item(request, title)
        self.tabs.setCurrentWidget(self.queue_tab)

    def _on_download_completed(self, title: str, quality: str, path: str, ok: bool) -> None:
        if not ok or not title:
            return
        url = self.download_tab.url_entry.text().strip()
        self.history.add(title=title, quality=quality, path=path, url=url)
        self.history_tab.refresh(self.history.entries)

    def _on_queue_item_completed(self, title: str, quality: str, ok: bool) -> None:
        if not ok or not title:
            return
        self.history.add(title=title, quality=quality, path=self.queue_tab.save_dir, url="")
        self.history_tab.refresh(self.history.entries)

    def _on_clear_history(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        answer = QMessageBox.question(
            self,
            "Clear History",
            "Delete all download history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.history.clear()
            self.history_tab.refresh(self.history.entries)
