"""Entry point for starting the Qwen FastAPI server."""
from src.app.main import app
from src.app.core.config import settings


def main() -> None:
    """Start the FastAPI server with uvicorn."""
    import uvicorn

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
