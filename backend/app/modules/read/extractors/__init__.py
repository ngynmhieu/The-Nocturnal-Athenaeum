"""Per-site extractors — for readers the generic `scraper.py` can't read.

Each site module exposes the same small interface:

    matches(url) -> bool                     does this extractor own the URL?
    scrape(url) -> list[ImageCandidate]      one volume/chapter's pages, in order
    list_series(url) -> list[SeriesEntry]    a series page's volumes, in order
    REFERER                                  what image downloads must send

`ScrapeService` asks `for_url()` first and falls back to the generic scraper.
"""
from types import ModuleType

from . import mangafire
from .base import ExtractorError, SeriesEntry

_SITES: tuple[ModuleType, ...] = (mangafire,)


def for_url(url: str) -> ModuleType | None:
    """The extractor that owns `url`, or None for the generic scraper."""
    return next((site for site in _SITES if site.matches(url)), None)


__all__ = ["ExtractorError", "SeriesEntry", "for_url"]
