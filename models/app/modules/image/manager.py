"""Upscaler lifecycle and inference.

Weights are fetched on first use (not at startup — the upscaler is cheap and
rarely needed), verified against the pinned sha256 *before* torch.load, and then
kept resident. Output is the net's native scale downsampled with INTER_AREA to
the configured output scale, which is crisper than a straight x2 net would be.
"""
from __future__ import annotations

import hashlib
import logging
import os
import threading
from pathlib import Path
from typing import Dict, Optional

import cv2
import httpx
import numpy as np
import torch

from .config import UpscalerConfig, load_configs
from .network import SRVGGNetCompact

logger = logging.getLogger(__name__)


def cache_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) if base else Path.home() / ".cache"
    return root / "nocturnal-models" / "image"


def verify_weights(path: Path, sha256: str) -> None:
    """Raise ValueError unless the file's SHA-256 equals `sha256`."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    if h.hexdigest() != sha256.lower():
        raise ValueError(f"sha256 mismatch for {path.name}: expected {sha256}, got {h.hexdigest()}")


class UpscalerManager:
    def __init__(self, configs: Dict[str, UpscalerConfig]):
        self._configs = configs
        self._nets: Dict[str, torch.nn.Module] = {}
        self._lock = threading.Lock()

    def default_id(self) -> Optional[str]:
        for c in self._configs.values():
            if c.default:
                return c.id
        return next(iter(self._configs), None)

    def _resolve(self, model_id: Optional[str]) -> UpscalerConfig:
        mid = model_id or self.default_id()
        if mid not in self._configs:
            raise ValueError(f"Unknown upscaler model '{mid}'.")
        return self._configs[mid]

    def _fetch_weights(self, cfg: UpscalerConfig) -> Path:
        path = cache_dir() / f"{cfg.id}.pth"
        if path.exists():
            try:
                verify_weights(path, cfg.sha256)
                return path
            except ValueError:
                logger.warning("Cached weights for '%s' failed verification; re-downloading.", cfg.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        logger.info("Downloading %s ...", cfg.weights_url)
        with httpx.stream("GET", cfg.weights_url, follow_redirects=True, timeout=120) as r:
            r.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)
        try:
            verify_weights(tmp, cfg.sha256)
        except ValueError:
            tmp.unlink(missing_ok=True)
            raise
        tmp.replace(path)
        return path

    def _load(self, cfg: UpscalerConfig) -> torch.nn.Module:
        path = self._fetch_weights(cfg)
        state = torch.load(path, map_location="cpu", weights_only=True)
        if "params" in state:
            state = state["params"]
        net = SRVGGNetCompact(cfg.num_feat, cfg.num_conv, cfg.net_scale)
        net.load_state_dict(state, strict=True)
        return net.eval().to(cfg.device)

    def upscale(self, model_id: Optional[str], image_bgr: np.ndarray) -> np.ndarray:
        """uint8 BGR (h, w, 3) -> uint8 BGR (h*output_scale, w*output_scale, 3)."""
        cfg = self._resolve(model_id)
        with self._lock:
            if cfg.id not in self._nets:
                self._nets[cfg.id] = self._load(cfg)
            net = self._nets[cfg.id]
            rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            x = torch.from_numpy(rgb).permute(2, 0, 1).float().div(255.0).unsqueeze(0).to(cfg.device)
            with torch.inference_mode():
                y = self._run(net, x, cfg)
            out = y.squeeze(0).clamp(0, 1).mul(255.0).round().byte().permute(1, 2, 0).cpu().numpy()
        h, w = image_bgr.shape[:2]
        size = (w * cfg.output_scale, h * cfg.output_scale)
        out = cv2.resize(np.ascontiguousarray(out), size, interpolation=cv2.INTER_AREA)
        return cv2.cvtColor(out, cv2.COLOR_RGB2BGR)

    @staticmethod
    def _run(net: torch.nn.Module, x: torch.Tensor, cfg: UpscalerConfig) -> torch.Tensor:
        t = cfg.tile
        _, _, h, w = x.shape
        if not t or (h <= t and w <= t):
            return net(x)
        # Tiled: run overlapping tiles and crop the margin, so seams don't show.
        pad, s = 10, cfg.net_scale
        out = x.new_zeros((1, 3, h * s, w * s))
        for y0 in range(0, h, t):
            for x0 in range(0, w, t):
                y1, x1 = min(y0 + t, h), min(x0 + t, w)
                ya, xa = max(y0 - pad, 0), max(x0 - pad, 0)
                yb, xb = min(y1 + pad, h), min(x1 + pad, w)
                tile = net(x[:, :, ya:yb, xa:xb])
                out[:, :, y0 * s:y1 * s, x0 * s:x1 * s] = tile[
                    :, :, (y0 - ya) * s:(y1 - ya) * s, (x0 - xa) * s:(x1 - xa) * s]
        return out


manager = UpscalerManager(load_configs())
