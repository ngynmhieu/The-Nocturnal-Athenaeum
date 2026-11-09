"""HTTP routes for the read module — thin orchestration only."""
import uuid
from contextlib import contextmanager

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from backend.app.shared.images import UpscaleRejected, UpscaleUnavailable
from .dependencies import get_read_service, get_scrape_service, get_version_service
from .extractors import ExtractorError
from .schemas import (
    AcceptVersionRequest,
    CoverFromLibraryRequest,
    ImportRequest,
    LibraryAssetInfo,
    LibraryAssetRecord,
    LibraryImportRequest,
    MangaCreate,
    MangaDetail,
    MangaSummary,
    MangaUpdate,
    OrganizeRequest,
    PageInfo,
    PageRecord,
    PageVersionInfo,
    ReorderRequest,
    ScrapeRequest,
    ScrapeResult,
    SectionCreate,
    SectionSummary,
    SectionUpdate,
    SeriesRequest,
    SeriesResult,
    TranslateRequest,
    VersionKind,
    VersionPreview,
)
from .services import PageVersionService, ReadService, ScrapeService, VersionError
from .translate import TranslateRefusal

_UPSCALER_DOWN = "The upscaler isn't running. Start the models service and try again."

router = APIRouter(prefix="/read", tags=["read"])


# --- mangas --------------------------------------------------------

@router.get("/mangas", response_model=list[MangaSummary])
async def list_mangas(service: ReadService = Depends(get_read_service)):
    return await service.list_mangas()


@router.post("/mangas", response_model=MangaSummary)
async def create_manga(body: MangaCreate, service: ReadService = Depends(get_read_service)):
    return await service.create_manga(body)


@router.get("/mangas/{manga_id}", response_model=MangaDetail)
async def get_manga(manga_id: uuid.UUID, service: ReadService = Depends(get_read_service)):
    manga = await service.get_manga(manga_id)
    if manga is None:
        raise HTTPException(status_code=404, detail="Manga not found")
    return manga


@router.patch("/mangas/{manga_id}", response_model=MangaSummary)
async def update_manga(
    manga_id: uuid.UUID, body: MangaUpdate, service: ReadService = Depends(get_read_service)
):
    manga = await service.update_manga(manga_id, body)
    if manga is None:
        raise HTTPException(status_code=404, detail="Manga not found")
    return manga


@router.post("/mangas/{manga_id}/cover/from-library", response_model=MangaSummary)
async def set_manga_cover_from_library(
    manga_id: uuid.UUID, body: CoverFromLibraryRequest, service: ReadService = Depends(get_read_service)
):
    manga = await service.set_manga_cover_from_library(manga_id, body)
    if manga is None:
        raise HTTPException(status_code=404, detail="Manga not found")
    return manga


@router.delete("/mangas/{manga_id}", status_code=204)
async def delete_manga(manga_id: uuid.UUID, service: ReadService = Depends(get_read_service)):
    if not await service.delete_manga(manga_id):
        raise HTTPException(status_code=404, detail="Manga not found")


# --- sections --------------------------------------------------------

@router.post("/mangas/{manga_id}/sections", response_model=SectionSummary)
async def create_section(
    manga_id: uuid.UUID, body: SectionCreate, service: ReadService = Depends(get_read_service)
):
    section = await service.create_section(manga_id, body)
    if section is None:
        raise HTTPException(status_code=404, detail="Manga not found")
    return section


@router.patch("/sections/{section_id}", response_model=SectionSummary)
async def update_section(
    section_id: uuid.UUID, body: SectionUpdate, service: ReadService = Depends(get_read_service)
):
    section = await service.update_section(section_id, body)
    if section is None:
        raise HTTPException(status_code=404, detail="Section not found")
    return section


@router.post("/sections/{section_id}/cover/from-library", response_model=SectionSummary)
async def set_section_cover_from_library(
    section_id: uuid.UUID, body: CoverFromLibraryRequest, service: ReadService = Depends(get_read_service)
):
    section = await service.set_section_cover_from_library(section_id, body)
    if section is None:
        raise HTTPException(status_code=404, detail="Section not found")
    return section


@router.delete("/sections/{section_id}", status_code=204)
async def delete_section(section_id: uuid.UUID, service: ReadService = Depends(get_read_service)):
    if not await service.delete_section(section_id):
        raise HTTPException(status_code=404, detail="Section not found")


# --- pages --------------------------------------------------------

@router.get("/sections/{section_id}/pages", response_model=list[PageInfo])
async def list_pages(section_id: uuid.UUID, service: ReadService = Depends(get_read_service)):
    pages = await service.list_pages(section_id)
    if pages is None:
        raise HTTPException(status_code=404, detail="Section not found")
    return pages


@router.post("/sections/{section_id}/pages", response_model=list[PageInfo])
async def record_pages(
    section_id: uuid.UUID,
    body: list[PageRecord],
    service: ReadService = Depends(get_read_service),
):
    pages = await service.record_pages(section_id, body)
    if pages is None:
        raise HTTPException(status_code=404, detail="Section not found")
    return pages


@router.patch("/sections/{section_id}/pages/order", status_code=204)
async def reorder_pages(
    section_id: uuid.UUID,
    body: ReorderRequest,
    service: ReadService = Depends(get_read_service),
):
    result = await service.reorder_pages(section_id, body.ordered_page_ids)
    if result is None:
        raise HTTPException(status_code=404, detail="Section not found")
    if not result:
        raise HTTPException(
            status_code=400,
            detail="ordered_page_ids must exactly match the section's current pages",
        )


@router.delete("/pages/{page_id}", status_code=204)
async def delete_page(page_id: uuid.UUID, service: ReadService = Depends(get_read_service)):
    if not await service.delete_page(page_id):
        raise HTTPException(status_code=404, detail="Page not found")


# --- page versions (upscaled / translated) ------------------------------------

@contextmanager
def _version_errors():
    """Map the versions service's refusals to HTTP — the one place they're translated."""
    try:
        yield
    except VersionError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message)
    except TranslateRefusal as exc:
        raise HTTPException(status_code=422, detail=exc.message)
    except UpscaleRejected as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except UpscaleUnavailable:
        raise HTTPException(status_code=503, detail=_UPSCALER_DOWN)


@router.post("/pages/{page_id}/upscale", response_model=VersionPreview)
async def upscale_page(page_id: uuid.UUID, service: PageVersionService = Depends(get_version_service)):
    with _version_errors():
        return await service.upscale_preview(page_id)


@router.post("/pages/{page_id}/translate", response_model=VersionPreview)
async def translate_page(
    page_id: uuid.UUID, body: TranslateRequest, service: PageVersionService = Depends(get_version_service)
):
    with _version_errors():
        return await service.translate_preview(page_id, body.reference_page_id)


@router.post("/pages/{page_id}/versions/accept", response_model=PageVersionInfo)
async def accept_version(
    page_id: uuid.UUID, body: AcceptVersionRequest, service: PageVersionService = Depends(get_version_service)
):
    with _version_errors():
        return await service.accept(page_id, body.kind, body.language, body.reference_page_id)


@router.delete("/pages/{page_id}/versions/preview", status_code=204)
async def discard_version_preview(
    page_id: uuid.UUID,
    kind: VersionKind = Query(...),
    service: PageVersionService = Depends(get_version_service),
):
    with _version_errors():
        await service.discard(page_id, kind)


@router.delete("/pages/{page_id}/versions", status_code=204)
async def remove_version(
    page_id: uuid.UUID,
    kind: VersionKind = Query(...),
    language: str | None = Query(default=None),
    service: PageVersionService = Depends(get_version_service),
):
    with _version_errors():
        await service.remove(page_id, kind, language)


# --- scrape + import --------------------------------------------------------

@router.post("/scrape", response_model=ScrapeResult)
async def scrape(body: ScrapeRequest, service: ScrapeService = Depends(get_scrape_service)):
    try:
        return await service.scrape(body.url)
    except ExtractorError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/scrape/series", response_model=SeriesResult)
async def list_series(body: SeriesRequest, service: ScrapeService = Depends(get_scrape_service)):
    try:
        return await service.list_series(body.url, body.language)
    except ExtractorError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/sections/{section_id}/import", response_model=list[PageInfo])
async def import_into(
    section_id: uuid.UUID,
    body: ImportRequest,
    at: int | None = Query(default=None, ge=0),
    service: ScrapeService = Depends(get_scrape_service),
):
    """`?at=N` inserts the pages starting at position N (later pages move down);
    without it they're appended."""
    pages = await service.import_into(section_id, body.urls, body.referer, body.sizes, at)
    if pages is None:
        raise HTTPException(status_code=404, detail="Section not found")
    return pages


# --- library pool --------------------------------------------------------

@router.get("/library", response_model=list[LibraryAssetInfo])
async def list_library(service: ReadService = Depends(get_read_service)):
    return await service.list_library()


@router.post("/library")
async def record_library_assets(
    body: list[LibraryAssetRecord], service: ReadService = Depends(get_read_service)
):
    """Streams one NDJSON `LibraryStreamItem` line per record, the moment each
    one is validated + recorded (see `ReadService.stream_record_library_assets`)."""
    return StreamingResponse(
        service.stream_record_library_assets(body), media_type="application/x-ndjson"
    )


@router.post("/library/import")
async def import_to_library(
    body: LibraryImportRequest, service: ScrapeService = Depends(get_scrape_service)
):
    """Streams one NDJSON `LibraryStreamItem` line per URL, the moment each one
    is downloaded + uploaded (see `ScrapeService.stream_import_to_library`)."""
    return StreamingResponse(
        service.stream_import_to_library(body.urls, body.referer), media_type="application/x-ndjson"
    )


@router.post("/sections/{section_id}/pages/from-library", response_model=list[PageInfo])
async def organize_from_library(
    section_id: uuid.UUID,
    body: OrganizeRequest,
    at: int | None = Query(default=None, ge=0),
    service: ReadService = Depends(get_read_service),
):
    """`?at=N` inserts at position N (later pages move down); default appends."""
    pages = await service.organize_from_library(section_id, body.asset_ids, at)
    if pages is None:
        raise HTTPException(status_code=404, detail="Section not found")
    return pages


@router.delete("/library/{asset_id}", status_code=204)
async def discard_library_asset(
    asset_id: uuid.UUID, service: ReadService = Depends(get_read_service)
):
    if not await service.discard_library_asset(asset_id):
        raise HTTPException(status_code=404, detail="Library asset not found")
