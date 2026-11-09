"""Upscaler configuration — loaded entirely from `models/*.json`.

Adding an upscaler of the same architecture is just dropping a JSON file in
`models/`; there's no code to touch here.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

MODELS_DIR = Path(__file__).resolve().parent / "models"


@dataclass(frozen=True)
class UpscalerConfig:
    """One upscaler's settings, loaded from its JSON file."""
    id: str
    weights_url: str
    # Pinned digest of the weights file; checked before torch.load.
    sha256: str
    # Scale the network natively produces.
    net_scale: int = 4
    # Scale actually returned; the net output is downscaled (INTER_AREA) to it.
    output_scale: int = 2
    num_feat: int = 64
    num_conv: int = 16
    # CPU by default: the GPU is held by the LLM, and this net is small.
    device: str = "cpu"
    # Tile edge in px; 0 = run the whole image in one pass.
    tile: int = 0
    description: str = ""
    default: bool = False

    @classmethod
    def from_file(cls, path: Path) -> "UpscalerConfig":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            id=data["id"],
            weights_url=data["weights_url"],
            sha256=data["sha256"],
            net_scale=data.get("net_scale", 4),
            output_scale=data.get("output_scale", 2),
            num_feat=data.get("num_feat", 64),
            num_conv=data.get("num_conv", 16),
            device=data.get("device", "cpu"),
            tile=data.get("tile", 0),
            description=data.get("description", ""),
            default=data.get("default", False),
        )


def load_configs() -> Dict[str, UpscalerConfig]:
    """Read every models/*.json into a {id: UpscalerConfig} map."""
    configs = [UpscalerConfig.from_file(p) for p in sorted(MODELS_DIR.glob("*.json"))]
    return {c.id: c for c in configs}
