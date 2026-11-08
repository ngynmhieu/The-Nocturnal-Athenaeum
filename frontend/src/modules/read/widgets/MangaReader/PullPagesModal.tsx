import { useState } from "react";
import { Globe, Loader2, X } from "lucide-react";
import { Modal, Tooltip } from "@/shared/ui";
import { PickerGrid } from "../../shared";
import { usePullPages, useScrapePages } from "../../features";
import type { Page } from "../../entities";

interface PullPagesModalProps {
  open: boolean;
  onClose: () => void;
  sectionId: string;
  onPulled: (pages: Page[]) => void;
}

/** Direct pull: paste a volume/chapter link → every page, in the site's own
 *  order, straight into this section (no pool). Everything starts selected;
 *  reviewing is optional and only ever *skips* pages — it never reorders them. */
export function PullPagesModal({ open, onClose, sectionId, onPulled }: PullPagesModalProps) {
  const [url, setUrl] = useState("");
  const [reviewing, setReviewing] = useState(false);
  const [skipped, setSkipped] = useState<Set<string>>(new Set());
  const [pullError, setPullError] = useState<string | null>(null);
  const { scrape, candidates, sourceUrl, scraping, error, reset } = useScrapePages();
  const { pull, pulling } = usePullPages(sectionId);

  const kept = candidates.filter((c) => !skipped.has(c.url));

  const runScrape = async () => {
    setSkipped(new Set());
    setReviewing(false);
    setPullError(null);
    await scrape(url);
  };

  const runPull = async () => {
    setPullError(null);
    try {
      const pages = await pull(kept, sourceUrl);
      reset();
      setUrl("");
      onPulled(pages);
    } catch (err) {
      setPullError((err as Error).message);
    }
  };

  const toggle = (key: string) =>
    setSkipped((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  return (
    <Modal open={open} onClose={onClose} size="window">
      <div className="flex items-center gap-2">
        <h2 className="flex-1 text-base font-medium text-[var(--owl-brown-dark)]">Pull pages from a link</h2>
        <Tooltip content="Close" side="right">
          <button
            onClick={onClose}
            aria-label="Close"
            className="p-1.5 rounded-md text-[var(--owl-brown-muted)] transition-colors hover:bg-[var(--owl-brown-mid)]/10 hover:text-[var(--owl-brown-deep)] cursor-pointer"
          >
            <X size={16} />
          </button>
        </Tooltip>
      </div>

      <div className="mt-3 flex flex-col gap-3">
        <div className="flex gap-2">
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && runScrape()}
            placeholder="Paste a volume or chapter link…"
            className="flex-1 min-w-0 rounded-md border border-[var(--owl-border)] bg-transparent px-3 py-1.5 text-sm text-[var(--owl-brown-deep)] placeholder:text-[var(--owl-brown-muted)] outline-none focus:border-[var(--owl-orange)]"
          />
          <button
            onClick={runScrape}
            disabled={scraping || pulling || !url.trim()}
            className="flex items-center gap-1.5 rounded-md border border-[var(--owl-border)] px-3 py-1.5 text-sm text-[var(--owl-brown)] hover:bg-[var(--owl-brown-mid)]/10 transition-colors cursor-pointer disabled:opacity-50"
          >
            {scraping ? <Loader2 size={15} aria-hidden="true" className="animate-spin" /> : <Globe size={15} aria-hidden="true" />}
            {scraping ? "Finding pages…" : "Find pages"}
          </button>
        </div>

        {error && <p className="text-sm text-[var(--owl-danger)]">{error}</p>}
        {pullError && <p className="text-sm text-[var(--owl-danger)]">{pullError}</p>}

        {candidates.length > 0 && (
          <>
            <div className="flex items-center gap-3">
              <p className="flex-1 text-sm text-[var(--owl-brown-deep)]">
                Found {candidates.length} pages, in the site's order
                {skipped.size > 0 && ` — skipping ${skipped.size}`}.
              </p>
              <button
                onClick={() => setReviewing((r) => !r)}
                className="text-xs text-[var(--owl-orange-deep)] hover:underline cursor-pointer"
              >
                {reviewing ? "Hide pages" : "Review / skip pages"}
              </button>
            </div>

            {reviewing ? (
              <PickerGrid
                items={candidates.map((c) => ({ key: c.url, previewUrl: c.url }))}
                picked={kept.map((c) => c.url)}
                onItemClick={(key) => toggle(key)}
                onSelectAll={() => setSkipped(new Set())}
                onClear={() => setSkipped(new Set(candidates.map((c) => c.url)))}
                busy={pulling}
                busyLabel="Pulling…"
                confirmLabel="Pull"
                itemNoun="page"
                hint="click a page to skip it. Some sites block previews here; the pull still works."
                onConfirm={runPull}
              />
            ) : (
              kept.length > 0 && (
                <button
                  onClick={runPull}
                  disabled={pulling}
                  className="flex w-fit items-center gap-1.5 rounded-md bg-[var(--owl-brown)] px-3 py-1.5 text-sm text-[var(--owl-cream)] hover:bg-[var(--owl-brown-deep)] transition-colors cursor-pointer disabled:opacity-50"
                >
                  {pulling && <Loader2 size={14} aria-hidden="true" className="animate-spin" />}
                  {pulling ? "Pulling… (this can take a minute)" : `Pull ${kept.length} page${kept.length > 1 ? "s" : ""}`}
                </button>
              )
            )}
          </>
        )}
      </div>
    </Modal>
  );
}
