"""Decide how workers obtain cookies after the read-once browser export.

The cookie file is written as a side-effect of the bootstrap flatten call (a single
``YoutubeDL`` configured with both ``cookiesfrombrowser`` and ``cookiefile``). This
module only inspects the result: if a non-empty file was produced, every worker
reuses it; otherwise we warn and fall back to each worker reading the browser
directly (slower, and the workers contend on the browser's locked cookie store).
"""

from collections.abc import Callable
from pathlib import Path

from .options import CookieMode


def determine_cookie_mode(
    cookie_file: Path, browser: str, *, warn: Callable[[str], None]
) -> CookieMode:
    """Return a file-based cookie mode if the export succeeded, else fall back."""
    if cookie_file.exists() and cookie_file.stat().st_size > 0:
        return CookieMode.from_file(cookie_file)

    warn(
        f"No cookie file was written; workers will read '{browser}' directly "
        "(slower, and may contend on the browser's cookie store)."
    )
    return CookieMode.from_browser(browser)
