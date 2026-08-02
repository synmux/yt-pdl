"""Resolved run configuration and state-directory path layout.

Everything here is pure: the resolver takes ``cwd`` and ``is_tty`` as explicit
arguments rather than reading the real filesystem or terminal, so the CLI layer
supplies the live values while tests can pin them deterministically.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

WATCH_LATER_URL = "https://www.youtube.com/playlist?list=WL"
"""Default playlist: the signed-in user's Watch Later list."""

STATE_DIR_NAME = ".ytdlp-state"
"""Name of the per-output state directory holding cookies, archive and reports."""

_BYTE_ORDER_MARK = chr(0xFEFF)
_URL_FILE_COMMENT_PREFIXES = ("#", ";", "]")


def parse_url_file(text: str) -> tuple[str, ...]:
    """Parse ``--batch-file`` text: one source URL per line (yt-dlp parity).

    Strips a leading byte-order mark and per-line whitespace; skips blank lines
    and comment lines starting with ``#``, ``;`` or ``]``.
    """
    urls: list[str] = []
    for raw_line in text.lstrip(_BYTE_ORDER_MARK).splitlines():
        line = raw_line.strip()
        if not line or line.startswith(_URL_FILE_COMMENT_PREFIXES):
            continue
        urls.append(line)
    return tuple(urls)


@dataclass(frozen=True, slots=True)
class StatePaths:
    """Absolute paths for the output directory and every state artefact."""

    output_dir: Path
    state_dir: Path
    cookie_file: Path
    entries_file: Path
    archive_file: Path
    failed_file: Path
    report_file: Path


@dataclass(frozen=True, slots=True)
class RunConfig:
    """A fully-resolved download/dry-run configuration."""

    jobs: int
    urls: tuple[str, ...]
    paths: StatePaths
    browser: str
    remux_format: str
    fragments: int
    dry_run: bool
    plain: bool


def resolve_state_paths(output_dir: Path, *, cwd: Path | None = None) -> StatePaths:
    """Resolve ``output_dir`` to an absolute path and derive the state layout.

    A relative ``output_dir`` is joined onto ``cwd`` (defaulting to the process
    working directory). Symlinks are deliberately not resolved, keeping the
    result a predictable join of the inputs.
    """
    base = cwd if cwd is not None else Path.cwd()
    output_abs = output_dir if output_dir.is_absolute() else base / output_dir
    state_dir = output_abs / STATE_DIR_NAME
    return StatePaths(
        output_dir=output_abs,
        state_dir=state_dir,
        cookie_file=state_dir / "cookies.txt",
        entries_file=state_dir / "entries.json",
        archive_file=state_dir / "archive.txt",
        failed_file=state_dir / "failed.txt",
        report_file=state_dir / "report.txt",
    )


def resolve_run_config(
    *,
    jobs: int,
    urls: Sequence[str],
    output_dir: Path,
    browser: str,
    remux_format: str,
    fragments: int,
    dry_run: bool,
    plain_flag: bool,
    is_tty: bool,
    cwd: Path | None = None,
) -> RunConfig:
    """Build a :class:`RunConfig` from raw CLI inputs.

    ``plain`` is forced on when the user passes ``--plain`` **or** when stdout is
    not a terminal (Textual cannot render without a TTY).
    """
    paths = resolve_state_paths(output_dir, cwd=cwd)
    return RunConfig(
        jobs=jobs,
        urls=tuple(urls),
        paths=paths,
        browser=browser,
        remux_format=remux_format,
        fragments=fragments,
        dry_run=dry_run,
        plain=plain_flag or not is_tty,
    )
