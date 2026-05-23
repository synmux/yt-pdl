"""Per-worker and overall status widgets for the download UI."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, ProgressBar

from ..events import ProgressUpdate


class WorkerPanel(Widget):
    """One bordered panel per worker: current title plus a live progress bar."""

    DEFAULT_CSS = """
    WorkerPanel {
        height: auto;
        border: round $primary;
        padding: 0 1;
        margin: 0 0 1 0;
    }
    """

    def __init__(self, worker_index: int) -> None:
        super().__init__(id=f"worker-{worker_index}")
        self._worker_index = worker_index
        self.border_title = f"Worker {worker_index}"

    def compose(self) -> ComposeResult:
        yield Label("idle", id=f"worker-{self._worker_index}-title")
        yield ProgressBar(total=100, show_eta=False, id=f"worker-{self._worker_index}-bar")

    def start(self, title: str) -> None:
        self._title_label.update(title)
        self._bar.update(total=100, progress=0)

    def apply(self, update: ProgressUpdate) -> None:
        meta = "  ".join(
            part for part in (update.percent_str, update.speed_str, update.eta_str) if part
        )
        self._title_label.update(f"{update.title}  {meta}".rstrip())
        if update.percent is not None:
            self._bar.update(progress=update.percent)

    def idle(self) -> None:
        self._bar.update(progress=100)

    @property
    def _title_label(self) -> Label:
        return self.query_one(f"#worker-{self._worker_index}-title", Label)

    @property
    def _bar(self) -> ProgressBar:
        return self.query_one(f"#worker-{self._worker_index}-bar", ProgressBar)


class OverallStatus(Widget):
    """Overall progress bar plus a completed/total and failed counter."""

    DEFAULT_CSS = """
    OverallStatus {
        height: auto;
        border: round $accent;
        padding: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("0/0 done · 0 failed", id="overall-counts")
        yield ProgressBar(total=100, show_eta=False, id="overall-bar")

    def render_counts(self, completed: int, failed: int, total: int) -> None:
        self.query_one("#overall-counts", Label).update(
            f"{completed}/{total} done · {failed} failed"
        )
        if total:
            self.query_one("#overall-bar", ProgressBar).update(
                total=total, progress=completed + failed
            )
