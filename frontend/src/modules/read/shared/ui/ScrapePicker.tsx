import { useState } from "react";
import { Globe } from "lucide-react";
import { useScrapePages } from "../../features/library/scrape-pages";
import type { ImportStatus } from "../importStatus";
import { CollectProgress } from "./CollectProgress";

interface ScrapePickerProps {
  /** Called with every image found, in page order, plus the Referer downloads
   *  need (some sites hotlink-protect on it). */
  onImport: (urls: string[], referer: string) => Promise<void> | void;
  busy: boolean;
  /** Per-URL status while `busy`, for the progress line. */
  importStatus?: Record<string, ImportStatus>;
}

/** Paste URL → scrape → every image found goes straight into the pool, in page
 *  order. No candidate-picking step: the pool is where images are picked and
 *  ordered (and unwanted ones discarded). */
export function ScrapePicker({ onImport, busy, importStatus }: ScrapePickerProps) {
  const [url, setUrl] = useState("");
  const { scrape, scraping, error, reset } = useScrapePages();
  const [notice, setNotice] = useState<string | null>(null);

  const run = async () => {
    setNotice(null);
    const result = await scrape(url);
    if (!result) return;
    if (result.candidates.length === 0) {
      setNotice("No images found on that page.");
      return;
    }
    await onImport(result.candidates.map((c) => c.url), result.referer);
    setUrl("");
    reset();
  };

  const working = scraping || busy;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-2">
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !working && run()}
          placeholder="Paste a chapter or image URL…"
          className="flex-1 min-w-0 rounded-md border border-[var(--owl-border)] bg-transparent px-3 py-1.5 text-sm text-[var(--owl-brown-deep)] placeholder:text-[var(--owl-brown-muted)] outline-none focus:border-[var(--owl-orange)]"
        />
        <button
          onClick={run}
          disabled={working || !url.trim()}
          className="flex items-center gap-1.5 rounded-md border border-[var(--owl-border)] px-3 py-1.5 text-sm text-[var(--owl-brown)] hover:bg-[var(--owl-brown-mid)]/10 transition-colors cursor-pointer disabled:opacity-50"
        >
          <Globe size={15} aria-hidden="true" />
          {scraping ? "Scraping…" : busy ? "Collecting…" : "Scrape"}
        </button>
      </div>

      {error && <p className="text-sm text-[var(--owl-danger)]">{error}</p>}
      {notice && <p className="text-sm text-[var(--owl-brown-muted)]">{notice}</p>}
      {busy && <CollectProgress status={importStatus} />}
    </div>
  );
}
