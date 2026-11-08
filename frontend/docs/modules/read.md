# Read Module — Architecture (manga reader, displayed as "Lector")

> Per-module doc for the manga-reader frontend. Code-level module name: **`read`**
> (`modules/read/`). **"Lector"** is the user-facing label only — the sidebar nav
> text and page headings — never a folder name. Pairs with `backend/docs/modules/read.md`
> and `supabase/docs/modules/read.md`. Read `frontend_guidelines.md` first, including
> its networking section (the new `shared/lib/storage.ts` wrapper).

## Status

**Proposal.** Agreed design, not yet built.

## Overview

A manga library: browse all series, open one to see its **Volumes** / **Chapters**
tabs, build a volume/chapter by uploading local images or scraping a site, and read it
in a fast, modern reader. It also has an **image pool** — a personal staging area where
you collect scraped or uploaded images (across many sessions) that aren't tied to any
manga yet, then organize them into a volume/chapter later. The defining choice (see the
guidelines): **image bytes go frontend ↔ Supabase Storage directly**; the backend owns
only metadata (what exists, who owns it, page order).

## Structure

```
frontend/src/
  shared/
    lib/
      storage.ts                     ← NEW: supabase-js Storage wrapper (uploadToBucket, createSignedUrls)
  modules/
    read/
      index.ts                       ← public API (pages + provider for the router)
      pages/
        MangaCollectionPage.tsx      ← /lector — grid of all mangas
        MangaSectionsPage.tsx        ← /lector/manga/:mangaId — Volumes/Chapters tabs + sections
        MangaReaderPage.tsx          ← /lector/manga/:mangaId/read/:sectionId — the reading view
        LibraryPage.tsx              ← /lector/pool — the unassigned image pool
      widgets/
        MangaGrid/                   ← library grid (+ MangaCard)
        SectionTabs.tsx              ← Volumes | Chapters switch
        SectionGrid/                 ← a tab's sections (+ SectionCard)
        PullSeriesModal.tsx          ← series link → tick volumes → create + direct-pull each
        UploadTray/                  ← local-file staging with drag-reorder (+ components)
        ScrapePicker/                ← paste URL → pick + order scraped images (+ components)
        LibraryHeader.tsx            ← pool page header: back link + Edit/Done toggle
        LibraryCollect.tsx           ← pool page: the scrape/upload collect section
        LibraryStorage.tsx           ← pool page: selection toolbar + PoolGrid + lightbox
        PoolGrid/                    ← the pool grid itself: select + discard (+ components)
        Reader/                      ← virtualized page viewer + controls (+ components)
        PullPagesModal.tsx           ← (MangaReader/) volume/chapter link → direct pull into this section
      features/                      ← grouped by the page each fulfills an action for
        manga-collection/
          create-manga/              ← create a series
          set-manga-cover/           ← pick a library asset as a manga's cover
        manga-sections/
          create-section/            ← add a volume/chapter
          delete-section/            ← remove a volume/chapter
          set-section-cover/         ← pick a library asset as a section's cover
          pull-series/               ← series link → volumes; create + pull each, one at a time
        manga-reader/
          insert-from-library/       ← selected library assets (ordered) → POST /read/sections/:id/pages/from-library (?at=N to insert mid-section)
          delete-page/               ← remove one page → DELETE /read/pages/:id
          reorder-pages/             ← drag-reorder → PATCH …/pages/order
          pull-pages/                ← scraped candidates (site order) → POST /read/sections/:id/import
          set-reader-width/          ← Full / ¾ / ½ page-strip width, remembered in localStorage
        library/
          collect-to-library/        ← scraped/uploaded images → POST /read/library/import or /read/library
          discard-from-library/      ← remove a library asset (row + Storage file)
          scrape-pages/              ← URL → POST /read/scrape → candidates
      entities/
        manga/                       ← Manga types + collection provider
        section/                     ← Section types
        page/                        ← Page types + reader runtime/progress
        library-asset/               ← LibraryAsset types + pool list provider
      shared/
        api/read.ts                  ← module-local endpoint callers (metadata only)
        useSignedPages.ts            ← batch-sign a section's pages for the reader
```

> Endpoint callers live **in the module** (`modules/read/shared/api/read.ts`), not
> `shared/api/`, because only this module uses them (per the api-vs-module rule). They
> cover **metadata only** — the image bytes never go through these callers.

## Routing

Three routes under the existing `ProtectedRoute → AppLayout` children. The paths use
the **display** name `/lector/*` (user-facing), while the code lives in `modules/read`:

```
/lector                              → MangaCollectionPage
/lector/manga/:mangaId               → MangaSectionsPage   (tabs read ?tab=volumes|chapters)
/lector/manga/:mangaId/read/:sectionId → MangaReaderPage
/lector/pool                         → LibraryPage          (the unassigned image pool)
```

A `MangaCollectionProvider` (the manga collection, mirroring `ConversationsProvider`) wraps
these so the grid and detail page share one source of truth. One new sidebar nav item,
labelled **"Lector"**, points at `/lector` (added in `app/layouts/Sidebar/navItems.ts`).

## Direct pull — a link straight into a volume/chapter

The fast path for a series hosted on a supported reader site (see
`backend/docs/modules/read.md` → `extractors/`). No pool, and no picking order by
hand: pages land in **the site's own order**.

- **One volume/chapter** — reader edit mode → **Pull from link** (`PullPagesModal`):
  paste a volume/chapter link → `scrape-pages` (`POST /read/scrape`) → "Found N
  pages" → **Pull** → `pull-pages` sends every candidate, in site order, to
  `POST /read/sections/{id}/import` with the extractor's `referer` and each page's
  size. Reviewing is optional and can only *skip* pages (everything starts
  selected), never reorder them; previews may not load for hotlink-protected
  sites, but the backend download still works.
- **A whole series** — sections page, Volumes tab, edit mode → **Pull series**
  (`PullSeriesModal`): paste the series link → `POST /read/scrape/series` lists its
  volumes; volumes this manga already has start unticked → **Pull N volumes** →
  `pull-series` goes one volume at a time: scrape → create the section → import,
  showing per-volume status. A failed volume is marked and the rest continue.

### Fixing pages in place

In the reader's edit mode every page carries `PageEditOverlay` (in
`widgets/MangaReader/components/`):

- **✕** in its corner: the first click arms it ("Remove?"), the second removes the
  page (`delete-page` → `DELETE /read/pages/{id}`, row + Storage file, later pages
  move up). Moving the pointer away disarms it.
- **Click the page** → a menu: **Move up one page**, **Move down one page**, **Add
  page before**, **Add page after**, **Remove this page** (also asks twice). A move
  swaps the page with its neighbour and saves the whole new order via
  `reorder-pages` (`PATCH …/pages/order`); Move up is hidden on the first page and
  Move down on the last. The add options open `PoolPickerModal` with an `at`
  position, so whatever is picked (scraped, uploaded, or already in the pool) goes
  in at that spot via `POST …/pages/from-library?at=N`.

## The two upload flows

### Local upload — direct to Storage
1. Open a section (or create one via `create-section`).
2. `UploadTray`: pick local images, **drag to reorder** — this staging order is the
   page order. Dimensions are read client-side (`Image`/`createImageBitmap`) for the
   `width/height` metadata.
3. `upload-pages` uploads each file **straight to Storage** via
   `shared/lib/storage.ts → uploadToBucket`, to
   `manga/{userId}/{mangaId}/{sectionId}/{position}-{uuid}.{ext}` — parallel, no
   backend round-trip for bytes. RLS lets a user write only under their own prefix.
4. Once uploaded, `POST /read/sections/{id}/pages` records the ordered rows
   `[{storage_path, position, width, height}]`.

### Scrape — pick from a site
1. `ScrapePicker`: paste a URL → `scrape-pages` calls `POST /read/scrape {url}`.
2. Backend returns candidate image URLs; the picker shows them as a selectable,
   reorderable grid.
3. `import-pages` sends the chosen, ordered URLs to
   `POST /read/sections/{id}/import` — the **backend** downloads + uploads them
   (browsers can't fetch cross-origin/hotlink-protected images) and records the rows.
4. The picker then refetches the section's pages.

> Both upload flows have a **"send to pool"** variant when you don't yet know which
> manga the images belong to — see *The image pool* below. `ScrapePicker` and
> `UploadTray` are reused there; only the destination endpoint differs.

## The image pool (staging)

`/lector/pool` (`LibraryPage` + `PoolGrid`) is a personal, manga-less collection you fill
over time, then drain into series when you're ready. It exists because scraping and
uploading often happen *before* you've decided the target volume/chapter — you gather
first, organize later.

**Filling the library** (`collect-to-library`) — each item reveals in the pool the
moment *it* finishes, not batched to the end. Both endpoints stream one NDJSON
`LibraryStreamItem` line per item as the backend finishes it (see
`backend/docs/modules/read.md` → `services/library_stream.py`); the frontend reads
that stream via `shared/lib/ndjson.ts`'s `streamNdjson` (a plain `fetch` +
`ReadableStream` reader, not `EventSource`, since the browser's native SSE API can't
carry this app's Bearer token). `position` is still fixed from each batch's
*original* order — reserved upfront, before any item's work starts — immune to
which item actually finishes first:
- *Scrape → pool:* same `ScrapePicker` candidate flow, but the chosen URLs go to
  `POST /read/library/import`, streamed — the backend downloads each one
  (bounded concurrency) → uploads to `{userId}/_pool/…` → records it, reporting it
  the instant that URL is done. You can repeat this across many sessions; assets
  accumulate.
- *Upload → pool:* same `UploadTray`; files upload to `{userId}/_pool/…` via
  `shared/lib/storage.ts` concurrently first (bytes only — order-independent),
  then `POST /read/library` streams the (fast) record step for all of them.

**Draining the library** (`insert-from-library`):
1. `PoolGrid` shows the pool (assets resolved to previews via batch signed URLs, like
   the reader) and lets you **select + drag-order** the ones for a section.
2. Pick a target manga + volume/chapter (or create one), then
   `POST /read/sections/{id}/pages/from-library` with the ordered `asset_ids`.
3. The backend turns each into a `manga_page` (reusing the same Storage object — no
   re-upload) and removes it from the pool. The inserted assets **disappear from the
   pool grid** and appear as the section's pages — your "gets a manga link, leaves the
   pool."

**Discarding**: an unused asset can be deleted (`DELETE /read/library/{id}`), which
removes both the row and its Storage file.

## Reading — fast & modern

`MangaReaderPage` loads ordered metadata via `GET /read/sections/{id}/pages`, then
`useSignedPages` **batch-signs** all of that section's `storage_path`s in one
`createSignedUrls` call (private bucket → temporary CDN links, ~1h TTL). The `Reader`
widget then:
- Renders a **virtualized** vertical scroll (only on-screen pages mounted).
- **Preloads** the next page(s) ahead of the viewport.
- Reserves each page's box from the stored `width/height` → **no layout shift**.
- Uses `loading="lazy"` and an IntersectionObserver to track progress.

### Reader width

Full width is too wide on big screens, so the reader header has a **Full · ¾ · ½**
picker (`set-reader-width` → `useReaderWidth`). It narrows the page strip and
keeps it centred, in both reading and edit mode. The choice is one preference for
every manga, stored in the browser's `localStorage` (`lector.readerWidth`), so it
is per-browser and does not sync across devices. If storage is unavailable, the
reader falls back to full width. Phones (below `md`) always read full width, and
the picker is hidden there.

Because images load directly from the Storage CDN (not proxied through FastAPI), the
reader stays fast even for large volumes.

## `shared/lib/storage.ts` (new shared infra)

A thin supabase-js wrapper so features never touch the raw client (mirrors how
`fetchWithToken` centralizes the token):

```ts
uploadToBucket(path: string, file: Blob): Promise<void>          // storage.from(MANGA_BUCKET).upload(...)
createSignedUrls(paths: string[], expiresIn?: number): Promise<string[]>
```

It reads the same authenticated Supabase session the rest of the app uses, so Storage
RLS sees the logged-in user. This is the one sanctioned place to use the Supabase
client for Storage — features/entities call this, not the SDK directly.

## `shared/lib/ndjson.ts` (new shared infra)

A thin, generic streaming-fetch wrapper — for endpoints that stream newline-
delimited JSON instead of returning one JSON body:

```ts
streamNdjson<T>(input: string, init?: RequestInit): AsyncGenerator<T>
```

Goes through `fetchWithToken` (so streamed endpoints authenticate the same way as
every other call) rather than the browser's native `EventSource`, which can't send
a custom `Authorization` header. `readApi.ts`'s `requestStream<T>()` wraps this with
the same camelCase pipeline `request<T>()` uses for normal calls — currently the
only consumers are `importToLibrary`/`recordLibraryAssets` (see *The image pool*).

## Entities

- `manga` — `Manga` (`id, title, coverPath, updatedAt`), the library list provider.
- `section` — `Section` (`id, mangaId, kind: "volume"|"chapter", number, title`).
- `page` — `Page` (`id, storagePath, position, width, height`) + reader progress state.
- `library-asset` — `LibraryAsset` (`id, storagePath, sourceUrl, position, width,
  height, createdAt`) + the pool list provider (oldest-first by `position`, assigned
  by the backend from each collect batch's original order — a page's actual reading
  order is chosen separately, at organize time).

## Design notes

- All colors via `--owl-*` CSS variables; proportional units only (per guidelines).
- The library grid and reader are media-heavy → covers use thumbnails (future) and the
  reader virtualizes; never render a whole volume's `<img>`s at once.
- Metadata reads/writes go through `fetchWithToken` (backend); **bytes** go through
  `shared/lib/storage.ts` (Storage). Two paths, by design — see the guidelines.
