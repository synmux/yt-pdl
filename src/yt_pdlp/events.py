"""The engine-to-UI seam: structured events, an observer type, and a result builder.

The download engine knows nothing about Textual or plain output. It emits these
immutable events through an :data:`EventObserver` callback. Front-ends turn events
into widget updates or printed lines, while :class:`RunResultBuilder` accumulates
the authoritative :class:`RunResult` for reconciliation — independent of any UI.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeAlias


@dataclass(frozen=True, slots=True)
class WorkerStarted:
    worker_index: int


@dataclass(frozen=True, slots=True)
class VideoStarted:
    worker_index: int
    video_id: str
    title: str
    url: str


@dataclass(frozen=True, slots=True)
class ProgressUpdate:
    worker_index: int
    video_id: str
    title: str
    percent: float | None
    downloaded_bytes: int | None
    total_bytes: int | None
    speed: float | None
    eta: int | None
    percent_str: str
    speed_str: str
    eta_str: str
    stage: str  # 'downloading' | 'remuxing'


@dataclass(frozen=True, slots=True)
class VideoFinished:
    worker_index: int
    video_id: str
    title: str
    filename: str | None


@dataclass(frozen=True, slots=True)
class VideoSkipped:
    """The item was already recorded in the archive, so it was not downloaded."""

    worker_index: int
    video_id: str
    title: str


@dataclass(frozen=True, slots=True)
class VideoFailed:
    worker_index: int
    video_id: str
    title: str
    reason: str
    is_rate_limited: bool


@dataclass(frozen=True, slots=True)
class WorkerFinished:
    worker_index: int
    processed: int
    failed: int


Event: TypeAlias = (
    WorkerStarted
    | VideoStarted
    | ProgressUpdate
    | VideoFinished
    | VideoSkipped
    | VideoFailed
    | WorkerFinished
)

EventObserver: TypeAlias = Callable[[Event], None]


def fan_out(*observers: EventObserver) -> EventObserver:
    """Combine several observers into one that calls each in turn, in order."""

    def emit(event: Event) -> None:
        for observer in observers:
            observer(event)

    return emit


@dataclass
class RunResult:
    """Run-level truth, used to build the reconciliation report."""

    downloaded_ids: set[str]
    failed_ids: set[str]
    skipped_ids: set[str]
    failure_reasons: dict[str, str]
    cancelled: bool = False


class RunResultBuilder:
    """An :data:`EventObserver` that accumulates outcomes into a :class:`RunResult`."""

    def __init__(self) -> None:
        self._downloaded: set[str] = set()
        self._failed: set[str] = set()
        self._skipped: set[str] = set()
        self._failure_reasons: dict[str, str] = {}

    def __call__(self, event: Event) -> None:
        match event:
            case VideoFinished():
                self._downloaded.add(event.video_id)
            case VideoSkipped():
                self._skipped.add(event.video_id)
            case VideoFailed():
                self._failed.add(event.video_id)
                self._failure_reasons[event.video_id] = event.reason
            case _:
                pass

    def result(self, *, cancelled: bool = False) -> RunResult:
        return RunResult(
            downloaded_ids=set(self._downloaded),
            failed_ids=set(self._failed),
            skipped_ids=set(self._skipped),
            failure_reasons=dict(self._failure_reasons),
            cancelled=cancelled,
        )
