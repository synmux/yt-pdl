"""Smoke tests for the Textual UI via the run_test harness (no real terminal)."""

from fakes import fake_ydl_factory
from yt_pdlp.archive import Entry
from yt_pdlp.config import resolve_run_config
from yt_pdlp.options import CookieMode
from yt_pdlp.tui.app import DownloadApp
from yt_pdlp.tui.summary import SummaryScreen

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
        plain_flag=False,
        is_tty=True,
        cwd=tmp_path,
    )


def _entries(ids):
    return [Entry(i, f"https://youtu.be/{i}", f"Title {i}") for i in ids]


def _app(tmp_path, entries, *, ydl_factory, jobs=2):
    return DownloadApp(
        entries,
        _config(tmp_path, jobs=jobs),
        COOKIE_MODE,
        ydl_factory=ydl_factory,
        summarise=lambda _result: "SUMMARY REPORT",
    )


async def test_tui_runs_workers_and_shows_summary(tmp_path):
    app = _app(tmp_path, _entries(["a", "b"]), ydl_factory=fake_ydl_factory())
    async with app.run_test() as pilot:
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()

        assert app._completed == 2
        assert app._failed == 0
        assert isinstance(app.screen, SummaryScreen)


async def test_tui_counts_failures(tmp_path):
    app = _app(
        tmp_path,
        _entries(["ok", "bad"]),
        ydl_factory=fake_ydl_factory(fail_ids=frozenset({"bad"})),
    )
    async with app.run_test() as pilot:
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()

        assert app._completed == 1
        assert app._failed == 1


async def test_tui_quit_cancels_mid_run(tmp_path):
    entries = _entries([f"v{index}" for index in range(20)])
    app = _app(tmp_path, entries, ydl_factory=fake_ydl_factory(delay=0.05), jobs=2)
    async with app.run_test() as pilot:
        await pilot.pause()  # let workers start
        await pilot.press("q")
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()

        assert app._cancelled is True
        # Cancelled mid-run: not every video was downloaded.
        assert len(app._builder.result().downloaded_ids) < len(entries)
