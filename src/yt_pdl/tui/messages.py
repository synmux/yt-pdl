"""Thread-safe message carrying an engine event into the Textual app."""

from textual.message import Message

from ..events import Event


class EngineEventMessage(Message):
    """Wraps an engine :data:`Event` for delivery to the app's UI thread.

    Posted from worker threads via ``post_message`` (thread-safe, non-blocking),
    which is the recommended channel for high-frequency progress updates.
    """

    def __init__(self, event: Event) -> None:
        self.event = event
        super().__init__()
