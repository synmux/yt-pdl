"""Tests for requested/landed/failed reconciliation set maths."""

from yt_pdlp.archive import Entry
from yt_pdlp.reconcile import failed_urls, reconcile


def test_landed_is_archive_intersect_requested_ignoring_unrelated():
    rec = reconcile(requested_ids={"a", "b", "c"}, archive_ids={"a", "b", "z"})
    assert rec.landed_ids == {"a", "b"}
    assert rec.failed_ids == {"c"}
    assert rec.requested_count == 3
    assert rec.landed_count == 2
    assert rec.failed_count == 1


def test_already_present_excludes_downloaded_this_run():
    rec = reconcile(
        requested_ids={"a", "b"},
        archive_ids={"a", "b"},
        downloaded_this_run={"b"},
    )
    assert rec.landed_ids == {"a", "b"}
    assert rec.downloaded_this_run == {"b"}
    assert rec.already_present == {"a"}
    assert rec.downloaded_count == 1
    assert rec.already_present_count == 1


def test_downloaded_this_run_clamped_to_landed():
    rec = reconcile(
        requested_ids={"a"},
        archive_ids={"a"},
        downloaded_this_run={"a", "ghost"},
    )
    assert rec.downloaded_this_run == {"a"}
    assert rec.already_present == set()


def test_missing_files_when_file_presence_supplied():
    rec = reconcile(
        requested_ids={"a", "b"},
        archive_ids={"a", "b"},
        landed_with_files={"a"},
    )
    assert rec.missing_files == {"b"}
    assert rec.missing_files_count == 1


def test_missing_files_empty_when_not_supplied():
    rec = reconcile(requested_ids={"a"}, archive_ids={"a"})
    assert rec.missing_files == set()


def test_failed_urls_in_entries_order():
    entries = [
        Entry(id="a", url="https://x/a", title="A"),
        Entry(id="b", url="https://x/b", title="B"),
        Entry(id="c", url="https://x/c", title="C"),
    ]
    rec = reconcile(requested_ids={"a", "b", "c"}, archive_ids={"b"})
    assert failed_urls(rec, entries) == ["https://x/a", "https://x/c"]
