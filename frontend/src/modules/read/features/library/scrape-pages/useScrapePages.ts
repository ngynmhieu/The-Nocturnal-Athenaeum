import { useCallback, useState } from "react";
import { readApi, type ScrapeCandidate } from "../../../shared";

/** Paste a URL → backend fetches the page and returns its candidate images (also
 *  returned from `scrape`, so a caller can act on them right away). No
 *  persistence — collecting them is the caller's next step. */
export function useScrapePages() {
  const [candidates, setCandidates] = useState<ScrapeCandidate[]>([]);
  /** What imports send as the Referer — the extractor's required one when it
   *  names one, otherwise the page URL the candidates came from. */
  const [sourceUrl, setSourceUrl] = useState<string | null>(null);
  const [scraping, setScraping] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const scrape = useCallback(async (url: string): Promise<{ candidates: ScrapeCandidate[]; referer: string } | null> => {
    const trimmed = url.trim();
    if (!trimmed) return null;
    setScraping(true);
    setError(null);
    try {
      const result = await readApi.scrape(trimmed);
      setCandidates(result.candidates);
      setSourceUrl(result.referer ?? trimmed);
      return { candidates: result.candidates, referer: result.referer ?? trimmed };
    } catch (err) {
      setError((err as Error).message);
      setCandidates([]);
      setSourceUrl(null);
      return null;
    } finally {
      setScraping(false);
    }
  }, []);

  const reset = useCallback(() => {
    setCandidates([]);
    setSourceUrl(null);
    setError(null);
  }, []);

  return { scrape, candidates, sourceUrl, scraping, error, reset };
}
