"""Tests for run configuration, URL-file parsing and state-path resolution."""

import dataclasses
from pathlib import Path

import pytest

from yt_pdlp.config import (
    STATE_DIR_NAME,
    WATCH_LATER_URL,
    parse_url_file,
    resolve_run_config,
    resolve_state_paths,
)


def _resolve(**overrides):
    settings = {
        "jobs": 4,
        "urls": (WATCH_LATER_URL,),
        "output_dir": Path("downloads"),
        "browser": "chrome",
        "remux_format": "mp4",
        "fragments": 1,
        "dry_run": False,
        "plain_flag": False,
        "is_tty": True,
        "cwd": Path("/work"),
    }
    settings.update(overrides)
    return resolve_run_config(**settings)


def test_state_paths_layout_under_output_dir():
    output = Path("/tmp/media")
    paths = resolve_state_paths(output, cwd=Path("/unused"))

    assert paths.output_dir == output
    assert paths.state_dir == output / STATE_DIR_NAME
    assert paths.cookie_file == output / STATE_DIR_NAME / "cookies.txt"
    assert paths.entries_file == output / STATE_DIR_NAME / "entries.json"
    assert paths.archive_file == output / STATE_DIR_NAME / "archive.txt"
    assert paths.failed_file == output / STATE_DIR_NAME / "failed.txt"
    assert paths.report_file == output / STATE_DIR_NAME / "report.txt"


def test_relative_output_resolved_against_cwd():
    paths = resolve_state_paths(Path("downloads"), cwd=Path("/home/user/project"))

    assert paths.output_dir == Path("/home/user/project/downloads")
    assert paths.archive_file == Path("/home/user/project/downloads/.ytdlp-state/archive.txt")


def test_absolute_output_left_untouched():
    paths = resolve_state_paths(Path("/srv/dl"), cwd=Path("/home/user"))
    assert paths.output_dir == Path("/srv/dl")


@pytest.mark.parametrize(
    ("plain_flag", "is_tty", "expected_plain"),
    [
        (False, True, False),
        (False, False, True),
        (True, True, True),
        (True, False, True),
    ],
)
def test_plain_is_flag_or_not_tty(plain_flag, is_tty, expected_plain):
    config = _resolve(plain_flag=plain_flag, is_tty=is_tty)
    assert config.plain is expected_plain


def test_run_config_carries_fields_and_paths():
    config = _resolve(
        jobs=6,
        urls=("https://example.com/playlist",),
        output_dir=Path("out"),
        browser="firefox",
        remux_format="",
        fragments=3,
        dry_run=True,
    )
    assert config.jobs == 6
    assert config.urls == ("https://example.com/playlist",)
    assert config.browser == "firefox"
    assert config.remux_format == ""
    assert config.fragments == 3
    assert config.dry_run is True
    assert config.paths.output_dir == Path("/work/out")


def test_run_config_normalises_urls_to_a_tuple():
    config = _resolve(urls=["https://a.example/one", "https://b.example/two"])
    assert config.urls == ("https://a.example/one", "https://b.example/two")


def test_run_config_is_frozen():
    config = _resolve()
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.jobs = 99  # type: ignore[misc]


def test_parse_url_file_skips_comments_blanks_and_whitespace():
    byte_order_mark = chr(0xFEFF)
    text = byte_order_mark + (
        "# leading comment\n"
        "\n"
        "https://a.example/one\n"
        "   https://b.example/two   \n"
        "; semicolon comment\n"
        "] bracket comment\n"
        "https://c.example/three"
    )
    assert parse_url_file(text) == (
        "https://a.example/one",
        "https://b.example/two",
        "https://c.example/three",
    )


def test_parse_url_file_of_only_comments_or_empty_yields_nothing():
    assert parse_url_file("") == ()
    assert parse_url_file("# a\n; b\n] c\n\n") == ()
