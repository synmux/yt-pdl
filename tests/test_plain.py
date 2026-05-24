"""Tests for the plain (non-TTY) runner."""

import threading

from fakes import fake_ydl_factory
from yt_pdl.archive import Entry
from yt_pdl.config import resolve_run_config
from yt_pdl.options import CookieMode
from yt_pdl.plain import run_plain

COOKIE_MODE = CookieMode.from_browser("chrome")


def _config(tmp_path, jobs=2):
    return resolve_run_config(
        jobs=jobs,
        url="https://example.com/playlist",
        output_dir=tmp_path,
        browser="chrome",
        remux_format="mp4",
        fragments=1,
        dry_run=False,
        plain_flag=True,
        is_tty=False,
        cwd=tmp_path,
    )


def _entries(ids):
    return [Entry(i, f"https://youtu.be/{i}", f"Title {i}") for i in ids]


def test_run_plain_downloads_all_and_prints(tmp_path, capsys):
    result = run_plain(
        _entries(["a", "b"]),
        _config(tmp_path),
        COOKIE_MODE,
        ydl_factory=fake_ydl_factory(),
    )
    out = capsys.readouterr().out

    assert result.downloaded_ids == {"a", "b"}
    assert result.cancelled is False
    assert "Title a" in out
    assert "Title b" in out


def test_run_plain_reports_failure_line(tmp_path, capsys):
    result = run_plain(
        _entries(["ok", "bad"]),
        _config(tmp_path),
        COOKIE_MODE,
        ydl_factory=fake_ydl_factory(fail_ids=frozenset({"bad"})),
    )
    out = capsys.readouterr().out

    assert result.failed_ids == {"bad"}
    assert "FAILED" in out


def test_run_plain_cancelled_returns_partial(tmp_path):
    cancel_event = threading.Event()
    cancel_event.set()
    result = run_plain(
        _entries(["a", "b", "c"]),
        _config(tmp_path),
        COOKIE_MODE,
        ydl_factory=fake_ydl_factory(),
        cancel_event=cancel_event,
    )
    assert result.cancelled is True
    assert result.downloaded_ids == set()
