"""Typed exceptions for operational failures (mapped to clear CLI errors)."""


class YtdlpParallelError(Exception):
    """Base class for all yt-pdlp operational errors."""


class FlattenError(YtdlpParallelError):
    """No videos could be extracted from the playlist (auth failure, wrong URL)."""


class NoStateError(YtdlpParallelError):
    """A flush was requested but no persisted state (entries.json) was found."""
