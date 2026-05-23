"""Download-archive parsing and persistence of the flattened playlist.

The download archive is yt-dlp's resume/skip primitive: one line per successfully
downloaded item, formatted ``<extractor_lowercased> <video_id>`` (e.g.
``youtube BaW_jenozKc``). Reconciliation keys on the trailing video id only, so a
shared archive containing unrelated ids still reconciles correctly.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Entry:
    """One flattened playlist item (mirrors the entries.json object shape)."""

    id: str
    url: str
    title: str


def parse_archive_ids(archive_text: str) -> set[str]:
    """Return the set of video ids from download-archive text.

    Each non-blank line ends with the video id (after the extractor prefix);
    blank and whitespace-only lines are ignored.
    """
    video_ids: set[str] = set()
    for line in archive_text.splitlines():
        tokens = line.split()
        if tokens:
            video_ids.add(tokens[-1])
    return video_ids


def read_archive_ids(archive_file: Path) -> set[str]:
    """Parse the archive file, returning an empty set when it does not exist."""
    if not archive_file.exists():
        return set()
    return parse_archive_ids(archive_file.read_text(encoding="utf-8"))


def archive_id_for(extractor_key: str, video_id: str) -> str:
    """Build an archive line body: ``<extractor_lowercased> <video_id>``."""
    return f"{extractor_key.lower()} {video_id}"


def extract_video_id(entry: Entry) -> str:
    """Return the video id for an entry (centralised for clarity at call sites)."""
    return entry.id


def entries_to_json(entries: list[Entry]) -> str:
    """Serialise entries to a pretty JSON array of ``{id, url, title}`` objects."""
    return json.dumps([asdict(entry) for entry in entries], indent=2, ensure_ascii=False)


def entries_from_json(text: str) -> list[Entry]:
    """Parse entries from JSON produced by :func:`entries_to_json`."""
    raw_items = json.loads(text)
    return [Entry(id=item["id"], url=item["url"], title=item["title"]) for item in raw_items]


def write_entries(entries_file: Path, entries: list[Entry]) -> None:
    """Write entries.json, creating parent directories as needed."""
    entries_file.parent.mkdir(parents=True, exist_ok=True)
    entries_file.write_text(entries_to_json(entries), encoding="utf-8")


def read_entries(entries_file: Path) -> list[Entry]:
    """Read entries.json back into a list of :class:`Entry`."""
    return entries_from_json(entries_file.read_text(encoding="utf-8"))
