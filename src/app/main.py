"""FastAPI application factory and configuration."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from .core.config import settings
from .llm.qwen_service import QwenService
from .services.chat_service import ChatService
from .api import agent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global instances
qwen_service: QwenService = None
chat_service: ChatService = None


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI app instance
    """
    app = FastAPI(
        title="Qwen Chat Server",
        description="FastAPI server for Qwen language model chat with streaming support",
        version="0.1.0",
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Startup event
    @app.on_event("startup")
    async def startup():
        """Initialize services on app startup."""
        global qwen_service, chat_service
        
        logger.info("Starting up Qwen Chat Server...")
        
        # Initialize Qwen service
        qwen_service = QwenService.get_instance()
        await qwen_service.load(
            model_name=settings.model_name,
            quantize=settings.quantize,
        )
        logger.info(f"Loaded model: {settings.model_name}")
        
        # Initialize chat service
        chat_service = ChatService(qwen_service)
        agent.set_chat_service(chat_service)
        logger.info("Chat service initialized")
    
    # Shutdown event
    @app.on_event("shutdown")
    async def shutdown():
        """Clean up resources on app shutdown."""
        global qwen_service, chat_service
        
        logger.info("Shutting down Qwen Chat Server...")
        
        if qwen_service:
            await qwen_service.close()
            logger.info("Model unloaded")
        
        qwen_service = None
        chat_service = None
    
    # Include routers
    app.include_router(agent.router)
    
    # Root endpoint
    @app.get("/")
    async def root():
        """Root endpoint - API info."""
        return {
            "name": "Qwen Chat Server",
            "version": "0.1.0",
            "docs_url": "/docs",
            "model": settings.model_name,
            "quantized": settings.quantize,
        }
    
    logger.info("FastAPI app configured")
    return app


# Create the app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level="info",
    )
