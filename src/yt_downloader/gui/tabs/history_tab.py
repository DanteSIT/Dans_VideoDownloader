"""
History tab — table of past downloads (Date / Title / Quality / Path).
Read-only view; data comes from HistoryStore via MainWindow.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core.models import HistoryEntry


class HistoryTab(QWidget):
    """Download history screen."""

    clear_requested = Signal()

    COLUMNS = ("Date", "Title", "Quality", "Save Path")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(8)

        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)   # Date
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)            # Title
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)   # Quality
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)            # Path

        root.addWidget(self.table, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        clear_btn = QPushButton("Clear History")
        clear_btn.setProperty("variant", "danger")
        clear_btn.clicked.connect(self.clear_requested.emit)
        btn_row.addWidget(clear_btn)
        root.addLayout(btn_row)

    # ── public API ───────────────────────────────────────────────────

    def refresh(self, entries: list[HistoryEntry]) -> None:
        """Rebuild the table from HistoryStore entries."""
        self.table.setRowCount(len(entries))
        bold = QFont()
        bold.setBold(False)
        for row, e in enumerate(entries):
            values = (e.date, e.title[:55], e.quality, e.path)
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(e.url if col == 1 else value)
                self.table.setItem(row, col, item)
