import { useCallback, useState } from "react";
import { readApi, type ImportStatus } from "../../../shared";
import type { Page } from "../../../entities";

/** Library → section, in one backend call — unlike scrape/upload, `insertFromLibrary`
 *  positions and inserts every page in one transaction (no per-item count to race
 *  on), so this stays a single batched request instead of a sequential loop.
 *  `at` places them from that position (later pages move down) instead of
 *  appending — how "add a page before/after this one" lands. */
export function useInsertFromLibrary(sectionId: string) {
  const [inserting, setInserting] = useState(false);
  const [insertStatus, setInsertStatus] = useState<Record<string, ImportStatus>>({});

  const insert = useCallback(
    async (assetIds: string[], at?: number): Promise<Page[]> => {
      if (assetIds.length === 0) return [];
      setInserting(true);
      setInsertStatus(Object.fromEntries(assetIds.map((id) => [id, "importing"])));
      try {
        return await readApi.insertFromLibrary(sectionId, assetIds, at);
      } finally {
        setInserting(false);
        setInsertStatus({});
      }
    },
    [sectionId]
  );

  return { insert, inserting, insertStatus };
}
