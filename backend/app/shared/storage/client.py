"""Storage client — a thin wrapper around Supabase Storage for one bucket.

Built once during the app lifespan with the **service-role** key (bypasses Storage
RLS, so it may write under any user's prefix on their behalf — used only for the
`read` module's scrape-import path, which is the one place bytes flow through the
backend). `storage3`'s client is synchronous, so every call runs in a threadpool to
avoid blocking the event loop (same pattern as `AuthService.verify`).
"""
from __future__ import annotations

import httpx
from fastapi.concurrency import run_in_threadpool
from storage3.exceptions import StorageApiError
from supabase import Client, ClientOptions, create_client


class StorageObjectNotFound(Exception):
    """The requested object doesn't exist in the bucket."""


class StorageClient:
    """Upload/remove/sign objects in one Supabase Storage bucket."""

    def __init__(self, supabase: Client, bucket: str) -> None:
        self._bucket = supabase.storage.from_(bucket)

    @classmethod
    def create(cls, url: str, service_role_key: str, bucket: str) -> "StorageClient":
        # storage3's default client negotiates HTTP/2, multiplexing every request
        # over one shared connection. The read module's scrape-import runs several
        # uploads concurrently (each in its own threadpool worker via `upload`
        # below), and concurrent threads racing on that one multiplexed socket
        # raises WinError 10035 (non-blocking recv) on Windows. Plain HTTP/1.1
        # instead opens one pooled connection per concurrent request.
        http_client = httpx.Client(http2=False)
        options = ClientOptions(httpx_client=http_client)
        return cls(create_client(url, service_role_key, options), bucket)

    async def upload(self, path: str, data: bytes, content_type: str | None = None) -> None:
        # Paths embed a fresh UUID and are never rewritten (immutable content),
        # so let browsers/CDN cache the object for a year instead of the 1h default.
        file_options = {"cache-control": "31536000"}
        if content_type:
            file_options["content-type"] = content_type
        await run_in_threadpool(self._bucket.upload, path, data, file_options)

    async def remove(self, paths: list[str]) -> None:
        if not paths:
            return
        await run_in_threadpool(self._bucket.remove, paths)

    async def download(self, path: str) -> bytes:
        try:
            return await run_in_threadpool(self._bucket.download, path)
        except StorageApiError as exc:
            if _is_not_found(exc):
                raise StorageObjectNotFound(path) from exc
            raise

    async def move(self, src: str, dst: str) -> None:
        await run_in_threadpool(self._bucket.move, src, dst)

    async def create_signed_urls(self, paths: list[str], expires_in: int = 3600) -> list[str]:
        if not paths:
            return []
        responses = await run_in_threadpool(self._bucket.create_signed_urls, paths, expires_in)
        return [response["signedURL"] for response in responses]


def _is_not_found(exc: StorageApiError) -> bool:
    # Storage reports a missing object as `{"statusCode": "404", "error": "not_found"}`
    # inside an HTTP 400 or 404, depending on the server version.
    return str(exc.status) == "404" or str(exc.code).lower() in ("not_found", "nosuchkey")
