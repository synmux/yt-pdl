"""Click CLI: a default-command group exposing ``download`` and ``flush``.

A bare or option-first invocation runs ``download`` (the default); ``flush`` and
``--help`` route normally. Input validation uses Click types so bad input fails
fast with a clear message and a non-zero exit.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import click

from .config import WATCH_LATER_URL, resolve_run_config
from .errors import FlattenError, YtdlpParallelError
from .runner import run_download, run_flush

_SWEET_SPOT_MAX = 8


class DefaultGroup(click.Group):
    """A group whose bare/option-first invocation falls through to a default command."""

    _PASSTHROUGH = frozenset({"--help", "-h"})

    def __init__(
        self, *args: Any, default_command: str | None = None, **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self.default_command = default_command

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        if self.default_command is not None and (
            not args
            or (args[0] not in self.commands and args[0] not in self._PASSTHROUGH)
        ):
            args = [self.default_command, *args]
        return super().parse_args(ctx, args)


@click.group(cls=DefaultGroup, default_command="download")
def cli() -> None:
    """Download a YouTube playlist with several concurrent yt-dlp workers."""


@cli.command()
@click.option(
    "--jobs",
    "-j",
    type=click.IntRange(min=1),
    default=4,
    show_default=True,
    help="Number of concurrent workers.",
)
@click.option(
    "--url",
    "-u",
    default=WATCH_LATER_URL,
    show_default=True,
    help="Playlist (or any yt-dlp-supported) URL.",
)
@click.option(
    "--output",
    "-o",
    "output_dir",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    default=Path("downloads"),
    show_default=True,
    help="Output directory (created if absent).",
)
@click.option(
    "--browser",
    "-b",
    default="chrome",
    show_default=True,
    help="Browser to read cookies from.",
)
@click.option(
    "--format",
    "-f",
    "remux_format",
    default="mp4",
    show_default=True,
    help="Remux container; an empty string disables remux.",
)
@click.option(
    "--fragments",
    "-N",
    type=click.IntRange(min=1),
    default=1,
    show_default=True,
    help="concurrent_fragment_downloads per worker (intra-video).",
)
@click.option(
    "--dry-run", is_flag=True, default=False, help="Plan only; download nothing."
)
@click.option(
    "--plain",
    "plain",
    is_flag=True,
    default=False,
    help="Disable the Textual UI; emit line-based progress.",
)
def download(
    jobs: int,
    url: str,
    output_dir: Path,
    browser: str,
    remux_format: str,
    fragments: int,
    dry_run: bool,
    plain: bool,
) -> None:
    """Download outstanding playlist items (the default command)."""
    config = resolve_run_config(
        jobs=jobs,
        url=url,
        output_dir=output_dir,
        browser=browser,
        remux_format=remux_format,
        fragments=fragments,
        dry_run=dry_run,
        plain_flag=plain,
        is_tty=sys.stdout.isatty(),
    )
    if jobs > _SWEET_SPOT_MAX:
        click.echo(
            f"Warning: {jobs} workers exceeds the 4–8 sweet spot; YouTube may "
            "throttle (HTTP 429) and total throughput can drop.",
            err=True,
        )
    try:
        exit_code = run_download(
            config, warn=lambda message: click.echo(message, err=True)
        )
    except FlattenError as error:
        click.echo(
            f"{error}\nAre you signed in to YouTube in {browser!r}? On macOS you "
            f"may need to grant Keychain access or quit {browser}.",
            err=True,
        )
        raise SystemExit(1) from error
    except YtdlpParallelError as error:
        click.echo(str(error), err=True)
        raise SystemExit(1) from error
    raise SystemExit(exit_code)


@cli.command()
@click.option(
    "--output",
    "-o",
    "output_dir",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    default=Path("downloads"),
    show_default=True,
    help="Locate and reconcile this output's state directory.",
)
@click.option(
    "--url",
    "-u",
    default=None,
    help="Re-flatten this playlist to define the requested set.",
)
def flush(output_dir: Path, url: str | None) -> None:
    """Reconcile requested vs landed vs failed for an existing output directory."""
    try:
        exit_code = run_flush(output_dir, url)
    except YtdlpParallelError as error:
        click.echo(str(error), err=True)
        raise SystemExit(1) from error
    raise SystemExit(exit_code)
