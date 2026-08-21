"""
System dependency checks — verifies ffmpeg / atomicparsley exist and can
install them via the system package manager (apt/dnf/pacman).

TWEAK: add or remove required tools in SYSTEM_TOOLS.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys

# TWEAK: system tools checked at startup (must be on PATH)
SYSTEM_TOOLS = ["ffmpeg", "atomicparsley"]

_INSTALL_CMDS = {
    "apt-get": ["sudo", "apt-get", "install", "-y", "-qq"],
    "dnf": ["sudo", "dnf", "install", "-y", "-q"],
    "pacman": ["sudo", "pacman", "-S", "--noconfirm", "-q"],
}


def check_tool(tool: str) -> bool:
    return shutil.which(tool) is not None


def missing_tools() -> list[str]:
    return [t for t in SYSTEM_TOOLS if not check_tool(t)]


def install_tools(tools: list[str]) -> tuple[int, list[str]]:
    if not tools:
        return 0, []

    system = platform.system()
    if system == "Windows":
        return 0, [f"Windows: {t} (manual install required)" for t in tools]
    if system != "Linux":
        return 0, [f"{system}: {t} (manual install required)" for t in tools]

    manager = next((m for m in _INSTALL_CMDS if shutil.which(m)), None)
    if manager is None:
        return 0, [f"Manual: {t}" for t in tools] 

    installed = 0
    failed: list[str] = []
    for tool in tools:
        try:
            subprocess.run(
                [*_INSTALL_CMDS[manager], tool],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            installed += 1
        except (subprocess.CalledProcessError, OSError):
            failed.append(f"{manager}: {tool}")
    return installed, failed


def pip_install(package: str) -> bool:
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", package],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (subprocess.CalledProcessError, OSError):
        return False


WINDOWS_MANUAL_LINKS = (
    "FFmpeg: https://ffmpeg.org/download.html\n"
    "AtomicParsley: https://github.com/wez/atomicparsley/releases"
)
