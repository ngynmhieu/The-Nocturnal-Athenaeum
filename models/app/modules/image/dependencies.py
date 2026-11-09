"""FastAPI dependency providers for the image module."""
from .manager import manager
from .service import ImageService

_service = ImageService(manager)


def get_image_service() -> ImageService:
    return _service
