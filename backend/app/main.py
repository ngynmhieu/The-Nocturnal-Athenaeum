"""FastAPI application factory, lifespan, and module wiring (composition root)."""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client

from .core.config import settings
from .shared.llm import QwenService
from .modules.chat import router as chat_router
from .modules.chat.service import ChatService
from .modules.auth import router as auth_router
from .modules.auth.service import AuthService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the model and wire services on startup; tear down on shutdown."""
    logger.info("Starting up Qwen Chat Server...")

    qwen_service = QwenService.get_instance()
    await qwen_service.load(
        model_name=settings.model_name,
        quantize=settings.quantize,
    )

    app.state.qwen_service = qwen_service
    app.state.chat_service = ChatService(qwen_service)

    supabase_client = create_client(settings.supabase_url, settings.supabase_anon_key)
    app.state.auth_service = AuthService(supabase_client)

    logger.info("FastAPI app ready")
    yield

    logger.info("Shutting down Qwen Chat Server...")
    await qwen_service.close()
    app.state.qwen_service = None
    app.state.chat_service = None
    app.state.auth_service = None


def create_app() -> FastAPI:
    app = FastAPI(
        title="Qwen Chat Server",
        description="FastAPI server for Qwen language model chat with streaming support",
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

    app.include_router(chat_router)
    app.include_router(auth_router)

    @app.get("/")
    async def root():
        return {
            "name": "Qwen Chat Server",
            "version": "0.1.0",
            "docs_url": "/docs",
            "model": settings.model_name,
            "quantized": settings.quantize,
        }

    logger.info("FastAPI app configured")
    return app


app = create_app()
