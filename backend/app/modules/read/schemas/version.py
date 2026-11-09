"""Page-version shapes — translate/accept requests + the preview response.

The accepted version itself is `PageVersionInfo` (in `page.py`, since it rides on
`PageInfo`); these are only the preview → accept round-trip.
"""
import uuid
from typing import Literal

from pydantic import BaseModel

VersionKind = Literal["upscaled", "translated"]


# --- requests (client → backend) -------------------------------------------

class TranslateRequest(BaseModel):
    """Body for `POST /read/pages/{id}/translate` — the page whose lettering to copy."""
    reference_page_id: uuid.UUID


class AcceptVersionRequest(BaseModel):
    """Body for `POST /read/pages/{id}/versions/accept` — which preview to keep.

    `language` defaults to `"en"` for a translation and is ignored for an upscale,
    as is `reference_page_id`.
    """
    kind: VersionKind
    language: str | None = None
    reference_page_id: uuid.UUID | None = None


# --- responses (backend → client) ------------------------------------------

class VersionPreview(BaseModel):
    """A not-yet-accepted result, stored at `preview_path`.

    Show it via `preview_url`, signed fresh for every preview: the path is reused by
    the next preview of the same page, so a URL signed from the path earlier (and
    cached) would show the old image.
    """
    kind: VersionKind
    language: str | None = None
    preview_path: str
    preview_url: str
    width: int
    height: int
    reference_page_id: uuid.UUID | None = None
