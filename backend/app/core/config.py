"""Configuration loader for the Qwen chat server."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from backend/.env.backend file
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env.backend")


class Settings:
    """Application settings loaded from environment variables."""

    # Model configuration
    model_name: str = os.getenv("MODEL_NAME", "Qwen/Qwen3-14B")
    quantize: bool = os.getenv("QUANTIZE", "false").lower() in ("true", "1", "yes")
    max_tokens: int = int(os.getenv("MAX_TOKENS", "1024"))

    # HuggingFace configuration
    hf_token: str = os.getenv("HF_TOKEN", "")

    # Server configuration
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    debug: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

    # Database configuration (Supabase Postgres — async driver)
    database_url: str = os.getenv("DATABASE_URL", "")

    # Supabase Auth — used to verify JWTs and read the user behind a token
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_anon_key: str = os.getenv("SUPABASE_ANON_KEY", "")


settings = Settings()
