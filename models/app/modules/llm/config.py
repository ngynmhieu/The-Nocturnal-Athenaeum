"""Model configuration — loaded entirely from `models/*.json`.

Adding a model is just dropping a JSON file in `models/`; there's no code to
touch here. SamplingConfig mirrors a model's optional `sampling` block.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

MODELS_DIR = Path(__file__).resolve().parent / "models"

# Capability names a model may declare. Clients read these from GET /v1/models
# and adapt their surface, rather than hardcoding what a given model can do.
CHAT, THINKING, TOOLS, VISION = "chat", "thinking", "tools", "vision"

REASONING_EFFORTS = ("low", "medium", "xhigh")


@dataclass(frozen=True)
class SamplingConfig:
    """Decoding/sampling knobs, loaded from a model's `sampling` JSON block.

    Defaults follow Unsloth's Qwen3.8 thinking-mode recommendation. Unlike the
    transformers engine this replaced, presence_penalty is applied natively by
    llama.cpp — no custom logits processor needed.
    """
    temperature: float = 1.0
    top_p: float = 0.95
    top_k: int = 20
    min_p: float = 0.0
    presence_penalty: float = 0.0

    @classmethod
    def from_dict(cls, data: dict) -> "SamplingConfig":
        return cls(
            temperature=data.get("temperature", 1.0),
            top_p=data.get("top_p", 0.95),
            top_k=data.get("top_k", 20),
            min_p=data.get("min_p", 0.0),
            presence_penalty=data.get("presence_penalty", 0.0),
        )


@dataclass(frozen=True)
class ModelConfig:
    """One model's settings, loaded from its JSON file."""
    id: str
    hf_repo: str
    gguf_file: str
    # Vision projector. Omit to load the model text-only even if it supports images.
    mmproj_file: Optional[str] = None
    # -1 = offload every layer to the GPU. Lower it only when the weights plus KV
    # cache exceed VRAM: past that point the driver pages over PCIe, which is far
    # slower than honestly running the surplus layers on the CPU.
    n_gpu_layers: int = -1
    # Context window. llama.cpp allocates this KV cache up front, so it is a real
    # VRAM cost paid at load whether or not a conversation ever grows into it.
    n_ctx: int = 8192
    capabilities: List[str] = field(default_factory=lambda: [CHAT])
    max_new_tokens: int = 1024
    max_thinking_tokens: int = 1024
    # Natural-language nudge + </think> injected when the thinking budget is hit,
    # so an over-budget thought lands gracefully instead of being cut mid-word.
    thinking_budget_message: str = "\n\n</think>\n\n"
    # Qwen3.8 defaults to "xhigh", which produces long deliberate reasoning. On
    # consumer hardware that is a lot of tokens before the user sees an answer.
    default_reasoning_effort: Optional[str] = None
    sampling: Optional[SamplingConfig] = None
    description: str = ""
    default: bool = False

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities

    @property
    def supports_thinking(self) -> bool:
        return self.supports(THINKING)

    @classmethod
    def from_file(cls, path: Path) -> "ModelConfig":
        data = json.loads(path.read_text(encoding="utf-8"))
        effort = data.get("default_reasoning_effort")
        if effort is not None and effort not in REASONING_EFFORTS:
            raise ValueError(
                f"{path.name}: default_reasoning_effort must be one of "
                f"{REASONING_EFFORTS}, got {effort!r}"
            )
        return cls(
            id=data["id"],
            hf_repo=data["hf_repo"],
            gguf_file=data["gguf_file"],
            mmproj_file=data.get("mmproj_file"),
            n_gpu_layers=data.get("n_gpu_layers", -1),
            n_ctx=data.get("n_ctx", 8192),
            capabilities=list(data.get("capabilities", [CHAT])),
            max_new_tokens=data.get("max_new_tokens", 1024),
            max_thinking_tokens=data.get("max_thinking_tokens", 1024),
            thinking_budget_message=data.get(
                "thinking_budget_message", "\n\n</think>\n\n"),
            default_reasoning_effort=effort,
            sampling=SamplingConfig.from_dict(data["sampling"]) if "sampling" in data else None,
            description=data.get("description", ""),
            default=data.get("default", False),
        )


def load_catalog() -> Dict[str, ModelConfig]:
    """Read every models/*.json into a {id: ModelConfig} map."""
    configs = [ModelConfig.from_file(p) for p in sorted(MODELS_DIR.glob("*.json"))]
    return {c.id: c for c in configs}
