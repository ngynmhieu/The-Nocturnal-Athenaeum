"""ORM model for the app-owned `profiles` table.

The table itself (FK into auth.users and RLS) is defined in
`supabase/migrations/20260613082710_create_profiles.sql` and applied with
`supabase db push` — NOT by SQLAlchemy `create_all`, because it foreign-keys
into Supabase's internal `auth.users`. This class is the backend's read/write
view of that table.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class Profile(Base):
    """A user's app-owned profile, 1-to-1 with a Supabase auth user (same UUID)."""

    __tablename__ = "profiles"

    # Same UUID as auth.users.id. The FK constraint lives in the SQL migration,
    # not here, since auth.users is outside this app's schema control.
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)

    email: Mapped[str | None] = mapped_column(String)
    full_name: Mapped[str | None] = mapped_column(String)
    avatar_url: Mapped[str | None] = mapped_column(String)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
