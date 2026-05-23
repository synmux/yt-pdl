"""Plain (non-TTY / --plain) runner: drive the engine and print line-based progress.

Used when stdout is not a terminal (CI, pipes) or when ``--plain`` is given. It runs
the same UI-agnostic engine as the Textual app, but via a ThreadPoolExecutor whose
shutdown joins the workers, and prints one line per notable event (no per-percent
spam) through a lock-guarded observer.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from .archive import Entry
from .config import RunConfig
from .engine import YoutubeDLFactory, run_engine, worker_count_for
from .events import (
    Event,
    RunResult,
    RunResultBuilder,
    VideoFailed,
    VideoFinished,
    VideoSkipped,
    VideoStarted,
    fan_out,
)
from .ytdlp_options import CookieMode


def _format_event(event: Event) -> str | None:
    """Format a notable event as one line, or None to ignore it (e.g. progress)."""
    match event:
        case VideoStarted():
            return f"[worker {event.worker_index}] ▶ {event.title}"
        case VideoFinished():
            return f"[worker {event.worker_index}] ✓ {event.title}"
        case VideoSkipped():
            return f"[worker {event.worker_index}] ↷ already have: {event.title}"
        case VideoFailed():
            note = " (HTTP 429 — consider lowering --jobs)" if event.is_rate_limited else ""
            return f"[worker {event.worker_index}] ✗ FAILED: {event.title} — {event.reason}{note}"
        case _:
            return None


def run_plain(
    entries: list[Entry],
    config: RunConfig,
    cookie_mode: CookieMode,
    *,
    ydl_factory: YoutubeDLFactory,
    cancel_event: threading.Event | None = None,
) -> RunResult:
    """Download every entry concurrently, printing progress lines; return the result."""
    cancel_event = cancel_event if cancel_event is not None else threading.Event()
    builder = RunResultBuilder()
    print_lock = threading.Lock()

    def print_line(event: Event) -> None:
        line = _format_event(event)
        if line is not None:
            with print_lock:
                print(line)

    observer = fan_out(print_line, builder)
    worker_count = max(worker_count_for(config.jobs, len(entries)), 1)

    try:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:

            def spawn(worker_callable: Callable[[], None]) -> None:
                executor.submit(worker_callable)

            run_engine(
                entries,
                config,
                cookie_mode,
                observer,
                ydl_factory=ydl_factory,
                spawn=spawn,
                is_cancelled=cancel_event.is_set,
            )
        # Leaving the context manager joins all submitted workers (shutdown wait=True).
    except KeyboardInterrupt:
        cancel_event.set()

    return builder.result(cancelled=cancel_event.is_set())
