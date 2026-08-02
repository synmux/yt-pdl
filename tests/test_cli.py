"""Tests for the Click CLI: default-command routing, validation, warnings."""

from pathlib import Path

import pytest
from click.testing import CliRunner

import yt_pdlp.cli as cli_module
from yt_pdlp.cli import cli
from yt_pdlp.config import WATCH_LATER_URL


@pytest.fixture
def runner():
    return CliRunner()


def _capture_download(monkeypatch):
    captured = {}

    def fake_run_download(config, *, warn, ydl_factory=None):
        captured["config"] = config
        return 0

    monkeypatch.setattr(cli_module, "run_download", fake_run_download)
    return captured


def test_bare_invocation_routes_to_download(runner, monkeypatch):
    captured = _capture_download(monkeypatch)
    result = runner.invoke(cli, [])
    assert result.exit_code == 0
    assert "config" in captured


def test_option_first_invocation_routes_to_download(runner, monkeypatch):
    captured = _capture_download(monkeypatch)
    result = runner.invoke(cli, ["-j", "6", "-u", "https://example.com/pl"])
    assert result.exit_code == 0
    assert captured["config"].jobs == 6
    assert captured["config"].urls == ("https://example.com/pl",)


def test_flush_subcommand_routes_to_flush(runner, monkeypatch):
    seen = {}

    def fake_run_flush(output_dir, url, *, ydl_factory=None):
        seen["output_dir"] = output_dir
        seen["url"] = url
        return 0

    monkeypatch.setattr(cli_module, "run_flush", fake_run_flush)
    result = runner.invoke(cli, ["flush", "-o", "somedir"])
    assert result.exit_code == 0
    assert seen["output_dir"] == Path("somedir")
    assert seen["url"] is None


def test_invalid_jobs_rejected(runner, monkeypatch):
    _capture_download(monkeypatch)
    result = runner.invoke(cli, ["-j", "0"])
    assert result.exit_code != 0


def test_invalid_fragments_rejected(runner, monkeypatch):
    _capture_download(monkeypatch)
    result = runner.invoke(cli, ["-N", "0"])
    assert result.exit_code != 0


def test_output_must_be_a_directory(runner, monkeypatch, tmp_path):
    _capture_download(monkeypatch)
    a_file = tmp_path / "afile"
    a_file.write_text("x", encoding="utf-8")
    result = runner.invoke(cli, ["-o", str(a_file)])
    assert result.exit_code != 0


def test_jobs_over_eight_warns(runner, monkeypatch):
    _capture_download(monkeypatch)
    result = runner.invoke(cli, ["-j", "12"])
    assert result.exit_code == 0
    assert "sweet spot" in result.output.lower() or "429" in result.output


def test_dry_run_flag_reaches_config(runner, monkeypatch):
    captured = _capture_download(monkeypatch)
    result = runner.invoke(cli, ["--dry-run"])
    assert result.exit_code == 0
    assert captured["config"].dry_run is True


def test_non_tty_forces_plain(runner, monkeypatch):
    # Under CliRunner stdout is not a TTY, so plain must be forced on.
    captured = _capture_download(monkeypatch)
    runner.invoke(cli, [])
    assert captured["config"].plain is True


def test_default_source_is_watch_later(runner, monkeypatch):
    captured = _capture_download(monkeypatch)
    runner.invoke(cli, [])
    assert captured["config"].urls == (WATCH_LATER_URL,)


def test_batch_file_supplies_sources(runner, monkeypatch, tmp_path):
    captured = _capture_download(monkeypatch)
    batch = tmp_path / "urls.txt"
    batch.write_text(
        "# playlists, channels or single videos\nhttps://example.com/one\n\nhttps://example.com/two\n",
        encoding="utf-8",
    )
    result = runner.invoke(cli, ["-a", str(batch)])
    assert result.exit_code == 0
    assert captured["config"].urls == ("https://example.com/one", "https://example.com/two")


def test_batch_file_combines_after_url(runner, monkeypatch, tmp_path):
    captured = _capture_download(monkeypatch)
    batch = tmp_path / "urls.txt"
    batch.write_text("https://example.com/from-file\n", encoding="utf-8")
    result = runner.invoke(cli, ["-u", "https://example.com/pl", "-a", str(batch)])
    assert result.exit_code == 0
    assert captured["config"].urls == ("https://example.com/pl", "https://example.com/from-file")


def test_empty_batch_file_is_a_usage_error(runner, monkeypatch, tmp_path):
    _capture_download(monkeypatch)
    batch = tmp_path / "urls.txt"
    batch.write_text("# nothing here\n\n", encoding="utf-8")
    result = runner.invoke(cli, ["-a", str(batch)])
    assert result.exit_code != 0
    assert "no urls" in result.output.lower()


def test_missing_batch_file_rejected(runner, monkeypatch, tmp_path):
    _capture_download(monkeypatch)
    result = runner.invoke(cli, ["-a", str(tmp_path / "absent.txt")])
    assert result.exit_code != 0
