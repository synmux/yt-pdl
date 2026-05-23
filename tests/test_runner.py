"""Tests for the run_download dry-run path (read-only plan, no download)."""

from fakes import fake_flat_factory
from ytdlp_parallel.archive import Entry, read_entries
from ytdlp_parallel.config import resolve_run_config
from ytdlp_parallel.runner import run_download


def _dry_config(tmp_path):
    return resolve_run_config(
        jobs=4,
        url="https://example.com/playlist",
        output_dir=tmp_path / "dl",
        browser="chrome",
        remux_format="mp4",
        fragments=1,
        dry_run=True,
        plain_flag=False,
        is_tty=True,
        cwd=tmp_path,
    )


def test_dry_run_prints_plan_writes_entries_no_media(tmp_path, capsys):
    config = _dry_config(tmp_path)
    info = {
        "entries": [
            {"id": "a", "url": "https://youtu.be/a", "title": "A"},
            {"id": "b", "url": "https://youtu.be/b", "title": "B"},
        ]
    }
    code = run_download(config, ydl_factory=fake_flat_factory(info), warn=lambda _m: None)
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
    config = _dry_config(tmp_path)
    config.paths.state_dir.mkdir(parents=True, exist_ok=True)
    config.paths.archive_file.write_text("youtube a\n", encoding="utf-8")
    info = {
        "entries": [
            {"id": "a", "url": "u1", "title": "A"},
            {"id": "b", "url": "u2", "title": "B"},
        ]
    }
    run_download(config, ydl_factory=fake_flat_factory(info), warn=lambda _m: None)
    out = capsys.readouterr().out

    present_line = next(line for line in out.splitlines() if "already in archive" in line)
    assert "1" in present_line


def test_dry_run_no_warning_when_cookie_file_written(tmp_path):
    config = _dry_config(tmp_path)
    info = {"entries": [{"id": "a", "url": "u", "title": "A"}]}
    warnings: list[str] = []
    run_download(
        config,
        ydl_factory=fake_flat_factory(info, write_cookies=True),
        warn=warnings.append,
    )
    assert warnings == []


def test_dry_run_warns_when_cookie_file_missing(tmp_path):
    config = _dry_config(tmp_path)
    info = {"entries": [{"id": "a", "url": "u", "title": "A"}]}
    warnings: list[str] = []
    run_download(
        config,
        ydl_factory=fake_flat_factory(info, write_cookies=False),
        warn=warnings.append,
    )
    assert len(warnings) == 1
