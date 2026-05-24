"""End-to-end integration: auto-flush report at end of run, and resume across runs."""

from fakes import fake_ydl_factory
from yt_pdl.config import resolve_run_config
from yt_pdl.runner import run_download

_THREE = {
    "entries": [
        {"id": "a", "url": "https://youtu.be/a", "title": "Alpha"},
        {"id": "b", "url": "https://youtu.be/b", "title": "Bravo"},
        {"id": "c", "url": "https://youtu.be/c", "title": "Charlie"},
    ]
}


def _config(tmp_path, jobs=2):
    return resolve_run_config(
        jobs=jobs,
        url="https://example.com/playlist",
        output_dir=tmp_path / "dl",
        browser="chrome",
        remux_format="mp4",
        fragments=1,
        dry_run=False,
        plain_flag=True,
        is_tty=False,
        cwd=tmp_path,
    )


def _line(text, label):
    return next(line for line in text.splitlines() if label in line)


def test_auto_flush_writes_report_and_failed(tmp_path, capsys):
    config = _config(tmp_path)
    code = run_download(
        config,
        ydl_factory=fake_ydl_factory(info=_THREE, fail_ids=frozenset({"c"})),
        warn=lambda _m: None,
    )
    out = capsys.readouterr().out

    assert code == 0
    report = config.paths.report_file.read_text(encoding="utf-8")
    assert "2" in _line(report, "Downloaded now:")
    assert "1" in _line(report, "Failed / missing:")
    assert (
        config.paths.failed_file.read_text(encoding="utf-8").strip()
        == "https://youtu.be/c"
    )
    assert "Playlist:" in out  # report also printed to stdout


def test_resume_skips_archived_retries_failed(tmp_path, capsys):
    config = _config(tmp_path)

    # First run: a and b succeed (recorded in the archive); c fails (not recorded).
    run_download(
        config,
        ydl_factory=fake_ydl_factory(info=_THREE, fail_ids=frozenset({"c"})),
        warn=lambda _m: None,
    )
    capsys.readouterr()  # discard first-run output

    # Second run: a and b are skipped via the archive; only c is attempted (succeeds).
    run_download(
        config, ydl_factory=fake_ydl_factory(info=_THREE), warn=lambda _m: None
    )
    out = capsys.readouterr().out

    assert "↷ already have: Alpha" in out
    assert "↷ already have: Bravo" in out
    assert "✓ Charlie" in out
    assert "✓ Alpha" not in out  # not re-downloaded

    report = config.paths.report_file.read_text(encoding="utf-8")
    assert "0" in _line(report, "Failed / missing:")
    assert config.paths.failed_file.read_text(encoding="utf-8") == ""
