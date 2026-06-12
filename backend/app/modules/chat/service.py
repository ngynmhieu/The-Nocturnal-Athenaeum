"""Chat orchestration service — normalizes history and drives the LLM engine."""
from typing import Any, Dict, Iterator, List

from backend.app.shared.llm import QwenService
from .schemas import Message

MessageDict = Dict[str, str]


class ChatService:
    """Orchestrates a conversation into a streamed response from the engine.

    Holds no model internals — it depends only on the injected QwenService and
    turns API-shaped messages into the engine's expected dict format.
    """

    def __init__(self, qwen_service: QwenService):
        self._qwen_service = qwen_service

    def _normalize_messages(self, messages: List[Message]) -> List[MessageDict]:
        return [{"role": message.role, "content": message.content} for message in messages]

    def stream_response(
        self,
        messages: List[Message],
        max_new_tokens: int = 1024,
        enable_thinking: bool = False,
    ) -> Iterator[str]:
        """Stream the assistant's response chunk by chunk."""
        for chunk in self._qwen_service.stream_generate(
            messages=self._normalize_messages(messages),
            max_new_tokens=max_new_tokens,
            enable_thinking=enable_thinking,
        ):
            yield chunk

    def health_check(self) -> Dict[str, Any]:
        return {
            "status": "ok",
            "ready": self._qwen_service.is_ready(),
            "model_loaded": self._qwen_service.is_loaded,
            "model_name": self._qwen_service.model_name,
        }
