"""HTTP routes for the auth module — thin orchestration only.

POST /me  → record (upsert) the caller's profile; called once after login.
GET  /me  → read the caller's stored profile.
Both require a valid Bearer token via `get_current_user`.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_session
from .dependencies import get_auth_service, get_current_user
from .models import Profile
from .schemas import CurrentUser, ProfileResponse
from .service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/me", response_model=ProfileResponse)
async def sync_profile(
    user: CurrentUser = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
    session: AsyncSession = Depends(get_session),
):
    """Create or refresh the caller's profile row, then return it."""
    return await auth_service.sync_profile(user, session)


@router.get("/me", response_model=ProfileResponse)
async def read_profile(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Return the caller's stored profile, or 404 if they haven't synced yet."""
    profile = await session.get(Profile, uuid.UUID(user.id))
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found; call POST /auth/me first")
    return profile
