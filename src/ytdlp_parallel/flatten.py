"""Flatten a playlist URL into a list of Entry objects via read-only extraction.

When called with the bootstrap options (which include ``cookiesfrombrowser`` and a
``cookiefile``), this single ``extract_info`` call also writes ``cookies.txt`` as a
side-effect, so the browser is read exactly once per run.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from .archive import Entry
from .errors import FlattenError


class FlatExtractor(Protocol):
    """The slice of ``yt_dlp.YoutubeDL`` used for read-only flat extraction."""

    def __enter__(self) -> FlatExtractor: ...

    def __exit__(self, *exc_info: object) -> bool | None: ...

    def extract_info(self, url: str, *, download: bool) -> dict[str, Any] | None: ...


FlatExtractorFactory = Callable[[dict[str, Any]], FlatExtractor]


def _watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def flatten_playlist(
    url: str, opts: dict[str, Any], *, ydl_factory: FlatExtractorFactory
) -> list[Entry]:
    """Extract a playlist's entries. Raise :class:`FlattenError` if none are found."""
    with ydl_factory(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    # A missing info dict or absent "entries" key means extraction itself failed
    # (auth failure, wrong URL). An *empty* entries list is a valid but empty
    # playlist — the caller treats that as "nothing to do" and exits 0.
    if not info or info.get("entries") is None:
        raise FlattenError(f"No videos were extracted from {url!r}.")

    entries: list[Entry] = []
    for raw_entry in info["entries"]:
        if not raw_entry:
            continue
        video_id = raw_entry.get("id")
        if not video_id:
            continue
        entries.append(
            Entry(
                id=video_id,
                url=raw_entry.get("url") or _watch_url(video_id),
                title=raw_entry.get("title") or video_id,
            )
        )

    return entries
