"""Persistence for mangas/sections/pages/library_assets — the read module's DB component.

All access is scoped to a user_id (ownership is enforced here, not by RLS — the
backend connects as a privileged role where auth.uid() is not populated). Methods on
a child of an already-resolved parent (sections under a manga, pages under a section)
trust that the caller (the service) already resolved that parent through an
ownership-checked lookup — they don't re-check, matching `ConversationRepository`.
"""
import uuid

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import LibraryAsset, Manga, MangaPage, MangaSection


class ReadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()

    # --- mangas --------------------------------------------------------

    async def list_mangas(self, user_id: uuid.UUID) -> list[Manga]:
        result = await self._session.execute(
            select(Manga).where(Manga.user_id == user_id).order_by(Manga.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get_manga(self, manga_id: uuid.UUID, user_id: uuid.UUID) -> Manga | None:
        result = await self._session.execute(
            select(Manga).where(Manga.id == manga_id, Manga.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create_manga(
        self, user_id: uuid.UUID, title: str, description: str | None = None
    ) -> Manga:
        manga = Manga(user_id=user_id, title=title, description=description)
        self._session.add(manga)
        await self._session.flush()
        return manga

    async def update_manga(self, manga_id: uuid.UUID, user_id: uuid.UUID, **fields) -> None:
        """Apply `fields` (already existence/ownership-checked by the caller)."""
        if not fields:
            return
        await self._session.execute(
            update(Manga)
            .where(Manga.id == manga_id, Manga.user_id == user_id)
            .values(**fields, updated_at=func.now())
        )

    async def delete_manga(self, manga_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        result = await self._session.execute(
            delete(Manga).where(Manga.id == manga_id, Manga.user_id == user_id)
        )
        return result.rowcount > 0

    # --- sections --------------------------------------------------------

    async def list_sections(self, manga_id: uuid.UUID) -> list[MangaSection]:
        result = await self._session.execute(
            select(MangaSection)
            .where(MangaSection.manga_id == manga_id)
            .order_by(MangaSection.kind, MangaSection.number)
        )
        return list(result.scalars().all())

    async def create_section(
        self,
        manga_id: uuid.UUID,
        user_id: uuid.UUID,
        kind: str,
        number: float | None,
        title: str | None,
    ) -> MangaSection | None:
        """Insert a section under `manga_id`, or None if it isn't owned by `user_id`."""
        manga = await self.get_manga(manga_id, user_id)
        if manga is None:
            return None
        section = MangaSection(manga_id=manga_id, kind=kind, number=number, title=title)
        self._session.add(section)
        await self._session.flush()
        return section

    async def get_section(self, section_id: uuid.UUID, user_id: uuid.UUID) -> MangaSection | None:
        result = await self._session.execute(
            select(MangaSection)
            .join(Manga, Manga.id == MangaSection.manga_id)
            .where(MangaSection.id == section_id, Manga.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def delete_section(self, section_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        result = await self._session.execute(
            delete(MangaSection).where(
                MangaSection.id == section_id,
                MangaSection.manga_id.in_(select(Manga.id).where(Manga.user_id == user_id)),
            )
        )
        return result.rowcount > 0

    async def update_section(self, section_id: uuid.UUID, user_id: uuid.UUID, **fields) -> None:
        """Apply `fields` (already existence/ownership-checked by the caller)."""
        if not fields:
            return
        await self._session.execute(
            update(MangaSection)
            .where(
                MangaSection.id == section_id,
                MangaSection.manga_id.in_(select(Manga.id).where(Manga.user_id == user_id)),
            )
            .values(**fields)
        )

    async def first_page_paths(self, section_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
        """First page's `storage_path` per section (by `position`) — batched in one
        query so listing a manga's sections doesn't fetch pages per-section."""
        if not section_ids:
            return {}
        ranked = (
            select(
                MangaPage.section_id,
                MangaPage.storage_path,
                func.row_number()
                .over(partition_by=MangaPage.section_id, order_by=MangaPage.position)
                .label("rn"),
            )
            .where(MangaPage.section_id.in_(section_ids))
            .subquery()
        )
        result = await self._session.execute(
            select(ranked.c.section_id, ranked.c.storage_path).where(ranked.c.rn == 1)
        )
        return {row.section_id: row.storage_path for row in result.all()}

    # --- pages --------------------------------------------------------

    async def list_pages(self, section_id: uuid.UUID) -> list[MangaPage]:
        result = await self._session.execute(
            select(MangaPage)
            .where(MangaPage.section_id == section_id)
            .order_by(MangaPage.position)
        )
        return list(result.scalars().all())

    async def count_pages(self, section_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(MangaPage).where(MangaPage.section_id == section_id)
        )
        return result.scalar_one()

    async def insert_pages(
        self, section_id: uuid.UUID, rows: list[dict]
    ) -> list[MangaPage]:
        """`rows` = [{storage_path, position, width, height}, ...]."""
        pages = [
            MangaPage(
                section_id=section_id,
                storage_path=row["storage_path"],
                position=row["position"],
                width=row.get("width"),
                height=row.get("height"),
            )
            for row in rows
        ]
        self._session.add_all(pages)
        await self._session.flush()
        return pages

    async def set_positions(self, section_id: uuid.UUID, ordered_page_ids: list[uuid.UUID]) -> bool:
        """Rewrite `position` to each id's index in `ordered_page_ids`.

        False if the id set doesn't exactly match the section's current pages
        (stale client state) — nothing is written in that case. Goes through a
        negative-position staging pass first: `(section_id, position)` is unique,
        so writing final positions directly can collide with a row that hasn't
        moved yet (e.g. swapping two pages).
        """
        existing = await self._session.execute(
            select(MangaPage.id).where(MangaPage.section_id == section_id)
        )
        existing_ids = {row[0] for row in existing.all()}
        if set(ordered_page_ids) != existing_ids:
            return False

        for index, page_id in enumerate(ordered_page_ids):
            await self._session.execute(
                update(MangaPage).where(MangaPage.id == page_id).values(position=-(index + 1))
            )
        for index, page_id in enumerate(ordered_page_ids):
            await self._session.execute(
                update(MangaPage).where(MangaPage.id == page_id).values(position=index)
            )
        return True

    async def get_page(self, page_id: uuid.UUID, user_id: uuid.UUID) -> MangaPage | None:
        result = await self._session.execute(
            select(MangaPage)
            .join(MangaSection, MangaSection.id == MangaPage.section_id)
            .join(Manga, Manga.id == MangaSection.manga_id)
            .where(MangaPage.id == page_id, Manga.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def delete_page(self, page: MangaPage) -> None:
        """Delete one page and close the gap it leaves (later pages move up one)."""
        await self._session.delete(page)
        await self._session.flush()
        await self._shift_positions(page.section_id, from_position=page.position + 1, by=-1)

    async def reserve_positions(self, section_id: uuid.UUID, count: int, at: int | None = None) -> int:
        """Free `count` consecutive positions and return the first one.

        `at=None` appends after the last page. Otherwise the pages from `at` on
        (clamped to the section's length) move down by `count` to make room, so
        new pages can land in front of / behind any existing page.
        """
        total = await self.count_pages(section_id)
        if at is None or at >= total:
            return total
        start = max(at, 0)
        if count > 0:
            await self._shift_positions(section_id, from_position=start, by=count)
        return start

    async def _shift_positions(self, section_id: uuid.UUID, from_position: int, by: int) -> None:
        """Add `by` to every position `>= from_position`. Two passes through
        negatives (as in `set_positions`): the unique `(section_id, position)`
        index is checked row by row, so a one-step shift would collide with a
        neighbour that hasn't moved yet."""
        await self._session.execute(
            update(MangaPage)
            .where(MangaPage.section_id == section_id, MangaPage.position >= from_position)
            .values(position=-(MangaPage.position + by) - 1)
        )
        await self._session.execute(
            update(MangaPage)
            .where(MangaPage.section_id == section_id, MangaPage.position < 0)
            .values(position=-MangaPage.position - 1)
        )

    async def manga_storage_paths(self, manga_id: uuid.UUID) -> list[str]:
        """Every Storage object under a manga (cover + section covers + pages) —
        gathered before delete, since the DB cascade drops rows, not files."""
        paths: list[str] = []
        manga = await self._session.get(Manga, manga_id)
        if manga and manga.cover_path:
            paths.append(manga.cover_path)

        sections = await self.list_sections(manga_id)
        paths.extend(section.cover_path for section in sections if section.cover_path)

        section_ids = [section.id for section in sections]
        if section_ids:
            result = await self._session.execute(
                select(MangaPage.storage_path).where(MangaPage.section_id.in_(section_ids))
            )
            paths.extend(row[0] for row in result.all())
        return paths

    async def section_storage_paths(self, section_id: uuid.UUID) -> list[str]:
        """Every Storage object under one section (cover + pages), gathered before delete."""
        paths: list[str] = []
        section = await self._session.get(MangaSection, section_id)
        if section and section.cover_path:
            paths.append(section.cover_path)
        result = await self._session.execute(
            select(MangaPage.storage_path).where(MangaPage.section_id == section_id)
        )
        paths.extend(row[0] for row in result.all())
        return paths

    # --- library pool --------------------------------------------------------

    async def list_library(self, user_id: uuid.UUID) -> list[LibraryAsset]:
        """In collect order — the pool reads top-to-bottom as a collection queue,
        with freshly collected images landing at the bottom. Excludes reserved
        slots still awaiting their download/upload (see `reserve_library_asset_slots`)
        — an in-flight streaming collect shouldn't show a broken card if the pool
        is viewed from another tab mid-batch."""
        result = await self._session.execute(
            select(LibraryAsset)
            .where(LibraryAsset.user_id == user_id, LibraryAsset.storage_path.is_not(None))
            .order_by(LibraryAsset.position.asc())
        )
        return list(result.scalars().all())

    async def count_library_assets(self, user_id: uuid.UUID) -> int:
        """Counts reserved-but-unfilled slots too (deliberately no `storage_path`
        filter here) — that's what makes `reserve_library_asset_slots` safe
        against a second concurrent batch reading a stale count."""
        result = await self._session.execute(
            select(func.count()).select_from(LibraryAsset).where(LibraryAsset.user_id == user_id)
        )
        return result.scalar_one()

    async def reserve_library_asset_slots(
        self, user_id: uuid.UUID, source_urls: list[str | None]
    ) -> list[uuid.UUID]:
        """Insert one placeholder row per item (`storage_path=NULL`, `position`
        reserved, `source_url` set where already known) — real rows, committed
        immediately, before any download/upload starts. Returns their ids in the
        same order as `source_urls`, for the caller to fill in later via
        `fill_library_asset`.

        Takes a user-scoped advisory lock (released automatically at this
        method's commit) before reading the current count: two batches for the
        same user landing at once (e.g. a scrape import and an upload import
        both starting around the same time) would otherwise both read the same
        count and collide on `position`. The lock is held only for this fast
        insert, never across the slow download/upload phase that follows.
        """
        await self._session.execute(
            text("select pg_advisory_xact_lock(hashtext(:user_id)::bigint)"), {"user_id": str(user_id)}
        )
        start_position = await self.count_library_assets(user_id)
        assets = [
            LibraryAsset(user_id=user_id, source_url=source_url, position=start_position + index)
            for index, source_url in enumerate(source_urls)
        ]
        self._session.add_all(assets)
        await self._session.flush()
        await self._session.commit()  # release the lock now, before any slow I/O
        return [asset.id for asset in assets]

    async def fill_library_asset(self, asset_id: uuid.UUID, fields: dict) -> LibraryAsset:
        """`fields` = {storage_path, width, height} — completes a reserved slot
        once its download/upload has finished."""
        await self._session.execute(
            update(LibraryAsset).where(LibraryAsset.id == asset_id).values(**fields)
        )
        result = await self._session.execute(select(LibraryAsset).where(LibraryAsset.id == asset_id))
        return result.scalar_one()

    async def get_library_assets(
        self, asset_ids: list[uuid.UUID], user_id: uuid.UUID
    ) -> list[LibraryAsset]:
        """Owned assets among `asset_ids`, in the given order (unowned/missing ids dropped)."""
        result = await self._session.execute(
            select(LibraryAsset).where(
                LibraryAsset.id.in_(asset_ids), LibraryAsset.user_id == user_id
            )
        )
        by_id = {asset.id: asset for asset in result.scalars().all()}
        return [by_id[asset_id] for asset_id in asset_ids if asset_id in by_id]

    async def delete_library_assets(self, asset_ids: list[uuid.UUID], user_id: uuid.UUID) -> int:
        result = await self._session.execute(
            delete(LibraryAsset).where(
                LibraryAsset.id.in_(asset_ids), LibraryAsset.user_id == user_id
            )
        )
        return result.rowcount
