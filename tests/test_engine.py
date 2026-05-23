"""Tests for the UI-agnostic download engine and work-queue distribution."""

import threading

from fakes import RecordingObserver, fake_ydl_factory
from ytdlp_parallel.archive import Entry
from ytdlp_parallel.config import resolve_run_config
from ytdlp_parallel.engine import build_queue, run_engine, worker_count_for
from ytdlp_parallel.events import (
    ProgressUpdate,
    VideoFailed,
    VideoFinished,
    VideoSkipped,
    VideoStarted,
    WorkerFinished,
    WorkerStarted,
)
from ytdlp_parallel.ytdlp_options import CookieMode

COOKIE_MODE = CookieMode.from_browser("chrome")


def _config(tmp_path, jobs=4):
    return resolve_run_config(
        jobs=jobs,
        url="https://example.com/playlist",
        output_dir=tmp_path,
        browser="chrome",
        remux_format="mp4",
        fragments=1,
        dry_run=False,
        plain_flag=False,
        is_tty=True,
        cwd=tmp_path,
    )


def _entries(ids):
    return [Entry(id=i, url=f"https://youtu.be/{i}", title=f"Title {i}") for i in ids]


def _inline_spawn(worker):
    worker()


def _ids(events, event_type):
    return [event.video_id for event in events if isinstance(event, event_type)]


def test_worker_count_for():
    assert worker_count_for(4, 10) == 4
    assert worker_count_for(8, 3) == 3
    assert worker_count_for(4, 0) == 0


def test_build_queue_contains_all_entries():
    entries = _entries(["a", "b", "c"])
    work_queue = build_queue(entries)
    drained = []
    while not work_queue.empty():
        drained.append(work_queue.get_nowait())
    assert drained == entries


def test_engine_processes_every_id_exactly_once(tmp_path):
    entries = _entries(["a", "b", "c", "d", "e"])
    observer = RecordingObserver()
    count = run_engine(
        entries,
        _config(tmp_path, jobs=3),
        COOKIE_MODE,
        observer,
        ydl_factory=fake_ydl_factory(),
        spawn=_inline_spawn,
    )
    assert count == 3
    assert sorted(_ids(observer.events, VideoStarted)) == ["a", "b", "c", "d", "e"]
    assert sorted(_ids(observer.events, VideoFinished)) == ["a", "b", "c", "d", "e"]
    assert len([e for e in observer.events if isinstance(e, WorkerStarted)]) == 3


def test_engine_emits_failed_for_scripted_failure(tmp_path):
    observer = RecordingObserver()
    run_engine(
        _entries(["ok", "bad"]),
        _config(tmp_path),
        COOKIE_MODE,
        observer,
        ydl_factory=fake_ydl_factory(fail_ids=frozenset({"bad"})),
        spawn=_inline_spawn,
    )
    failed = [e for e in observer.events if isinstance(e, VideoFailed)]
    assert _ids(observer.events, VideoFinished) == ["ok"]
    assert [event.video_id for event in failed] == ["bad"]
    assert "Private video" in failed[0].reason
    assert failed[0].is_rate_limited is False


def test_engine_detects_rate_limit(tmp_path):
    observer = RecordingObserver()
    run_engine(
        _entries(["x"]),
        _config(tmp_path),
        COOKIE_MODE,
        observer,
        ydl_factory=fake_ydl_factory(fail_ids=frozenset({"x"}), rate_limited_ids=frozenset({"x"})),
        spawn=_inline_spawn,
    )
    failed = [e for e in observer.events if isinstance(e, VideoFailed)]
    assert failed[0].is_rate_limited is True


def test_engine_skips_archived_ids(tmp_path):
    config = _config(tmp_path)
    config.paths.archive_file.parent.mkdir(parents=True, exist_ok=True)
    config.paths.archive_file.write_text("youtube a\n", encoding="utf-8")
    observer = RecordingObserver()
    run_engine(
        _entries(["a", "b"]),
        config,
        COOKIE_MODE,
        observer,
        ydl_factory=fake_ydl_factory(),
        spawn=_inline_spawn,
    )
    assert _ids(observer.events, VideoSkipped) == ["a"]
    assert _ids(observer.events, VideoFinished) == ["b"]


def test_engine_emits_progress_updates(tmp_path):
    observer = RecordingObserver()
    run_engine(
        _entries(["a"]),
        _config(tmp_path),
        COOKIE_MODE,
        observer,
        ydl_factory=fake_ydl_factory(),
        spawn=_inline_spawn,
    )
    progress = [e for e in observer.events if isinstance(e, ProgressUpdate)]
    assert progress
    assert progress[0].percent == 50.0
    assert progress[0].stage == "downloading"


def test_worker_finished_reports_processed_and_failed(tmp_path):
    observer = RecordingObserver()
    run_engine(
        _entries(["a", "bad", "c"]),
        _config(tmp_path, jobs=1),
        COOKIE_MODE,
        observer,
        ydl_factory=fake_ydl_factory(fail_ids=frozenset({"bad"})),
        spawn=_inline_spawn,
    )
    finished = [e for e in observer.events if isinstance(e, WorkerFinished)]
    assert len(finished) == 1
    assert finished[0].processed == 3
    assert finished[0].failed == 1


def test_engine_distributes_across_threads(tmp_path):
    entries = _entries([f"v{n}" for n in range(20)])
    lock = threading.Lock()
    events = []

    def observer(event):
        with lock:
            events.append(event)

    threads = []

    def threaded_spawn(worker):
        thread = threading.Thread(target=worker)
        thread.start()
        threads.append(thread)

    run_engine(
        entries,
        _config(tmp_path, jobs=4),
        COOKIE_MODE,
        observer,
        ydl_factory=fake_ydl_factory(),
        spawn=threaded_spawn,
    )
    for thread in threads:
        thread.join()

    started = _ids(events, VideoStarted)
    assert sorted(started) == sorted(entry.id for entry in entries)
    assert len(started) == len(entries)
    worker_finished = [e for e in events if isinstance(e, WorkerFinished)]
    assert sum(event.processed for event in worker_finished) == len(entries)
