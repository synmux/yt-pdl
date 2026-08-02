"""Construct the option dicts handed to ``yt_dlp.YoutubeDL``.

These functions are pure (no I/O, no ``YoutubeDL`` instantiation) so the exact
dicts can be asserted in tests. They encode the verified yt-dlp API facts:

* remux is a **postprocessor**, not an option key, and is omitted when no format
  is requested (``preferedformat`` is yt-dlp's spelling, single "r");
* ``ignoreerrors`` must be set explicitly (the API default is ``False``), on the
  flatten/export opts too — an unavailable source then yields a ``None`` info
  dict instead of raising ``DownloadError`` out of ``extract_info``;
* ``remote_components`` must allow ``ejs:github``: cookie-authenticated YouTube
  clients need yt-dlp's EJS challenge-solver script (run via Deno/Node), which
  yt-dlp refuses to fetch unless explicitly permitted — without it every video
  yields only storyboard images ("Requested format is not available");
* the output directory is set via ``paths={'home': ...}`` with a filename-only
  ``outtmpl``;
* cookies come from a file or directly from the browser, never both.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import RunConfig

ProgressHook = Callable[[dict[str, Any]], None]
OUTPUT_TEMPLATE = "%(title)s [%(id)s].%(ext)s"


@dataclass(frozen=True, slots=True)
class CookieMode:
    """How workers should obtain cookies: a written file, or the live browser."""

    cookiefile: Path | None = None
    cookiesfrombrowser: tuple[str, ...] | None = None

    @classmethod
    def from_file(cls, cookie_file: Path) -> "CookieMode":
        return cls(cookiefile=cookie_file)

    @classmethod
    def from_browser(cls, browser: str) -> "CookieMode":
        return cls(cookiesfrombrowser=(browser,))


def _apply_cookies(opts: dict[str, Any], cookie_mode: CookieMode) -> None:
    if cookie_mode.cookiefile is not None:
        opts["cookiefile"] = str(cookie_mode.cookiefile)
    elif cookie_mode.cookiesfrombrowser is not None:
        opts["cookiesfrombrowser"] = cookie_mode.cookiesfrombrowser


def build_download_opts(
    config: RunConfig,
    *,
    cookie_mode: CookieMode,
    progress_hook: ProgressHook | None = None,
    postprocessor_hook: ProgressHook | None = None,
    logger: object | None = None,
) -> dict[str, Any]:
    """Build the per-worker download options for one ``YoutubeDL`` instance."""
    opts: dict[str, Any] = {
        "paths": {"home": str(config.paths.output_dir)},
        "outtmpl": OUTPUT_TEMPLATE,
        "download_archive": str(config.paths.archive_file),
        "concurrent_fragment_downloads": config.fragments,
        "remote_components": ["ejs:github"],
        "ignoreerrors": True,
        "overwrites": False,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }
    _apply_cookies(opts, cookie_mode)
    if config.remux_format:
        opts["postprocessors"] = [
            {"key": "FFmpegVideoRemuxer", "preferedformat": config.remux_format}
        ]
    if progress_hook is not None:
        opts["progress_hooks"] = [progress_hook]
    if postprocessor_hook is not None:
        opts["postprocessor_hooks"] = [postprocessor_hook]
    if logger is not None:
        opts["logger"] = logger
    return opts


def build_flatten_opts(*, cookie_mode: CookieMode) -> dict[str, Any]:
    """Build the read-only flat-extraction options (no download)."""
    opts: dict[str, Any] = {
        "extract_flat": "in_playlist",
        "ignoreerrors": True,
        "quiet": True,
        "no_warnings": True,
    }
    _apply_cookies(opts, cookie_mode)
    return opts


def build_cookie_export_opts(config: RunConfig) -> dict[str, Any]:
    """Build options that read the browser once and dump cookies to the file.

    Used for the combined bootstrap call: a single read-only ``extract_info``
    both flattens the playlist and writes ``cookies.txt`` for the workers to reuse.
    """
    return {
        "cookiesfrombrowser": (config.browser,),
        "cookiefile": str(config.paths.cookie_file),
        "extract_flat": "in_playlist",
        "ignoreerrors": True,
        "quiet": True,
        "no_warnings": True,
    }
