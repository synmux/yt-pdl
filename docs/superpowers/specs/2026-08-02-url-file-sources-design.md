# URL-file sources for `download`

**Date:** 2026-08-02 · **Status:** approved for implementation (queued instruction
from syn: "support loading urls from a file. each entry may be a playlist, a
channel, or an individual video.")

## Goal

Let `yt-pdlp download` take its sources from a text file as well as (or instead
of) `--url`. Each line may be a playlist URL, a channel URL, or an individual
video URL. All sources feed one flatten → one queue → one archive → one report,
so resume/reconcile semantics stay exactly as they are today.

## Approaches considered

1. **One config, many sources (chosen).** `RunConfig.url: str` becomes
   `urls: tuple[str, ...]`; the runner flattens each source and merges entries
   (deduplicated by video id, first occurrence wins) before the queue is built.
   Single state dir, single report — matches the existing resume model.
2. **Loop at the CLI: one `run_download` per URL.** Rejected: each run would
   overwrite `entries.json`, fragment reports, and re-read the browser cookie
   store per source (violating the read-once invariant).
3. **Delegate to yt-dlp's own `batch-file` handling.** Rejected: flattening
   happens in our bootstrap call, not yt-dlp's CLI layer; we would lose the
   planner/reconciler's single requested-set view.

## CLI

- New option on `download`: `--batch-file` / `-a` (name mirrors yt-dlp),
  `click.Path(exists=True, dir_okay=False)`.
- `--url` loses its eager default (`None` sentinel). Resolution:
  `sources = ([url] if given) + (parsed file lines if given)`; if the result is
  empty, fall back to Watch Later — so today's behaviours are unchanged, and
  `-u` combines with `-a` rather than conflicting.
- A batch file that parses to zero URLs is a `click.UsageError` (explicit
  failure beats silently downloading Watch Later).
- `flush` keeps its single `--url`; it reconciles against the cached, already
  merged `entries.json`, so it needs no batch option (out of scope).

## File format (yt-dlp `--batch-file` parity)

`config.parse_url_file(text) -> tuple[str, ...]` (pure): strip a leading BOM,
strip whitespace per line, drop blank lines and comment lines starting with
`#`, `;` or `]`.

## Flattening mixed source types

`flatten.flatten_playlist` becomes `flatten.flatten_source(url, opts, *,
ydl_factory, warn=None, _depth=0)`:

- **Playlist info** (`entries` present): as today — flat entries become
  `Entry` objects.
- **Single video** (no `entries` key but an `id`): one `Entry`
  (`webpage_url` preferred over the input URL; title falls back to the id).
  Only a dict with neither `entries` nor `id` raises `FlattenError`.
- **Channel URLs**: yt-dlp returns a playlist whose entries are either videos
  or _sub-playlists_ (tab/playlist references, e.g. `ie_key: YoutubeTab`, or
  `_type: playlist` with inline entries). Sub-playlists are recursed into,
  capped at depth 2; beyond the cap the entry is skipped with a `warn(...)`
  message (never silently).
- `flatten.dedupe_entries(entries)`: order-preserving, first occurrence wins.

## Runner data flow

```plaintext
first, *rest = config.urls
entries  = flatten_source(first, cookie-export opts)   # browser read once
cookie_mode = determine_cookie_mode(...)               # unchanged
entries += flatten_source(each rest, flatten opts using cookie file)
entries  = dedupe_entries(entries)                     # then exactly as today
```

Subsequent sources must NOT use the cookie-export opts — that would re-read
the browser store per source and regress the read-once invariant.

## Error handling

- Any source failing extraction raises `FlattenError` and aborts (consistent
  with today; partial silent success would corrupt the requested set).
- All sources empty → "nothing to do", exit 0 (existing invariant).

## Testing

- `test_config`: `parse_url_file` (comments, blanks, BOM, whitespace);
  `resolve_run_config` produces `urls` tuple.
- `test_flatten`: single-video info; nested channel→tab recursion; depth cap
  warns and skips; dedupe. `FakeYoutubeDL` gains an optional per-URL `infos`
  mapping (falls back to the existing single `info`).
- `test_cli`: `-a` alone, `-a` + `-u` combined, neither → Watch Later,
  empty file → usage error.
- `test_runner`: multi-source run merges + dedupes; cookie export only for the
  first source.

## Out of scope

`--batch-file` on `flush`; per-source reporting; non-YouTube extractor
special-casing.
