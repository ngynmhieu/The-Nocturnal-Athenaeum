"""FastAPI application factory, lifespan, and module wiring (composition root).

"OpenAI-compatible" refers to the API format only; the model is Qwen, run locally.
"""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .modules.llm import router as llm_router
from .modules.llm.manager import manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the default model on startup; unload on shutdown."""
    logger.info("Starting up Models Service...")

    model_id = manager.default_id()
    if model_id:
        logger.info("Loading default model '%s'...", model_id)
        manager.ensure(model_id)
        # Pay the one-time CUDA kernel JIT here rather than on the first request.
        manager.warmup()
        logger.info("Model '%s' ready.", model_id)
    else:
        logger.warning("No models found in app/modules/llm/models/.")

    logger.info("FastAPI app ready")
    yield

    logger.info("Shutting down Models Service...")
    manager.unload()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Models Service",
        description="Hosts local models behind an OpenAI-compatible API.",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(llm_router)

    @app.get("/")
    async def root():
        return {
            "name": "Models Service",
            "version": "0.1.0",
            "docs_url": "/docs",
            "loaded_model": manager.current_model_id,
        }

    logger.info("FastAPI app configured")
    return app


app = create_app()
