"""Image service: bytes in, bytes out. Keeps the router thin."""
import cv2
import numpy as np

from .manager import UpscalerManager


class ImageService:
    def __init__(self, manager: UpscalerManager):
        self._manager = manager

    def upscale_bytes(self, data: bytes, model: str | None) -> bytes:
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Not a readable image.")
        out = self._manager.upscale(model, img)
        ok, buf = cv2.imencode(".png", out)
        if not ok:
            raise ValueError("Could not encode the upscaled image.")
        return buf.tobytes()
