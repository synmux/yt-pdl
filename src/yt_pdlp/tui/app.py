"""The Textual application: thread workers post events that update the UI.

Worker threads run the UI-agnostic engine and marshal every event to the app via
``post_message`` (thread-safe). All widget mutation happens in
``on_engine_event_message`` on the UI thread. Completion is detected by counting
``WorkerFinished`` events, after which the summary screen is shown. Reconciliation
is injected as ``summarise`` so this module never imports the runner.
"""

from __future__ import annotations

from collections.abc import Callable

from textual import work
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Footer, Header, RichLog
from textual.worker import get_current_worker

from ..archive import Entry
from ..config import RunConfig
from ..engine import YoutubeDLFactory, build_queue, run_worker, worker_count_for
from ..events import (
    Event,
    ProgressUpdate,
    RunResult,
    RunResultBuilder,
    VideoFailed,
    VideoFinished,
    VideoSkipped,
    VideoStarted,
    WorkerFinished,
)
from ..options import CookieMode
from .messages import EngineEventMessage
from .summary import SummaryScreen
from .widgets import OverallStatus, WorkerPanel

Summariser = Callable[[RunResult], str]


class DownloadApp(App[RunResult]):
    """Live download UI: per-worker panels, an overall counter, and a log."""

    CSS = """
    #workers { height: 1fr; }
    #log { height: 8; border: round $secondary; }
    """
    BINDINGS = [("q", "graceful_quit", "Quit")]
    TITLE = "yt-pdlp"

    def __init__(
        self,
        entries: list[Entry],
        config: RunConfig,
        cookie_mode: CookieMode,
        *,
        ydl_factory: YoutubeDLFactory,
        summarise: Summariser,
    ) -> None:
        super().__init__()
        self._entries = entries
        self._config = config
        self._cookie_mode = cookie_mode
        self._ydl_factory = ydl_factory
        self._summarise = summarise
        self._queue = build_queue(entries)
        self._worker_count = worker_count_for(config.jobs, len(entries))
        self._builder = RunResultBuilder()
        self._completed = 0
        self._failed = 0
        self._workers_finished = 0
        self._cancelled = False
        self._run_result: RunResult | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield OverallStatus(id="overall")
        with VerticalScroll(id="workers"):
            for worker_index in range(self._worker_count):
                yield WorkerPanel(worker_index)
        yield RichLog(id="log", markup=False, highlight=False)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(OverallStatus).render_counts(0, 0, len(self._entries))
        for worker_index in range(self._worker_count):
            self._run_one(worker_index)

    @work(thread=True)
    def _run_one(self, worker_index: int) -> None:
        worker = get_current_worker()
        run_worker(
            worker_index,
            self._queue,
            self._config,
            self._cookie_mode,
            self._emit,
            is_cancelled=lambda: worker.is_cancelled,
            ydl_factory=self._ydl_factory,
        )

    def _emit(self, event: Event) -> None:
        """Marshal an engine event to the UI thread (thread-safe)."""
        self.post_message(EngineEventMessage(event))

    def on_engine_event_message(self, message: EngineEventMessage) -> None:
        event = message.event
        self._builder(event)
        match event:
            case VideoStarted():
                self._panel(event.worker_index).start(event.title)
                self._write_log(f"▶ worker {event.worker_index}: {event.title}")
            case ProgressUpdate():
                self._panel(event.worker_index).apply(event)
            case VideoFinished():
                self._completed += 1
                self._panel(event.worker_index).idle()
                self._write_log(f"✓ {event.title}")
                self._refresh_overall()
            case VideoSkipped():
                self._completed += 1
                self._write_log(f"↷ already have: {event.title}")
                self._refresh_overall()
            case VideoFailed():
                self._failed += 1
                note = (
                    " (HTTP 429 — consider lowering --jobs)"
                    if event.is_rate_limited
                    else ""
                )
                self._write_log(f"✗ FAILED {event.title}: {event.reason}{note}")
                self._refresh_overall()
            case WorkerFinished():
                self._workers_finished += 1
                if self._workers_finished >= self._worker_count:
                    self._finish()

    def action_graceful_quit(self) -> None:
        if self._run_result is not None:
            self.exit(self._run_result)
            return
        self._cancelled = True
        self._write_log("Cancelling — finishing current downloads…")
        self.workers.cancel_all()

    def _panel(self, worker_index: int) -> WorkerPanel:
        return self.query_one(f"#worker-{worker_index}", WorkerPanel)

    def _write_log(self, text: str) -> None:
        self.query_one("#log", RichLog).write(text)

    def _refresh_overall(self) -> None:
        self.query_one(OverallStatus).render_counts(
            self._completed, self._failed, len(self._entries)
        )

    def _finish(self) -> None:
        self._run_result = self._builder.result(cancelled=self._cancelled)
        self.push_screen(SummaryScreen(self._summarise(self._run_result)))


def run_textual(
    entries: list[Entry],
    config: RunConfig,
    cookie_mode: CookieMode,
    *,
    ydl_factory: YoutubeDLFactory,
    summarise: Summariser,
) -> RunResult:
    """Run the Textual app to completion and return the collected RunResult."""
    app = DownloadApp(
        entries, config, cookie_mode, ydl_factory=ydl_factory, summarise=summarise
    )
    result = app.run()
    if result is None:
        return RunResult(
            downloaded_ids=set(),
            failed_ids=set(),
            skipped_ids=set(),
            failure_reasons={},
            cancelled=True,
        )
    return result
