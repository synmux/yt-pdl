"""The completion screen: shows the flush report; press q to close."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Static


class SummaryScreen(Screen):
    """Displays the reconciliation report once the run has finished."""

    def __init__(self, report_text: str) -> None:
        super().__init__()
        self._report_text = report_text

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Static(self._report_text, id="summary-report")
        yield Footer()
