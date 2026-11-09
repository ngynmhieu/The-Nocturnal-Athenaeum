# Translate by Reference + Upscale Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add **Upscale** and **Translate by reference** to Lector's page menu. Each one produces a preview the user accepts or discards. An accepted result replaces the page in the reader, with the original kept behind a switch.

**Architecture:**
- **Models service:** a new `image` module runs Real-ESRGAN `realesr-animevideov3` (PyTorch) behind `POST /v1/images/upscale`.
- **Backend `read` module:** owns a pure OpenCV pipeline (`read/translate/`: align → tone-match → diff regions → keep text → composite) and a `PageVersionService` that previews, accepts, discards and removes per-page versions, stored in a new `manga_page_versions` table.
- **Frontend reader:** shows a page's chosen version with an Original switch. Edit mode adds the menu items, a pick-reference mode, and a preview with Accept / Discard.

**Tech Stack:** PyTorch (CPU wheels), OpenCV (`opencv-python-headless`), NumPy, FastAPI, SQLAlchemy async, Supabase Postgres + Storage, React + TypeScript + Tailwind, pytest (new, dev-only).

**Spec:** `docs/superpowers/specs/2026-11-09-manga-translate-by-reference-design.md`

## Global Constraints

- Read each module's docs before touching it (`CLAUDE.md` Rule 1): `models/docs/models_guideline.md`, `backend/docs/backend_guidelines.md` + `backend/docs/modules/read.md`, `supabase/docs/supabase_guidelines.md` + `supabase/docs/modules/read.md`, `frontend/docs/frontend_guidelines.md` + `frontend/docs/styling_guidelines.md` + `frontend/docs/modules/read.md`.
- The backend holds no model in-process. Upscaling runs only in the models service, reached over HTTP at `settings.models_service_url` (default `http://localhost:8001/v1`).
- In the models service, a module is a model type and a model is data: the upscaler's parameters live in `models/app/modules/image/models/realesr-animevideov3.json`.
- Weights come only from the official release: `https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-animevideov3.pth`, sha256 `b8a8376811077954d82ca3fcf476f1ac3da3e8a68a4f4d71363008000a18b75d`.
- **Upscaler device: CPU** (decided at planning). `torch` from PyPI is CPU-only on Windows, so there is no clash with llama.cpp's pip CUDA runtime and no VRAM contention with the 12.5 GB LLM. The spike measured 2.4 s per page. The JSON has a `device` field so `"cuda"` can be tried later.
- Upscale = run the net at ×4, then downscale with `INTER_AREA` to ×2 of the input.
- **Originals are never modified or deleted** by Upscale or Translate. Deleting a page, section or manga also deletes its version files.
- No generative or inpainting models anywhere in this feature.
- **Database target is the local Supabase** (`127.0.0.1:54321`), applied with `supabase/run_migration.bat`. Do not push to the cloud.
- UI colors use `--owl-*` CSS variables only, with proportional units (`rem`, `%`), never raw px for sizing.
- User-facing refusal copy (exact):
  - `"These pages don't line up closely enough to translate by reference."`
  - `"Nothing to translate: these pages have the same text."`
  - `"Pick a different page as the reference."` (reference = target)
  - `"The upscaler isn't running. Start the models service and try again."` (models service unreachable)
- Version storage paths:
  - preview: `{user_id}/_preview/{page_id}-{kind}.png`
  - accepted: `{user_id}/{manga_id}/{section_id}/v-{uuid}.png`
- "Large page" threshold: hide **Upscale** when `page.height >= 1600`. Translate skips its own upscale step when the target's height is ≥ the reference's height.
- Real manga pages must **not** be committed as test fixtures (copyrighted). Tests use synthetic images.

## Review Focus

1. **The wrong page picked as reference** (unrelated page, or very different crop): the user expects a clear refusal, not a mangled page. Test: `test_unrelated_reference_is_refused` (Task 2).
2. **Color pages** (covers, colour inserts): the output must stay in color with untouched art pixels identical. Test: `test_color_page_keeps_color_and_art` (Task 3).
3. **Models service not running** while the user clicks Upscale or Translate: the user expects the exact "upscaler isn't running" message, not a 500. Test: `test_upscale_unreachable_raises_unavailable` (Task 5).
4. **Accept clicked twice / after Discard / after the page was deleted:** the user expects no crash and no orphaned file. Test: `test_accept_without_preview_returns_404` (Task 6).
5. **Picking the target page itself as the reference:** the user expects the exact "Pick a different page" message. Test: `test_reference_equal_target_rejected` (Task 6).

---

### Task 1: Models service — `image` module with the upscaler

**Files:**
- Create: `models/app/modules/image/__init__.py` (exports `router`)
- Create: `models/app/modules/image/config.py` (`UpscalerConfig`, `load_configs()`)
- Create: `models/app/modules/image/network.py` (`SRVGGNetCompact`)
- Create: `models/app/modules/image/manager.py` (`UpscalerManager`, module-level `manager`)
- Create: `models/app/modules/image/service.py` (`ImageService`)
- Create: `models/app/modules/image/dependencies.py` (`get_image_service`)
- Create: `models/app/modules/image/router.py`
- Create: `models/app/modules/image/models/realesr-animevideov3.json`
- Create: `models/tests/__init__.py`, `models/tests/test_image.py`
- Create: `models/requirements-dev.txt` (`-r requirements.txt`, `pytest`)
- Create: `models/docs/modules/image.md`
- Modify: `models/app/main.py` (include the image router; don't load the upscaler in lifespan)
- Modify: `models/requirements.txt` (add `torch`, `numpy`, `opencv-python-headless`)
- Modify: `models/docs/models_guideline.md` (layout tree + "Two model types now")

**Interfaces:**
- Produces (HTTP): `POST /v1/images/upscale`
  - request: body = raw image bytes, any `Content-Type: image/*`; optional query `model` (defaults to the JSON with `"default": true`)
  - response `200`: `image/png` bytes at ×2 width and height
  - response `400`: `{"detail": "Not a readable image."}`
- Produces (Python): `UpscalerManager.upscale(model_id: str | None, image_bgr: np.ndarray) -> np.ndarray` (uint8 BGR, `(2h, 2w, 3)`)
- Model JSON fields: `id`, `weights_url`, `sha256`, `net_scale` (4), `output_scale` (2), `num_feat` (64), `num_conv` (16), `device` ("cpu"), `tile` (0 = whole image), `description`, `default` (true).

- [ ] **Step 1: Write the failing tests** in `models/tests/test_image.py`

```python
def test_network_upscales_4x():
    net = SRVGGNetCompact(num_feat=8, num_conv=2, upscale=4)
    out = net(torch.zeros(1, 3, 10, 12))
    assert out.shape == (1, 3, 40, 48)

def test_config_loads_shipped_json():
    cfgs = load_configs()
    cfg = cfgs["realesr-animevideov3"]
    assert cfg.net_scale == 4 and cfg.output_scale == 2 and cfg.device == "cpu" and cfg.default
    assert cfg.sha256 == "b8a8376811077954d82ca3fcf476f1ac3da3e8a68a4f4d71363008000a18b75d"

def test_manager_output_is_double_size_bgr():
    m = UpscalerManager(load_configs())
    m._nets["realesr-animevideov3"] = SRVGGNetCompact(num_feat=8, num_conv=2, upscale=4).eval()  # skip download
    out = m.upscale(None, np.full((30, 20, 3), 200, np.uint8))
    assert out.shape == (60, 40, 3) and out.dtype == np.uint8

def test_bad_sha256_refuses_weights(tmp_path):
    bad = tmp_path / "w.pth"; bad.write_bytes(b"not weights")
    with pytest.raises(ValueError, match="sha256"):
        verify_weights(bad, "b8a8376811077954d82ca3fcf476f1ac3da3e8a68a4f4d71363008000a18b75d")

def test_upscale_endpoint_rejects_non_image():
    client = TestClient(create_app())
    r = client.post("/v1/images/upscale", content=b"hello", headers={"Content-Type": "image/png"})
    assert r.status_code == 400 and r.json()["detail"] == "Not a readable image."
```

The endpoint test must not trigger the LLM lifespan load. Construct `TestClient(create_app())` without entering its context manager, so lifespan doesn't run.

- [ ] **Step 2: Run the tests and check they fail**

Run: `cd models && .venv\Scripts\python -m pip install -r requirements-dev.txt && .venv\Scripts\python -m pytest tests/test_image.py -v`
Expected: FAIL with import errors (`app.modules.image` not found).

- [ ] **Step 3: Implement the module**

- `network.py`: `SRVGGNetCompact(num_feat=64, num_conv=16, upscale=4)` keeps Real-ESRGAN's exact layer layout, so the published `params` state dict loads:
  - `body = [Conv2d(3,f,3,1,1), PReLU(f)] + num_conv × [Conv2d(f,f,3,1,1), PReLU(f)] + [Conv2d(f, 3*u*u, 3,1,1)]` held in `nn.ModuleList` named `body`
  - `upsampler = nn.PixelShuffle(u)`
  - `forward` = `upsampler(body(x)) + F.interpolate(x, scale_factor=u, mode="nearest")`
- `config.py`: frozen dataclass `UpscalerConfig` with the JSON fields listed above. `load_configs() -> dict[str, UpscalerConfig]` reads `models/*.json` (mirrors `llm/config.py`).
- `manager.py`:
  - `verify_weights(path: Path, sha256: str) -> None` raises `ValueError("sha256 mismatch …")`.
  - Weights are cached at `%LOCALAPPDATA%/nocturnal-models/image/{id}.pth` (fallback `~/.cache/nocturnal-models/image/`). They are downloaded with `httpx` on first use and verified before `torch.load(..., weights_only=True)`, using the state dict's `"params"` key when present.
  - `upscale(...)` loads lazily under a `threading.Lock`, converts BGR → RGB float `[0,1]` on `torch.inference_mode()`, runs the net, then resizes the ×4 result to `(2w, 2h)` with `cv2.INTER_AREA`.
- `service.py`: `ImageService.upscale_bytes(data: bytes, model: str | None) -> bytes` decodes with `cv2.imdecode(..., IMREAD_COLOR)` (`None` raises `ValueError("Not a readable image.")`) and encodes PNG.
- `router.py`: a thin, sync `def` endpoint (runs in the threadpool). It reads `await request.body()` in an `async def` wrapper and calls the service via `run_in_threadpool`. `ValueError` maps to 400 with its message. Returns `Response(content=..., media_type="image/png")`.

- [ ] **Step 4: Run the tests and check they pass**

Run: `cd models && .venv\Scripts\python -m pytest tests/test_image.py -v`
Expected: 5 passed.

- [ ] **Step 5: Smoke-test with the real weights** (downloads 2.4 MB once)

Run `run_models.bat`, then post any local manga page:
`curl -s -X POST --data-binary @page.jpg -H "Content-Type: image/jpeg" http://localhost:8001/v1/images/upscale -o up.png`
Expected: `up.png` is twice the width and height, crisp line art, and the request takes ≈ 2–4 s on CPU for a 609×1024 page.

- [ ] **Step 6: Write `models/docs/modules/image.md`** (purpose, JSON fields, endpoint, CPU decision and how to switch `device`) and update the layout tree in `models_guideline.md`.

- [ ] **Step 7: Commit**

```bash
git add models/
git commit -m "models: add image module with Real-ESRGAN anime upscaler"
```

---

### Task 2: Backend pipeline — alignment with refusal

**Files:**
- Create: `backend/app/modules/read/translate/__init__.py` (re-exports public names from Tasks 2–3)
- Create: `backend/app/modules/read/translate/errors.py`
- Create: `backend/app/modules/read/translate/align.py`
- Create: `backend/tests/__init__.py`, `backend/tests/read/__init__.py`, `backend/tests/read/conftest.py`, `backend/tests/read/test_translate_align.py`
- Create: `backend/requirements-dev.txt` (`-r requirements.txt`, `pytest`, `pytest-asyncio`)
- Modify: `backend/requirements.txt` (add `opencv-python-headless`, `numpy`)

**Interfaces:**
- Produces:
  - `class TranslateRefusal(Exception)` with `.message: str` (user-facing copy from Global Constraints)
  - `@dataclass(frozen=True) class Alignment: matrix: np.ndarray  # 2×3 float, maps reference → target; inliers: int; residual_p90: float`
  - `align(reference_gray: np.ndarray, target_gray: np.ndarray) -> Alignment`, which raises `TranslateRefusal("These pages don't line up closely enough to translate by reference.")`
- `conftest.py` produces the synthetic fixtures used by Tasks 2–3:
  - `make_page(seed: int, h: int, w: int, bubble_text: list[str], color: bool = False) -> np.ndarray`: a busy random "art" background (random lines/circles/hatching, so SIFT has features), white ellipse bubbles, black `cv2.putText` text inside them.
  - `make_pair(color: bool = False) -> (target_bgr, reference_bgr, bubbles)`: the target is 1024 tall with Japanese-stand-in text (e.g. `"AAAA"`). The reference is the same art scaled ×1.84, shifted ~40 px, with different bubble text (`"HELLO THERE"`) and one **edited-art patch** (a grey-filled rectangle over the art, outside the bubbles). `bubbles` are the bubble boxes `(x0, y0, x1, y1)` in target coordinates, padded by 8 px. With `color=True`, the art uses saturated colours.
  - `gray(img: np.ndarray) -> np.ndarray`: BGR → grayscale.
  - A `pair` pytest fixture returning `make_pair()`.

- [ ] **Step 1: Write the failing tests** in `test_translate_align.py`

```python
def test_aligns_scaled_shifted_reference(pair):
    target, reference, _ = pair
    a = align(gray(reference), gray(target))
    assert a.inliers >= 100 and a.residual_p90 <= 1.5
    scale = math.hypot(a.matrix[0, 0], a.matrix[1, 0])
    assert abs(scale - 1 / 1.84) < 0.01

def test_unrelated_reference_is_refused():
    with pytest.raises(TranslateRefusal) as e:
        align(gray(make_page(1, 1885, 1200, ["X"])), gray(make_page(2, 1024, 610, ["Y"])))
    assert e.value.message == "These pages don't line up closely enough to translate by reference."
```

- [ ] **Step 2: Run the tests and check they fail**

Run: `cd backend && .venv\Scripts\python -m pip install -r requirements-dev.txt && .venv\Scripts\python -m pytest tests/read/test_translate_align.py -v`
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement `align`**

- SIFT (`nfeatures=8000`), BFMatcher knn with ratio 0.75, and `cv2.estimateAffinePartial2D(..., method=cv2.RANSAC, ransacReprojThreshold=2.0)`.
- Refuse when there are fewer than 8 good matches, the matrix is `None`, `inliers < 100`, or `residual_p90 > 2.5`. (The spike's worst real pair was 426 inliers / 1.06 px.)

- [ ] **Step 4: Run the tests and check they pass**

Run: `cd backend && .venv\Scripts\python -m pytest tests/read/test_translate_align.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/requirements.txt backend/requirements-dev.txt backend/tests backend/app/modules/read/translate
git commit -m "read: add page alignment for translate-by-reference"
```

---

### Task 3: Backend pipeline — text regions and composite

**Files:**
- Create: `backend/app/modules/read/translate/regions.py`
- Create: `backend/app/modules/read/translate/compose.py`
- Create: `backend/tests/read/test_translate_compose.py`
- Create: `backend/scripts/try_translate.py` (dev-only CLI: `python -m backend.scripts.try_translate <target> <reference> <out>`, for checking against real pages locally, never committed with images)

**Interfaces:**
- Consumes: `align`, `Alignment`, `TranslateRefusal` (Task 2).
- Produces:
  - `match_tone(reference_gray_warped: np.ndarray, target_gray: np.ndarray, covered: np.ndarray) -> np.ndarray  # uint8 LUT (256,)`
  - `class TextClassifier(Protocol): def is_text(self, region: np.ndarray, ref_gray: np.ndarray, tgt_gray: np.ndarray, scale: float) -> bool` and `GlyphHeuristic()` implementing it (the seam for a future detector)
  - `text_mask(ref_gray: np.ndarray, tgt_gray: np.ndarray, covered: np.ndarray, classifier: TextClassifier = GlyphHeuristic()) -> np.ndarray  # uint8 0/1`
  - `translate_by_reference(target_bgr: np.ndarray, reference_bgr: np.ndarray) -> np.ndarray  # same shape as target_bgr`, which raises `TranslateRefusal` (alignment, or `"Nothing to translate: these pages have the same text."` when the mask is empty)

Constants (from the spike, tuned at 1024 px height; multiply every size by `k = target_height / 1024`):
- diff threshold `45` on 3×3-blurred images
- open kernel `int(2k)`
- group dilation `int(13k) | 1`
- glyph = dark (`< 110`) component with area in `[3k², 400k²]`
- text if glyphs(ref) ≥ 4 **and** glyphs(target) ≥ 2 **and** ink-on-paper fraction (`>200 or <110`) > 0.8
- composite alpha = text mask dilated 5×5, then Gaussian 7×7

- [ ] **Step 1: Write the failing tests** in `test_translate_compose.py`

```python
def test_bubbles_get_reference_text(pair):
    target, reference, bubbles = pair
    out = translate_by_reference(target, reference)
    for (x0, y0, x1, y1) in bubbles:  # bubble boxes in target coordinates
        assert np.abs(out[y0:y1, x0:x1].astype(int) - target[y0:y1, x0:x1]).mean() > 5

def test_art_outside_text_untouched(pair):
    target, reference, bubbles = pair
    out = translate_by_reference(target, reference)
    outside = np.ones(target.shape[:2], bool)
    for (x0, y0, x1, y1) in bubbles: outside[y0:y1, x0:x1] = False
    assert np.array_equal(out[outside], target[outside])  # includes the edited-art patch area

def test_identical_text_is_refused(pair):
    target, _, _ = pair
    ref = cv2.resize(target, None, fx=1.84, fy=1.84)
    with pytest.raises(TranslateRefusal) as e:
        translate_by_reference(target, ref)
    assert e.value.message == "Nothing to translate: these pages have the same text."

def test_color_page_keeps_color_and_art():
    target, reference, bubbles = make_pair(color=True)
    out = translate_by_reference(target, reference)
    assert out.shape == target.shape and out.ndim == 3
    assert not np.array_equal(out[..., 0], out[..., 2])  # still colour, not collapsed to grey
```

`test_art_outside_text_untouched` is the anti-goal test: no reference pixels outside the text regions, the edited-art patch included. Bubble boxes from `make_pair` must cover the feathered edge (pad them by 8 px).

- [ ] **Step 2: Run the tests and check they fail**

Run: `cd backend && .venv\Scripts\python -m pytest tests/read/test_translate_compose.py -v`
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement `regions.py` and `compose.py`**

- Detection runs on grayscale; compositing runs on the BGR images.
- Warp the reference with the alignment matrix (`INTER_AREA`, white border) and build a `covered` mask the same way.
- `match_tone` learns a median-per-level LUT on blurred, covered pixels (needs > 30 samples per level, otherwise identity), made monotonic with `np.maximum.accumulate`. Apply it per channel.
- `text_mask` follows the constants above.
- Blend `target*(1-α) + ref*α` only where α > 0, so pixels with α == 0 stay byte-identical.

- [ ] **Step 4: Run the tests and check they pass**

Run: `cd backend && .venv\Scripts\python -m pytest tests/read -v`
Expected: 6 passed.

- [ ] **Step 5: Check against real pages (manual, local only)**

Export pages 161 (EN) and 162 (JA) of Vol. 19 from the app, upscale 162 via Task 1's endpoint, then run `python -m backend.scripts.try_translate 162_up.png 161.jpg out.png`.
Expected: all five bubbles are English and none of the edited art is copied (compare with the spike result the user approved).

- [ ] **Step 6: Commit**

```bash
git add backend/app/modules/read/translate backend/tests/read backend/scripts/try_translate.py
git commit -m "read: add text-region detection and compositing for translate-by-reference"
```

---

### Task 4: Supabase — `manga_page_versions` table

**Files:**
- Create: `supabase/schema/read/manga_page_versions.sql`
- Create: the generated migration under `supabase/migrations/` (via the script, not by hand)
- Modify: `supabase/docs/modules/read.md` (data shape, table section, the `_preview/` storage prefix, notes on cascade + file clean-up)

**Interfaces:**
- Produces table `public.manga_page_versions`:
  - `id uuid pk default gen_random_uuid()`
  - `page_id uuid not null references public.manga_pages(id) on delete cascade`
  - `kind text not null check (kind in ('upscaled','translated'))`
  - `language text` (null for upscaled)
  - `check ((kind = 'upscaled') = (language is null))`
  - `storage_path text not null`, `width integer`, `height integer`
  - `reference_page_id uuid references public.manga_pages(id) on delete set null`
  - `created_at timestamptz not null default now()`
  - unique index `manga_page_versions_page_kind_lang_idx on (page_id, kind, coalesce(language, ''))`
  - index on `page_id`
  - RLS enabled, with select/insert/update/delete policies joining `manga_pages → manga_sections → mangas` on `auth.uid()` (copy the shape from `manga_pages.sql`)

- [ ] **Step 1: Write `manga_page_versions.sql`** with the shape above and a header comment in the style of `manga_pages.sql`.

- [ ] **Step 2: Generate and apply locally**

Run: `supabase\run_migration.bat` (from the repo root; local stack running).
Expected: it detects the new fragment, generates `…_add_manga_page_versions.sql`, shows the diff, and applies it after you confirm.

- [ ] **Step 3: Verify the table exists**

Run: `psql "<local DATABASE_URL without +asyncpg>" -c "\d public.manga_page_versions"`
Expected: the columns, unique index and RLS shown as enabled.

- [ ] **Step 4: Update `supabase/docs/modules/read.md`**, then commit

```bash
git add supabase/
git commit -m "supabase: add manga_page_versions table"
```

---

### Task 5: Backend — version persistence, Storage helpers, upscale client

**Files:**
- Modify: `backend/app/modules/read/models.py` (add `MangaPageVersion` ORM mirror)
- Modify: `backend/app/modules/read/repository.py`
- Modify: `backend/app/modules/read/schemas/page.py` (+ re-export in `schemas/__init__.py`)
- Modify: `backend/app/modules/read/services/read.py` (`list_pages`, `delete_page`, `delete_section`, `delete_manga` include versions)
- Modify: `backend/app/shared/storage/client.py` (`download`, `move`)
- Modify: `backend/app/main.py` (build `app.state.upscale_client` in the lifespan, next to `storage_client`)
- Create: `backend/app/shared/images/__init__.py`, `backend/app/shared/images/upscale_client.py`
- Create: `backend/tests/read/test_upscale_client.py`

**Interfaces:**
- Produces:
  - `class PageVersionInfo(BaseModel)`: `id: UUID, kind: Literal["upscaled","translated"], language: str | None, storage_path: str, width: int | None, height: int | None, reference_page_id: UUID | None`
  - `PageInfo.versions: list[PageVersionInfo] = []`
  - Repository:
    - `list_versions(page_ids: list[UUID]) -> dict[UUID, list[MangaPageVersion]]`
    - `get_version(page_id, kind, language) -> MangaPageVersion | None`
    - `upsert_version(page_id, kind, language, storage_path, width, height, reference_page_id) -> tuple[MangaPageVersion, str | None]` (returns the replaced file path, if any)
    - `delete_version(page_id, kind, language) -> str | None` (the deleted file path)
    - `version_paths_for_pages(page_ids) -> list[str]`
  - `manga_storage_paths` / `section_storage_paths` also return version paths.
  - `StorageClient.download(path: str) -> bytes`, `StorageClient.move(src: str, dst: str) -> None`
  - `class UpscaleUnavailable(Exception)`
  - `class UpscaleClient: def __init__(self, base_url: str); async def upscale(self, image: bytes, content_type: str) -> bytes`. It POSTs to `{base_url}/images/upscale` with a 120 s timeout and raises `UpscaleUnavailable` on connect error or 5xx. Built once in the backend lifespan and stored on `app.state.upscale_client`, next to `storage_client`.

- [ ] **Step 1: Write the failing test** in `test_upscale_client.py`

```python
async def test_upscale_unreachable_raises_unavailable():
    client = UpscaleClient("http://127.0.0.1:9/v1")  # nothing listens on port 9
    with pytest.raises(UpscaleUnavailable):
        await client.upscale(b"\x89PNG...", "image/png")
```

- [ ] **Step 2: Run it and check it fails**

Run: `cd backend && .venv\Scripts\python -m pytest tests/read/test_upscale_client.py -v`
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement** the ORM mirror, repository methods, schema field, Storage `download`/`move` (via `run_in_threadpool` on the storage3 bucket's `download` / `move`, like the existing methods), `UpscaleClient`, and lifespan wiring.
  - `list_pages` fills `versions` with one extra query (`list_versions`).
  - `delete_page` removes the page's version files after commit.
  - `delete_section`/`delete_manga` pick them up through the extended `*_storage_paths`.

- [ ] **Step 4: Run the tests**

Run: `cd backend && .venv\Scripts\python -m pytest tests -v`
Expected: all pass (7).

- [ ] **Step 5: Manual check**

Run the app, open Vol. 19, and check `GET /read/sections/{id}/pages` in the browser network tab.
Expected: each page has `"versions": []`, and the reader still works as before.

- [ ] **Step 6: Commit**

```bash
git add backend/
git commit -m "read: persist page versions; storage download/move; upscale client"
```

---

### Task 6: Backend — preview / accept / discard / remove endpoints

**Files:**
- Create: `backend/app/modules/read/services/versions.py` (`PageVersionService`)
- Create: `backend/app/modules/read/schemas/version.py` (+ re-export)
- Modify: `backend/app/modules/read/router.py`, `backend/app/modules/read/dependencies.py` (`get_version_service`), `backend/app/modules/read/services/__init__.py`
- Create: `backend/tests/read/test_versions_service.py`
- Modify: `backend/docs/modules/read.md` (endpoints table, `translate/` component, versions service, dependency flow)

**Interfaces:**
- Consumes: `translate_by_reference`, `TranslateRefusal` (Task 3); repository/Storage/`UpscaleClient` (Task 5).
- Produces (HTTP; every route checks page ownership, 404 if not owned):

| Method & path | Body | Returns |
|---|---|---|
| `POST /read/pages/{id}/upscale` | — | `VersionPreview` |
| `POST /read/pages/{id}/translate` | `{reference_page_id}` | `VersionPreview` |
| `POST /read/pages/{id}/versions/accept` | `{kind, language?, reference_page_id?}` | `PageVersionInfo` |
| `DELETE /read/pages/{id}/versions/preview?kind=…` | — | 204 |
| `DELETE /read/pages/{id}/versions?kind=…&language=…` | — | 204 |

  - `VersionPreview`: `{kind, language, preview_path, width, height, reference_page_id}`
  - `TranslateRefusal` → 422 `{"detail": message}`
  - `UpscaleUnavailable` → 503 `{"detail": "The upscaler isn't running. Start the models service and try again."}`
  - reference == target → 422 `"Pick a different page as the reference."`
  - reference in another section → 404
  - accept with no preview object → 404
- Service behaviour:
  - **upscale:** download the original → `UpscaleClient.upscale` → upload as PNG to `{user}/_preview/{page_id}-upscaled.png` (overwrite: remove, then upload).
  - **translate:**
    1. Download the target's base image: the accepted upscaled version if one exists, otherwise the original.
    2. Upscale it via the client unless the base height ≥ the reference height.
    3. Run `translate_by_reference` in `run_in_threadpool`.
    4. Upload to `{user}/_preview/{page_id}-translated.png`.
    - language is fixed to `"en"`.
  - **accept:** download the preview → decode dims → `move` it to `{user}/{manga}/{section}/v-{uuid}.png` → `upsert_version` → commit → remove the replaced file (if any).
  - **discard:** remove the preview object (no error if missing).
  - **remove:** `delete_version` → commit → remove the file.

- [ ] **Step 1: Write the failing service tests** in `test_versions_service.py`, using in-memory fakes for the repository, Storage and `UpscaleClient`. Use `pytest-asyncio` and the fixtures from Task 2's conftest.

```python
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
```

The fixtures `svc`, `page`, `ref_page`, `storage` and `upscaler` are defined in this test file. They're in-memory fakes: `storage.objects`/`storage.removed` record paths, and `upscaler.calls` records calls and returns a ×2 resize. `VersionError(status: int, message: str)` is the service's own exception. The router maps it, along with `TranslateRefusal` → 422 and `UpscaleUnavailable` → 503.

- [ ] **Step 2: Run them and check they fail**

Run: `cd backend && .venv\Scripts\python -m pytest tests/read/test_versions_service.py -v`
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement** `PageVersionService`, the schemas, router routes (thin) and `get_version_service`.

- [ ] **Step 4: Run all backend tests**

Run: `cd backend && .venv\Scripts\python -m pytest tests -v`
Expected: all pass (11).

- [ ] **Step 5: Manual end-to-end via `/docs`**

With all services running, call `POST /read/pages/{page162}/translate` with `{reference_page_id: page161}`, then open `preview_path` via a signed URL.
Expected: English bubbles on Japanese art at about 1218×2048. Then call accept, and `GET …/pages` shows the version.

- [ ] **Step 6: Update `backend/docs/modules/read.md`** and commit

```bash
git add backend/
git commit -m "read: upscale/translate preview, accept, discard, remove endpoints"
```

---

### Task 7: Frontend — show versions with an Original switch

**Files:**
- Modify: `frontend/src/modules/read/shared/api/readApi.ts` (`PageVersionInfo`, `PageInfo.versions`, `VersionPreview`, and the five callers)
- Create: `frontend/src/modules/read/entities/page/displayedImage.ts`
- Modify: `frontend/src/modules/read/entities/page/index.ts` (export it)
- Modify: `frontend/src/modules/read/pages/MangaReaderPage.tsx` (sign version paths too)
- Modify: `frontend/src/modules/read/widgets/MangaReader/Reader.tsx`, `widgets/MangaReader/components/PageView.tsx`

**Interfaces:**
- Produces:
  - `displayedImage(page: Page, showOriginal: boolean): { path: string; width: number | null; height: number | null; label: "Original" | "English" | "Upscaled" }`
    - order: translated (`language === "en"`) → upscaled → original
    - `showOriginal` forces the original
  - `readApi`:
    - `upscalePage(pageId): Promise<VersionPreview>`
    - `translatePage(pageId, referencePageId): Promise<VersionPreview>`
    - `acceptVersion(pageId, body: {kind, language?, referencePageId?}): Promise<PageVersionInfo>`
    - `discardPreview(pageId, kind): Promise<void>`
    - `removeVersion(pageId, kind, language?): Promise<void>`
    - request bodies are snake_cased by hand, as existing callers do
  - `PageView` gains `originalToggle?: { label: string; showingOriginal: boolean; onToggle: () => void }`. It renders a small pill button at the bottom-right of the page (`--owl-*` colours, `rem` sizing) reading e.g. "Original / English", with the active side emphasised. The aspect ratio uses the displayed image's dims.
  - `Reader` keeps `showOriginal: Set<string>` in state (not persisted) and passes the matching `urls[...]`.

- [ ] **Step 1: Implement**

Use `useSignedUrls` with every page's `storagePath` plus all `versions[].storagePath`.

- [ ] **Step 2: Type-check and lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: both succeed with no new errors.

- [ ] **Step 3: Manual check in the app**

After Task 6's manual accept of page 162, reload the reader.
Expected:
- page 162 shows the English version at the new aspect ratio with no layout jump
- the pill flips to the Japanese original and back
- other pages are unchanged and show no pill

- [ ] **Step 4: Commit**

```bash
git add frontend/src/modules/read
git commit -m "lector: show accepted page versions with an Original switch"
```

---

### Task 8: Frontend — menu items, pick-reference mode, preview Accept / Discard

**Files:**
- Modify: `frontend/src/shared/ui/Dropdown.tsx` (`DropdownItem` gains `disabled?: boolean`: muted colour, `aria-disabled`, no `onClick`)
- Create: `frontend/src/modules/read/features/manga-reader/page-versions/usePageVersions.ts`, `index.ts` (+ export from `features/index.ts`)
- Create: `frontend/src/modules/read/widgets/MangaReader/components/VersionPreview.tsx`
- Create: `frontend/src/modules/read/widgets/MangaReader/components/PickReferenceBanner.tsx`
- Modify: `frontend/src/modules/read/widgets/MangaReader/components/PageEditOverlay.tsx`, `widgets/MangaReader/Reader.tsx`, `pages/MangaReaderPage.tsx`
- Modify: `frontend/docs/modules/read.md` ("Fixing pages in place" + a new "Upscale and translate" section)

**Interfaces:**
- Consumes: the `readApi` callers and `displayedImage` (Task 7).
- Produces:
  - `usePageVersions(onChanged: () => Promise<void>)` returns:
    - `busyId: string | null`
    - `preview: (VersionPreview & { pageId: string }) | null`
    - `error: string | null` (the backend's `detail`, shown verbatim)
    - `upscale(page)`, `translate(page, referencePage)`, `accept()`, `discard()`, `remove(page, kind)`
  - `PageEditOverlay` new props:
    - `onUpscale?: (page) => void` (omitted when the page has an upscaled version or `height >= 1600`)
    - `onRemoveUpscale?`, `onTranslate?: (page) => void` (enters pick mode), `onRemoveTranslation?`
- Menu order (exact labels):
  1. Move up one page
  2. Move down one page
  3. Add page before
  4. Add page after
  5. **Upscale** *or* **Remove upscale**
  6. **Translate by reference…**
  7. **Translate directly — coming later** (disabled)
  8. **Remove translation** (only when one exists)
  9. Remove this page
  - Flat items: the shared `Dropdown` has no submenu component, and building one isn't worth it for two items.
  - Raise `MENU_HEIGHT_PX` to fit up to nine items.
- **Right-click** (`onContextMenu`, with `preventDefault`) on the page button opens the same menu at the pointer. Left-click keeps working.
- **Pick-reference mode** (state in `Reader`: `pickingFor: Page | null`):
  - `PickReferenceBanner` is sticky at the top of the strip: "Pick the reference page for p.N · Esc to cancel".
  - The target gets an outline using `--owl-*`; the pages at index ±1 get a dashed "suggested" outline.
  - Clicking any other page calls `translate(target, clicked)`. Clicking the target does nothing. Esc cancels.
- **Preview:** `VersionPreview` overlays the target page with the signed preview image, plus **Accept** and **Discard** buttons. While a request runs, the target page shows the existing `busy` pulse. Errors show in the page's existing `pageError` line.

- [ ] **Step 1: Implement** the hook, components, Dropdown `disabled`, overlay changes and page wiring.

- [ ] **Step 2: Type-check and lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: success.

- [ ] **Step 3: Manual walkthrough in the app** (Vol. 19, edit mode)

1. Right-click page 162 → **Translate by reference…** → the banner shows and page 161 is suggested → click 161 → the preview appears → **Accept**. Page 162 now reads in English with the switch.
2. Right-click page 24 → **Upscale** → preview → **Discard**. The page is unchanged and the preview file is gone from Storage.
3. Page 24 → **Upscale** → **Accept** → the menu now shows **Remove upscale**.
4. **Translate by reference…** on page 24 with page 23 as reference: it uses the upscaled base.
5. Translate page 98 with page 23 as reference → the exact "don't line up" message.
6. Stop the models service → **Upscale** on page 26 → the exact "upscaler isn't running" message.
7. Pick the target itself → nothing happens. Esc leaves pick mode.
8. **Remove translation** on page 162 → the Japanese original again.

Expected: every step behaves as written, with no console errors.

- [ ] **Step 4: Update `frontend/docs/modules/read.md`**, then commit

```bash
git add frontend/
git commit -m "lector: upscale and translate-by-reference from the page menu"
```
