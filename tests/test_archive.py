"""Tests for download-archive parsing and entries.json persistence."""

from yt_pdlp.archive import (
    Entry,
    archive_id_for,
    entries_from_json,
    entries_to_json,
    extract_video_id,
    parse_archive_ids,
    read_archive_ids,
    read_entries,
    write_entries,
)


def test_parse_archive_ids_takes_last_token_and_ignores_blanks():
    text = "youtube abc\nvimeo XYZ\n\n  \nbad\n"
    assert parse_archive_ids(text) == {"abc", "XYZ", "bad"}


def test_parse_archive_ids_preserves_hyphen_and_underscore_ids():
    text = "youtube aqz-KE-bpKQ\nyoutube eRsGyu_VLvQ\n"
    assert parse_archive_ids(text) == {"aqz-KE-bpKQ", "eRsGyu_VLvQ"}


def test_parse_archive_ids_empty_text():
    assert parse_archive_ids("") == set()


def test_read_archive_ids_missing_file_is_empty(tmp_path):
    assert read_archive_ids(tmp_path / "nope.txt") == set()


def test_read_archive_ids_reads_file(tmp_path):
    archive = tmp_path / "archive.txt"
    archive.write_text("youtube one\nyoutube two\n", encoding="utf-8")
    assert read_archive_ids(archive) == {"one", "two"}


def test_archive_id_for_lowercases_extractor():
    assert archive_id_for("Youtube", "BaW_jenozKc") == "youtube BaW_jenozKc"


def test_entries_json_round_trip():
    entries = [
        Entry(id="abc", url="https://youtu.be/abc", title="First"),
        Entry(id="def", url="https://youtu.be/def", title="Second [HD]"),
    ]
    text = entries_to_json(entries)
    assert entries_from_json(text) == entries


def test_extract_video_id_returns_entry_id():
    assert extract_video_id(Entry(id="xyz", url="u", title="t")) == "xyz"


def test_write_and_read_entries_round_trip(tmp_path):
    entries = [Entry(id="abc", url="https://youtu.be/abc", title="First")]
    target = tmp_path / "state" / "entries.json"
    write_entries(target, entries)
    assert target.exists()
    assert read_entries(target) == entries
