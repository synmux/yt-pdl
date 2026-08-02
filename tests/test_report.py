"""Tests for human-readable report and dry-run plan rendering."""

from pathlib import Path

from yt_pdlp.config import resolve_run_config
from yt_pdlp.reconcile import reconcile
from yt_pdlp.report import render_dry_run_plan, render_report_text


def _rec(requested, archive, downloaded=None, landed_with_files=None):
    return reconcile(
        requested_ids=requested,
        archive_ids=archive,
        downloaded_this_run=downloaded,
        landed_with_files=landed_with_files,
    )


def _line_with(text: str, label: str) -> str:
    return next(line for line in text.splitlines() if label in line)


def test_report_text_shows_counts_and_british_labels():
    # requested 4; landed {a,b,c}; downloaded {c}; already_present {a,b}; failed {d}
    rec = _rec({"a", "b", "c", "d"}, {"a", "b", "c"}, downloaded={"c"})
    text = render_report_text(rec)

    assert "4" in _line_with(text, "Playlist:")
    assert "2" in _line_with(text, "Already present:")
    assert "1" in _line_with(text, "Downloaded now:")
    assert "1" in _line_with(text, "Failed / missing:")
    assert "skipped via archive" in text


def test_report_text_notes_cancellation():
    text = render_report_text(_rec({"a"}, {"a"}), cancelled=True)
    assert "cancelled" in text.lower()


def test_report_text_lists_failure_reasons():
    rec = _rec({"a", "b"}, {"a"})  # b failed
    text = render_report_text(rec, failure_reasons={"b": "Private video"})
    assert "Private video" in text
    assert "b" in text


def test_report_text_warns_about_missing_files():
    # both archived, but b has no file on disk
    rec = _rec({"a", "b"}, {"a", "b"}, landed_with_files={"a"})
    text = render_report_text(rec)
    assert "no output file" in text.lower()


def test_dry_run_plan_contains_banner_paths_and_opts():
    config = resolve_run_config(
        jobs=4,
        urls=("https://www.youtube.com/playlist?list=WL",),
        output_dir=Path("downloads"),
        browser="chrome",
        remux_format="mp4",
        fragments=2,
        dry_run=True,
        plain_flag=False,
        is_tty=True,
        cwd=Path("/work"),
    )
    effective_opts = {
        "outtmpl": "%(title)s [%(id)s].%(ext)s",
        "download_archive": str(config.paths.archive_file),
        "concurrent_fragment_downloads": 2,
    }
    plan = render_dry_run_plan(
        config,
        total=1000,
        already_present=120,
        outstanding=880,
        effective_opts=effective_opts,
    )

    assert "DRY RUN" in plan
    assert "nothing downloaded" in plan.lower()
    assert "1000" in plan
    assert "120" in plan
    assert "880" in plan
    assert str(config.paths.archive_file) in plan
    assert str(config.paths.cookie_file) in plan
    assert "%(title)s [%(id)s].%(ext)s" in plan
    assert "chrome" in plan
