import httpx
import pytest

from backend.app.shared.images.upscale_client import UpscaleClient, UpscaleRejected, UpscaleUnavailable


def _client(handler) -> UpscaleClient:
    client = UpscaleClient("http://models.test/v1")
    client._transport = httpx.MockTransport(handler)
    return client


async def test_upscale_unreachable_raises_unavailable():
    client = UpscaleClient("http://127.0.0.1:9/v1")  # nothing listens on port 9
    with pytest.raises(UpscaleUnavailable):
        await client.upscale(b"\x89PNG...", "image/png")


async def test_upscale_posts_bytes_and_returns_png():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["type"], seen["body"] = str(request.url), request.headers["content-type"], request.content
        return httpx.Response(200, content=b"PNGDATA", headers={"content-type": "image/png"})

    assert await _client(handler).upscale(b"raw", "image/jpeg") == b"PNGDATA"
    assert seen == {"url": "http://models.test/v1/images/upscale", "type": "image/jpeg", "body": b"raw"}


@pytest.mark.parametrize("status", [500, 503])
async def test_upscale_5xx_raises_unavailable(status):
    client = _client(lambda request: httpx.Response(status, json={"detail": "no weights"}))
    with pytest.raises(UpscaleUnavailable):
        await client.upscale(b"raw", "image/png")


async def test_upscale_4xx_raises_rejected_with_detail():
    client = _client(lambda request: httpx.Response(400, json={"detail": "unreadable image"}))
    with pytest.raises(UpscaleRejected, match="unreadable image"):
        await client.upscale(b"raw", "image/png")
