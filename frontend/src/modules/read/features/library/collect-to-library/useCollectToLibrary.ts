import { useCallback, useState } from "react";
import { uploadToBucket, mapWithConcurrency } from "@/shared/lib";
import { useSession } from "@/modules/auth";
import { readApi, readImageSize, fileExtension, type ImportStatus } from "../../../shared";
import type { LibraryAsset } from "../../../entities";

/** Matches the backend's own download concurrency (see ScrapeService) — only
 *  used for the upload flow's client-side Storage puts; the scrape flow's
 *  concurrency is entirely the backend's concern (bounded server-side). */
const CONCURRENCY = 5;

export type CollectResult = { ok: true; asset: LibraryAsset } | { ok: false; error: string };

/** A stream dropping mid-flight leaves some keys stuck on "importing" forever
 *  (their line never arrived) — resolve those to "error" locally so nothing
 *  spins forever. Not ground truth: an item stuck this way may have actually
 *  finished server-side (see the callers' catch blocks, which still refresh()
 *  the pool after). */
function resolveStuckToError(status: Record<string, ImportStatus>): Record<string, ImportStatus> {
  return Object.fromEntries(
    Object.entries(status).map(([key, value]) => [key, value === "importing" ? "error" : value])
  );
}

/** Fill the library (the unassigned image staging area) — both collect flows
 *  land in `{user_id}/_pool/` with no manga attached: scrape candidates go
 *  through the backend (server-side download), local files go direct-to-storage
 *  then get recorded. Inserting them into a section is a separate, later
 *  action (`insert-from-library`, see `PoolPickerModal`). The other way pages
 *  reach a section skips the pool entirely: a direct pull from a link
 *  (`pull-pages` / `pull-series`).
 *
 *  Both endpoints stream one result per item as it finishes (not batched to
 *  the end) — `onItem` fires per item so the caller can reveal it in the pool
 *  immediately. `position` is still assigned from the batch's original order,
 *  not arrival order — see `ReadRepository.reserve_library_asset_slots`. */
export function useCollectToLibrary() {
  const { user } = useSession();
  const [collecting, setCollecting] = useState(false);
  const [importStatus, setImportStatus] = useState<Record<string, ImportStatus>>({});

  const importUrlsToLibrary = useCallback(
    async (urls: string[], referer: string | undefined, onItem: (key: string, result: CollectResult) => void) => {
      if (urls.length === 0) return;
      setCollecting(true);
      setImportStatus(Object.fromEntries(urls.map((url) => [url, "importing"])));
      try {
        for await (const line of readApi.importToLibrary(urls, referer)) {
          const key = urls[line.index];
          setImportStatus((prev) => ({ ...prev, [key]: line.ok ? "done" : "error" }));
          onItem(key, line.ok ? { ok: true, asset: line.asset } : { ok: false, error: line.error });
        }
      } catch (err) {
        setImportStatus((prev) => resolveStuckToError(prev));
        throw err;
      } finally {
        setCollecting(false);
        setImportStatus({});
      }
    },
    []
  );

  const uploadFilesToLibrary = useCallback(
    async (items: { id: string; file: File }[], onItem: (key: string, result: CollectResult) => void) => {
      if (!user || items.length === 0) return;
      setCollecting(true);
      setImportStatus(Object.fromEntries(items.map(({ id }) => [id, "importing"])));
      try {
        // Bytes upload concurrently (independent per-file); mapWithConcurrency
        // keeps the results index-aligned to `items`, so the one streamed
        // record call below still reports them against the original items.
        const uploaded = await mapWithConcurrency(items, CONCURRENCY, async ({ file }) => {
          const path = `${user.id}/_pool/${crypto.randomUUID()}${fileExtension(file)}`;
          const size = await readImageSize(file);
          await uploadToBucket(path, file);
          return { storagePath: path, width: size?.width, height: size?.height };
        });
        for await (const line of readApi.recordLibraryAssets(uploaded)) {
          const key = items[line.index].id;
          setImportStatus((prev) => ({ ...prev, [key]: line.ok ? "done" : "error" }));
          onItem(key, line.ok ? { ok: true, asset: line.asset } : { ok: false, error: line.error });
        }
      } catch (err) {
        setImportStatus((prev) => resolveStuckToError(prev));
        throw err;
      } finally {
        setCollecting(false);
        setImportStatus({});
      }
    },
    [user]
  );

  return { importUrlsToLibrary, uploadFilesToLibrary, collecting, importStatus };
}
