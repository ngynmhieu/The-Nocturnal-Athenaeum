import { useCallback, useEffect, useRef, useState } from "react";
import { readApi } from "../../../shared";
import type { VersionKind, VersionPreview } from "../../../shared";
import type { Page } from "../../../entities";

/** A generated version waiting for Accept / Discard, and the page it belongs to. */
export type PagePreview = VersionPreview & { pageId: string };

/** Best-effort delete of a preview's Storage file (the next preview of that
 *  page overwrites it anyway, so a failure here is harmless). */
const dropPreviewFile = (p: { pageId: string; kind: VersionKind }) => {
  readApi.discardPreview(p.pageId, p.kind).catch(() => {});
};

/** Upscale / translate-by-reference a page, then Accept or Discard the preview —
 *  and remove an accepted version. One request and one preview at a time: while
 *  either is pending, `upscale` / `translate` do nothing. `error` is the
 *  backend's `detail`, which is already user-facing copy, so show it verbatim.
 *  `onChanged` refetches the section after anything that changes its versions.
 *  `dismiss` (leaving edit mode) drops the preview now *and* any preview still
 *  being generated; unmounting does the same. */
export function usePageVersions(onChanged: () => Promise<void>) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [preview, setPreviewState] = useState<PagePreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Refs mirror the state so the guards below never act on a stale render.
  const busyRef = useRef<string | null>(null);
  const previewRef = useRef<PagePreview | null>(null);
  // Bumped by `dismiss` / unmount: a request started under an older generation
  // was dismissed mid-flight, so its result is thrown away instead of shown.
  const generationRef = useRef(0);
  // An Accept is in flight — the backend is moving the preview file, so it must
  // not be discarded underneath it.
  const acceptingRef = useRef(false);

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
    const generation = generationRef.current;
    try {
      await work();
    } catch (err) {
      // A dismissed request's failure isn't news to anyone.
      if (generation === generationRef.current) {
        setError(err instanceof Error ? err.message : "Something went wrong — try again.");
      }
    } finally {
      busyRef.current = null;
      setBusyId(null);
    }
  }, []);

  /** Show a freshly generated preview — unless it was dismissed while it was
   *  being made, in which case its file is deleted straight away. */
  const receive = useCallback((generation: number, next: PagePreview) => {
    if (generation !== generationRef.current) {
      dropPreviewFile(next);
      return;
    }
    previewRef.current = next;
    setPreviewState(next);
  }, []);

  const upscale = useCallback(
    async (page: Page) => {
      if (previewRef.current) return;
      await run(page.id, async () => {
        const generation = generationRef.current;
        const result = await readApi.upscalePage(page.id);
        receive(generation, { ...result, pageId: page.id });
      });
    },
    [run, receive]
  );

  const translate = useCallback(
    async (page: Page, referencePage: Page) => {
      if (previewRef.current || page.id === referencePage.id) return;
      await run(page.id, async () => {
        const generation = generationRef.current;
        const result = await readApi.translatePage(page.id, referencePage.id);
        receive(generation, { ...result, pageId: page.id });
      });
    },
    [run, receive]
  );

  const accept = useCallback(async () => {
    const current = previewRef.current;
    if (!current) return;
    await run(current.pageId, async () => {
      const generation = generationRef.current;
      acceptingRef.current = true;
      try {
        await readApi.acceptVersion(current.pageId, {
          kind: current.kind,
          language: current.language,
          referencePageId: current.referencePageId,
        });
      } catch (err) {
        // A failed accept keeps the preview open to retry or discard — unless
        // it was dismissed meanwhile, then its file goes now.
        if (generation !== generationRef.current) {
          setPreview(null);
          dropPreviewFile(current);
        }
        throw err;
      } finally {
        acceptingRef.current = false;
      }
      // Accepted: the preview file is now the version.
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

  /** Drop everything pending, without waiting on the busy guard: the open
   *  preview (unless it's being accepted — that finishes and saves), any
   *  preview still being generated (see `receive`), and the error line. */
  const dismiss = useCallback(() => {
    generationRef.current += 1;
    setError(null);
    const current = previewRef.current;
    if (current && !acceptingRef.current) {
      setPreview(null);
      dropPreviewFile(current);
    }
  }, []);

  const remove = useCallback(
    async (page: Page, kind: VersionKind) => {
      await run(page.id, async () => {
        await readApi.removeVersion(page.id, kind, kind === "translated" ? "en" : null);
        await onChanged();
      });
    },
    [run, onChanged]
  );

  // Leaving the reader: same as `dismiss` — an in-flight upscale / translate
  // deletes its result on arrival, and an open preview (not mid-accept) goes now.
  useEffect(
    () => () => {
      generationRef.current += 1;
      const current = previewRef.current;
      if (current && !acceptingRef.current) dropPreviewFile(current);
    },
    []
  );

  return { busyId, preview, error, upscale, translate, accept, discard, dismiss, remove };
}
