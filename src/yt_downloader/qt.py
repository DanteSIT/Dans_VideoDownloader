"""
Qt binding compatibility layer.

Prefers PySide6; falls back to PyQt5 if PySide6 is not installed.
Import all Qt classes from this module instead of PySide6 directly,
e.g.:

    from ..qt import Qt, Signal, QtWidgets
"""

try:  # preferred binding
    from PySide6.QtCore import QTimer, QThread, Qt, Signal  # noqa: F401
    from PySide6.QtGui import QFont, QGuiApplication, QPixmap, QTextCursor  # noqa: F401
    from PySide6.QtWidgets import (  # noqa: F401
        QApplication,
        QCheckBox,
        QComboBox,
        QFileDialog,
        QFrame,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QListWidget,
        QMainWindow,
        QMessageBox,
        QProgressBar,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QTabWidget,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )

    QT_LIB = "PySide6"

except ImportError:  # fallback binding (covers the API subset used here)
    from PyQt5.QtCore import QTimer, QThread, Qt  # noqa: F401
    from PyQt5.QtCore import pyqtSignal as Signal  # noqa: F401
    from PyQt5.QtGui import QFont, QGuiApplication, QPixmap, QTextCursor  # noqa: F401
    from PyQt5.QtWidgets import (  # noqa: F401
        QApplication,
        QCheckBox,
        QComboBox,
        QFileDialog,
        QFrame,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QListWidget,
        QMainWindow,
        QMessageBox,
        QProgressBar,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QTabWidget,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )

    QT_LIB = "PyQt5"
