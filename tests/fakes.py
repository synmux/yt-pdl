"""Test doubles for yt-dlp — no network, no terminal.

``FakeYoutubeDL`` mimics the parts of ``yt_dlp.YoutubeDL`` the engine relies on:
it derives the video id from the URL's last path segment, drives the progress
hook(s) and logger as yt-dlp would, records successful ids to the download
archive, and returns 0 (all ok) or 1 (a failure occurred).
"""

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ytdlp_parallel.archive import archive_id_for
from ytdlp_parallel.events import Event


class FakeYoutubeDL:
    """A scripted stand-in for ``yt_dlp.YoutubeDL``."""

    def __init__(
        self,
        opts: dict[str, Any],
        *,
        fail_ids: frozenset[str],
        rate_limited_ids: frozenset[str],
        archive_lock: threading.Lock,
    ) -> None:
        self._opts = opts
        self._fail_ids = fail_ids
        self._rate_limited_ids = rate_limited_ids
        self._archive_lock = archive_lock

    def __enter__(self) -> "FakeYoutubeDL":
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False

    def download(self, urls: list[str]) -> int:
        return_code = 0
        for url in urls:
            video_id = url.rsplit("/", 1)[-1]
            if video_id in self._fail_ids:
                return_code = 1
                self._emit_error(video_id)
            else:
                self._emit_success(video_id)
        return return_code

    def _hooks(self) -> list[Callable[[dict[str, Any]], None]]:
        return self._opts.get("progress_hooks", [])

    def _emit_success(self, video_id: str) -> None:
        for hook in self._hooks():
            hook(
                {
                    "status": "downloading",
                    "info_dict": {"id": video_id},
                    "downloaded_bytes": 512,
                    "total_bytes": 1024,
                    "speed": 256.0,
                    "eta": 2,
                    "_percent_str": " 50.0%",
                    "_speed_str": "256.00B/s",
                    "_eta_str": "00:02",
                }
            )
            hook(
                {
                    "status": "finished",
                    "info_dict": {"id": video_id},
                    "filename": f"{video_id}.mp4",
                    "downloaded_bytes": 1024,
                    "total_bytes": 1024,
                }
            )
        self._record_archive(video_id)

    def _emit_error(self, video_id: str) -> None:
        message = (
            "ERROR: [youtube] HTTP Error 429: Too Many Requests"
            if video_id in self._rate_limited_ids
            else "ERROR: Private video. Sign in if you've been granted access"
        )
        logger = self._opts.get("logger")
        if logger is not None:
            logger.error(message)
        for hook in self._hooks():
            hook({"status": "error", "info_dict": {"id": video_id}})

    def _record_archive(self, video_id: str) -> None:
        archive = self._opts.get("download_archive")
        if archive is None:
            return
        archive_path = Path(archive)
        with self._archive_lock:
            archive_path.parent.mkdir(parents=True, exist_ok=True)
            with archive_path.open("a", encoding="utf-8") as handle:
                handle.write(archive_id_for("youtube", video_id) + "\n")


def fake_ydl_factory(
    *,
    fail_ids: frozenset[str] = frozenset(),
    rate_limited_ids: frozenset[str] = frozenset(),
) -> Callable[[dict[str, Any]], FakeYoutubeDL]:
    """Build a factory that produces scripted ``FakeYoutubeDL`` instances.

    All instances share one lock so concurrent archive appends stay line-clean.
    """
    archive_lock = threading.Lock()

    def factory(opts: dict[str, Any]) -> FakeYoutubeDL:
        return FakeYoutubeDL(
            opts,
            fail_ids=fail_ids,
            rate_limited_ids=rate_limited_ids,
            archive_lock=archive_lock,
        )

    return factory


class RecordingObserver:
    """Collects emitted events for assertions (not thread-safe; see lock usage)."""

    def __init__(self) -> None:
        self.events: list[Event] = []

    def __call__(self, event: Event) -> None:
        self.events.append(event)
