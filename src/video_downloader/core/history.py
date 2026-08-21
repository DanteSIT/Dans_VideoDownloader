"""
History persistence — load/add/clear download_history.json.
The JSON file lives in ~/.config/youtube-downloader/ (see config.py).
"""

from __future__ import annotations

import json
from datetime import datetime

from .config import MAX_HISTORY_ENTRIES, history_file
from .models import HistoryEntry


class HistoryStore:
    def __init__(self) -> None:
        self._entries: list[HistoryEntry] = []
        self.load()

    @property
    def entries(self) -> list[HistoryEntry]:
        return self._entries

    def load(self) -> list[HistoryEntry]:
        path = history_file()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self._entries = [HistoryEntry.from_dict(d) for d in data if isinstance(d, dict)]
            except (json.JSONDecodeError, OSError):
                self._entries = []
        return self._entries

    def save(self) -> None:
        path = history_file()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps([e.to_dict() for e in self._entries], indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass

    def add(self, title: str, quality: str, path: str, url: str) -> None:
        entry = HistoryEntry(
            date=datetime.now().strftime("%Y-%m-%d %H:%M"),
            title=title,
            quality=quality,
            path=path,
            url=url,
        )
        self._entries.insert(0, entry)
        self._entries = self._entries[:MAX_HISTORY_ENTRIES]
        self.save()

    def clear(self) -> None:
        self._entries.clear()
        self.save()
