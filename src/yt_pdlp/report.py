"""Render the human-readable reconciliation report and the dry-run plan.

The same plain-text report is written to ``report.txt``, printed to stdout after a
run, and shown on the Textual summary screen, so there is a single rendering path.
"""

import pprint
from typing import Any

from .config import RunConfig
from .options import OUTPUT_TEMPLATE
from .reconcile import Reconciliation

_LABEL_WIDTH = 18


def render_report_text(
    reconciliation: Reconciliation,
    *,
    cancelled: bool = False,
    failure_reasons: dict[str, str] | None = None,
) -> str:
    """Render the reconciliation as an aligned plain-text block (British English)."""
    rec = reconciliation
    lines = [
        f"{'Playlist:':<{_LABEL_WIDTH}}{rec.requested_count:>5} videos",
        f"{'Already present:':<{_LABEL_WIDTH}}{rec.already_present_count:>5}"
        "  (skipped via archive)",
        f"{'Downloaded now:':<{_LABEL_WIDTH}}{rec.downloaded_count:>5}",
        f"{'Failed / missing:':<{_LABEL_WIDTH}}{rec.failed_count:>5}",
    ]

    if cancelled:
        lines += ["", "Run cancelled — figures above are partial."]

    if rec.missing_files_count:
        lines += [
            "",
            f"Warning: {rec.missing_files_count} archived video(s) have no output file on disk.",
        ]

    if failure_reasons:
        lines += ["", "Failures:"]
        lines += [
            f"  {video_id}: {reason}"
            for video_id, reason in sorted(failure_reasons.items())
        ]

    return "\n".join(lines)


def render_dry_run_plan(
    config: RunConfig,
    *,
    total: int,
    already_present: int,
    outstanding: int,
    effective_opts: dict[str, Any],
) -> str:
    """Render the ``--dry-run`` plan: resolved options, counts, opts, paths, banner."""
    paths = config.paths
    lines = [
        "yt-pdlp — dry run plan",
        "",
        "Resolved options:",
        f"  jobs:      {config.jobs}",
        f"  url:       {config.url}",
        f"  output:    {paths.output_dir}",
        f"  browser:   {config.browser}",
        f"  format:    {config.remux_format or '(no remux)'}",
        f"  fragments: {config.fragments}",
        "",
        "Playlist:",
        f"  total found:                     {total}",
        f"  already in archive (would skip): {already_present}",
        f"  outstanding (would download):    {outstanding}",
        "",
        "Output template:",
        f"  {OUTPUT_TEMPLATE}",
        "",
        "State paths:",
        f"  state dir: {paths.state_dir}",
        f"  cookies:   {paths.cookie_file}",
        f"  entries:   {paths.entries_file}",
        f"  archive:   {paths.archive_file}",
        f"  failed:    {paths.failed_file}",
        f"  report:    {paths.report_file}",
        "",
        "Effective per-worker yt-dlp options:",
        pprint.pformat(effective_opts, indent=2, sort_dicts=True),
        "",
        "=== DRY RUN — nothing downloaded ===",
    ]
    return "\n".join(lines)
