"""Tests for cookie-mode determination after the read-once export."""

from yt_pdlp.ytdlp_options import CookieMode

from yt_pdlp.cookies import determine_cookie_mode


def test_cookie_mode_from_written_file(tmp_path):
    cookie_file = tmp_path / "cookies.txt"
    cookie_file.write_text(
        "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\n", encoding="utf-8"
    )
    warnings: list[str] = []

    mode = determine_cookie_mode(cookie_file, "chrome", warn=warnings.append)

    assert mode == CookieMode.from_file(cookie_file)
    assert warnings == []


def test_cookie_mode_falls_back_when_file_missing(tmp_path):
    cookie_file = tmp_path / "cookies.txt"  # never created
    warnings: list[str] = []

    mode = determine_cookie_mode(cookie_file, "chrome", warn=warnings.append)

    assert mode == CookieMode.from_browser("chrome")
    assert len(warnings) == 1
    assert "chrome" in warnings[0]


def test_cookie_mode_falls_back_when_file_empty(tmp_path):
    cookie_file = tmp_path / "cookies.txt"
    cookie_file.write_text("", encoding="utf-8")
    warnings: list[str] = []

    mode = determine_cookie_mode(cookie_file, "firefox", warn=warnings.append)

    assert mode == CookieMode.from_browser("firefox")
    assert len(warnings) == 1
    assert "firefox" in warnings[0]
