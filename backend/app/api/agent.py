"""FastAPI routes for chat agent."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import json

from ..schemas import ChatRequest
from ..services import ChatService

_chat_service: ChatService = None


def get_chat_service() -> ChatService:
    if _chat_service is None:
        raise HTTPException(status_code=503, detail="Chat service not initialized")
    return _chat_service


def set_chat_service(service: ChatService) -> None:
    global _chat_service
    _chat_service = service


router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.get("/health")
async def health_check(chat_service: ChatService = Depends(get_chat_service)):
    return chat_service.health_check()


@router.post("/chat")
async def chat(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
):
    messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]

    def stream_generator():
        try:
            for chunk in chat_service.stream_response(
                messages=messages,
                max_new_tokens=request.max_tokens or 1024,
                enable_thinking=request.enable_thinking or False,
            ):
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(stream_generator(), media_type="text/event-stream")
