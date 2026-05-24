"""Orchestration: resolve config, bootstrap cookies + flatten, plan/run, reconcile.

This wires the pure layers together and (later) selects the front-end. It is the
only module that imports ``yt_dlp`` — and does so lazily so importing the package,
running ``--dry-run``, or running ``flush`` against cached state stays cheap.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .archive import Entry, read_archive_ids, read_entries, write_entries
from .config import RunConfig, resolve_run_config, resolve_state_paths
from .cookies import determine_cookie_mode
from .errors import NoStateError
from .events import RunResult
from .flatten import flatten_playlist
from .options import build_cookie_export_opts, build_download_opts
from .plain import run_plain
from .reconcile import Reconciliation, failed_urls, reconcile
from .report import render_dry_run_plan, render_report_text

Warn = Callable[[str], None]
YdlFactory = Callable[[dict[str, Any]], Any]

_FLUSH_BROWSER = "chrome"


def _default_ydl_factory() -> YdlFactory:
    import yt_dlp

    return yt_dlp.YoutubeDL


def _resolve_factory(ydl_factory: YdlFactory | None) -> YdlFactory:
    return ydl_factory if ydl_factory is not None else _default_ydl_factory()


def run_download(
    config: RunConfig, *, warn: Warn, ydl_factory: YdlFactory | None = None
) -> int:
    """Resolve, bootstrap cookies + flatten, then plan (dry-run) or download."""
    factory = _resolve_factory(ydl_factory)
    config.paths.state_dir.mkdir(parents=True, exist_ok=True)

    export_opts = build_cookie_export_opts(config)
    entries = flatten_playlist(config.url, export_opts, ydl_factory=factory)
    write_entries(config.paths.entries_file, entries)
    cookie_mode = determine_cookie_mode(
        config.paths.cookie_file, config.browser, warn=warn
    )

    if config.dry_run:
        _print_dry_run(config, entries, cookie_mode)
        return 0

    if not entries:
        print("Nothing to do — the playlist is empty.")
        return 0

    if config.plain:
        run_result = run_plain(entries, config, cookie_mode, ydl_factory=factory)
    else:
        # Imported lazily so --dry-run/flush/--help never pay Textual's import cost.
        from .tui.app import run_textual

        run_result = run_textual(
            entries,
            config,
            cookie_mode,
            ydl_factory=factory,
            summarise=lambda result: _reconcile_run(config, entries, result)[1],
        )

    return _finalise_run(config, entries, run_result)


def _print_dry_run(config: RunConfig, entries, cookie_mode) -> None:
    archive_ids = read_archive_ids(config.paths.archive_file)
    requested_ids = {entry.id for entry in entries}
    already_present = len(requested_ids & archive_ids)
    outstanding = len(requested_ids) - already_present
    effective_opts = build_download_opts(config, cookie_mode=cookie_mode)
    print(
        render_dry_run_plan(
            config,
            total=len(entries),
            already_present=already_present,
            outstanding=outstanding,
            effective_opts=effective_opts,
        )
    )


def _reconcile_run(
    config: RunConfig, entries: list[Entry], run_result: RunResult
) -> tuple[Reconciliation, str]:
    """Reconcile a finished run against the archive and render the report text."""
    archive_ids = read_archive_ids(config.paths.archive_file)
    requested_ids = {entry.id for entry in entries}
    reconciliation = reconcile(
        requested_ids=requested_ids,
        archive_ids=archive_ids,
        downloaded_this_run=run_result.downloaded_ids,
        landed_with_files=_landed_ids_with_files(
            config.paths.output_dir, requested_ids & archive_ids
        ),
    )
    report_text = render_report_text(
        reconciliation,
        cancelled=run_result.cancelled,
        failure_reasons=run_result.failure_reasons,
    )
    return reconciliation, report_text


def _finalise_run(
    config: RunConfig, entries: list[Entry], run_result: RunResult
) -> int:
    """Auto flush: reconcile, write report.txt + failed.txt, and print the report.

    Shared by the plain and Textual paths so the end-of-run report is identical.
    """
    reconciliation, report_text = _reconcile_run(config, entries, run_result)
    config.paths.report_file.write_text(report_text + "\n", encoding="utf-8")
    _write_failed(config.paths.failed_file, failed_urls(reconciliation, entries))
    print(report_text)
    return 0


def run_flush(
    output_dir: Path, url: str | None, *, ydl_factory: YdlFactory | None = None
) -> int:
    """Reconcile requested vs landed vs failed for an existing output directory.

    With ``url`` the playlist is re-flattened to redefine the requested set;
    otherwise the cached ``entries.json`` is used (raising :class:`NoStateError`
    when there is none). Always exits 0 on success — it is a report.
    """
    if url is not None:
        config = resolve_run_config(
            jobs=1,
            url=url,
            output_dir=output_dir,
            browser=_FLUSH_BROWSER,
            remux_format="",
            fragments=1,
            dry_run=False,
            plain_flag=True,
            is_tty=False,
        )
        paths = config.paths
        paths.state_dir.mkdir(parents=True, exist_ok=True)
        export_opts = build_cookie_export_opts(config)
        entries = flatten_playlist(
            url, export_opts, ydl_factory=_resolve_factory(ydl_factory)
        )
        write_entries(paths.entries_file, entries)
    else:
        paths = resolve_state_paths(output_dir)
        if not paths.entries_file.exists():
            raise NoStateError(
                f"No state found at {paths.state_dir}. Run a download first, "
                "or pass --url to re-flatten the playlist."
            )
        entries = read_entries(paths.entries_file)

    requested_ids = {entry.id for entry in entries}
    archive_ids = read_archive_ids(paths.archive_file)
    landed = requested_ids & archive_ids
    reconciliation = reconcile(
        requested_ids=requested_ids,
        archive_ids=archive_ids,
        landed_with_files=_landed_ids_with_files(paths.output_dir, landed),
    )

    report_text = render_report_text(reconciliation)
    paths.report_file.parent.mkdir(parents=True, exist_ok=True)
    paths.report_file.write_text(report_text + "\n", encoding="utf-8")
    _write_failed(paths.failed_file, failed_urls(reconciliation, entries))
    print(report_text)
    return 0


def _landed_ids_with_files(output_dir: Path, landed_ids: set[str]) -> set[str]:
    """Return landed ids whose output file (``... [id].ext``) exists on disk."""
    if not output_dir.exists():
        return set()
    file_names = [item.name for item in output_dir.iterdir() if item.is_file()]
    return {
        video_id
        for video_id in landed_ids
        if any(f"[{video_id}]" in name for name in file_names)
    }


def _write_failed(failed_file: Path, urls: list[str]) -> None:
    failed_file.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(urls)
    failed_file.write_text(content + "\n" if content else "", encoding="utf-8")
