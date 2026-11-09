"""Service layer for the read module — one scope per file, exposed here.

Three distinct responsibilities, deliberately kept as separate instances:

- ReadService (read.py) — CRUD over mangas/sections/pages, reorder, and the
  library pool (list/record/organize/discard). Request-scoped.
- ScrapeService (scrape.py) — fetch+extract candidates from a page, then import
  chosen ones (download server-side, upload to Storage) into a section or the
  pool. Request-scoped.
- PageVersionService (versions.py) — upscaled/translated versions of a page:
  preview, accept, discard, remove. Request-scoped.

This __init__ is the package's public contract; import services from here, not
from the individual modules.
"""
from .read import ReadService
from .scrape import ScrapeService
from .versions import PageVersionService, VersionError

__all__ = ["PageVersionService", "ReadService", "ScrapeService", "VersionError"]
