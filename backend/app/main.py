"""FastAPI application factory, lifespan, and module wiring (composition root)."""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client

from .core.config import settings
from .shared.images import UpscaleClient
from .shared.llm import LlmClient
from .shared.storage import StorageClient
from .modules.chat import router as chat_router
from .modules.chat.services import ModelService
from .modules.auth import router as auth_router
from .modules.auth.service import AuthService
from .modules.read import router as read_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Wire services on startup; tear down on shutdown.

    The model is NOT loaded here — it runs in the standalone models service. The
    backend only builds a thin HTTP client to it, so startup is instant.
    """
    logger.info("Starting up backend...")

    llm_client = LlmClient(
        base_url=settings.models_service_url,
        model=settings.model_name,
        api_key=settings.models_service_api_key,
    )
    # llm_client is shared: ModelService holds it directly; the request-scoped
    # ChatService pulls it from app.state per request.
    app.state.llm_client = llm_client
    app.state.model_service = ModelService(llm_client)

    supabase_client = create_client(settings.supabase_url, settings.supabase_anon_key)
    app.state.auth_service = AuthService(supabase_client)

    # Service-role client for the read module's scrape-import path (server-side
    # download -> upload) — bypasses Storage RLS, so it is never exposed to the frontend.
    app.state.storage_client = StorageClient.create(
        settings.supabase_url, settings.supabase_service_role_key, settings.manga_bucket
    )

    # Upscale requests go to the same models service as chat.
    app.state.upscale_client = UpscaleClient(settings.models_service_url)

    logger.info("FastAPI app ready")
    yield

    logger.info("Shutting down backend...")
    app.state.model_service = None
    app.state.auth_service = None
    app.state.llm_client = None
    app.state.storage_client = None
    app.state.upscale_client = None


def create_app() -> FastAPI:
    app = FastAPI(
        title="Qwen Chat Server",
        description="FastAPI backend; LLM inference is delegated to the models service",
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
    app.include_router(read_router)

    @app.get("/")
    async def root():
        return {
            "name": "Qwen Chat Server",
            "version": "0.1.0",
            "docs_url": "/docs",
            "model": settings.model_name,
            "models_service": settings.models_service_url,
        }

    logger.info("FastAPI app configured")
    return app


app = create_app()
