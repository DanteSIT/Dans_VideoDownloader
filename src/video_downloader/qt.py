"""
Qt binding compatibility layer.

Import all Qt classes from this module instead of PySide6 directly,
e.g.:

    from ..qt import Qt, Signal, QtWidgets

The GUI is built exclusively on PySide6.
"""

from PySide6.QtCore import Qt, QThread, QTimer, Signal  # noqa: F401
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
