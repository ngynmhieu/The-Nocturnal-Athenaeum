import { useCallback, useState } from "react";
import { readApi, sizesByUrl, type SeriesEntry } from "../../../shared";

export type SeriesPullStatus =
  | { state: "waiting" }
  | { state: "pulling" }
  | { state: "done"; pages: number }
  | { state: "error"; message: string };

/** Series page → its volumes; then, for each chosen one, create the section and
 *  direct-pull its pages (site order). One volume at a time, on purpose: each
 *  pull drives a headless browser plus ~200 downloads on the backend, and a
 *  failed volume shouldn't stop the rest. Status is keyed by entry URL. */
export function usePullSeries(mangaId: string) {
  const [entries, setEntries] = useState<SeriesEntry[]>([]);
  const [finding, setFinding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pulling, setPulling] = useState(false);
  const [status, setStatus] = useState<Record<string, SeriesPullStatus>>({});

  /** Resolves to the found entries too, so the caller can seed its selection. */
  const find = useCallback(async (url: string): Promise<SeriesEntry[]> => {
    const trimmed = url.trim();
    if (!trimmed) return [];
    setFinding(true);
    setError(null);
    setStatus({});
    try {
      const result = await readApi.scrapeSeries(trimmed);
      setEntries(result.entries);
      return result.entries;
    } catch (err) {
      setError((err as Error).message);
      setEntries([]);
      return [];
    } finally {
      setFinding(false);
    }
  }, []);

  const pullAll = useCallback(
    async (chosen: SeriesEntry[]) => {
      setPulling(true);
      setStatus(Object.fromEntries(chosen.map((e) => [e.url, { state: "waiting" } as SeriesPullStatus])));
      const mark = (url: string, next: SeriesPullStatus) => setStatus((prev) => ({ ...prev, [url]: next }));
      try {
        for (const entry of chosen) {
          mark(entry.url, { state: "pulling" });
          try {
            const scraped = await readApi.scrape(entry.url);
            if (scraped.candidates.length === 0) throw new Error("No pages found");
            const section = await readApi.createSection(mangaId, {
              kind: entry.kind,
              number: entry.number,
              title: entry.title,
            });
            const pages = await readApi.importIntoSection(
              section.id,
              scraped.candidates.map((c) => c.url),
              scraped.referer ?? entry.url,
              sizesByUrl(scraped.candidates)
            );
            mark(entry.url, { state: "done", pages: pages.length });
          } catch (err) {
            mark(entry.url, { state: "error", message: (err as Error).message });
          }
        }
      } finally {
        setPulling(false);
      }
    },
    [mangaId]
  );

  return { find, entries, finding, error, pullAll, pulling, status };
}
