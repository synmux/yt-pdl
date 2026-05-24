"""The UI-agnostic download engine: a shared queue drained by N worker functions.

Each worker owns its own ``YoutubeDL`` instance (yt-dlp is synchronous and not safe
to share across threads), pulls entries from the queue until it is empty or the run
is cancelled, and reports progress and outcomes through an injected event observer.
The engine imports neither ``yt_dlp`` nor Textual: the ``YoutubeDL`` factory and the
worker-spawning strategy are both injected, so the same engine drives the TUI and
the plain runner and is fully testable with fakes.
"""

from __future__ import annotations

import queue
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from .archive import Entry, read_archive_ids
from .config import RunConfig
from .events import (
    EventObserver,
    ProgressUpdate,
    VideoFailed,
    VideoFinished,
    VideoSkipped,
    VideoStarted,
    WorkerFinished,
    WorkerStarted,
)
from .options import CookieMode, build_download_opts

_RATE_LIMIT_MARKERS = ("429", "too many requests")


class YoutubeDLLike(Protocol):
    """The slice of the ``yt_dlp.YoutubeDL`` interface the engine uses."""

    def __enter__(self) -> YoutubeDLLike: ...

    def __exit__(self, *exc_info: object) -> bool | None: ...

    def download(self, urls: list[str]) -> int: ...


YoutubeDLFactory = Callable[[dict[str, Any]], YoutubeDLLike]
WorkerSpawner = Callable[[Callable[[], None]], None]


def _never_cancelled() -> bool:
    return False


class _CapturingLogger:
    """Captures yt-dlp error lines so a failure reason can be reported."""

    def __init__(self) -> None:
        self.errors: list[str] = []

    def debug(self, message: str) -> None:
        pass

    def info(self, message: str) -> None:
        pass

    def warning(self, message: str) -> None:
        pass

    def error(self, message: str) -> None:
        self.errors.append(str(message))


@dataclass
class _DownloadState:
    filename: str | None = None
    saw_error: bool = False


def build_queue(entries: list[Entry]) -> queue.Queue[Entry]:
    """Return a FIFO queue pre-loaded with every entry (no sentinels needed)."""
    work_queue: queue.Queue[Entry] = queue.Queue()
    for entry in entries:
        work_queue.put(entry)
    return work_queue


def worker_count_for(jobs: int, entry_count: int) -> int:
    """Spawn at most ``jobs`` workers, and never more than there are videos."""
    return min(jobs, entry_count)


def _is_rate_limited(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _RATE_LIMIT_MARKERS)


def _compute_percent(status: dict[str, Any]) -> float | None:
    downloaded = status.get("downloaded_bytes")
    total = status.get("total_bytes") or status.get("total_bytes_estimate")
    if downloaded is not None and total:
        return 100.0 * downloaded / total
    return None


def _make_progress_hook(
    worker_index: int, entry: Entry, emit: EventObserver, state: _DownloadState
) -> Callable[[dict[str, Any]], None]:
    def hook(status: dict[str, Any]) -> None:
        phase = status.get("status")
        if phase == "downloading":
            emit(
                ProgressUpdate(
                    worker_index=worker_index,
                    video_id=entry.id,
                    title=entry.title,
                    percent=_compute_percent(status),
                    downloaded_bytes=status.get("downloaded_bytes"),
                    total_bytes=status.get("total_bytes")
                    or status.get("total_bytes_estimate"),
                    speed=status.get("speed"),
                    eta=status.get("eta"),
                    percent_str=str(status.get("_percent_str", "")).strip(),
                    speed_str=str(status.get("_speed_str", "")).strip(),
                    eta_str=str(status.get("_eta_str", "")).strip(),
                    stage="downloading",
                )
            )
        elif phase == "finished":
            state.filename = status.get("filename")
        elif phase == "error":
            state.saw_error = True

    return hook


def _download_one(
    worker_index: int,
    entry: Entry,
    config: RunConfig,
    cookie_mode: CookieMode,
    emit: EventObserver,
    ydl_factory: YoutubeDLFactory,
) -> bool:
    """Download a single entry. Return ``True`` if it failed, else ``False``."""
    emit(VideoStarted(worker_index, entry.id, entry.title, entry.url))

    if entry.id in read_archive_ids(config.paths.archive_file):
        emit(VideoSkipped(worker_index, entry.id, entry.title))
        return False

    state = _DownloadState()
    logger = _CapturingLogger()
    hook = _make_progress_hook(worker_index, entry, emit, state)
    opts = build_download_opts(
        config, cookie_mode=cookie_mode, progress_hook=hook, logger=logger
    )

    return_code = 1
    try:
        with ydl_factory(opts) as ydl:
            return_code = ydl.download([entry.url])
    except Exception as exc:
        # One bad video must never kill the worker; record and carry on.
        logger.errors.append(str(exc))
        state.saw_error = True

    if return_code != 0 or state.saw_error:
        reason = logger.errors[-1] if logger.errors else "download failed"
        emit(
            VideoFailed(
                worker_index=worker_index,
                video_id=entry.id,
                title=entry.title,
                reason=reason,
                is_rate_limited=_is_rate_limited(reason),
            )
        )
        return True

    emit(VideoFinished(worker_index, entry.id, entry.title, state.filename))
    return False


def run_worker(
    worker_index: int,
    work_queue: queue.Queue[Entry],
    config: RunConfig,
    cookie_mode: CookieMode,
    emit: EventObserver,
    *,
    is_cancelled: Callable[[], bool],
    ydl_factory: YoutubeDLFactory,
) -> None:
    """Drain the queue: download each entry until empty or cancelled."""
    emit(WorkerStarted(worker_index))
    processed = 0
    failed = 0
    while not is_cancelled():
        try:
            entry = work_queue.get_nowait()
        except queue.Empty:
            break
        if _download_one(worker_index, entry, config, cookie_mode, emit, ydl_factory):
            failed += 1
        processed += 1
    emit(WorkerFinished(worker_index, processed=processed, failed=failed))


def run_engine(
    entries: list[Entry],
    config: RunConfig,
    cookie_mode: CookieMode,
    emit: EventObserver,
    *,
    ydl_factory: YoutubeDLFactory,
    spawn: WorkerSpawner,
    is_cancelled: Callable[[], bool] = _never_cancelled,
) -> int:
    """Build the queue and spawn the workers. Return the number spawned.

    Completion is not awaited here: the caller (Textual app or ThreadPoolExecutor)
    decides how to join, and learns completion from the ``WorkerFinished`` events.
    """
    work_queue = build_queue(entries)
    count = worker_count_for(config.jobs, len(entries))
    for worker_index in range(count):
        spawn(
            _make_worker_callable(
                worker_index,
                work_queue,
                config,
                cookie_mode,
                emit,
                is_cancelled,
                ydl_factory,
            )
        )
    return count


def _make_worker_callable(
    worker_index: int,
    work_queue: queue.Queue[Entry],
    config: RunConfig,
    cookie_mode: CookieMode,
    emit: EventObserver,
    is_cancelled: Callable[[], bool],
    ydl_factory: YoutubeDLFactory,
) -> Callable[[], None]:
    def worker() -> None:
        run_worker(
            worker_index,
            work_queue,
            config,
            cookie_mode,
            emit,
            is_cancelled=is_cancelled,
            ydl_factory=ydl_factory,
        )

    return worker
