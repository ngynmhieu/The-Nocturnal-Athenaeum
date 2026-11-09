"""User-facing refusal for the translate-by-reference pipeline.

A refusal is not a bug: it means the pipeline looked at the pages and decided the
result would be wrong, so it says so instead of producing a bad page. `message` is
shown to the user as-is.
"""
from __future__ import annotations


class TranslateRefusal(Exception):
    """The pipeline declined to translate; `message` is safe to show the user."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
