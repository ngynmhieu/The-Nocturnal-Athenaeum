"""Headless-browser helper for per-site extractors — open a page, capture one JSON response.

Some readers render entirely client-side: the HTML is an empty shell and the page
list arrives from the site's own API, signed with a token its JavaScript computes.
Rather than reimplement that, we let a real (headless) Chromium load the page like a
normal visitor and simply *listen* for the API response the site makes itself.

Playwright runs in a dedicated thread with its own event loop: it launches Chromium
as a subprocess, which on Windows needs a Proactor loop — not guaranteed for the
server's loop (uvicorn picks a Selector loop on Windows in some modes).
"""
from __future__ import annotations

import asyncio
import re
import sys
from typing import Any

from .base import ExtractorError

# Playwright's bundled Chromium identifies as "HeadlessChrome" by default, which some
# CDNs reject outright; present the same desktop UA the httpx scraper uses.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
CAPTURE_TIMEOUT_MS = 45_000

async def capture_json(url: str, response_url: re.Pattern[str]) -> Any:
    """Open `url` headlessly and return the JSON body of the first successful
    response whose URL matches `response_url`."""
    return await asyncio.to_thread(_run_in_own_loop, url, response_url)


def _run_in_own_loop(url: str, response_url: re.Pattern[str]) -> Any:
    loop = asyncio.ProactorEventLoop() if sys.platform == "win32" else asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_capture(url, response_url))
    finally:
        loop.close()


async def _capture(url: str, response_url: re.Pattern[str]) -> Any:
    try:
        from playwright.async_api import Error as PlaywrightError
        from playwright.async_api import async_playwright
    except ImportError as exc:  # optional dependency — only per-site extractors need it
        raise ExtractorError(
            "Playwright isn't installed on the backend — run `pip install playwright` "
            "then `playwright install chromium`."
        ) from exc

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page(user_agent=USER_AGENT)
                async with page.expect_response(
                    lambda r: r.ok and response_url.search(r.url) is not None,
                    timeout=CAPTURE_TIMEOUT_MS,
                ) as captured:
                    await page.goto(url, wait_until="domcontentloaded", timeout=CAPTURE_TIMEOUT_MS)
                response = await captured.value
                return await response.json()
            finally:
                await browser.close()
    except PlaywrightError as exc:
        raise ExtractorError(f"The page didn't load its image list in time ({exc.message.splitlines()[0]})") from exc
