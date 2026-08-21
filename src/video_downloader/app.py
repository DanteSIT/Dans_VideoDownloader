"""
Application bootstrap — builds the QApplication, applies the dark theme,
shows MainWindow and runs the startup dependency check (ffmpeg /
atomicparsley). This is the single entry point used by main.py,
`python -m video_downloader` and the `video-downloader` console script.
"""

from __future__ import annotations

import platform

from .core import config
from .qt import QApplication, QMessageBox


def _run_dependency_check(window) -> None:
    """Offer to install any missing system tools on startup."""
    from .core import dependencies
    from .gui.workers import DependencyInstallWorker

    missing = dependencies.missing_tools()
    if not missing:
        return

    listing = "\n".join(f"  • {tool}" for tool in missing)
    answer = QMessageBox.question(
        window,
        "Missing Dependencies",
        "The following system tools are missing:\n\n"
        f"{listing}\n\nWould you like to install them now?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    if answer != QMessageBox.StandardButton.Yes:
        return

    worker = DependencyInstallWorker(missing, [], window)

    def on_done(installed: int, failed: list[str]) -> None:
        if not failed:
            QMessageBox.information(
                window,
                "Installation Complete",
                f"✓ Successfully installed {installed} dependencies!\n\n"
                "The application is ready to use.",
            )
            return

        msg = f"Installed {installed} dependencies.\n\nFailed to install {len(failed)}:\n\n"
        msg += "\n".join(f"  • {item}" for item in failed)
        if platform.system() == "Windows":
            msg += (
                f"\n\nFor Windows, you can manually download:\n"
                f"  • {dependencies.WINDOWS_MANUAL_LINKS}"
            )
        QMessageBox.warning(window, "Installation Partial", msg)

    worker.done.connect(on_done)
    worker.start()
    window._dep_worker = worker  # keep a reference so GC doesn't kill it


def main() -> int:
    from .gui.main_window import MainWindow
    from .gui.theme import build_stylesheet

    app = QApplication([])
    app.setApplicationName(config.APP_NAME)
    app.setStyleSheet(build_stylesheet())

    window = MainWindow()
    window.show()

    # TWEAK: remove this line to skip the ffmpeg/atomicparsley startup check
    _run_dependency_check(window)

    return app.exec()
