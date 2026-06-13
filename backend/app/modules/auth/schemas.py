"""API-boundary shapes for the auth module.

`CurrentUser` is the lightweight, token-derived identity passed around the app
(returned by `get_current_user`). `ProfileResponse` is the stored profile row
returned over HTTP by the `/me` endpoints.
"""
import uuid

from pydantic import BaseModel, ConfigDict


class CurrentUser(BaseModel):
    """Who is making this request — derived from the verified JWT, not the DB.

    `id` and `email` identify the user; `full_name` / `avatar_url` come from the
    OAuth provider's metadata and are carried here so `sync_profile` can persist
    them without a second round-trip to Supabase.
    """

    id: str
    email: str | None = None
    full_name: str | None = None
    avatar_url: str | None = None


class ProfileResponse(BaseModel):
    """The stored profile row, as returned by GET/POST /me."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str | None = None
    full_name: str | None = None
    avatar_url: str | None = None
