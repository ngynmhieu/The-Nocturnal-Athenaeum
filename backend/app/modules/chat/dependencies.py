"""Dependency providers — the chat module's DI surface.

The ChatService is built once during the app lifespan and stored on
`app.state`; this provider hands it to route handlers via `Depends`.
"""
from fastapi import HTTPException, Request

from .service import ChatService


def get_chat_service(request: Request) -> ChatService:
    service = getattr(request.app.state, "chat_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Chat service not initialized")
    return service
