"""Tests for run configuration and state-path resolution."""

import dataclasses
from pathlib import Path

import pytest

from ytdlp_parallel.config import (
    STATE_DIR_NAME,
    WATCH_LATER_URL,
    resolve_run_config,
    resolve_state_paths,
)


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
    assert paths.archive_file == Path(
        "/home/user/project/downloads/.ytdlp-state/archive.txt"
    )


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
    config = resolve_run_config(
        jobs=4,
        url=WATCH_LATER_URL,
        output_dir=Path("downloads"),
        browser="chrome",
        remux_format="mp4",
        fragments=1,
        dry_run=False,
        plain_flag=plain_flag,
        is_tty=is_tty,
        cwd=Path("/work"),
    )
    assert config.plain is expected_plain


def test_run_config_carries_fields_and_paths():
    config = resolve_run_config(
        jobs=6,
        url="https://example.com/playlist",
        output_dir=Path("out"),
        browser="firefox",
        remux_format="",
        fragments=3,
        dry_run=True,
        plain_flag=False,
        is_tty=True,
        cwd=Path("/work"),
    )
    assert config.jobs == 6
    assert config.url == "https://example.com/playlist"
    assert config.browser == "firefox"
    assert config.remux_format == ""
    assert config.fragments == 3
    assert config.dry_run is True
    assert config.paths.output_dir == Path("/work/out")


def test_run_config_is_frozen():
    config = resolve_run_config(
        jobs=4,
        url=WATCH_LATER_URL,
        output_dir=Path("downloads"),
        browser="chrome",
        remux_format="mp4",
        fragments=1,
        dry_run=False,
        plain_flag=False,
        is_tty=True,
        cwd=Path("/work"),
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.jobs = 99  # type: ignore[misc]
