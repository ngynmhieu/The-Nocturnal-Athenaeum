"""OpenAI-compatible request shapes (format only — the model is Qwen, run locally)."""
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    # `protected_namespaces=()` silences pydantic's warning about the `model` field.
    model_config = ConfigDict(protected_namespaces=())

    model: str
    messages: List[ChatMessage]
    max_tokens: Optional[int] = None
    stream: bool = False

    # Model-specific knobs. These are declared rather than accepted as loose extras:
    # the manager takes explicit keyword arguments, so an unrecognised field must be
    # rejected here instead of being silently dropped on the way down.
    enable_thinking: Optional[bool] = None
    reasoning_effort: Optional[Literal["low", "medium", "xhigh"]] = None

    def options(self) -> dict:
        """Recognised passthrough params, omitting any the caller left unset so the
        model's own JSON defaults apply."""
        opts = {
            "enable_thinking": self.enable_thinking,
            "reasoning_effort": self.reasoning_effort,
        }
        return {k: v for k, v in opts.items() if v is not None}
