"""FastAPI routes for chat agent."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import json

from ..schemas import ChatRequest, ChatResponse, StreamChunk
from ..services import ChatService

# Global reference to chat service (injected by main.py during startup)
_chat_service: ChatService = None


def get_chat_service() -> ChatService:
    """Dependency injection for chat service."""
    if _chat_service is None:
        raise HTTPException(status_code=503, detail="Chat service not initialized")
    return _chat_service


def set_chat_service(service: ChatService) -> None:
    """Set the global chat service reference (called during app startup)."""
    global _chat_service
    _chat_service = service


router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.get("/health")
async def health_check(chat_service: ChatService = Depends(get_chat_service)):
    """Health check endpoint.
    
    Returns:
        Status, readiness, and model information
    """
    return chat_service.health_check()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
):
    """Non-streaming chat endpoint.
    
    Args:
        request: ChatRequest with messages and optional parameters
        
    Returns:
        ChatResponse with generated response and timing
    """
    try:
        # Convert Pydantic Message objects to dicts for the service
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
    """Streaming chat endpoint.
    
    Streams tokens as they are generated, returning JSONL format.
    Each line is a JSON object with a 'chunk' field.
    
    Args:
        request: ChatRequest with messages and optional parameters
        
    Returns:
        StreamingResponse with tokens streamed as JSONL
    """
    
    async def stream_generator():
        """Generator that yields tokens as JSONL lines."""
        try:
            # Convert Pydantic Message objects to dicts for the service
            messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
            
            for chunk in chat_service.stream_response(
                messages=messages,
                max_new_tokens=request.max_tokens or 1024,
                enable_thinking=request.enable_thinking or False,
            ):
                # Yield each chunk as Server-Sent Event (SSE) 'data' frame
                payload = json.dumps({"chunk": chunk})
                yield f"data: {payload}\n\n"
        except Exception as e:
            err = json.dumps({"error": str(e)})
            yield f"event: error\ndata: {err}\n\n"
    
    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
    )