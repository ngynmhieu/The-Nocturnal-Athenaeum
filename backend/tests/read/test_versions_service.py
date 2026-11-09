"""PageVersionService — preview / accept / discard / remove, against in-memory fakes.

The repository, Storage and upscaler are fakes; the translate pipeline is the real
one, run on the synthetic pair from `conftest.make_pair`.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from backend.app.modules.auth.schemas import CurrentUser
from backend.app.modules.read.services import PageVersionService, VersionError
from backend.app.shared.images import UpscaleUnavailable
from backend.app.shared.storage import StorageObjectNotFound

from .conftest import make_pair


def _png(img: np.ndarray) -> bytes:
    return cv2.imencode(".png", img)[1].tobytes()


def _dims(data: bytes) -> tuple[int, int]:
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    return img.shape[1], img.shape[0]


# --- fakes ----------------------------------------------------------------

class FakeStorage:
    """Like Supabase Storage: upload never overwrites, remove ignores missing paths."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.removed: list[str] = []

    async def upload(self, path: str, data: bytes, content_type: str | None = None) -> None:
        if path in self.objects:
            raise RuntimeError(f"duplicate: {path}")
        self.objects[path] = data

    async def remove(self, paths: list[str]) -> None:
        for path in paths:
            if self.objects.pop(path, None) is not None:
                self.removed.append(path)

    async def download(self, path: str) -> bytes:
        if path not in self.objects:
            raise StorageObjectNotFound(path)
        return self.objects[path]

    async def move(self, src: str, dst: str) -> None:
        if src not in self.objects:
            raise StorageObjectNotFound(src)
        self.objects[dst] = self.objects.pop(src)


class FakeUpscaler:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.down = False

    async def upscale(self, image: bytes, content_type: str) -> bytes:
        self.calls.append(content_type)
        if self.down:
            raise UpscaleUnavailable("down")
        img = cv2.imdecode(np.frombuffer(image, np.uint8), cv2.IMREAD_COLOR)
        # Nearest, not cubic: smoothing closes the 1 px gaps between the fixture's
        # "AAAA" glyphs, and one merged blob is too big to count as letters.
        return _png(cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST))


class FakeRepo:
    def __init__(self, user_id: uuid.UUID) -> None:
        self.user_id = user_id
        self.sections: dict[uuid.UUID, SimpleNamespace] = {}
        self.pages: dict[uuid.UUID, SimpleNamespace] = {}
        self.versions: dict[tuple, SimpleNamespace] = {}
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        pass

    async def get_page(self, page_id, user_id):
        return self.pages.get(page_id) if user_id == self.user_id else None

    async def get_section(self, section_id, user_id):
        return self.sections.get(section_id) if user_id == self.user_id else None

    async def get_version(self, page_id, kind, language):
        return self.versions.get((page_id, kind, language))

    async def upsert_version(self, page_id, kind, language, storage_path, width, height, reference_page_id):
        old = self.versions.get((page_id, kind, language))
        row = SimpleNamespace(
            id=old.id if old else uuid.uuid4(), page_id=page_id, kind=kind, language=language,
            storage_path=storage_path, width=width, height=height, reference_page_id=reference_page_id,
        )
        self.versions[(page_id, kind, language)] = row
        return row, (old.storage_path if old else None)

    async def delete_version(self, page_id, kind, language):
        row = self.versions.pop((page_id, kind, language), None)
        return row.storage_path if row else None


# --- fixtures ----------------------------------------------------------------

@pytest.fixture(scope="module")
def images():
    target, ref, _ = make_pair()
    return _png(target), _png(ref)


@pytest.fixture
def user():
    return CurrentUser(id=str(uuid.uuid4()))


@pytest.fixture
def repo(user):
    return FakeRepo(uuid.UUID(user.id))


@pytest.fixture
def storage():
    return FakeStorage()


@pytest.fixture
def upscaler():
    return FakeUpscaler()


@pytest.fixture
def section(repo, user):
    s = SimpleNamespace(id=uuid.uuid4(), manga_id=uuid.uuid4())
    repo.sections[s.id] = s
    return s


def _add_page(repo, storage, section, user, data: bytes, position: int, ext: str = "png"):
    page = SimpleNamespace(id=uuid.uuid4(), section_id=section.id,
                           storage_path=f"{user.id}/{section.manga_id}/{section.id}/{position}-{uuid.uuid4()}.{ext}")
    repo.pages[page.id] = page
    storage.objects[page.storage_path] = data
    return page


@pytest.fixture
def page(repo, storage, section, user, images):
    return _add_page(repo, storage, section, user, images[0], 1)


@pytest.fixture
def ref_page(repo, storage, section, user, images):
    return _add_page(repo, storage, section, user, images[1], 0)


@pytest.fixture
def svc(repo, user, storage, upscaler):
    return PageVersionService(repo, user, storage, upscaler)


# --- brief's tests ------------------------------------------------------------

async def test_reference_equal_target_rejected(svc, page):
    with pytest.raises(VersionError) as e:
        await svc.translate_preview(page.id, page.id)
    assert e.value.status == 422 and e.value.message == "Pick a different page as the reference."


async def test_accept_without_preview_returns_404(svc, page):
    with pytest.raises(VersionError) as e:
        await svc.accept(page.id, kind="upscaled", language=None, reference_page_id=None)
    assert e.value.status == 404


async def test_accept_replaces_old_version_and_deletes_its_file(svc, page, storage):
    await svc.upscale_preview(page.id); first = await svc.accept(page.id, "upscaled", None, None)
    await svc.upscale_preview(page.id); second = await svc.accept(page.id, "upscaled", None, None)
    assert first.storage_path in storage.removed and second.storage_path in storage.objects


async def test_translate_starts_from_accepted_upscale(svc, page, ref_page, upscaler):
    await svc.upscale_preview(page.id); await svc.accept(page.id, "upscaled", None, None)
    upscaler.calls.clear()
    await svc.translate_preview(page.id, ref_page.id)
    assert upscaler.calls == []  # base is already large enough


# --- more behaviour ------------------------------------------------------------

async def test_upscale_preview_uploads_png_to_preview_path(svc, page, storage, user, upscaler):
    preview = await svc.upscale_preview(page.id)
    assert preview.kind == "upscaled" and preview.language is None and preview.reference_page_id is None
    assert preview.preview_path == f"{user.id}/_preview/{page.id}-upscaled.png"
    assert (preview.width, preview.height) == (1220, 2048)
    assert _dims(storage.objects[preview.preview_path]) == (1220, 2048)
    assert upscaler.calls == ["image/png"]


async def test_preview_rerun_overwrites(svc, page, storage):
    first = await svc.upscale_preview(page.id)
    second = await svc.upscale_preview(page.id)
    assert first.preview_path == second.preview_path and second.preview_path in storage.objects


async def test_translate_from_original_upscales_first(svc, page, ref_page, storage, user, upscaler):
    preview = await svc.translate_preview(page.id, ref_page.id)
    assert upscaler.calls == ["image/png"]  # 1024 < reference's 1884
    assert preview.kind == "translated" and preview.language == "en"
    assert preview.reference_page_id == ref_page.id
    assert preview.preview_path == f"{user.id}/_preview/{page.id}-translated.png"
    assert (preview.width, preview.height) == (1220, 2048)
    assert storage.objects[page.storage_path] and storage.objects[ref_page.storage_path]  # untouched


async def test_reference_in_another_section_is_404(svc, repo, storage, user, page, images):
    other = SimpleNamespace(id=uuid.uuid4(), manga_id=uuid.uuid4())
    repo.sections[other.id] = other
    far = _add_page(repo, storage, other, user, images[1], 0)
    with pytest.raises(VersionError) as e:
        await svc.translate_preview(page.id, far.id)
    assert e.value.status == 404


async def test_unknown_page_is_404(svc):
    for call in (lambda: svc.upscale_preview(uuid.uuid4()),
                 lambda: svc.discard(uuid.uuid4(), "upscaled"),
                 lambda: svc.remove(uuid.uuid4(), "upscaled", None)):
        with pytest.raises(VersionError) as e:
            await call()
        assert e.value.status == 404


async def test_undecodable_original_is_422(svc, repo, storage, section, user, upscaler):
    upscaler.calls.clear()
    bad = _add_page(repo, storage, section, user, b"not an image", 5)
    ref = _add_page(repo, storage, section, user, b"also not", 6)
    with pytest.raises(VersionError) as e:
        await svc.translate_preview(bad.id, ref.id)
    assert e.value.status == 422


async def test_upscale_unavailable_propagates(svc, page, upscaler):
    upscaler.down = True
    with pytest.raises(UpscaleUnavailable):
        await svc.upscale_preview(page.id)


async def test_accept_moves_preview_and_records_version(svc, page, section, storage, repo, user):
    preview = await svc.upscale_preview(page.id)
    version = await svc.accept(page.id, "upscaled", "ignored", uuid.uuid4())
    assert preview.preview_path not in storage.objects
    assert version.storage_path.startswith(f"{user.id}/{section.manga_id}/{section.id}/v-")
    assert version.storage_path.endswith(".png") and version.storage_path in storage.objects
    assert (version.width, version.height) == (1220, 2048)
    assert version.language is None and version.reference_page_id is None  # upscaled carries neither
    assert repo.commits == 1


async def test_accept_translated_defaults_language_en(svc, page, ref_page):
    await svc.translate_preview(page.id, ref_page.id)
    version = await svc.accept(page.id, "translated", None, ref_page.id)
    assert version.kind == "translated" and version.language == "en"
    assert version.reference_page_id == ref_page.id


async def test_discard_removes_preview_and_tolerates_missing(svc, page, storage):
    preview = await svc.upscale_preview(page.id)
    await svc.discard(page.id, "upscaled")
    assert preview.preview_path not in storage.objects
    await svc.discard(page.id, "upscaled")  # nothing there: still fine


async def test_remove_deletes_version_and_file(svc, page, storage, repo):
    await svc.upscale_preview(page.id)
    version = await svc.accept(page.id, "upscaled", None, None)
    await svc.remove(page.id, "upscaled", None)
    assert version.storage_path in storage.removed
    assert (page.id, "upscaled", None) not in repo.versions
    with pytest.raises(VersionError) as e:
        await svc.remove(page.id, "upscaled", None)
    assert e.value.status == 404


# --- router: error mapping ------------------------------------------------------------

@pytest.fixture
def client(svc):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.app.modules.read.dependencies import get_version_service
    from backend.app.modules.read.router import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_version_service] = lambda: svc
    return TestClient(app)


def test_router_maps_upscaler_down_to_503(client, page, upscaler):
    upscaler.down = True
    response = client.post(f"/read/pages/{page.id}/upscale")
    assert response.status_code == 503
    assert response.json() == {"detail": "The upscaler isn't running. Start the models service and try again."}


def test_router_maps_refusal_and_version_errors(client, page, repo, storage, section, user, images):
    response = client.post(f"/read/pages/{page.id}/translate", json={"reference_page_id": str(page.id)})
    assert response.status_code == 422 and response.json()["detail"] == "Pick a different page as the reference."
    twin = _add_page(repo, storage, section, user, images[0], 3)  # identical image: nothing to translate
    response = client.post(f"/read/pages/{page.id}/translate", json={"reference_page_id": str(twin.id)})
    assert response.status_code == 422 and response.json()["detail"].startswith("Nothing to translate")
    assert client.delete(f"/read/pages/{uuid.uuid4()}/versions/preview?kind=upscaled").status_code == 404


def test_router_preview_accept_remove_round_trip(client, page):
    preview = client.post(f"/read/pages/{page.id}/upscale").json()
    assert (preview["width"], preview["height"]) == (1220, 2048)
    version = client.post(f"/read/pages/{page.id}/versions/accept", json={"kind": "upscaled"})
    assert version.status_code == 200 and version.json()["kind"] == "upscaled"
    assert client.delete(f"/read/pages/{page.id}/versions?kind=upscaled").status_code == 204
    assert client.delete(f"/read/pages/{page.id}/versions/preview?kind=bogus").status_code == 422
