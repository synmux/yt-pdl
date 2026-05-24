"""Reconcile what was requested against what actually landed.

Pure set maths, independent of files and the network:

* **requested** — video ids from the flattened playlist.
* **landed**    — archive ids intersected with requested (so a shared archive
                  holding ids from other playlists never inflates the result).
* **failed**    — requested minus landed (outstanding; retried next run).

When run-level information is available, ``downloaded_this_run`` (clamped to
landed) splits landed into freshly downloaded vs already present, and
``landed_with_files`` flags landed ids whose output file is missing on disk.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from .archive import Entry


@dataclass(frozen=True, slots=True)
class Reconciliation:
    """The outcome of comparing requested ids against the archive."""

    requested_ids: frozenset[str]
    landed_ids: frozenset[str]
    failed_ids: frozenset[str]
    downloaded_this_run: frozenset[str]
    already_present: frozenset[str]
    missing_files: frozenset[str]

    @property
    def requested_count(self) -> int:
        return len(self.requested_ids)

    @property
    def landed_count(self) -> int:
        return len(self.landed_ids)

    @property
    def failed_count(self) -> int:
        return len(self.failed_ids)

    @property
    def downloaded_count(self) -> int:
        return len(self.downloaded_this_run)

    @property
    def already_present_count(self) -> int:
        return len(self.already_present)

    @property
    def missing_files_count(self) -> int:
        return len(self.missing_files)


def reconcile(
    *,
    requested_ids: Iterable[str],
    archive_ids: Iterable[str],
    downloaded_this_run: Iterable[str] | None = None,
    landed_with_files: Iterable[str] | None = None,
) -> Reconciliation:
    """Compute the reconciliation sets.

    ``downloaded_this_run`` is clamped to ``landed`` so a spuriously-reported id
    can never make ``already_present`` negative or escape the landed set.
    """
    requested = frozenset(requested_ids)
    landed = frozenset(archive_ids) & requested
    failed = requested - landed

    if downloaded_this_run is None:
        downloaded = frozenset()
    else:
        downloaded = frozenset(downloaded_this_run) & landed
    already_present = landed - downloaded

    if landed_with_files is None:
        missing_files = frozenset()
    else:
        missing_files = landed - frozenset(landed_with_files)

    return Reconciliation(
        requested_ids=requested,
        landed_ids=landed,
        failed_ids=failed,
        downloaded_this_run=downloaded,
        already_present=already_present,
        missing_files=missing_files,
    )


def failed_urls(reconciliation: Reconciliation, entries: list[Entry]) -> list[str]:
    """Return the URLs of outstanding (failed) entries, in playlist order."""
    return [entry.url for entry in entries if entry.id in reconciliation.failed_ids]
