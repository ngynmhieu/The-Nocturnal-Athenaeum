"""LlmService — turns OpenAI-shaped requests into manager calls and OpenAI
responses (including SSE streaming). Keeps the router thin."""
import json
import time
import uuid

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from .manager import LlmManager
from .schemas import ChatCompletionRequest


class LlmService:
    def __init__(self, manager: LlmManager) -> None:
        self._manager = manager

    def health(self) -> dict:
        return {"status": "ok", "loaded_model": self._manager.current_model_id}

    def list_models(self) -> dict:
        return {
            "object": "list",
            "data": [
                {
                    "id": cfg.id,
                    "object": "model",
                    "owned_by": "local",
                    "description": cfg.description,
                    "loaded": cfg.id == self._manager.current_model_id,
                    # Lets the backend and frontend adapt their surface to what the
                    # loaded model can actually do, instead of hardcoding it.
                    "capabilities": cfg.capabilities,
                }
                for cfg in self._manager.list_configs()
            ],
        }

    def complete(self, req: ChatCompletionRequest):
        try:
            self._manager.ensure(req.model)
        except KeyError:
            known = ", ".join(cfg.id for cfg in self._manager.list_configs())
            raise HTTPException(404, f"Model '{req.model}' not in catalog. Known: {known}")

        messages = [m.model_dump() for m in req.messages]
        opts = req.options()
        created = int(time.time())
        completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"

        if req.stream:
            return StreamingResponse(
                self._sse(req, messages, opts, created, completion_id),
                media_type="text/event-stream",
            )

        try:
            result = self._manager.generate(messages, req.max_tokens, **opts)
        except ValueError as exc:  # e.g. the latest message alone exceeds n_ctx
            raise HTTPException(400, str(exc))
        message: dict = {"role": "assistant", "text": result.text}
        if result.thinking:
            message["thinking"] = result.thinking
        return {
            "id": completion_id,
            "object": "chat.completion",
            "created": created,
            "model": req.model,
            "choices": [
                {
                    "index": 0,
                    "message": message,
                    "finish_reason": "stop",
                }
            ],
        }

    def _sse(self, req, messages, opts, created, completion_id):
        try:
            for chunk_type, chunk_text in self._manager.stream(messages, req.max_tokens, **opts):
                delta = {"thinking": chunk_text} if chunk_type == "thinking" else {"text": chunk_text}
                payload = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": req.model,
                    "choices": [
                        {"index": 0, "delta": delta, "finish_reason": None}
                    ],
                }
                yield f"data: {json.dumps(payload)}\n\n"
            done = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": req.model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
            yield f"data: {json.dumps(done)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:  # surface engine errors as an SSE error frame
            yield f"data: {json.dumps({'error': {'message': str(exc)}})}\n\n"
