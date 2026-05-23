# ytdlp-parallel

Download a large YouTube playlist with **several yt-dlp workers running
concurrently**, showing each worker's live progress in a [Textual](https://textual.textualize.io/)
terminal UI. It supports a planning **dry-run** and a post-run **flush** report
that reconciles how many videos actually landed versus failed.

## Why

yt-dlp has no built-in option to download multiple playlist *items* in parallel —
its `-N` / `--concurrent-fragments` flag only parallelises fragments *within a
single* video, so playlist items are processed one at a time. Downloading a
~1,000-item playlist (such as Watch Later) therefore crawls. `ytdlp-parallel`
runs several downloads at once in one process, with a live UI and resumability.

## Requirements

- Python ≥ 3.11
- [`ffmpeg`](https://ffmpeg.org/) on your `PATH` (needed to remux to mp4)
- A browser you are signed in to YouTube with (default: Chrome) — Watch Later is
  private, so cookies are required.

## Install & run

This project uses [`uv`](https://docs.astral.sh/uv/):

```bash
uv sync                       # create the environment
uv run ytdlp-parallel --help  # see all options
```

## Usage

`ytdlp-parallel` is a command group with a default command, so a bare invocation
downloads:

```bash
# Download Watch Later with 4 workers (the defaults)
uv run ytdlp-parallel

# Six workers, a specific playlist, into ./videos
uv run ytdlp-parallel -j 6 -u "https://www.youtube.com/playlist?list=PLxxxx" -o ./videos

# Plan only — contacts YouTube read-only, downloads nothing
uv run ytdlp-parallel --dry-run

# Reconcile an existing output directory without downloading
uv run ytdlp-parallel flush -o ./videos
```

### `download` options (the default command)

| Option | Short | Default | Meaning |
|---|---|---|---|
| `--jobs` | `-j` | `4` | Number of concurrent workers. |
| `--url` | `-u` | Watch Later | Playlist (or any yt-dlp-supported) URL. |
| `--output` | `-o` | `./downloads` | Output directory (created if absent). |
| `--browser` | `-b` | `chrome` | Browser to read cookies from. |
| `--format` | `-f` | `mp4` | Remux container; an empty string disables remux. |
| `--fragments` | `-N` | `1` | `concurrent_fragment_downloads` per worker (intra-video). |
| `--dry-run` | | off | Plan only; download nothing. |
| `--plain` | | auto | Disable the Textual UI; emit line-based progress (auto-on when stdout is not a terminal). |

### `flush` options

| Option | Short | Default | Meaning |
|---|---|---|---|
| `--output` | `-o` | `./downloads` | Locate and reconcile this output's state directory. |
| `--url` | `-u` | _(optional)_ | Re-flatten this playlist to define the "requested" set instead of using the cached list. |

## How it works

- A **shared work queue** holds every playlist entry. `--jobs` workers each pull
  the next entry and download it, so the work load-balances naturally across
  videos of very different lengths.
- Each worker owns its own `yt_dlp.YoutubeDL` instance and reports progress
  through a UI-agnostic event stream. A **Textual** front-end renders per-worker
  panels and an overall counter; a **plain** front-end prints line-based progress
  when there is no terminal.
- A shared **download archive** records only successful downloads, so re-running
  the same command **skips** what is already done and **retries** what failed.
- The browser cookie store is read **once** and written to a reusable cookie
  file; every worker then reads the file (browsers lock their cookie database, so
  reading it from many workers at once would contend).

## State directory

Everything lives under `<output>/.ytdlp-state/`:

| File | Purpose |
|---|---|
| `cookies.txt` | Cookies exported once from the browser. **Sensitive** — it holds a live session; keep it private. |
| `entries.json` | The flattened playlist: a list of `{id, url, title}`. |
| `archive.txt` | The yt-dlp download archive (resume + skip). |
| `failed.txt` | Outstanding URLs after a run or flush, one per line — retry with `yt-dlp -a failed.txt …` or just re-run. |
| `report.txt` | The last completion report. |

Downloaded media files go directly under `<output>/`.

## A note on concurrency

The realistic sweet spot is **4–8 workers**. The bottleneck is YouTube's
per-account/IP throttling (HTTP 429), not your machine — beyond a handful of
workers, total throughput usually *drops*. `ytdlp-parallel` warns when you ask
for more than 8 but does not stop you.

## Development

```bash
uv run pytest -q                       # tests
uv run ruff check src tests            # lint
uv run ruff format --check src tests   # formatting
uv run ty check src                    # type-check
```

The download engine is deliberately decoupled from the UI, and yt-dlp, the
network, and the terminal are faked **in tests only** so the whole tool runs
offline in CI.
