"""Chat orchestration service - handles conversation flow and history."""
from typing import Any, Dict, Iterator, List, Mapping, Sequence
from ..llm.qwen_service import QwenService

MessageDict = Dict[str, str]


class ChatService:
    """Service for managing chat conversations and calling the LLM."""

    def __init__(self, qwen_service: QwenService):
        self.qwen_service = qwen_service
        self.conversations: Dict[str, List[MessageDict]] = {}

    def _normalize_messages(self, messages: Sequence[Mapping[str, str]]) -> List[MessageDict]:
        return [{"role": message["role"], "content": message["content"]} for message in messages]

    def stream_response(
        self,
        messages: Sequence[Mapping[str, str]],
        conversation_id: str = "default",
        max_new_tokens: int = 1024,
        enable_thinking: bool = False,
    ) -> Iterator[str]:
        for chunk in self.qwen_service.stream_generate(
            messages=self._normalize_messages(messages),
            max_new_tokens=max_new_tokens,
            enable_thinking=enable_thinking,
        ):
            yield chunk

    def health_check(self) -> Dict[str, Any]:
        return {
            "status": "ok",
            "ready": self.qwen_service.is_ready(),
            "model_loaded": self.qwen_service.is_loaded,
            "model_name": self.qwen_service.model_name,
        }
