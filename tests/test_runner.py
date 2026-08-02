"""Tests for run_download: dry-run plan, empty playlist, and plain execution."""

import pytest

from fakes import fake_ydl_factory
from yt_pdlp.archive import Entry, read_entries
from yt_pdlp.config import resolve_run_config
from yt_pdlp.errors import FlattenError
from yt_pdlp.runner import run_download

_TWO_ENTRIES = {
    "entries": [
        {"id": "a", "url": "https://youtu.be/a", "title": "A"},
        {"id": "b", "url": "https://youtu.be/b", "title": "B"},
    ]
}


def _config(tmp_path, *, dry_run, plain=True, urls=("https://example.com/playlist",)):
    return resolve_run_config(
        jobs=2,
        urls=urls,
        output_dir=tmp_path / "dl",
        browser="chrome",
        remux_format="mp4",
        fragments=1,
        dry_run=dry_run,
        plain_flag=plain,
        is_tty=False,
        cwd=tmp_path,
    )


def test_dry_run_prints_plan_writes_entries_no_media(tmp_path, capsys):
    config = _config(tmp_path, dry_run=True)
    code = run_download(
        config, ydl_factory=fake_ydl_factory(info=_TWO_ENTRIES), warn=lambda _m: None
    )
    out = capsys.readouterr().out

    assert code == 0
    assert "DRY RUN" in out
    assert "nothing downloaded" in out.lower()
    assert read_entries(config.paths.entries_file) == [
        Entry("a", "https://youtu.be/a", "A"),
        Entry("b", "https://youtu.be/b", "B"),
    ]
    media = [item for item in config.paths.output_dir.iterdir() if item.is_file()]
    assert media == []


def test_dry_run_counts_already_present(tmp_path, capsys):
    config = _config(tmp_path, dry_run=True)
    config.paths.state_dir.mkdir(parents=True, exist_ok=True)
    config.paths.archive_file.write_text("youtube a\n", encoding="utf-8")
    run_download(config, ydl_factory=fake_ydl_factory(info=_TWO_ENTRIES), warn=lambda _m: None)
    out = capsys.readouterr().out

    present_line = next(line for line in out.splitlines() if "already in archive" in line)
    assert "1" in present_line


def test_dry_run_no_warning_when_cookie_file_written(tmp_path):
    config = _config(tmp_path, dry_run=True)
    warnings: list[str] = []
    run_download(
        config,
        ydl_factory=fake_ydl_factory(info=_TWO_ENTRIES, write_cookies=True),
        warn=warnings.append,
    )
    assert warnings == []


def test_dry_run_warns_when_cookie_file_missing(tmp_path):
    config = _config(tmp_path, dry_run=True)
    warnings: list[str] = []
    run_download(
        config,
        ydl_factory=fake_ydl_factory(info=_TWO_ENTRIES, write_cookies=False),
        warn=warnings.append,
    )
    assert len(warnings) == 1


def test_empty_playlist_exits_zero_without_running(tmp_path, capsys):
    config = _config(tmp_path, dry_run=False)
    code = run_download(
        config, ydl_factory=fake_ydl_factory(info={"entries": []}), warn=lambda _m: None
    )
    assert code == 0
    assert "nothing to do" in capsys.readouterr().out.lower()


def test_multiple_sources_merge_and_dedupe(tmp_path):
    config = _config(
        tmp_path, dry_run=False, urls=("https://pl.example/one", "https://pl.example/two")
    )
    factory = fake_ydl_factory(
        infos={
            "https://pl.example/one": {
                "entries": [
                    {"id": "a", "url": "https://youtu.be/a", "title": "A"},
                    {"id": "b", "url": "https://youtu.be/b", "title": "B"},
                ]
            },
            "https://pl.example/two": {
                "entries": [
                    {"id": "b", "url": "https://youtu.be/b", "title": "B"},
                    {"id": "c", "url": "https://youtu.be/c", "title": "C"},
                ]
            },
        }
    )
    code = run_download(config, ydl_factory=factory, warn=lambda _m: None)

    assert code == 0
    assert [entry.id for entry in read_entries(config.paths.entries_file)] == ["a", "b", "c"]


def test_unavailable_source_skipped_with_warning(tmp_path):
    config = _config(
        tmp_path, dry_run=False, urls=("https://dead.example/video", "https://pl.example/live")
    )
    warnings: list[str] = []
    factory = fake_ydl_factory(
        infos={
            "https://dead.example/video": None,  # yt-dlp: "Video unavailable"
            "https://pl.example/live": {
                "entries": [{"id": "a", "url": "https://youtu.be/a", "title": "A"}]
            },
        }
    )
    code = run_download(config, ydl_factory=factory, warn=warnings.append)

    assert code == 0
    assert [entry.id for entry in read_entries(config.paths.entries_file)] == ["a"]
    assert len(warnings) == 1
    assert "https://dead.example/video" in warnings[0]


def test_all_sources_unavailable_raises_flatten_error(tmp_path):
    config = _config(tmp_path, dry_run=False, urls=("https://dead.example/video",))
    factory = fake_ydl_factory(infos={"https://dead.example/video": None})

    with pytest.raises(FlattenError):
        run_download(config, ydl_factory=factory, warn=lambda _m: None)


def test_plain_run_downloads_and_writes_report(tmp_path, capsys):
    config = _config(tmp_path, dry_run=False, plain=True)
    code = run_download(
        config, ydl_factory=fake_ydl_factory(info=_TWO_ENTRIES), warn=lambda _m: None
    )
    out = capsys.readouterr().out

    assert code == 0
    assert config.paths.report_file.exists()
    assert "Downloaded now:" in out
    report = config.paths.report_file.read_text(encoding="utf-8")
    assert "Playlist:" in report
    # failed.txt written (empty, since both succeeded)
    assert config.paths.failed_file.exists()
    assert config.paths.failed_file.read_text(encoding="utf-8") == ""
