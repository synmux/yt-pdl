"""Tests for the engine event types, fan_out, and RunResultBuilder."""

import dataclasses

import pytest

from yt_pdl.events import (
    ProgressUpdate,
    RunResultBuilder,
    VideoFailed,
    VideoFinished,
    VideoSkipped,
    WorkerStarted,
    fan_out,
)


def test_events_are_frozen():
    event = WorkerStarted(worker_index=0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.worker_index = 1  # type: ignore[misc]


def test_progress_update_carries_fields():
    update = ProgressUpdate(
        worker_index=2,
        video_id="vid",
        title="T",
        percent=42.0,
        downloaded_bytes=100,
        total_bytes=200,
        speed=50.0,
        eta=3,
        percent_str="42%",
        speed_str="50.0B/s",
        eta_str="00:03",
        stage="downloading",
    )
    assert update.worker_index == 2
    assert update.percent == 42.0
    assert update.stage == "downloading"


def test_fan_out_calls_each_observer_in_order():
    calls: list[tuple[str, object]] = []

    def first(event):
        calls.append(("first", event))

    def second(event):
        calls.append(("second", event))

    observer = fan_out(first, second)
    event = WorkerStarted(worker_index=0)
    observer(event)

    assert calls == [("first", event), ("second", event)]


def test_run_result_builder_accumulates_outcomes():
    builder = RunResultBuilder()
    builder(VideoFinished(worker_index=0, video_id="a", title="A", filename="a.mp4"))
    builder(VideoSkipped(worker_index=1, video_id="b", title="B"))
    builder(
        VideoFailed(
            worker_index=0,
            video_id="c",
            title="C",
            reason="Private video",
            is_rate_limited=False,
        )
    )
    # Progress updates must not affect the accumulated result.
    builder(
        ProgressUpdate(
            worker_index=0,
            video_id="a",
            title="A",
            percent=50.0,
            downloaded_bytes=1,
            total_bytes=2,
            speed=None,
            eta=None,
            percent_str="50%",
            speed_str="",
            eta_str="",
            stage="downloading",
        )
    )

    result = builder.result()
    assert result.downloaded_ids == {"a"}
    assert result.skipped_ids == {"b"}
    assert result.failed_ids == {"c"}
    assert result.failure_reasons == {"c": "Private video"}
    assert result.cancelled is False


def test_run_result_builder_marks_cancelled():
    builder = RunResultBuilder()
    builder(VideoFinished(worker_index=0, video_id="a", title="A", filename=None))
    assert builder.result(cancelled=True).cancelled is True
