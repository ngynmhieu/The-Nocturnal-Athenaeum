"""Upscale client — posts an image to the models service and returns the x2 PNG.

Thin and business-agnostic, like `LlmClient`: the model lives in the models service.
A down or failing service (connect error, timeout, any 5xx) is `UpscaleUnavailable`;
a 4xx means the request itself was bad (unreadable image) and is `UpscaleRejected`,
so callers can tell "try later" from "this image won't ever work".
"""
from __future__ import annotations

import httpx

_TIMEOUT = 120.0  # CPU upscaling of a full manga page is slow


class UpscaleUnavailable(Exception):
    """The models service is unreachable, timed out, or failed (5xx)."""


class UpscaleRejected(Exception):
    """The models service refused the image (4xx); the message is its `detail`."""


class UpscaleClient:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._transport: httpx.AsyncBaseTransport | None = None  # tests inject a mock

    async def upscale(self, image: bytes, content_type: str) -> bytes:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT, transport=self._transport) as http:
                response = await http.post(
                    f"{self._base_url}/images/upscale",
                    content=image,
                    headers={"content-type": content_type},
                )
        except httpx.HTTPError as exc:  # connect errors, timeouts, protocol errors
            raise UpscaleUnavailable(f"models service unreachable: {exc!r}") from exc

        if response.status_code >= 500:
            raise UpscaleUnavailable(f"models service error {response.status_code}: {_detail(response)}")
        if response.status_code >= 400:
            raise UpscaleRejected(_detail(response))
        return response.content


def _detail(response: httpx.Response) -> str:
    try:
        return str(response.json().get("detail", response.text))
    except Exception:
        return response.text
