"""Test doubles for yt-dlp — no network, no terminal.

``FakeYoutubeDL`` mimics the parts of ``yt_dlp.YoutubeDL`` the tool relies on, so
one factory serves both the flatten (``extract_info``) and the download
(``download``) phases, exactly as the real class does:

* ``extract_info`` returns the configured playlist info and, like yt-dlp, writes
  the cookie file as a side-effect when ``write_cookies`` is set;
* ``download`` derives the video id from the URL, drives the progress hook(s) and
  logger, records successful ids to the archive, and returns 0/1.
"""

import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from yt_pdlp.archive import archive_id_for
from yt_pdlp.events import Event


class FakeYoutubeDL:
    """A scripted stand-in for ``yt_dlp.YoutubeDL`` (flatten + download)."""

    def __init__(
        self,
        opts: dict[str, Any],
        *,
        info: dict[str, Any] | None,
        fail_ids: frozenset[str],
        rate_limited_ids: frozenset[str],
        write_cookies: bool,
        archive_lock: threading.Lock,
        delay: float,
    ) -> None:
        self._opts = opts
        self._info = info
        self._fail_ids = fail_ids
        self._rate_limited_ids = rate_limited_ids
        self._write_cookies = write_cookies
        self._archive_lock = archive_lock
        self._delay = delay

    def __enter__(self) -> "FakeYoutubeDL":
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False

    def extract_info(self, url: str, *, download: bool) -> dict[str, Any] | None:
        cookie_file = self._opts.get("cookiefile")
        if self._write_cookies and cookie_file:
            path = Path(cookie_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
        return self._info

    def download(self, urls: list[str]) -> int:
        return_code = 0
        for url in urls:
            if self._delay:
                time.sleep(self._delay)
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
    info: dict[str, Any] | None = None,
    fail_ids: frozenset[str] = frozenset(),
    rate_limited_ids: frozenset[str] = frozenset(),
    write_cookies: bool = True,
    delay: float = 0.0,
) -> Callable[[dict[str, Any]], FakeYoutubeDL]:
    """Build a factory producing scripted ``FakeYoutubeDL`` instances.

    All instances share one lock so concurrent archive appends stay line-clean.
    ``delay`` adds a per-video sleep so cancellation can be exercised mid-run.
    """
    archive_lock = threading.Lock()

    def factory(opts: dict[str, Any]) -> FakeYoutubeDL:
        return FakeYoutubeDL(
            opts,
            info=info,
            fail_ids=fail_ids,
            rate_limited_ids=rate_limited_ids,
            write_cookies=write_cookies,
            archive_lock=archive_lock,
            delay=delay,
        )

    return factory


class RecordingObserver:
    """Collects emitted events for assertions (not thread-safe; see lock usage)."""

    def __init__(self) -> None:
        self.events: list[Event] = []

    def __call__(self, event: Event) -> None:
        self.events.append(event)
