"""Chat orchestration service - handles conversation flow and history."""
from typing import Any, Dict, Iterator, List, Mapping, Sequence
from ..llm.qwen_service import QwenService

MessageDict = Dict[str, str]


class ChatService:
    """Service for managing chat conversations and calling the LLM.
    
    This service:
    - Manages conversation history
    - Orchestrates calls to QwenService
    - Handles chat logic and context management
    """
    
    def __init__(self, qwen_service: QwenService):
        """Initialize chat service with a QwenService instance.
        
        Args:
            qwen_service: The language model service to use for generation
        """
        self.qwen_service = qwen_service
        self.conversations: Dict[str, List[MessageDict]] = {}

    def _normalize_messages(self, messages: Sequence[Mapping[str, str]]) -> List[MessageDict]:
        """Normalize message objects into plain role/content dictionaries.

        The outer layer passes simple dicts today, but this keeps the chat
        service tolerant of mapping-like inputs while the inner model layer is
        still abstract.
        """
        return [{"role": message["role"], "content": message["content"]} for message in messages]
    
    def generate_response(
        self,
        messages: List[Dict[str, str]],
        conversation_id: str = "default",
        max_new_tokens: int = 1024,
        enable_thinking: bool = False,
    ) -> Dict[str, Any]:
        """Generate a non-streaming response.
        
        Args:
            messages: Chat history
            conversation_id: ID to track conversation (optional)
            max_new_tokens: Max tokens to generate
            enable_thinking: Enable thinking mode
            
        Returns:
            Dict with 'response', 'elapsed_time', 'conversation_id'
        """
        # TODO: Call qwen_service.generate_once
        response, elapsed_time = self.qwen_service.generate_once(
            messages=self._normalize_messages(messages),
            max_new_tokens=max_new_tokens,
            enable_thinking=enable_thinking,
        )
        
        return {
            "response": response,
            "elapsed_time": elapsed_time,
            "conversation_id": conversation_id,
        }
    
    def stream_response(
        self,
        messages: Sequence[Mapping[str, str]],
        conversation_id: str = "default",
        max_new_tokens: int = 1024,
        enable_thinking: bool = False,
    ) -> Iterator[str]:
        """Stream a response token by token.
        
        Args:
            messages: Chat history
            conversation_id: ID to track conversation (optional)
            max_new_tokens: Max tokens to generate
            enable_thinking: Enable thinking mode
            
        Yields:
            Token chunks as they are generated
        """
        for chunk in self.qwen_service.stream_generate(
            messages=self._normalize_messages(messages),
            max_new_tokens=max_new_tokens,
            enable_thinking=enable_thinking,
        ):
            yield chunk
    
    def health_check(self) -> Dict[str, Any]:
        """Check service health and readiness.
        
        Returns:
            Dict with 'status', 'ready', 'model_loaded'
        """
        return {
            "status": "ok",
            "ready": self.qwen_service.is_ready(),
            "model_loaded": self.qwen_service.is_loaded,
            "model_name": self.qwen_service.model_name,
        }
