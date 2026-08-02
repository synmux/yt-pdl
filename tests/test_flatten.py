"""Tests for flattening playlist/channel/video sources into Entry objects."""

from typing import Any

import pytest

from yt_pdlp.archive import Entry
from yt_pdlp.errors import FlattenError
from yt_pdlp.flatten import dedupe_entries, flatten_source


class _FakeExtractor:
    """Maps each source URL to a scripted info dict (None = extraction failure)."""

    def __init__(self, infos: dict[str, dict[str, Any] | None]) -> None:
        self._infos = infos

    def __enter__(self) -> "_FakeExtractor":
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False

    def extract_info(self, url: str, *, download: bool) -> dict[str, Any] | None:
        assert download is False
        return self._infos[url]


def _factory(infos: dict[str, dict[str, Any] | None]):
    def make(opts: dict[str, Any]) -> _FakeExtractor:
        return _FakeExtractor(infos)

    return make


def test_flatten_maps_playlist_entries():
    info = {
        "entries": [
            {"id": "a", "url": "https://youtu.be/a", "title": "A"},
            {"id": "b", "url": "https://youtu.be/b", "title": "B"},
        ]
    }
    entries = flatten_source("u", {}, ydl_factory=_factory({"u": info}))
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
    entries = flatten_source("u", {}, ydl_factory=_factory({"u": info}))
    assert [entry.id for entry in entries] == ["a", "c"]


def test_flatten_uses_fallbacks_for_missing_title_and_url():
    info = {"entries": [{"id": "xyz"}]}
    entries = flatten_source("u", {}, ydl_factory=_factory({"u": info}))
    assert entries[0].id == "xyz"
    assert entries[0].title == "xyz"
    assert entries[0].url == "https://www.youtube.com/watch?v=xyz"


def test_flatten_raises_when_info_none():
    with pytest.raises(FlattenError):
        flatten_source("u", {}, ydl_factory=_factory({"u": None}))


def test_flatten_returns_empty_for_empty_playlist():
    # A valid but empty playlist is "nothing to do", not an extraction failure.
    assert flatten_source("u", {}, ydl_factory=_factory({"u": {"entries": []}})) == []


def test_flatten_single_video_yields_one_entry():
    info = {"id": "vid1", "title": "Solo", "webpage_url": "https://www.youtube.com/watch?v=vid1"}
    entries = flatten_source(
        "https://youtu.be/vid1", {}, ydl_factory=_factory({"https://youtu.be/vid1": info})
    )
    assert entries == [Entry("vid1", "https://www.youtube.com/watch?v=vid1", "Solo")]


def test_flatten_single_video_falls_back_to_source_url_and_id_title():
    entries = flatten_source(
        "https://youtu.be/vid2", {}, ydl_factory=_factory({"https://youtu.be/vid2": {"id": "vid2"}})
    )
    assert entries == [Entry("vid2", "https://youtu.be/vid2", "vid2")]


def test_flatten_raises_without_entries_or_id():
    with pytest.raises(FlattenError):
        flatten_source("u", {}, ydl_factory=_factory({"u": {"uploader": "someone"}}))


def test_flatten_channel_recurses_into_tab_references():
    channel = {
        "entries": [
            {"_type": "url", "ie_key": "YoutubeTab", "id": "videos-tab", "url": "https://tab"}
        ]
    }
    tab = {
        "entries": [
            {"id": "a", "url": "u1", "title": "A"},
            {"id": "b", "url": "u2", "title": "B"},
        ]
    }
    entries = flatten_source(
        "https://chan", {}, ydl_factory=_factory({"https://chan": channel, "https://tab": tab})
    )
    assert [entry.id for entry in entries] == ["a", "b"]


def test_flatten_expands_inline_nested_playlists():
    info = {
        "entries": [
            {"_type": "playlist", "id": "pl", "entries": [{"id": "a", "url": "u1", "title": "A"}]}
        ]
    }
    entries = flatten_source("u", {}, ydl_factory=_factory({"u": info}))
    assert [entry.id for entry in entries] == ["a"]


def test_flatten_depth_cap_warns_and_skips():
    channel = {
        "entries": [{"_type": "url", "ie_key": "YoutubeTab", "id": "t1", "url": "https://tab"}]
    }
    tab = {
        "entries": [
            {"id": "a", "url": "u1", "title": "A"},
            {"_type": "url", "ie_key": "YoutubeTab", "id": "t2", "url": "https://deeper"},
        ]
    }
    warnings: list[str] = []
    entries = flatten_source(
        "https://chan",
        {},
        ydl_factory=_factory({"https://chan": channel, "https://tab": tab}),
        warn=warnings.append,
    )
    assert [entry.id for entry in entries] == ["a"]
    assert len(warnings) == 1


def test_dedupe_entries_keeps_first_occurrence_order():
    entries = [Entry("a", "u1", "A"), Entry("b", "u2", "B"), Entry("a", "u3", "A duplicate")]
    assert dedupe_entries(entries) == [Entry("a", "u1", "A"), Entry("b", "u2", "B")]
