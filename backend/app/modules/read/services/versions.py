"""Upscaled / translated page versions — preview, accept, discard, remove. Request-scoped.

Every result is a **preview** first: written to `{user}/_preview/{page_id}-{kind}.png`
(overwritten by the next run) and returned for the user to look at. Accept moves it
to a final, uuid-named path next to the page's own file and records the version row;
discard deletes it. The original and reference images are only ever read.

Ownership is enforced here like `ReadService`: every page is resolved through
`ReadRepository.get_page(…, user_id)`, and a page that isn't the caller's is a 404.
The image work (decode, encode, the translate pipeline) is CPU-bound, so it runs in
the threadpool, off the event loop.
"""
from __future__ import annotations

import asyncio
import logging
import mimetypes
import uuid

import cv2
import numpy as np
from fastapi.concurrency import run_in_threadpool

from backend.app.modules.auth.schemas import CurrentUser
from backend.app.shared.images import UpscaleClient
from backend.app.shared.storage import StorageClient, StorageObjectNotFound
from ..repository import ReadRepository
from ..schemas import PageVersionInfo, VersionPreview
from ..translate import translate_by_reference
from .read import owns_path

logger = logging.getLogger(__name__)

_TRANSLATE_LANGUAGE = "en"  # translate-by-reference always targets English for now

_PAGE_NOT_FOUND = "Page not found"
_SAME_PAGE = "Pick a different page as the reference."
_UNREADABLE = "This page's image couldn't be read."


class VersionError(Exception):
    """A request the service refuses; the router returns `status` with `message` as detail."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


class PageVersionService:
    def __init__(
        self, repo: ReadRepository, user: CurrentUser, storage: StorageClient, upscaler: UpscaleClient
    ) -> None:
        self._repo = repo
        self._user_id = uuid.UUID(user.id)
        self._storage = storage
        self._upscaler = upscaler

    # --- previews --------------------------------------------------------

    async def upscale_preview(self, page_id: uuid.UUID) -> VersionPreview:
        """Upscale the **original** image (never an earlier upscale) into a preview."""
        page = await self._own_page(page_id)
        original = await self._storage.download(self._own_path(page.storage_path))
        png = await self._upscaler.upscale(original, _content_type(page.storage_path))
        width, height = await self._dims(png)
        path, url = await self._put_preview(page_id, "upscaled", png)
        return VersionPreview(kind="upscaled", preview_path=path, preview_url=url, width=width, height=height)

    async def translate_preview(self, page_id: uuid.UUID, reference_page_id: uuid.UUID) -> VersionPreview:
        """Copy the reference page's lettering onto the target, as a preview.

        Starts from the accepted upscale when there is one, as is. Otherwise from the
        original, upscaled first unless it's already at least as tall as the reference,
        so the reference's lettering is barely resized. `TranslateRefusal` propagates.
        """
        page = await self._own_page(page_id)
        if reference_page_id == page_id:
            raise VersionError(422, _SAME_PAGE)
        reference = await self._repo.get_page(reference_page_id, self._user_id)
        if reference is None or reference.section_id != page.section_id:
            raise VersionError(404, "Reference page not found in this section")

        upscaled = await self._repo.get_version(page_id, "upscaled", None)
        base_path = self._own_path(upscaled.storage_path if upscaled is not None else page.storage_path)
        ref_path = self._own_path(reference.storage_path)
        base_bytes, ref_bytes = await asyncio.gather(
            self._storage.download(base_path), self._storage.download(ref_path)
        )
        base, ref = await run_in_threadpool(_decode, base_bytes), await run_in_threadpool(_decode, ref_bytes)
        if upscaled is None and base.shape[0] < ref.shape[0]:
            upscaled_bytes = await self._upscaler.upscale(base_bytes, _content_type(base_path))
            base = await run_in_threadpool(_decode, upscaled_bytes)

        result = await run_in_threadpool(translate_by_reference, base, ref)
        png = await run_in_threadpool(_encode_png, result)
        path, url = await self._put_preview(page_id, "translated", png)
        return VersionPreview(
            kind="translated", language=_TRANSLATE_LANGUAGE, preview_path=path, preview_url=url,
            width=result.shape[1], height=result.shape[0], reference_page_id=reference_page_id,
        )

    # --- accept / discard / remove --------------------------------------------

    async def accept(
        self, page_id: uuid.UUID, kind: str, language: str | None, reference_page_id: uuid.UUID | None
    ) -> PageVersionInfo:
        """Keep the preview: move it to its final path, record it, drop what it replaces."""
        page = await self._own_page(page_id)
        language = _language(kind, language)
        if kind == "upscaled":
            reference_page_id = None
        elif reference_page_id is not None and await self._repo.get_page(reference_page_id, self._user_id) is None:
            raise VersionError(404, "Reference page not found")

        preview_path = self._preview_path(page_id, kind)
        try:
            data = await self._storage.download(preview_path)
        except StorageObjectNotFound:
            raise VersionError(404, "No preview to accept. Run it again.")
        width, height = await self._dims(data)

        section = await self._repo.get_section(page.section_id, self._user_id)
        final_path = f"{self._user_id}/{section.manga_id}/{section.id}/v-{uuid.uuid4()}.png"
        await self._storage.move(preview_path, final_path)
        try:
            version, replaced_path = await self._repo.upsert_version(
                page_id, kind, language, final_path, width, height, reference_page_id
            )
            await self._repo.commit()
        except Exception:
            await self._repo.rollback()
            await self._storage.remove([final_path])  # don't leave an unrecorded file behind
            raise
        if replaced_path:
            await self._remove_quietly(replaced_path)
        return PageVersionInfo.model_validate(version)

    async def discard(self, page_id: uuid.UUID, kind: str) -> None:
        """Delete the preview; already gone is fine."""
        await self._own_page(page_id)
        await self._storage.remove([self._preview_path(page_id, kind)])

    async def remove(self, page_id: uuid.UUID, kind: str, language: str | None) -> None:
        """Delete an accepted version and its file; the original stays."""
        await self._own_page(page_id)
        path = await self._repo.delete_version(page_id, kind, _language(kind, language))
        if path is None:
            raise VersionError(404, "Version not found")
        await self._repo.commit()
        await self._remove_quietly(path)

    # --- helpers --------------------------------------------------------

    async def _own_page(self, page_id: uuid.UUID):
        page = await self._repo.get_page(page_id, self._user_id)
        if page is None:
            raise VersionError(404, _PAGE_NOT_FOUND)
        return page

    def _own_path(self, storage_path: str) -> str:
        """Storage is read with the service role, so never trust a stored path blindly.

        RLS on the version/page rows checks page ownership, not where the path points;
        a path outside `{user_id}/` is treated as the page not existing (404).
        """
        if not owns_path(self._user_id, storage_path):
            logger.warning("Refusing %r: outside user %s's prefix", storage_path, self._user_id)
            raise VersionError(404, _PAGE_NOT_FOUND)
        return storage_path

    async def _remove_quietly(self, storage_path: str) -> None:
        """Delete a file after its row change has committed.

        A failure leaves an orphan file, not a failed request — the change is saved —
        and a path outside the user's prefix is skipped, never deleted.
        """
        if not owns_path(self._user_id, storage_path):
            logger.warning("Not removing %r: outside user %s's prefix", storage_path, self._user_id)
            return
        try:
            await self._storage.remove([storage_path])
        except Exception:
            logger.exception("Couldn't remove %r after commit; orphaned", storage_path)

    def _preview_path(self, page_id: uuid.UUID, kind: str) -> str:
        return f"{self._user_id}/_preview/{page_id}-{kind}.png"

    async def _put_preview(self, page_id: uuid.UUID, kind: str, png: bytes) -> tuple[str, str]:
        """Upload the preview; return its path and a freshly signed URL.

        The path is fixed per (page, kind) and the object is cached for a year, so a
        URL signed for an earlier preview would show stale bytes. Storage's token only
        changes once a second (two signings in the same second are identical), so a
        random `v` query parameter makes every returned URL a fresh cache key; Storage
        ignores it.
        """
        # Storage won't overwrite an existing object, so clear the last preview first.
        path = self._preview_path(page_id, kind)
        await self._storage.remove([path])
        await self._storage.upload(path, png, "image/png")
        (url,) = await self._storage.create_signed_urls([path])
        return path, f"{url}{'&' if '?' in url else '?'}v={uuid.uuid4().hex}"

    async def _dims(self, data: bytes) -> tuple[int, int]:
        img = await run_in_threadpool(_decode, data)
        return img.shape[1], img.shape[0]


def _language(kind: str, language: str | None) -> str | None:
    """Upscales have no language; translations default to English."""
    return None if kind == "upscaled" else (language or _TRANSLATE_LANGUAGE)


def _content_type(path: str) -> str:
    return mimetypes.guess_type(path)[0] or "application/octet-stream"


def _decode(data: bytes) -> np.ndarray:
    """Always 3-channel BGR — the pipeline can't mix grey and colour pages."""
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR) if data else None
    if img is None:
        raise VersionError(422, _UNREADABLE)
    return img


def _encode_png(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise RuntimeError("PNG encoding failed")
    return buf.tobytes()
