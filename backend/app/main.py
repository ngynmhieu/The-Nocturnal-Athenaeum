"""FastAPI application factory and configuration."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from .core.config import settings
from .llm.qwen_service import QwenService
from .services.chat_service import ChatService
from .api import agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

qwen_service: QwenService = None
chat_service: ChatService = None


def create_app() -> FastAPI:
    app = FastAPI(
        title="Qwen Chat Server",
        description="FastAPI server for Qwen language model chat with streaming support",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def startup():
        global qwen_service, chat_service

        logger.info("Starting up Qwen Chat Server...")

        qwen_service = QwenService.get_instance()
        await qwen_service.load(
            model_name=settings.model_name,
            quantize=settings.quantize,
        )

        chat_service = ChatService(qwen_service)
        agent.set_chat_service(chat_service)

    @app.on_event("shutdown")
    async def shutdown():
        global qwen_service, chat_service

        logger.info("Shutting down Qwen Chat Server...")

        if qwen_service:
            await qwen_service.close()

        qwen_service = None
        chat_service = None

    app.include_router(agent.router)

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
