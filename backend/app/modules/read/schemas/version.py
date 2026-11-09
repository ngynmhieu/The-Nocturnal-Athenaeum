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
    """A not-yet-accepted result, stored at `preview_path` (sign it to show it)."""
    kind: VersionKind
    language: str | None = None
    preview_path: str
    width: int
    height: int
    reference_page_id: uuid.UUID | None = None
