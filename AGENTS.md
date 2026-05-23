# AGENTS.md — context for AI agents

`ytdlp-parallel` downloads a YouTube playlist with several concurrent yt-dlp
workers, a live Textual UI, a `--dry-run` planner, and a `flush` reconciliation
report. See `README.md` for user-facing docs and `PRD.md` for the full spec.

## Toolchain

- **Package manager:** `uv` (Python ≥ 3.11; the dev interpreter is 3.14).
- **Quality gates (all must pass before done):**
  ```bash
  uv run ruff check src tests
  uv run ruff format --check src tests
  uv run ty check src        # ty (Astral); infers the 3.11 target from requires-python
  uv run pytest -q
  ```
- **TDD:** write the failing test first, watch it fail, then implement. Commit
  per feature with Conventional Commits + GitMoji.

## Architecture (the seam)

The download **engine** (`engine.py`) is UI-agnostic: it drains a shared
`queue.Queue` of `Entry` objects with N worker functions, each owning its own
`YoutubeDL` (via an injected factory — the engine never imports `yt_dlp`), and
emits immutable **events** (`events.py`) through an `EventObserver` callback.

Two front-ends consume the same event stream:

- `tui/` — a Textual `App`; `@work(thread=True)` workers post `EngineEventMessage`s
  that update widgets on the UI thread.
- `plain.py` — a `ThreadPoolExecutor` that prints line-based progress.

`runner.py` wires everything (cookies → flatten → engine → reconcile → report) and
selects the front-end. It is the only module that imports `yt_dlp` (lazily) and
`tui.app` (lazily, so `--dry-run`/`flush`/`--help` don't pay Textual's import cost).

Pure, unit-tested modules: `config.py`, `archive.py`, `reconcile.py`,
`events.py`, `ytdlp_options.py`, `report.py`.

## Invariants — do not regress

- **Remux is a postprocessor, not an option.** Use
  `{'key': 'FFmpegVideoRemuxer', 'preferedformat': fmt}` (note `preferedformat`,
  single "r"); omit it entirely when `--format` is empty. `'remux_video'` does
  nothing.
- **`ignoreerrors=True` must be set explicitly** (yt-dlp's API default is `False`).
- **Archive lines are `<extractor_lowercased> <video_id>`** (e.g. `youtube abc`);
  reconciliation keys on the trailing video id only, so a shared archive with
  unrelated ids still reconciles correctly.
- **Read the browser cookie store once.** The bootstrap flatten call uses both
  `cookiesfrombrowser` and `cookiefile`, writing `cookies.txt` as a side-effect;
  workers then read the file. Fall back to per-worker `cookiesfrombrowser` (with a
  warning) only if the file is not produced.
- **Thread → UI:** worker threads must never touch widgets directly. Marshal via
  `post_message` (thread-safe, non-blocking) — never `call_from_thread` for
  high-frequency progress.
- **Textual API:** `from textual import work` (not `textual.work`);
  `worker.is_cancelled` is a property; `ProgressBar.update` is keyword-only;
  `Message.__init__` takes no `sender`. Verify against the installed version.
- **Empty playlist** (valid but zero entries) exits 0 ("nothing to do"); only a
  genuine extraction failure raises `FlattenError` (non-zero exit).
- **Resume** relies on the shared download archive: only successes are recorded,
  so failures retry on the next run.

## Testing notes

- yt-dlp, the network, and the terminal are faked **in tests only**
  (`tests/fakes.py`: one `FakeYoutubeDL` covering both `extract_info` and
  `download`). The TUI is smoke-tested via `App.run_test()`.
- `pytest-asyncio` is in `auto` mode, so async TUI tests need no marker.
- Concurrency tests assert invariants that always hold (each id processed once;
  `sum(processed) == len(entries)`), never scheduling-dependent balance.
