"""Shapes shared by every per-site extractor."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


class ExtractorError(Exception):
    """A per-site extractor couldn't produce a result — the message is user-facing."""


@dataclass
class SeriesEntry:
    """One volume/chapter listed on a series page — `url` is what `scrape()` takes."""
    kind: Literal["volume", "chapter"]
    number: float | None
    title: str | None
    url: str
