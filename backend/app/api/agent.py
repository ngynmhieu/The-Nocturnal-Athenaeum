"""FastAPI routes for chat agent."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import json

from ..schemas import ChatRequest, ChatResponse
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


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
):
    try:
        messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]

        result = chat_service.generate_response(
            messages=messages,
            max_new_tokens=request.max_tokens or 1024,
            enable_thinking=request.enable_thinking or False,
        )

        return ChatResponse(
            response=result["response"],
            elapsed_time=result["elapsed_time"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
):
    def stream_generator():
        try:
            messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]

            for chunk in chat_service.stream_response(
                messages=messages,
                max_new_tokens=request.max_tokens or 1024,
                enable_thinking=request.enable_thinking or False,
            ):
                payload = json.dumps({"chunk": chunk})
                yield f"data: {payload}\n\n"
        except Exception as e:
            err = json.dumps({"error": str(e)})
            yield f"event: error\ndata: {err}\n\n"

    return StreamingResponse(stream_generator(), media_type="text/event-stream")
