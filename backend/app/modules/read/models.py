"""ORM models for the read module — the read/write view of the persisted tables.

The tables themselves (FK into auth.users, RLS) are created by Supabase migrations
(`supabase/migrations/*_add_mangas.sql`, `*_add_manga_sections.sql`,
`*_add_manga_pages.sql`, `*_add_library_assets.sql`, `*_add_manga_page_versions.sql`), NOT by SQLAlchemy
`create_all`. These classes only let the backend query/insert rows. See
`backend/docs/modules/read.md` and `supabase/docs/modules/read.md`.
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class Manga(Base):
    """One manga series, owned by a user."""

    __tablename__ = "mangas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # FK into auth.users lives in the SQL migration only — that table isn't ORM-mapped.
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_path: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MangaSection(Base):
    """One volume or chapter of a manga — the tab discriminator is `kind`."""

    __tablename__ = "manga_sections"
    __table_args__ = (CheckConstraint("kind in ('volume', 'chapter')", name="manga_sections_kind_check"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    manga_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mangas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String, nullable=False)
    number: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    cover_path: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MangaPage(Base):
    """One page image, in `position` order within its section."""

    __tablename__ = "manga_pages"
    __table_args__ = (UniqueConstraint("section_id", "position", name="manga_pages_section_position_idx"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("manga_sections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    storage_path: Mapped[str] = mapped_column(String, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LibraryAsset(Base):
    """One unassigned image in a user's staging pool (scraped or uploaded, not yet
    organized into a manga). Owner-keyed directly on user_id — no parent manga to
    derive ownership through, unlike MangaSection/MangaPage.
    """

    __tablename__ = "library_assets"
    __table_args__ = (UniqueConstraint("user_id", "position", name="library_assets_user_position_idx"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    storage_path: Mapped[str | None] = mapped_column(String, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MangaPageVersion(Base):
    """An accepted derived version of a page: its upscaled and/or translated image.

    Unique per (page_id, kind, coalesce(language, '')) — that expression index lives
    in the migration only; the repository does the null-aware lookup itself.
    """

    __tablename__ = "manga_page_versions"
    __table_args__ = (CheckConstraint("kind in ('upscaled', 'translated')", name="manga_page_versions_kind_check"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("manga_pages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String, nullable=False)
    language: Mapped[str | None] = mapped_column(String, nullable=True)
    storage_path: Mapped[str] = mapped_column(String, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reference_page_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("manga_pages.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
