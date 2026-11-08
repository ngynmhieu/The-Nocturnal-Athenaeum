"""Scrape a page for candidate images, then import chosen ones — into a section or
the pool. Two requests, deliberately kept separate so the user can pick in between
(see `ScrapeService` in `backend/docs/modules/read.md`).
"""
import asyncio
import logging
import mimetypes
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from urllib.parse import urlparse

import httpx

from backend.app.modules.auth.schemas import CurrentUser
from backend.app.shared.storage import StorageClient
from .. import extractors, scraper
from ..repository import ReadRepository
from ..schemas import (
    PageInfo,
    PageSize,
    ScrapeCandidate,
    ScrapeResult,
    SeriesEntryInfo,
    SeriesResult,
)
from .library_stream import stream_collect

logger = logging.getLogger(__name__)

DOWNLOAD_CONCURRENCY = 5

Download = tuple[bytes, str | None]  # (content, content_type)


class ScrapeService:
    def __init__(self, repo: ReadRepository, user: CurrentUser, storage: StorageClient):
        self._repo = repo
        self._user_id = uuid.UUID(user.id)
        self._storage = storage

    async def scrape(self, url: str) -> ScrapeResult:
        """Fetch + extract candidate image URLs. No persistence. A per-site extractor
        (see `extractors/`) wins over the generic scraper when one owns the URL.
        Raises `extractors.ExtractorError` with a user-facing message on failure."""
        site = extractors.for_url(url)
        try:
            candidates = await (site.scrape(url) if site else scraper.scrape(url))
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            hint = (
                " It blocks automated requests — open the page in your browser, right-click "
                "the image → “Copy image address”, and paste that link instead."
                if code in (401, 402, 403, 429) else ""
            )
            raise extractors.ExtractorError(f"The site refused the request (HTTP {code}).{hint}") from exc
        except httpx.HTTPError as exc:
            raise extractors.ExtractorError(f"Couldn't reach that page ({type(exc).__name__}).") from exc
        return ScrapeResult(
            candidates=[ScrapeCandidate.model_validate(c) for c in candidates],
            referer=site.REFERER if site else None,
        )

    async def list_series(self, url: str, language: str) -> SeriesResult:
        """A series page's volumes, in reading order — each entry's `url` feeds `scrape`."""
        site = extractors.for_url(url)
        if site is None:
            raise extractors.ExtractorError("Pulling a whole series isn't supported for this site yet.")
        entries = await site.list_series(url, language)
        return SeriesResult(entries=[SeriesEntryInfo.model_validate(e) for e in entries])

    async def import_into(
        self,
        section_id: uuid.UUID,
        urls: list[str],
        referer: str | None = None,
        sizes: dict[str, PageSize] | None = None,
        at: int | None = None,
    ) -> list[PageInfo] | None:
        """Download + upload each URL server-side (browsers can't fetch cross-origin/
        hotlink-protected images), under the section's own prefix, then record pages
        in `urls` order — appended, or from position `at` with later pages moved
        down. A URL that fails to download is skipped, not fatal to the batch.
        """
        section = await self._repo.get_section(section_id, self._user_id)
        if section is None:
            return None

        downloads = await self._download_all(urls, referer)
        landed = [(url, download) for url, download in zip(urls, downloads) if download is not None]
        start_position = await self._repo.reserve_positions(section_id, len(landed), at)
        sizes = sizes or {}

        # Positions are fixed from the request order before uploading, so the
        # concurrent uploads below can finish in any order.
        semaphore = asyncio.Semaphore(DOWNLOAD_CONCURRENCY)

        async def _upload(position: int, url: str, download: Download) -> dict:
            content, content_type = download
            path = (
                f"{self._user_id}/{section.manga_id}/{section_id}/"
                f"{position}-{uuid.uuid4()}{_extension(url, content_type)}"
            )
            async with semaphore:
                await self._storage.upload(path, content, content_type)
            size = sizes.get(url) or PageSize()
            return {"storage_path": path, "position": position, "width": size.width, "height": size.height}

        rows = await asyncio.gather(
            *(_upload(start_position + i, url, download) for i, (url, download) in enumerate(landed))
        )

        pages = await self._repo.insert_pages(section_id, list(rows))
        await self._repo.commit()
        return [PageInfo.model_validate(page) for page in pages]

    async def stream_import_to_library(
        self, urls: list[str], referer: str | None = None
    ) -> AsyncGenerator[bytes, None]:
        """Same download as `import_into`, but into the pool: `{user_id}/_pool/...`,
        streamed — each URL's image is reported the moment it's downloaded and
        uploaded, not batched to the end (see `library_stream.stream_collect`).
        One shared client for the whole batch, unlike `_download_all`, since this
        stays open for the generator's full lifetime rather than one bounded call.
        """
        async with httpx.AsyncClient(timeout=scraper.REQUEST_TIMEOUT) as client:

            async def _prepare(url: str) -> dict:
                content, content_type = await scraper.download_image(client, url, referer=referer)
                path = f"{self._user_id}/_pool/{uuid.uuid4()}{_extension(url, content_type)}"
                await self._storage.upload(path, content, content_type)
                return {"storage_path": path, "width": None, "height": None}

            async for line in stream_collect(
                self._repo, self._user_id, urls, DOWNLOAD_CONCURRENCY, lambda url: url, _prepare
            ):
                yield line

    async def _download_all(self, urls: list[str], referer: str | None) -> list[Download | None]:
        """Download every URL concurrently (bounded), preserving order; a failed
        download becomes None rather than aborting the whole batch."""
        semaphore = asyncio.Semaphore(DOWNLOAD_CONCURRENCY)

        async def _one(client: httpx.AsyncClient, url: str) -> Download | None:
            async with semaphore:
                try:
                    return await scraper.download_image(client, url, referer=referer)
                except httpx.HTTPError as exc:
                    logger.warning("skip %s: %s", url, exc)
                    return None

        async with httpx.AsyncClient(timeout=scraper.REQUEST_TIMEOUT) as client:
            return await asyncio.gather(*(_one(client, url) for url in urls))


def _extension(url: str, content_type: str | None) -> str:
    suffix = Path(urlparse(url).path).suffix
    if not suffix and content_type:
        suffix = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ""
    return suffix or ".jpg"
