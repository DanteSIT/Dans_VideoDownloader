"""
Data classes — the plain objects passed between core and GUI.

  DownloadRequest : one thing the user wants to download
  QueueItem       : a request sitting in the batch queue
  HistoryEntry    : one row of download history
  VideoInfo       : result of fetching info for a URL
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DownloadRequest:
    url: str
    quality: str = "Best Available"
    audio_only: bool = False
    playlist: bool = False

    @property
    def label(self) -> str:
        return "MP3" if self.audio_only else self.quality

    @property
    def height(self) -> int | None:
        if self.audio_only or self.quality == "Best Available":
            return None
        digits = "".join(c for c in self.quality if c.isdigit())
        return int(digits) if digits else None


@dataclass
class QueueItem:
    request: DownloadRequest
    title: str = ""
    status: str = "Queued"

    def display(self) -> str:
        title = (self.title or self.request.url)[:70]
        return f"[{self.status:<8}]  {self.request.label:<12}  {title}"


@dataclass
class HistoryEntry:
    date: str
    title: str
    quality: str
    path: str
    url: str

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "title": self.title,
            "quality": self.quality,
            "path": self.path,
            "url": self.url,
        }

    @classmethod
    def from_dict(cls, data: dict) -> HistoryEntry:
        return cls(
            date=data.get("date", ""),
            title=data.get("title", ""),
            quality=data.get("quality", ""),
            path=data.get("path", ""),
            url=data.get("url", ""),
        )


@dataclass
class VideoInfo:
    raw: dict
    is_playlist: bool = False
    is_vr: bool = False
    qualities: list[str] = field(default_factory=list)
    sizes: dict[str, int] = field(default_factory=dict)

    @property
    def title(self) -> str:
        return self.raw.get("title", "Unknown")

    @property
    def entry_count(self) -> int:
        return len(self.raw.get("entries") or [])
