import { useCallback, useState } from "react";
import { readApi, type ScrapeCandidate } from "../../../shared";

/** Paste a URL → backend fetches the page and returns candidate images for the
 *  user to pick from. No persistence — import is a separate, second action. */
export function useScrapePages() {
  const [candidates, setCandidates] = useState<ScrapeCandidate[]>([]);
  /** What imports send as the Referer — the extractor's required one when it
   *  names one, otherwise the page URL the candidates came from. */
  const [sourceUrl, setSourceUrl] = useState<string | null>(null);
  const [scraping, setScraping] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const scrape = useCallback(async (url: string) => {
    const trimmed = url.trim();
    if (!trimmed) return;
    setScraping(true);
    setError(null);
    try {
      const result = await readApi.scrape(trimmed);
      setCandidates(result.candidates);
      setSourceUrl(result.referer ?? trimmed);
    } catch (err) {
      setError((err as Error).message);
      setCandidates([]);
      setSourceUrl(null);
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
