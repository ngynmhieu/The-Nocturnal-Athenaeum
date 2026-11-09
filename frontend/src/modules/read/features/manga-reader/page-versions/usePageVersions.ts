import { useCallback, useEffect, useRef, useState } from "react";
import { readApi } from "../../../shared";
import type { VersionKind, VersionPreview } from "../../../shared";
import type { Page } from "../../../entities";

/** A generated version waiting for Accept / Discard, and the page it belongs to. */
export type PagePreview = VersionPreview & { pageId: string };

/** Upscale / translate-by-reference a page, then Accept or Discard the preview —
 *  and remove an accepted version. One request and one preview at a time: while
 *  either is pending, `upscale` / `translate` do nothing. `error` is the
 *  backend's `detail`, which is already user-facing copy, so show it verbatim.
 *  `onChanged` refetches the section after anything that changes its versions. */
export function usePageVersions(onChanged: () => Promise<void>) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [preview, setPreviewState] = useState<PagePreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Refs mirror the state so the guards below never act on a stale render.
  const busyRef = useRef<string | null>(null);
  const previewRef = useRef<PagePreview | null>(null);

  const setPreview = (next: PagePreview | null) => {
    previewRef.current = next;
    setPreviewState(next);
  };

  /** Runs one request against `pageId`, with its busy pulse and error line. */
  const run = useCallback(async (pageId: string, work: () => Promise<void>) => {
    if (busyRef.current) return;
    busyRef.current = pageId;
    setBusyId(pageId);
    setError(null);
    try {
      await work();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong — try again.");
    } finally {
      busyRef.current = null;
      setBusyId(null);
    }
  }, []);

  const upscale = useCallback(
    async (page: Page) => {
      if (previewRef.current) return;
      await run(page.id, async () => {
        const result = await readApi.upscalePage(page.id);
        setPreview({ ...result, pageId: page.id });
      });
    },
    [run]
  );

  const translate = useCallback(
    async (page: Page, referencePage: Page) => {
      if (previewRef.current || page.id === referencePage.id) return;
      await run(page.id, async () => {
        const result = await readApi.translatePage(page.id, referencePage.id);
        setPreview({ ...result, pageId: page.id });
      });
    },
    [run]
  );

  const accept = useCallback(async () => {
    const current = previewRef.current;
    if (!current) return;
    await run(current.pageId, async () => {
      await readApi.acceptVersion(current.pageId, {
        kind: current.kind,
        language: current.language,
        referencePageId: current.referencePageId,
      });
      // Accepted: the preview file is now the version. A failed accept keeps
      // the preview open, so it can be retried or discarded.
      setPreview(null);
      await onChanged();
    });
  }, [run, onChanged]);

  const discard = useCallback(async () => {
    const current = previewRef.current;
    if (!current) return;
    await run(current.pageId, async () => {
      // Close it either way — if the delete fails the stale preview file is
      // simply overwritten by the next preview of this page.
      setPreview(null);
      await readApi.discardPreview(current.pageId, current.kind);
    });
  }, [run]);

  const remove = useCallback(
    async (page: Page, kind: VersionKind) => {
      await run(page.id, async () => {
        await readApi.removeVersion(page.id, kind, kind === "translated" ? "en" : null);
        await onChanged();
      });
    },
    [run, onChanged]
  );

  // Leaving the reader with a preview still open: drop its Storage file.
  useEffect(
    () => () => {
      const current = previewRef.current;
      if (current) readApi.discardPreview(current.pageId, current.kind).catch(() => {});
    },
    []
  );

  return { busyId, preview, error, upscale, translate, accept, discard, remove };
}
