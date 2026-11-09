# Lector: Translate a page by reference (+ Upscale) — design

Status: reviewed, awaiting approval · 2026-11-09

## 1. Intent

Some of the user's volumes hold the same page twice, deliberately: an **English**
page (to understand the story) next to the **Japanese** original (art the user
prefers). Reading both is clumsy. The user wants **one page**: the Japanese art
with English text in the speech bubbles.

The bigger idea is a **translation feature** for Lector: replace the text in a
page's bubbles with a chosen language, leaving the art alone. There are two ways
to get the words:

- **By reference** (this design, built first): the user points at a page that
  already has the translation (the English page). Its lettering is copied into the
  Japanese page's bubbles. No LLM is involved.
- **Directly** (later): no reference page exists. The system reads the Japanese
  text and an LLM translates it. This is out of scope here, but the design must
  leave room for it (see §8).

The first target language is **English**.

## 2. Goals, non-goals, anti-goals

**Goals**
- In the reader's edit mode, the page menu gets **Translate ▸ By reference…**. The
  user clicks the reference page, and the system produces the translated page.
- The result has **Japanese art + the reference's English lettering**, at roughly
  the reference page's resolution (the Japanese page is upscaled first, see §4).
- Fast enough to wait for: a few seconds per page.
- **Upscale** as its own page-menu item (user's decision). It sharpens a
  low-resolution page about 2× with the same anime upscaler, and the result
  replaces the page in the reader the same way a translation does (§6).

**Non-goals (for this version)**
- **Translate directly** (OCR + LLM). The menu shows it greyed out, see §8.
- Patching *art* differences from one edition into the other (for example,
  restoring detail the English edition edited out). The user called this a small
  later feature. The pipeline below already isolates those areas, so it can be
  added later.
- Batch or whole-volume translation, or automatic translation on upload. The user
  wants to do it by hand first.
- Translating sound effects drawn into the art. Only text that differs between the
  two pages can move; if the reference left a sound effect untranslated, it stays
  untranslated.
- Languages other than English.

**Anti-goals (what makes this a failure even if it "works")**
- **Damaging or altering the Japanese art outside the bubbles.** The art is the
  reason the Japanese page is kept. In particular, art from the reference must
  never leak in: the English edition has edited art areas, and copying those
  over would defeat the purpose.
- Generative fill-in or redraw models (diffusion inpainting, image-editing LLMs)
  in the by-reference path. They invent pixels.
- Silently producing a wrong result. If the two pages don't line up, say so and
  stop. Never guess.

## 3. What we know from the spike (Vol. 19, 7 pairs)

A throwaway spike ran on the real data (manga `a011b12d…`, section `260b29f5…`):

- **Pairs:** pages 23/24, 25/26, 97/98, 141/142, 148/149, 161/162, 163/164.
  **English first, Japanese second.** Nothing in the data marks them as pairs;
  they are just neighbours.
- **Resolution:** the English pages are about 1200×1885 or 1400×2199. The Japanese
  pages are about 610×1024, roughly half size.
- **Alignment:** a similarity transform (scale + shift + rotation) fits every
  pair with a **median error of 0.2–0.4 px** (90th percentile ≤ 1.1 px). It uses
  400–1200 inlier matches, and some pairs carry a constant ~40 px horizontal
  offset. These are the same scans, not redraws.
- **What differs:** only 1–5% of pixels. That's bubble text, plus a few art areas
  the English edition edited.
- **Tone:** the Japanese scan is slightly greyer. A per-page tone curve (lookup
  table) learned from pixels that agree fixes this.
- **Upscale:** Real-ESRGAN `realesr-animevideov3` (2.4 MB weights) took page 162
  from 609×1024 to 1218×2048 in **2.4 s on CPU**. The line art was clearly
  crisper than plain resizing. After that, the English lettering goes in at
  nearly its own size and looks almost like the reference.
- **Telling text from art** with a rule of thumb worked on all 7 pairs, *but only
  after scaling its size thresholds to the page height*. Before that, at 2×
  size, it mistook part of an edited art area for text. **Treat the rule as
  fragile.**

Spike scripts (for reference only, not production code) are in the session
scratchpad: `pull_pages.py`, `align.py`, `upscale.py` and `spike_bubbles.py`.

## 4. The pipeline (by reference)

Input: a **target** page (Japanese) and a **reference** page (English), both in
the same section and both owned by the user.

1. **Upscale the target** about 2× with an anime upscaler (Real-ESRGAN
   `realesr-animevideov3`: run at ×4, then downscale to ×2). Done first, so the
   reference's lettering is barely resized when copied.
   - Skip the upscale when the target is already at least as large as the
     reference. *(My call.)*
   - If the target already has an accepted **upscaled** version (§6), start
     from that instead of upscaling again. *(My call.)*
2. **Align the reference onto the upscaled target.** Use SIFT keypoints, ratio-test
   matching and RANSAC to fit a *similarity* transform (`estimateAffinePartial2D`,
   reprojection threshold about 2 px), then warp with area interpolation.
   - **Refuse** if the fit is poor: too few inliers or a high residual. The
     exact thresholds are the builder's call; the spike's worst pair had 426
     inliers and a 1.06 px 90th-percentile residual. The user gets a clear
     message ("These pages don't line up closely enough to translate by
     reference").
3. **Match tone.** Learn a monotonic lookup table from reference to target on
   pixels that agree, and apply it to the warped reference.
4. **Find difference regions.** Take the absolute difference of lightly blurred
   images, threshold it, apply small morphology, then dilate and group into
   connected regions. **All sizes scale with page height.**
5. **Keep only the text regions.** A region counts as text when *both* versions
   contain several small dark letter-sized shapes, and the region is mostly ink
   on paper (few mid-greys). Everything else counts as art and is never touched.
   - A trained text detector (comic-text-detector) would make this sturdier. It
     isn't required for this version, but the classifier should sit behind a
     small interface so a detector can replace or confirm it later (it is needed
     for "Translate directly" anyway).
6. **Composite.** Within the text regions (slightly dilated and feathered),
   blend the tone-matched reference over the upscaled target. Seams land on white
   bubble paper.
7. **Output** an image the size of the upscaled target, saved as a lossless or
   high-quality file.

## 5. Where things run (modules)

Follows the repo's rules: the backend holds no model in-process, and in the
models service, "a module is a model type".

**`models/` — a new `image` module** (sibling of `llm`), for image-to-image
models.
- Upscaling is a model, so it lives here. Add a model JSON for
  `realesr-animevideov3` (weights location, scale, tile size), following "a model
  is data".
- Exposes an upscale endpoint (custom, not OpenAI-shaped): image bytes in,
  upscaled image bytes out.
- **Engine: PyTorch** *(my call; the spike used it)*. llama.cpp can't run image
  models, and the service has no image runtime today. ONNX Runtime is the
  lighter alternative if install size matters. The builder may choose it, as
  long as the model weights come from the official Real-ESRGAN release.
- **GPU:** the machine has an RTX 5060 Ti (16 GB), which already holds the LLM
  (about 12.5 GB). The upscaler is small, but the builder must confirm it fits
  next to the LLM. If not, run it on CPU (2–3 s per page is acceptable). The
  RTX 50-series needs a PyTorch build with CUDA 12.8 or later.
- Load the model on first use, not at startup. *(My call.)*

**`backend/` — the `read` module** owns the translate operation (alignment and
compositing are plain image processing, not a model).
- New endpoints, for example `POST /read/pages/{target_id}/translate` with body
  `{ reference_page_id }` (runs the pipeline and returns a preview), and
  `POST /read/pages/{id}/upscale` (upscales the original and returns a preview).
  Both share accept, discard and remove-version endpoints (§6). The translate
  endpoint checks that both pages belong to the user and sit in the same section.
- Downloads both images from Storage (service role, like scrape import), calls
  the models service to upscale, runs steps 2–7 with OpenCV, uploads the result
  to the `manga` bucket under the user's prefix, and records it (see §6).
- New dependencies: `opencv-python-headless` and `numpy`. The image logic goes
  in its own extracted component (like `scraper.py`), for example
  `read/translate.py` or a `translate/` package, with its own tests on the
  spike's invariants.
- Runs synchronously within the request (a few seconds). No job queue in this
  version. *(My call; revisit if it gets slow.)*

**`supabase/` — schema.** The `manga_page_versions` table from §6. Schema change goes through the repo's normal
`schema/` → `gen_migration.py` → migration flow.

**`frontend/` — the `read` module.**
- `PageEditOverlay`'s menu gets **Upscale** and **Translate ▸** with **By
  reference…** (enabled) and **Directly** (greyed out, "coming later"). Order:
  Move up / Move down / Add before / Add after / Upscale / Translate ▸ / Remove
  this page.
  - **Upscale** is hidden when the page already has an upscaled version (then
    **Remove upscale** shows instead), and when the page is already large. The
    threshold for "large" is the builder's call; the spike's English pages,
    1885 px and up, didn't need it. *(My call.)*
  - The menu opens on a normal click today. The user described **right-clicking**
    the image, so right-click should open the same menu in edit mode. *(My call:
    keep the left click too.)*
- **Pick-reference mode:** a banner says "Pick the reference page for p.N · Esc
  to cancel", the target is outlined, the neighbouring pages are suggested (pairs
  are adjacent, reference usually before), and any page in the section can be
  clicked. Clicking calls the translate feature (for example
  `features/manga-reader/translate-page/`).
- Show progress while it runs (a spinner on the target page), refusal messages,
  then the preview with Accept / Discard (§6). Upscale uses the same progress,
  preview and Accept / Discard flow.
- In reading and edit mode, a page with a version shows it by default, with the
  **Original** switch on the page (§6).

## 6. Preview, saving, and what the reader shows

**Preview first (user's decision).** Translate does not save directly:
1. The user picks the reference, and the backend runs the pipeline. It writes the
   result to a **preview** object in Storage (for example
   `{user_id}/_preview/{page_id}-{kind}.{ext}`, overwritten by the next preview
   of the same page) and returns it.
2. The frontend shows the preview over the target page with **Accept** and
   **Discard**. Viewing it side by side with the original is a nice-to-have.
   *(My call.)*
3. **Accept** records the translation (below) and moves or copies the preview
   to its final path. **Discard** deletes the preview object. Clean-up of stale
   previews that were never accepted or discarded is left to the builder.

If no text regions are found, that is a refusal ("Nothing to translate: these
pages have the same text"), not an empty preview. *(My call.)*

**Reader after accepting: option A (user's decision).** The translated page
**replaces the Japanese page in place**. A small **Original / English** switch on
that page shows the untouched Japanese image. The **reference page stays** in the
volume as it is (it is not hidden or removed).

**Upscale works the same way (user's decision):** preview → Accept / Discard.
The accepted upscale replaces the page in the reader, with the original kept
behind the switch.

My calls for the rest:
- **Versions per page:** at most one **upscaled** version, and at most one
  **translated** version per language. Re-running either one replaces it: the
  same preview → accept flow, and accepting overwrites the old one (its file is
  deleted).
- **What the reader shows:** the translation if there is one, else the upscaled
  version if there is one, else the original. The switch flips between that and
  **Original**, labelled for what's shown ("Original / English" or "Original /
  Upscaled"). It's a per-page, in-the-moment toggle and is not remembered.
- **Upscale then translate:** Translate starts from the accepted upscaled version
  (§4 step 1). Removing the upscale afterwards leaves the translation alone
  (it is its own image).
- **Upscale always works from the original image**, never from an earlier
  upscale.
- The page menu (edit mode) gets **Remove translation** / **Remove upscale**
  when those exist. **Translate ▸ By reference…** stays available as
  "re-translate".
- **Deleting a page** also deletes its versions (row cascade plus file clean-up,
  like page files today). Reordering is unaffected: versions belong to the page,
  not to a position.
- **Data:** a new table, for example `manga_page_versions` (`page_id` FK →
  `manga_pages` on delete cascade, `kind` ('upscaled' | 'translated'),
  `language` (null for upscaled, 'en' for translated), `storage_path`, `width`,
  `height`, nullable `reference_page_id` (null for upscaled and later for
  "directly"), `created_at`, unique (`page_id`, `kind`, `language`) with nulls
  treated as equal, RLS through the owning manga like `manga_pages`).
  `GET /read/sections/{id}/pages` returns each page's versions so the reader can
  sign them in the same batch and reserve the right box size.

## 7. Constraints

- Follow each module's docs (`*/docs/*_guidelines.md`, `*/docs/modules/read.md`,
  `models/docs/modules/llm.md`): feature-sliced frontend, thin routers, ownership
  checks in services, CSS variables and proportional units in the UI.
- Image bytes: the frontend reads them from Storage via signed URLs as today.
  The backend reads and writes Storage with the service role only for this
  server-side operation, which matches the existing scrape-import exception.
- The original Japanese and reference pages are never modified or deleted by
  Translate or Upscale. The original image file is always kept.
- **Database target (user's decision): the local Supabase** the app runs against
  today (`127.0.0.1:54321`). Schema changes for this feature go there. `CLAUDE.md`
  and `supabase/docs/supabase_guidelines.md` still say "cloud-only, never run
  locally". That's out of date, and the docs should be corrected separately. It
  isn't part of this feature.

## 8. Leaving room for "Translate directly"

Not built now, but this version shouldn't block it:
- Keep the pipeline in stages (upscale → locate text → get text → place text),
  so "directly" can reuse upscale and replace the rest: a text detector (also a
  model, so a models-service module), OCR, LLM translation through the existing
  `llm` module, erase/inpaint, and typesetting.
- The menu item and the translated-version storage from §6 should not assume a
  reference page always exists.

## 9. Left to the builder

- Exact alignment refusal thresholds, morphology sizes and classifier constants
  (start from the spike's values, scaled by page height).
- Output file format and quality.
- Endpoint names and schema field names.
- PyTorch vs ONNX Runtime (§5), and GPU vs CPU for the upscaler.
- Tests: use the 7 Vol. 19 pairs as fixtures if practical. Key checks: alignment
  error, "no reference pixels outside text regions", and every bubble replaced.
