"""Tests for YoutubeDL option-dict construction (encodes verified yt-dlp API facts)."""

from pathlib import Path

from ytdlp_parallel.config import resolve_run_config
from ytdlp_parallel.ytdlp_options import (
    CookieMode,
    build_cookie_export_opts,
    build_download_opts,
    build_flatten_opts,
)


def _config(remux_format="mp4", fragments=1, browser="chrome", output="downloads"):
    return resolve_run_config(
        jobs=4,
        url="https://example.com/playlist",
        output_dir=Path(output),
        browser=browser,
        remux_format=remux_format,
        fragments=fragments,
        dry_run=False,
        plain_flag=False,
        is_tty=True,
        cwd=Path("/work"),
    )


def test_download_opts_core_keys():
    config = _config()
    opts = build_download_opts(
        config, cookie_mode=CookieMode.from_file(config.paths.cookie_file)
    )
    assert opts["outtmpl"] == "%(title)s [%(id)s].%(ext)s"
    assert opts["paths"] == {"home": "/work/downloads"}
    assert opts["download_archive"] == "/work/downloads/.ytdlp-state/archive.txt"
    assert opts["concurrent_fragment_downloads"] == 1
    assert opts["ignoreerrors"] is True
    assert opts["overwrites"] is False
    assert opts["quiet"] is True
    assert opts["no_warnings"] is True
    assert opts["noprogress"] is True


def test_download_opts_remux_present_when_format_set():
    opts = build_download_opts(
        _config(remux_format="mp4"), cookie_mode=CookieMode.from_file(Path("/c"))
    )
    assert opts["postprocessors"] == [
        {"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}
    ]


def test_download_opts_remux_absent_when_format_empty():
    opts = build_download_opts(
        _config(remux_format=""), cookie_mode=CookieMode.from_file(Path("/c"))
    )
    assert "postprocessors" not in opts


def test_download_opts_fragments_passthrough():
    opts = build_download_opts(
        _config(fragments=5), cookie_mode=CookieMode.from_file(Path("/c"))
    )
    assert opts["concurrent_fragment_downloads"] == 5


def test_download_opts_cookiefile_mode():
    opts = build_download_opts(
        _config(), cookie_mode=CookieMode.from_file(Path("/tmp/cookies.txt"))
    )
    assert opts["cookiefile"] == "/tmp/cookies.txt"
    assert "cookiesfrombrowser" not in opts


def test_download_opts_cookiesfrombrowser_mode():
    opts = build_download_opts(
        _config(browser="firefox"), cookie_mode=CookieMode.from_browser("firefox")
    )
    assert opts["cookiesfrombrowser"] == ("firefox",)
    assert "cookiefile" not in opts


def test_download_opts_hooks_only_when_provided():
    def hook(payload: dict) -> None:
        return None

    with_hooks = build_download_opts(
        _config(),
        cookie_mode=CookieMode.from_file(Path("/c")),
        progress_hook=hook,
        postprocessor_hook=hook,
    )
    assert with_hooks["progress_hooks"] == [hook]
    assert with_hooks["postprocessor_hooks"] == [hook]

    without_hooks = build_download_opts(
        _config(), cookie_mode=CookieMode.from_file(Path("/c"))
    )
    assert "progress_hooks" not in without_hooks
    assert "postprocessor_hooks" not in without_hooks


def test_download_opts_logger_only_when_provided():
    logger = object()
    with_logger = build_download_opts(
        _config(), cookie_mode=CookieMode.from_file(Path("/c")), logger=logger
    )
    assert with_logger["logger"] is logger

    without_logger = build_download_opts(
        _config(), cookie_mode=CookieMode.from_file(Path("/c"))
    )
    assert "logger" not in without_logger


def test_flatten_opts():
    opts = build_flatten_opts(cookie_mode=CookieMode.from_file(Path("/tmp/c.txt")))
    assert opts["extract_flat"] == "in_playlist"
    assert opts["quiet"] is True
    assert opts["no_warnings"] is True
    assert opts["cookiefile"] == "/tmp/c.txt"


def test_cookie_export_opts_reads_browser_and_writes_file():
    config = _config(browser="chrome")
    opts = build_cookie_export_opts(config)
    assert opts["cookiesfrombrowser"] == ("chrome",)
    assert opts["cookiefile"] == str(config.paths.cookie_file)
    assert opts["extract_flat"] == "in_playlist"
