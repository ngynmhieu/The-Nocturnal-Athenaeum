import camelcaseKeys from "camelcase-keys";
import { fetchWithToken, streamNdjson } from "@/shared/lib";

/** Backend shapes for the /read endpoints, camelCased on arrival (metadata only —
 *  image bytes go through shared/lib/storage.ts, never these callers). */

export interface MangaSummary {
  id: string;
  title: string;
  description: string | null;
  coverPath: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface SectionSummary {
  id: string;
  mangaId: string;
  kind: "volume" | "chapter";
  number: number | null;
  title: string | null;
  coverPath: string | null;
  /** First page's storage path — the display fallback when `coverPath` is unset. */
  firstPagePath: string | null;
  createdAt: string;
}

export interface MangaDetail extends MangaSummary {
  sections: SectionSummary[];
}

export type VersionKind = "upscaled" | "translated";

/** An accepted alternative image of a page (upscale, or a translation). */
export interface PageVersionInfo {
  id: string;
  kind: VersionKind;
  language: string | null;
  storagePath: string;
  width: number | null;
  height: number | null;
  referencePageId: string | null;
}

/** A generated-but-not-yet-accepted version. Show `previewUrl` directly — it is
 *  freshly signed and cache-busted; never sign `previewPath` via `useSignedUrls`. */
export interface VersionPreview {
  kind: VersionKind;
  language: string | null;
  previewPath: string;
  previewUrl: string;
  width: number | null;
  height: number | null;
  referencePageId: string | null;
}

export interface PageInfo {
  id: string;
  storagePath: string;
  position: number;
  width: number | null;
  height: number | null;
  createdAt: string;
  /** Accepted versions; older backends omit it, so `listPages` fills in `[]`. */
  versions: PageVersionInfo[];
}

export interface LibraryAssetInfo {
  id: string;
  storagePath: string;
  sourceUrl: string | null;
  position: number;
  width: number | null;
  height: number | null;
  createdAt: string;
}

export interface ScrapeCandidate {
  url: string;
  width: number | null;
  height: number | null;
}

export interface ScrapeResult {
  candidates: ScrapeCandidate[];
  /** Set when a per-site extractor knows what its image CDN requires as Referer. */
  referer: string | null;
}

/** One volume/chapter listed on a series page — `url` goes back into `scrape`. */
export interface SeriesEntry {
  kind: "volume" | "chapter";
  number: number | null;
  title: string | null;
  url: string;
}

export interface PageSize {
  width: number | null;
  height: number | null;
}

export interface SectionCreateInput {
  kind: "volume" | "chapter";
  number?: number | null;
  title?: string | null;
}

export interface LibraryAssetRecordInput {
  storagePath: string;
  sourceUrl?: string | null;
  width?: number | null;
  height?: number | null;
}

/** One NDJSON line from `/read/library` or `/read/library/import` — `index` is
 *  the item's position in the *request* array, not arrival order (items
 *  complete concurrently); callers must key off `index`, never line order. */
export type LibraryStreamItem =
  | { index: number; ok: true; asset: LibraryAssetInfo }
  | { index: number; ok: false; error: string };

/** One place for the fetch → error → camelCase pipeline all callers share. */
async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetchWithToken(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init.headers },
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail ?? "Request failed");
  }
  if (res.status === 204) return undefined as T;
  const raw = await res.json();
  return camelcaseKeys(raw, { deep: true }) as T;
}

/** Same camelCase pipeline as `request`, for endpoints that stream NDJSON lines
 *  instead of returning one JSON body. */
async function* requestStream<T>(path: string, init: RequestInit = {}): AsyncGenerator<T> {
  const stream = streamNdjson<Record<string, unknown>>(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init.headers },
  });
  for await (const raw of stream) {
    yield camelcaseKeys(raw, { deep: true }) as T;
  }
}

/** `?at=N` — insert new pages from position N instead of appending. */
const atQuery = (at?: number) => (at === undefined ? "" : `?at=${at}`);

export const readApi = {
  // --- mangas ---
  listMangas: () => request<MangaSummary[]>("/read/mangas"),

  createManga: (title: string, description?: string | null) =>
    request<MangaSummary>("/read/mangas", {
      method: "POST",
      body: JSON.stringify({ title, description: description ?? null }),
    }),

  getManga: (mangaId: string) => request<MangaDetail>(`/read/mangas/${mangaId}`),

  updateManga: (mangaId: string, patch: { title?: string; description?: string | null; coverPath?: string | null }) =>
    request<MangaSummary>(`/read/mangas/${mangaId}`, {
      method: "PATCH",
      body: JSON.stringify({
        ...(patch.title !== undefined && { title: patch.title }),
        ...(patch.description !== undefined && { description: patch.description }),
        ...(patch.coverPath !== undefined && { cover_path: patch.coverPath }),
      }),
    }),

  setMangaCover: (mangaId: string, assetId: string) =>
    request<MangaSummary>(`/read/mangas/${mangaId}/cover/from-library`, {
      method: "POST",
      body: JSON.stringify({ asset_id: assetId }),
    }),

  deleteManga: (mangaId: string) =>
    request<void>(`/read/mangas/${mangaId}`, { method: "DELETE" }),

  // --- sections ---
  createSection: (mangaId: string, input: SectionCreateInput) =>
    request<SectionSummary>(`/read/mangas/${mangaId}/sections`, {
      method: "POST",
      body: JSON.stringify({
        kind: input.kind,
        number: input.number ?? null,
        title: input.title ?? null,
      }),
    }),

  updateSection: (sectionId: string, patch: { coverPath?: string | null }) =>
    request<SectionSummary>(`/read/sections/${sectionId}`, {
      method: "PATCH",
      body: JSON.stringify({
        ...(patch.coverPath !== undefined && { cover_path: patch.coverPath }),
      }),
    }),

  setSectionCover: (sectionId: string, assetId: string) =>
    request<SectionSummary>(`/read/sections/${sectionId}/cover/from-library`, {
      method: "POST",
      body: JSON.stringify({ asset_id: assetId }),
    }),

  deleteSection: (sectionId: string) =>
    request<void>(`/read/sections/${sectionId}`, { method: "DELETE" }),

  // --- pages ---
  listPages: async (sectionId: string) => {
    const pages = await request<PageInfo[]>(`/read/sections/${sectionId}/pages`);
    return pages.map((p) => ({ ...p, versions: p.versions ?? [] }));
  },

  // --- page versions (upscale / translate by reference) ---
  upscalePage: (pageId: string) =>
    request<VersionPreview>(`/read/pages/${pageId}/upscale`, { method: "POST" }),

  translatePage: (pageId: string, referencePageId: string) =>
    request<VersionPreview>(`/read/pages/${pageId}/translate`, {
      method: "POST",
      body: JSON.stringify({ reference_page_id: referencePageId }),
    }),

  acceptVersion: (
    pageId: string,
    body: { kind: VersionKind; language?: string | null; referencePageId?: string | null }
  ) =>
    request<PageVersionInfo>(`/read/pages/${pageId}/versions/accept`, {
      method: "POST",
      body: JSON.stringify({
        kind: body.kind,
        ...(body.language != null && { language: body.language }),
        ...(body.referencePageId != null && { reference_page_id: body.referencePageId }),
      }),
    }),

  discardPreview: (pageId: string, kind: VersionKind) =>
    request<void>(`/read/pages/${pageId}/versions/preview?kind=${kind}`, { method: "DELETE" }),

  removeVersion: (pageId: string, kind: VersionKind, language?: string | null) =>
    request<void>(
      `/read/pages/${pageId}/versions?kind=${kind}${language ? `&language=${encodeURIComponent(language)}` : ""}`,
      { method: "DELETE" }
    ),

  /** Removes the page row and its Storage object; later pages move up one. */
  deletePage: (pageId: string) => request<void>(`/read/pages/${pageId}`, { method: "DELETE" }),

  reorderPages: (sectionId: string, orderedPageIds: string[]) =>
    request<void>(`/read/sections/${sectionId}/pages/order`, {
      method: "PATCH",
      body: JSON.stringify({ ordered_page_ids: orderedPageIds }),
    }),

  // --- scrape + import ---
  scrape: (url: string) =>
    request<ScrapeResult>("/read/scrape", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),

  scrapeSeries: (url: string) =>
    request<{ entries: SeriesEntry[] }>("/read/scrape/series", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),

  /** Direct pull: the backend downloads `urls` and appends them to the section in
   *  exactly this order — no pool in between. `sizes` is keyed by URL. `at`
   *  inserts them from that position instead (later pages move down). */
  importIntoSection: (
    sectionId: string,
    urls: string[],
    referer?: string | null,
    sizes?: Record<string, PageSize>,
    at?: number
  ) =>
    request<PageInfo[]>(`/read/sections/${sectionId}/import${atQuery(at)}`, {
      method: "POST",
      body: JSON.stringify({ urls, referer: referer ?? null, sizes: sizes ?? {} }),
    }),

  // --- library pool ---
  listLibrary: () => request<LibraryAssetInfo[]>("/read/library"),

  recordLibraryAssets: (records: LibraryAssetRecordInput[]) =>
    requestStream<LibraryStreamItem>("/read/library", {
      method: "POST",
      body: JSON.stringify(
        records.map((r) => ({
          storage_path: r.storagePath,
          source_url: r.sourceUrl ?? null,
          width: r.width ?? null,
          height: r.height ?? null,
        }))
      ),
    }),

  importToLibrary: (urls: string[], referer?: string) =>
    requestStream<LibraryStreamItem>("/read/library/import", {
      method: "POST",
      body: JSON.stringify({ urls, referer: referer ?? null }),
    }),

  /** `at` inserts from that position (later pages move down); omitted, they're appended. */
  insertFromLibrary: (sectionId: string, assetIds: string[], at?: number) =>
    request<PageInfo[]>(`/read/sections/${sectionId}/pages/from-library${atQuery(at)}`, {
      method: "POST",
      body: JSON.stringify({ asset_ids: assetIds }),
    }),

  discardLibraryAsset: (assetId: string) =>
    request<void>(`/read/library/${assetId}`, { method: "DELETE" }),
};
