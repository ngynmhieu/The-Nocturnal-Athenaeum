"""LLM engine — startup-lifecycle model singleton, shared infrastructure."""
from .qwen_service import QwenService

__all__ = ["QwenService"]
