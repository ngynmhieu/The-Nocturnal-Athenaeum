"""Storage client — Supabase Storage access (service-role), shared across modules."""
from .client import StorageClient, StorageObjectNotFound

__all__ = ["StorageClient", "StorageObjectNotFound"]
