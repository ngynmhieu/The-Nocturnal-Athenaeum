"""Read module API-boundary schemas (request/response shapes), grouped by purpose.

This package is the module's schema **public surface** — import from
`modules.read.schemas`, not the submodules. Grouped by sub-domain so each request
sits next to the responses it relates to:

    manga.py     /read/mangas*                    MangaCreate, MangaUpdate (req)
                                                    MangaSummary, MangaDetail (resp)
    section.py   /read/mangas/{id}/sections*,     SectionCreate, SectionUpdate (req)
                 /read/sections/{id}              SectionSummary (resp)
    page.py      /read/sections/{id}/pages*       PageRecord, ReorderRequest (req)
                                                    PageInfo, PageVersionInfo (resp)
    library.py   /read/library*,                  LibraryAssetRecord, OrganizeRequest,
                 /read/*/cover/from-library         CoverFromLibraryRequest (req)
                                                    LibraryAssetInfo (resp)
    scrape.py    /read/scrape*, /read/*/import     ScrapeRequest, SeriesRequest,
                                                    ImportRequest, LibraryImportRequest (req)
                                                    ScrapeResult, ScrapeCandidate,
                                                    SeriesResult, SeriesEntryInfo (resp)

Quick reference — which way does it cross the wire?

    Requests  (client → backend):  MangaCreate, MangaUpdate, SectionCreate, SectionUpdate,
                                    PageRecord, ReorderRequest, LibraryAssetRecord,
                                    OrganizeRequest, CoverFromLibraryRequest, ScrapeRequest,
                                    SeriesRequest, ImportRequest, LibraryImportRequest
    Responses (backend → client):  MangaSummary, MangaDetail, SectionSummary,
                                    PageInfo, PageVersionInfo, LibraryAssetInfo, ScrapeResult,
                                    ScrapeCandidate, SeriesResult, SeriesEntryInfo
"""
from .library import (
    CoverFromLibraryRequest,
    LibraryAssetInfo,
    LibraryAssetRecord,
    LibraryStreamItem,
    OrganizeRequest,
)
from .manga import MangaCreate, MangaDetail, MangaSummary, MangaUpdate
from .page import PageInfo, PageRecord, PageVersionInfo, ReorderRequest
from .scrape import (
    ImportRequest,
    LibraryImportRequest,
    PageSize,
    ScrapeCandidate,
    ScrapeRequest,
    ScrapeResult,
    SeriesEntryInfo,
    SeriesRequest,
    SeriesResult,
)
from .section import SectionCreate, SectionSummary, SectionUpdate

__all__ = [
    # --- requests (client → backend) ---
    "MangaCreate",
    "MangaUpdate",
    "SectionCreate",
    "SectionUpdate",
    "PageRecord",
    "ReorderRequest",
    "LibraryAssetRecord",
    "LibraryStreamItem",
    "OrganizeRequest",
    "CoverFromLibraryRequest",
    "ScrapeRequest",
    "SeriesRequest",
    "ImportRequest",
    "PageSize",
    "LibraryImportRequest",
    # --- responses (backend → client) ---
    "MangaSummary",
    "MangaDetail",
    "SectionSummary",
    "PageInfo",
    "PageVersionInfo",
    "LibraryAssetInfo",
    "ScrapeResult",
    "ScrapeCandidate",
    "SeriesResult",
    "SeriesEntryInfo",
]
