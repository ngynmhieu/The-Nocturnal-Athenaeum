import { useCallback, useState } from "react";
import { readApi, sizesByUrl, type ScrapeCandidate } from "../../../shared";
import type { Page } from "../../../entities";

/** Direct pull: scraped candidates → straight into a section, in the order given
 *  (the site's own page order), skipping the pool. One backend call — it
 *  downloads, uploads and records every page, so there's no per-item status. */
export function usePullPages(sectionId: string) {
  const [pulling, setPulling] = useState(false);

  const pull = useCallback(
    async (candidates: ScrapeCandidate[], referer: string | null): Promise<Page[]> => {
      if (candidates.length === 0) return [];
      setPulling(true);
      try {
        return await readApi.importIntoSection(
          sectionId,
          candidates.map((c) => c.url),
          referer,
          sizesByUrl(candidates)
        );
      } finally {
        setPulling(false);
      }
    },
    [sectionId]
  );

  return { pull, pulling };
}

