"""The `image` module — image-to-image models (Real-ESRGAN upscaler today).

Self-contained like `llm`: model configs (`models/*.json` + `config.py`), the
network (`network.py`), lifecycle + inference (`manager.py`), orchestration
(`service.py`), and routes (`router.py`).
"""
from .router import router

__all__ = ["router"]
