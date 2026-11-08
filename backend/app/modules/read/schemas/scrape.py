"""Scrape/import shapes — fetch-and-pick, then import into a section or the pool.

Deliberately two requests (scrape, then import) so the user picks between them —
see `ScrapeService` in `backend/docs/modules/read.md`.
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# --- requests (client → backend) -------------------------------------------

class ScrapeRequest(BaseModel):
    """Body for `POST /read/scrape`."""
    url: str = Field(..., min_length=1)


class SeriesRequest(BaseModel):
    """Body for `POST /read/scrape/series` — a series page on a supported site."""
    url: str = Field(..., min_length=1)
    language: str = "en"


class PageSize(BaseModel):
    width: int | None = None
    height: int | None = None


class ImportRequest(BaseModel):
    """Body for `POST /read/sections/{id}/import` — the chosen, ordered URLs.

    `referer` should be `ScrapeResult.referer` (falling back to the page URL
    originally scraped) — some sites hotlink-protect images on it, so the backend's
    download needs it too. `sizes` carries each URL's known dimensions (keyed by
    URL) so the reader can reserve page boxes without measuring.
    """
    urls: list[str] = Field(..., min_length=1)
    referer: str | None = None
    sizes: dict[str, PageSize] = Field(default_factory=dict)


class LibraryImportRequest(BaseModel):
    """Body for `POST /read/library/import` — same as `ImportRequest`, but the
    destination is the pool (no section, no ordering — the pool is unordered)."""
    urls: list[str] = Field(..., min_length=1)
    referer: str | None = None


# --- responses (backend → client) ------------------------------------------

class ScrapeCandidate(BaseModel):
    """One candidate image found on the page, for the user to pick from."""
    model_config = ConfigDict(from_attributes=True)

    url: str
    width: int | None = None
    height: int | None = None


class ScrapeResult(BaseModel):
    """Body of `POST /read/scrape`'s response — no persistence yet. `referer` is set
    when a per-site extractor knows what its image CDN requires."""
    candidates: list[ScrapeCandidate]
    referer: str | None = None


class SeriesEntryInfo(BaseModel):
    """One volume/chapter of a series — `url` goes back into `POST /read/scrape`."""
    model_config = ConfigDict(from_attributes=True)

    kind: Literal["volume", "chapter"]
    number: float | None = None
    title: str | None = None
    url: str


class SeriesResult(BaseModel):
    """Body of `POST /read/scrape/series`'s response, in reading order."""
    entries: list[SeriesEntryInfo]
