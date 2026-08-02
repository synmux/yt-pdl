"""Flatten source URLs (playlists, channels, single videos) into Entry objects.

When called with the bootstrap options (which include ``cookiesfrombrowser`` and a
``cookiefile``), the first ``extract_info`` call also writes ``cookies.txt`` as a
side-effect, so the browser is read exactly once per run.

Channel URLs flatten to playlists whose entries may themselves be playlists (tab
or playlist references). Those are recursed into, capped at
``MAX_PLAYLIST_DEPTH`` levels so a pathological tree cannot recurse forever;
skipped sub-playlists are reported through ``warn``, never dropped silently.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, Protocol

from .archive import Entry
from .errors import FlattenError

MAX_PLAYLIST_DEPTH = 2
"""How many playlist levels to expand (the source URL itself is depth 0)."""

_SUB_PLAYLIST_IE_KEYS = frozenset({"YoutubePlaylist", "YoutubeTab"})

Warn = Callable[[str], None]


class FlatExtractor(Protocol):
    """The slice of ``yt_dlp.YoutubeDL`` used for read-only flat extraction."""

    def __enter__(self) -> FlatExtractor: ...

    def __exit__(self, *exc_info: object) -> bool | None: ...

    def extract_info(self, url: str, *, download: bool) -> dict[str, Any] | None: ...


FlatExtractorFactory = Callable[[dict[str, Any]], FlatExtractor]


def _watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def flatten_source(
    url: str,
    opts: dict[str, Any],
    *,
    ydl_factory: FlatExtractorFactory,
    warn: Warn | None = None,
    _depth: int = 0,
) -> list[Entry]:
    """Flatten one source URL — playlist, channel or single video — into entries.

    Raise :class:`FlattenError` when extraction fails outright (no info dict, or
    a dict carrying neither ``entries`` nor an ``id``). An *empty* playlist
    returns an empty list — the caller treats that as "nothing to do".
    """
    with ydl_factory(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if not info:
        raise FlattenError(f"No videos were extracted from {url!r}.")

    if info.get("entries") is None:
        video_id = info.get("id")
        if not video_id:
            raise FlattenError(f"No videos were extracted from {url!r}.")
        return [
            Entry(
                id=video_id,
                url=info.get("webpage_url") or url,
                title=info.get("title") or video_id,
            )
        ]

    return _collect_entries(info["entries"], opts, ydl_factory=ydl_factory, warn=warn, depth=_depth)


def dedupe_entries(entries: Iterable[Entry]) -> list[Entry]:
    """Drop duplicate video ids, keeping the first occurrence and its order."""
    seen_ids: set[str] = set()
    unique: list[Entry] = []
    for entry in entries:
        if entry.id in seen_ids:
            continue
        seen_ids.add(entry.id)
        unique.append(entry)
    return unique


def _collect_entries(
    raw_entries: Iterable[dict[str, Any] | None],
    opts: dict[str, Any],
    *,
    ydl_factory: FlatExtractorFactory,
    warn: Warn | None,
    depth: int,
) -> list[Entry]:
    entries: list[Entry] = []
    for raw_entry in raw_entries:
        if not raw_entry:
            continue
        if raw_entry.get("entries") is not None:
            if depth + 1 >= MAX_PLAYLIST_DEPTH:
                _warn_skipped_sub_playlist(warn, raw_entry)
                continue
            entries.extend(
                _collect_entries(
                    raw_entry["entries"],
                    opts,
                    ydl_factory=ydl_factory,
                    warn=warn,
                    depth=depth + 1,
                )
            )
            continue
        if _is_sub_playlist_reference(raw_entry):
            sub_url = raw_entry.get("url")
            if depth + 1 >= MAX_PLAYLIST_DEPTH or not sub_url:
                _warn_skipped_sub_playlist(warn, raw_entry)
                continue
            entries.extend(
                flatten_source(sub_url, opts, ydl_factory=ydl_factory, warn=warn, _depth=depth + 1)
            )
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


def _is_sub_playlist_reference(raw_entry: dict[str, Any]) -> bool:
    if raw_entry.get("_type") == "playlist":
        return True
    return raw_entry.get("_type") == "url" and raw_entry.get("ie_key") in _SUB_PLAYLIST_IE_KEYS


def _warn_skipped_sub_playlist(warn: Warn | None, raw_entry: dict[str, Any]) -> None:
    if warn is None:
        return
    label = raw_entry.get("id") or raw_entry.get("url") or raw_entry.get("title") or "unknown"
    warn(
        f"Skipping nested playlist {label!r}: deeper than {MAX_PLAYLIST_DEPTH} "
        "levels or missing a URL."
    )
