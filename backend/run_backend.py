"""Backend entrypoint for starting the FastAPI server."""
from backend.app.main import app
from backend.app.core.config import settings


def main() -> None:
    """Start the backend server with Uvicorn using .env settings."""
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
