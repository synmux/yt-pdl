"""Tests for the standalone flush reconciliation."""

import pytest

from fakes import fake_ydl_factory
from yt_pdlp.archive import Entry, write_entries
from yt_pdlp.config import resolve_state_paths
from yt_pdlp.errors import NoStateError
from yt_pdlp.runner import run_flush


def _seed(tmp_path, entries, *, archive_ids, media_ids):
    paths = resolve_state_paths(tmp_path / "dl")
    paths.state_dir.mkdir(parents=True, exist_ok=True)
    write_entries(paths.entries_file, entries)
    paths.archive_file.write_text(
        "".join(f"youtube {video_id}\n" for video_id in archive_ids), encoding="utf-8"
    )
    for media_id in media_ids:
        (paths.output_dir / f"Title {media_id} [{media_id}].mp4").write_text("x", encoding="utf-8")
    return paths


def test_flush_reports_counts_and_writes_failed(tmp_path, capsys):
    entries = [
        Entry("a", "https://x/a", "A"),
        Entry("b", "https://x/b", "B"),
        Entry("c", "https://x/c", "C"),
    ]
    paths = _seed(tmp_path, entries, archive_ids=["a", "b"], media_ids=["a", "b"])

    code = run_flush(tmp_path / "dl", None)
    out = capsys.readouterr().out

    assert code == 0
    assert "3" in next(line for line in out.splitlines() if "Playlist:" in line)
    assert paths.failed_file.read_text(encoding="utf-8").strip() == "https://x/c"
    assert paths.report_file.exists()


def test_flush_warns_about_missing_output_file(tmp_path, capsys):
    entries = [Entry("a", "https://x/a", "A")]
    _seed(tmp_path, entries, archive_ids=["a"], media_ids=[])

    run_flush(tmp_path / "dl", None)
    out = capsys.readouterr().out

    assert "no output file" in out.lower()


def test_flush_no_state_raises(tmp_path):
    with pytest.raises(NoStateError):
        run_flush(tmp_path / "empty", None)


def test_flush_reflatten_with_url(tmp_path, capsys):
    paths = resolve_state_paths(tmp_path / "dl")
    paths.state_dir.mkdir(parents=True, exist_ok=True)
    paths.archive_file.write_text("youtube a\n", encoding="utf-8")
    info = {
        "entries": [
            {"id": "a", "url": "https://x/a", "title": "A"},
            {"id": "b", "url": "https://x/b", "title": "B"},
        ]
    }

    code = run_flush(
        tmp_path / "dl",
        "https://example.com/pl",
        ydl_factory=fake_ydl_factory(info=info),
    )
    out = capsys.readouterr().out

    assert code == 0
    assert "2" in next(line for line in out.splitlines() if "Playlist:" in line)
    assert paths.entries_file.exists()
