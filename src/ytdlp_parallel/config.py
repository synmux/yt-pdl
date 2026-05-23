"""Resolved run configuration and state-directory path layout.

Everything here is pure: the resolver takes ``cwd`` and ``is_tty`` as explicit
arguments rather than reading the real filesystem or terminal, so the CLI layer
supplies the live values while tests can pin them deterministically.
"""

from dataclasses import dataclass
from pathlib import Path

WATCH_LATER_URL = "https://www.youtube.com/playlist?list=WL"
"""Default playlist: the signed-in user's Watch Later list."""

STATE_DIR_NAME = ".ytdlp-state"
"""Name of the per-output state directory holding cookies, archive and reports."""


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
    url: str
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
    url: str,
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
        url=url,
        paths=paths,
        browser=browser,
        remux_format=remux_format,
        fragments=fragments,
        dry_run=dry_run,
        plain=plain_flag or not is_tty,
    )
