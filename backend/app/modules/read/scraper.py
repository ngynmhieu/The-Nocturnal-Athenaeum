"""Fetch a page URL, extract its candidate images, and download a chosen one's bytes.

Extracted component of the `read` module (see `backend/docs/modules/read.md` ->
scraper.py). Two stages, matching how `ScrapeService` uses it: `scrape()` (one page
fetch, plus any HTMX image fragments) returns candidates for the user to pick from;
`download_image()` fetches one chosen URL's bytes for the service to upload to
Storage. Knows nothing about Storage or the database — that's the service's job.

Responsible-use note: only import images you are authorized to copy. This
component is a generic extractor — it adds no anti-bot evasion, CAPTCHA
bypass, or rate-limit circumvention, and respecting a site's ToS/robots.txt is
the caller's responsibility.
"""
from __future__ import annotations

import html as html_lib
import logging
import re
from dataclasses import dataclass
from urllib.parse import urlencode, urljoin

import httpx
from selectolax.lexbor import LexborHTMLParser

logger = logging.getLogger(__name__)

# A real browser UA: bot-looking UAs trip Cloudflare and some image CDNs.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 20.0

# Some HTMX readers require an include param they keep only in client-side (Alpine)
# state, so it never appears as a form input we can read. We can't recover the
# user's choice, so send a sensible default keyed by param name. Without it the
# server typically returns a soft-400 fragment (so the page list looks empty).
HX_INCLUDE_DEFAULTS = {"reading_style": "long_strip"}

# `hx-include="[name='foo']"` -> the names whose form values HTMX would attach.
_HX_INCLUDE_NAME_RE = re.compile(r"\[name=['\"]?([\w-]+)['\"]?\]")

# Attributes a lazy-loader may hide the real URL behind (best first); `src` is the
# fallback, and is often a 1px placeholder until JS swaps in one of the above.
LAZY_ATTRS = (
    "data-src",
    "data-original",
    "data-lazy-src",
    "data-lazy",
    "data-url",
    "data-image",
    "data-cfsrc",  # Cloudflare Rocket Loader
    "data-echo",
    "data-original-src",
    "src",
)
SRCSET_ATTRS = ("data-srcset", "srcset")

# A bare image URL, used to mine inline <script> bodies. Slashes inside JSON/JS
# payloads are commonly escaped (`https:\/\/...`); callers normalize before matching.
IMAGE_URL_RE = re.compile(
    r"https?://[^\s\"'\\<>]+?\.(?:jpe?g|png|webp|gif|avif|bmp)(?:\?[^\s\"'\\<>]*)?",
    re.IGNORECASE,
)


@dataclass
class ImageCandidate:
    url: str
    width: int | None = None
    height: int | None = None


def _candidate_attrs(node) -> list[str]:
    """Lazy-loaders publish the real URL under various attributes; src is the fallback."""
    for attr in LAZY_ATTRS:
        value = node.attributes.get(attr)
        if value:
            return [value]
    for attr in SRCSET_ATTRS:
        srcset = node.attributes.get(attr)
        if srcset:
            # "url1 1x, url2 2x" -> take the first; good enough for a generic extractor.
            first = srcset.split(",")[0].strip().split(" ")[0]
            if first:
                return [first]
    return []


def _urls_from_scripts(tree) -> list[str]:
    """Mine inline `<script>` bodies for image URLs.

    Manga readers commonly build the page client-side, embedding the ordered page
    list as a JSON/JS array (e.g. `ts_reader.run({"sources":[{"images":[...]}]})`).
    Those URLs never appear as parseable `<img>` tags in the fetched HTML. Slashes
    are usually escaped inside such payloads, so normalize `\\/` -> `/` first.
    """
    urls: list[str] = []
    for node in tree.css("script"):
        text = node.text(deep=False)
        if not text or "http" not in text:
            continue
        for match in IMAGE_URL_RE.finditer(text.replace("\\/", "/")):
            urls.append(match.group(0))
    return urls


def _urls_from_raw_html(html: str) -> list[str]:
    """Last-resort scan of the whole document for image URLs.

    Some apps (e.g. Inertia.js) embed the image list as JSON inside an HTML
    *attribute* (`data-page="..."`), not in `<img>` tags or `<script>` bodies, so
    the structured passes miss it. We unescape HTML entities (`&quot;` etc.) and
    JSON slash-escapes first, then match. Used only as a fallback because matching
    raw text also pulls in incidental images (avatars, thumbnails, og:image).
    """
    text = html_lib.unescape(html).replace("\\/", "/")
    return [match.group(0) for match in IMAGE_URL_RE.finditer(text)]


def _parse_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def extract_image_candidates(html: str, base_url: str) -> list[ImageCandidate]:
    """Extract absolute, deduped image candidates from a page, in document order.

    Covers the three ways a page publishes images: plain/lazy-loaded `<img>` and
    `<picture><source>` tags, then image lists embedded as JSON/JS in inline
    `<script>` tags (common on readers that build the page client-side, where the
    `<img>` tags hold only placeholders). As a last resort, when none of those find
    anything, scans the raw HTML for image URLs embedded in attributes (Inertia.js
    `data-page` JSON and similar).
    """
    tree = LexborHTMLParser(html)
    seen: set[str] = set()
    candidates: list[ImageCandidate] = []

    def add(raw: str, width: int | None = None, height: int | None = None) -> None:
        absolute = urljoin(base_url, raw.strip())
        if absolute in seen or not absolute.startswith(("http://", "https://")):
            return
        seen.add(absolute)
        candidates.append(ImageCandidate(url=absolute, width=width, height=height))

    for node in tree.css("img, source"):
        raws = _candidate_attrs(node)
        if raws:
            add(
                raws[0],
                width=_parse_int(node.attributes.get("width")),
                height=_parse_int(node.attributes.get("height")),
            )

    for raw in _urls_from_scripts(tree):
        add(raw)

    if not candidates:  # friendly site, but URLs hide in an HTML attribute (Inertia, etc.)
        for raw in _urls_from_raw_html(html):
            add(raw)

    return candidates


def _hx_include_params(tree, node) -> dict[str, str]:
    """Resolve the form values an `hx-include` selector would attach to the request.

    Handles the `[name='x']` selector form (what readers use); for a name with no
    matching input in the document, falls back to `HX_INCLUDE_DEFAULTS`.
    """
    params: dict[str, str] = {}
    for name in _HX_INCLUDE_NAME_RE.findall(node.attributes.get("hx-include") or ""):
        el = tree.css_first(f"[name='{name}']")
        value = el.attributes.get("value") if el else None
        if value is None:
            value = HX_INCLUDE_DEFAULTS.get(name)
        if value is not None:
            params[name] = value
    return params


def _htmx_image_fragments(html: str, base_url: str) -> list[str]:
    """Find auto-loading HTMX fragments that fetch the page images.

    Readers like WeebCentral leave the chapter page imageless and pull the page
    list from a separate `hx-get` endpoint fired on `load`. We follow only
    image-looking endpoints (not comments/nav) and replicate the `hx-include`
    params, since the endpoint 400s without them.
    """
    tree = LexborHTMLParser(html)
    fragments: list[str] = []
    for node in tree.css("[hx-get]"):
        target = node.attributes.get("hx-get")
        trigger = node.attributes.get("hx-trigger") or ""
        if not target or "load" not in trigger or "image" not in target.lower():
            continue
        absolute = urljoin(base_url, target)
        params = _hx_include_params(tree, node)
        if params:
            absolute += ("&" if "?" in absolute else "?") + urlencode(params)
        fragments.append(absolute)
    return fragments


async def fetch_page(
    client: httpx.AsyncClient, url: str, *, hx: bool = False, referer: str | None = None
) -> str:
    headers: dict[str, str] = {}
    if hx:  # make the request look like an HTMX-issued one, or the server may 400
        headers["HX-Request"] = "true"
    if referer:
        headers["Referer"] = referer
        headers["HX-Current-URL"] = referer
    response = await client.get(url, headers=headers, follow_redirects=True)
    response.raise_for_status()
    return response.text


async def scrape(url: str) -> list[ImageCandidate]:
    """Fetch `url` and return its image candidates. The network-facing entry point.

    A direct image link is returned as its own single candidate.

    Static images come straight from the page; for client-rendered readers it also
    follows the page's HTMX lazy-load fragments (reusing the same session) and
    merges their images, deduping by URL while preserving order.
    """
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT
    ) as client:
        # Referer = the URL itself: harmless for a page, and what an image host's
        # hotlink rule wants when the link is a direct image ("Copy image address").
        response = await client.get(url, headers={"Referer": url}, follow_redirects=True)
        response.raise_for_status()
        if (response.headers.get("content-type") or "").startswith("image/"):
            return [ImageCandidate(url=url)]
        html = response.text
        candidates = extract_image_candidates(html, base_url=url)

        for fragment_url in _htmx_image_fragments(html, url):
            try:
                fragment = await fetch_page(client, fragment_url, hx=True, referer=url)
            except httpx.HTTPError as exc:
                logger.warning("skip hx fragment %s: %s", fragment_url, exc)
                continue
            candidates.extend(extract_image_candidates(fragment, base_url=fragment_url))

    seen: set[str] = set()
    deduped: list[ImageCandidate] = []
    for candidate in candidates:
        if candidate.url not in seen:
            seen.add(candidate.url)
            deduped.append(candidate)
    return deduped


async def download_image(
    client: httpx.AsyncClient, url: str, referer: str | None = None
) -> tuple[bytes, str | None]:
    """Download one candidate's bytes for the caller to upload to Storage.

    Returns (content, content_type). Raises `httpx.HTTPError` on failure — the
    caller decides whether to skip or abort the batch.
    """
    headers = {"User-Agent": USER_AGENT}
    if referer:
        headers["Referer"] = referer  # some sites hotlink-protect on this header
    response = await client.get(url, headers=headers, follow_redirects=True)
    response.raise_for_status()
    return response.content, response.headers.get("content-type")
