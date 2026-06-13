"""The auth module's PUBLIC surface.

`get_current_user` is the only thing other modules import from `auth` — every
protected route depends on it. `get_auth_service` hands out the AuthService
built once during the app lifespan and stored on `app.state`.
"""
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .schemas import CurrentUser
from .service import AuthService

# auto_error=False so a missing header yields None (our 401) instead of FastAPI's.
_bearer_scheme = HTTPBearer(auto_error=False)


def get_auth_service(request: Request) -> AuthService:
    service = getattr(request.app.state, "auth_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Auth service not initialized")
    return service


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> CurrentUser:
    """Extract the Bearer token and resolve it to the current user (or 401)."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return await auth_service.verify(credentials.credentials)
