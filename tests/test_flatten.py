"""Tests for flattening a playlist into Entry objects."""

from typing import Any

import pytest

from yt_pdl.archive import Entry
from yt_pdl.errors import FlattenError
from yt_pdl.flatten import flatten_playlist


class _FakeExtractor:
    def __init__(self, info: dict[str, Any] | None) -> None:
        self._info = info

    def __enter__(self) -> "_FakeExtractor":
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False

    def extract_info(self, url: str, *, download: bool) -> dict[str, Any] | None:
        assert download is False
        return self._info


def _factory(info: dict[str, Any] | None):
    def make(opts: dict[str, Any]) -> _FakeExtractor:
        return _FakeExtractor(info)

    return make


def test_flatten_maps_entries():
    info = {
        "entries": [
            {"id": "a", "url": "https://youtu.be/a", "title": "A"},
            {"id": "b", "url": "https://youtu.be/b", "title": "B"},
        ]
    }
    entries = flatten_playlist("u", {}, ydl_factory=_factory(info))
    assert entries == [
        Entry("a", "https://youtu.be/a", "A"),
        Entry("b", "https://youtu.be/b", "B"),
    ]


def test_flatten_skips_none_entries():
    info = {
        "entries": [
            {"id": "a", "url": "u1", "title": "A"},
            None,
            {"id": "c", "url": "u3", "title": "C"},
        ]
    }
    entries = flatten_playlist("u", {}, ydl_factory=_factory(info))
    assert [entry.id for entry in entries] == ["a", "c"]


def test_flatten_uses_fallbacks_for_missing_title_and_url():
    info = {"entries": [{"id": "xyz"}]}
    entries = flatten_playlist("u", {}, ydl_factory=_factory(info))
    assert entries[0].id == "xyz"
    assert entries[0].title == "xyz"
    assert entries[0].url == "https://www.youtube.com/watch?v=xyz"


def test_flatten_raises_when_info_none():
    with pytest.raises(FlattenError):
        flatten_playlist("u", {}, ydl_factory=_factory(None))


def test_flatten_returns_empty_for_empty_playlist():
    # A valid but empty playlist is "nothing to do", not an extraction failure.
    assert flatten_playlist("u", {}, ydl_factory=_factory({"entries": []})) == []


def test_flatten_raises_when_entries_key_absent():
    with pytest.raises(FlattenError):
        flatten_playlist("u", {}, ydl_factory=_factory({"id": "single-video"}))
