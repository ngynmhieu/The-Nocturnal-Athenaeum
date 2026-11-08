"""MangaFire (mangafire.to) — a fully client-rendered reader.

Its volume/chapter pages ship no images in the HTML; the browser calls
`/api/volumes/{id}` or `/api/chapters/{id}` (signed with a token the site's JS
builds) and gets back the ordered page list, with each page's size. We open the
reader page in a headless browser and read that response — see `browser.py`.

URL shapes:
    /title/{slug}                      series page (lists volumes)
    /title/{slug}/volume/{id}          one volume's reader
    /title/{slug}/chapter/{id}         one chapter's reader
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from ..scraper import ImageCandidate
from .base import ExtractorError, SeriesEntry
from .browser import capture_json

SITE = "https://mangafire.to"
# The image CDN rejects requests without a mangafire.to Referer.
REFERER = f"{SITE}/"

_READER_PATH_RE = re.compile(r"^/title/([^/]+)/(volume|chapter)/(\d+)")
_TITLE_PATH_RE = re.compile(r"^/title/([^/]+)")


def matches(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return host == "mangafire.to" or host.endswith(".mangafire.to")


async def scrape(url: str) -> list[ImageCandidate]:
    """Ordered page images of one volume or chapter."""
    match = _READER_PATH_RE.match(urlparse(url).path)
    if match is None:
        raise ExtractorError(
            "Paste a MangaFire volume or chapter link (…/volume/… or …/chapter/…), "
            "or use “Pull series” for a whole series page."
        )
    _, kind, item_id = match.groups()
    data = await capture_json(url, re.compile(rf"/api/{kind}s/{item_id}(?:\?|$)"))
    pages = (data.get("data") or {}).get("pages") or []
    return [
        ImageCandidate(url=page["url"], width=page.get("width"), height=page.get("height"))
        for page in pages
        if page.get("url")
    ]


async def list_series(url: str, language: str = "en") -> list[SeriesEntry]:
    """Every volume of a series in `language`, in reading order.

    Chapters aren't listed: the series page loads them 20 at a time, so a complete
    list would need paging through the UI. Pull chapters one link at a time instead.
    """
    match = _TITLE_PATH_RE.match(urlparse(url).path)
    if match is None:
        raise ExtractorError("Paste a MangaFire series link (https://mangafire.to/title/…).")
    slug = match.group(1)
    hid = slug.split("-", 1)[0]  # "pj5p9-mato-seihei-no-slave" -> "pj5p9"

    data = await capture_json(f"{SITE}/title/{slug}", re.compile(rf"/api/titles/{hid}/volumes(?:\?|$)"))
    items = [item for item in data.get("items") or [] if item.get("language") == language]
    items.sort(key=lambda item: item.get("number") or 0)
    return [
        SeriesEntry(
            kind="volume",
            number=item.get("number"),
            title=item.get("name") or None,
            url=f"{SITE}/title/{slug}/volume/{item['id']}",
        )
        for item in items
    ]
