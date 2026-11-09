"""Image-processing clients — HTTP access to the models service's image endpoints."""
from .upscale_client import UpscaleClient, UpscaleRejected, UpscaleUnavailable

__all__ = ["UpscaleClient", "UpscaleRejected", "UpscaleUnavailable"]
