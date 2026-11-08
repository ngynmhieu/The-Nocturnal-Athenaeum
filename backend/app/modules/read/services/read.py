"""CRUD over mangas/sections/pages, reorder, and the library pool — request-scoped.

Ownership is enforced here, not by table RLS (the backend connects as a privileged
role where auth.uid() is not populated) — every query is scoped to `user.id`. On
manga/section deletes and pool discards, the corresponding objects are removed from
the `manga` bucket via `shared/storage/` (the DB cascade drops rows only, not files).
"""
import uuid
from collections.abc import AsyncGenerator

from fastapi import HTTPException

from backend.app.modules.auth.schemas import CurrentUser
from backend.app.shared.storage import StorageClient
from ..repository import ReadRepository
from ..schemas import (
    CoverFromLibraryRequest,
    LibraryAssetInfo,
    LibraryAssetRecord,
    MangaCreate,
    MangaDetail,
    MangaSummary,
    MangaUpdate,
    PageInfo,
    PageRecord,
    SectionCreate,
    SectionSummary,
    SectionUpdate,
)
from .library_stream import stream_collect


class ReadService:
    def __init__(self, repo: ReadRepository, user: CurrentUser, storage: StorageClient):
        self._repo = repo
        self._user_id = uuid.UUID(user.id)
        self._storage = storage

    # --- mangas --------------------------------------------------------

    async def list_mangas(self) -> list[MangaSummary]:
        mangas = await self._repo.list_mangas(self._user_id)
        return [MangaSummary.model_validate(manga) for manga in mangas]

    async def create_manga(self, body: MangaCreate) -> MangaSummary:
        manga = await self._repo.create_manga(self._user_id, body.title, body.description)
        await self._repo.commit()
        return MangaSummary.model_validate(manga)

    async def get_manga(self, manga_id: uuid.UUID) -> MangaDetail | None:
        manga = await self._repo.get_manga(manga_id, self._user_id)
        if manga is None:
            return None
        sections = await self._repo.list_sections(manga_id)
        first_pages = await self._repo.first_page_paths([section.id for section in sections])
        return MangaDetail(
            **MangaSummary.model_validate(manga).model_dump(),
            sections=[
                SectionSummary.model_validate(section).model_copy(
                    update={"first_page_path": first_pages.get(section.id)}
                )
                for section in sections
            ],
        )

    async def update_manga(self, manga_id: uuid.UUID, body: MangaUpdate) -> MangaSummary | None:
        manga = await self._repo.get_manga(manga_id, self._user_id)
        if manga is None:
            return None
        fields = body.model_dump(exclude_unset=True)
        if fields:
            await self._repo.update_manga(manga_id, self._user_id, **fields)
            await self._repo.commit()
            manga = await self._repo.get_manga(manga_id, self._user_id)
        return MangaSummary.model_validate(manga)

    async def set_manga_cover_from_library(
        self, manga_id: uuid.UUID, body: CoverFromLibraryRequest
    ) -> MangaSummary | None:
        """Same idea as `organize_from_library`, just one asset and no `manga_pages`
        row: point `cover_path` at the asset's existing object, then remove it from
        the pool (not just leave it there — see `CoverFromLibraryRequest`)."""
        if await self._repo.get_manga(manga_id, self._user_id) is None:
            return None
        assets = await self._repo.get_library_assets([body.asset_id], self._user_id)
        if not assets:
            raise HTTPException(status_code=400, detail="asset_id is not an owned pool asset")

        await self._repo.update_manga(manga_id, self._user_id, cover_path=assets[0].storage_path)
        await self._repo.delete_library_assets([body.asset_id], self._user_id)
        await self._repo.commit()
        manga = await self._repo.get_manga(manga_id, self._user_id)
        return MangaSummary.model_validate(manga)

    async def delete_manga(self, manga_id: uuid.UUID) -> bool:
        if await self._repo.get_manga(manga_id, self._user_id) is None:
            return False
        paths = await self._repo.manga_storage_paths(manga_id)
        deleted = await self._repo.delete_manga(manga_id, self._user_id)
        if deleted:
            await self._repo.commit()
            await self._storage.remove(paths)
        return deleted

    # --- sections --------------------------------------------------------

    async def create_section(self, manga_id: uuid.UUID, body: SectionCreate) -> SectionSummary | None:
        section = await self._repo.create_section(
            manga_id, self._user_id, body.kind, body.number, body.title
        )
        if section is None:
            return None
        await self._repo.commit()
        return SectionSummary.model_validate(section)

    async def update_section(self, section_id: uuid.UUID, body: SectionUpdate) -> SectionSummary | None:
        section = await self._repo.get_section(section_id, self._user_id)
        if section is None:
            return None
        fields = body.model_dump(exclude_unset=True)
        if fields:
            await self._repo.update_section(section_id, self._user_id, **fields)
            await self._repo.commit()
            section = await self._repo.get_section(section_id, self._user_id)
        return SectionSummary.model_validate(section)

    async def set_section_cover_from_library(
        self, section_id: uuid.UUID, body: CoverFromLibraryRequest
    ) -> SectionSummary | None:
        """Section equivalent of `set_manga_cover_from_library` — see there for why
        the asset is removed from the pool, not just left in place."""
        if await self._repo.get_section(section_id, self._user_id) is None:
            return None
        assets = await self._repo.get_library_assets([body.asset_id], self._user_id)
        if not assets:
            raise HTTPException(status_code=400, detail="asset_id is not an owned pool asset")

        await self._repo.update_section(section_id, self._user_id, cover_path=assets[0].storage_path)
        await self._repo.delete_library_assets([body.asset_id], self._user_id)
        await self._repo.commit()
        section = await self._repo.get_section(section_id, self._user_id)
        return SectionSummary.model_validate(section)

    async def delete_section(self, section_id: uuid.UUID) -> bool:
        if await self._repo.get_section(section_id, self._user_id) is None:
            return False
        paths = await self._repo.section_storage_paths(section_id)
        deleted = await self._repo.delete_section(section_id, self._user_id)
        if deleted:
            await self._repo.commit()
            await self._storage.remove(paths)
        return deleted

    # --- pages --------------------------------------------------------

    async def list_pages(self, section_id: uuid.UUID) -> list[PageInfo] | None:
        if await self._repo.get_section(section_id, self._user_id) is None:
            return None
        pages = await self._repo.list_pages(section_id)
        return [PageInfo.model_validate(page) for page in pages]

    async def record_pages(
        self, section_id: uuid.UUID, records: list[PageRecord]
    ) -> list[PageInfo] | None:
        """Persist rows for files the frontend already uploaded direct to Storage."""
        if await self._repo.get_section(section_id, self._user_id) is None:
            return None
        self._require_own_prefix(record.storage_path for record in records)
        pages = await self._repo.insert_pages(section_id, [record.model_dump() for record in records])
        await self._repo.commit()
        return [PageInfo.model_validate(page) for page in pages]

    async def reorder_pages(
        self, section_id: uuid.UUID, ordered_page_ids: list[uuid.UUID]
    ) -> bool | None:
        """Tri-state: None = section not found/owned; False = ids don't match the
        section's current pages (stale client state, nothing written); True = done."""
        if await self._repo.get_section(section_id, self._user_id) is None:
            return None
        reordered = await self._repo.set_positions(section_id, ordered_page_ids)
        if reordered:
            await self._repo.commit()
        else:
            await self._repo.rollback()
        return reordered

    async def delete_page(self, page_id: uuid.UUID) -> bool:
        """Remove one page (row + its Storage object); later pages move up one."""
        page = await self._repo.get_page(page_id, self._user_id)
        if page is None:
            return False
        storage_path = page.storage_path
        await self._repo.delete_page(page)
        await self._repo.commit()
        await self._storage.remove([storage_path])
        return True

    # --- library pool --------------------------------------------------------

    async def list_library(self) -> list[LibraryAssetInfo]:
        assets = await self._repo.list_library(self._user_id)
        return [LibraryAssetInfo.model_validate(asset) for asset in assets]

    async def stream_record_library_assets(
        self, records: list[LibraryAssetRecord]
    ) -> AsyncGenerator[bytes, None]:
        """Persist pool rows for files the frontend already uploaded to `_pool/`,
        streamed — each record is reported the instant it's validated + recorded.
        There's no I/O left to bound (bytes are already in Storage), so every
        record validates/inserts concurrently. A record outside the caller's own
        prefix fails only that one item, not its siblings (a deliberate change
        from the previous whole-batch upfront check).
        """
        async def _prepare(record: LibraryAssetRecord) -> dict:
            self._require_own_prefix([record.storage_path], pool=True)
            return {"storage_path": record.storage_path, "width": record.width, "height": record.height}

        async for line in stream_collect(
            self._repo, self._user_id, records, len(records), lambda r: r.source_url, _prepare
        ):
            yield line

    async def organize_from_library(
        self, section_id: uuid.UUID, asset_ids: list[uuid.UUID], at: int | None = None
    ) -> list[PageInfo] | None:
        """Pool -> section: each asset becomes a page (reusing its existing Storage
        object — no byte move) and is removed from the pool, in one transaction.
        `at` inserts them starting at that position (later pages move down);
        None appends. None if the section isn't owned; 400 if an asset id isn't
        an owned pool asset.
        """
        if await self._repo.get_section(section_id, self._user_id) is None:
            return None
        assets = await self._repo.get_library_assets(asset_ids, self._user_id)
        if len(assets) != len(asset_ids):
            raise HTTPException(status_code=400, detail="one or more asset_ids are not owned pool assets")

        start_position = await self._repo.reserve_positions(section_id, len(assets), at)
        rows = [
            {
                "storage_path": asset.storage_path,
                "position": start_position + index,
                "width": asset.width,
                "height": asset.height,
            }
            for index, asset in enumerate(assets)
        ]
        pages = await self._repo.insert_pages(section_id, rows)
        await self._repo.delete_library_assets(asset_ids, self._user_id)
        await self._repo.commit()
        return [PageInfo.model_validate(page) for page in pages]

    async def discard_library_asset(self, asset_id: uuid.UUID) -> bool:
        assets = await self._repo.get_library_assets([asset_id], self._user_id)
        if not assets:
            return False
        deleted = await self._repo.delete_library_assets([asset_id], self._user_id)
        if deleted:
            await self._repo.commit()
            await self._storage.remove([assets[0].storage_path])
        return bool(deleted)

    # --- internal --------------------------------------------------------

    def _require_own_prefix(self, storage_paths, pool: bool = False) -> None:
        """Defense-in-depth: reject a recorded path outside the caller's own prefix
        even though Storage RLS already enforced this on the upload itself."""
        prefix = f"{self._user_id}/_pool/" if pool else f"{self._user_id}/"
        for path in storage_paths:
            if not path.startswith(prefix):
                raise HTTPException(
                    status_code=403,
                    detail=f"storage_path must be under the caller's own prefix: {path!r}",
                )
