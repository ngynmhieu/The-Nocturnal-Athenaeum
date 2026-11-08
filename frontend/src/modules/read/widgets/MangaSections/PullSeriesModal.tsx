import { useState } from "react";
import { Check, Globe, Loader2, X, AlertCircle } from "lucide-react";
import { Modal, Tooltip } from "@/shared/ui";
import { usePullSeries, type SeriesPullStatus } from "../../features";
import { sectionLabel } from "../../entities";

interface PullSeriesModalProps {
  open: boolean;
  onClose: () => void;
  mangaId: string;
  /** Volume numbers this manga already has — those start unticked. */
  existingNumbers: (number | null)[];
  /** Fires after each pull run so the page can refresh its sections. */
  onPulled: () => void;
}

/** Paste a series link → list its volumes → pull the ticked ones, each into a
 *  new volume section with its pages in the site's order. */
export function PullSeriesModal({ open, onClose, mangaId, existingNumbers, onPulled }: PullSeriesModalProps) {
  const [url, setUrl] = useState("");
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const { find, entries, finding, error, pullAll, pulling, status } = usePullSeries(mangaId);

  // Fresh list → tick every volume this manga doesn't already have.
  const runFind = async () => {
    const found = await find(url);
    setChosen(new Set(found.filter((e) => !existingNumbers.includes(e.number)).map((e) => e.url)));
  };

  const toggle = (key: string) =>
    setChosen((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  const runPull = async () => {
    await pullAll(entries.filter((e) => chosen.has(e.url)));
    onPulled();
  };

  return (
    <Modal open={open} onClose={onClose} size="window">
      <div className="flex items-center gap-2">
        <h2 className="flex-1 text-base font-medium text-[var(--owl-brown-dark)]">Pull volumes from a series</h2>
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
            onKeyDown={(e) => e.key === "Enter" && runFind()}
            placeholder="Paste a series link…"
            className="flex-1 min-w-0 rounded-md border border-[var(--owl-border)] bg-transparent px-3 py-1.5 text-sm text-[var(--owl-brown-deep)] placeholder:text-[var(--owl-brown-muted)] outline-none focus:border-[var(--owl-orange)]"
          />
          <button
            onClick={runFind}
            disabled={finding || pulling || !url.trim()}
            className="flex items-center gap-1.5 rounded-md border border-[var(--owl-border)] px-3 py-1.5 text-sm text-[var(--owl-brown)] hover:bg-[var(--owl-brown-mid)]/10 transition-colors cursor-pointer disabled:opacity-50"
          >
            {finding ? <Loader2 size={15} aria-hidden="true" className="animate-spin" /> : <Globe size={15} aria-hidden="true" />}
            {finding ? "Finding volumes…" : "Find volumes"}
          </button>
        </div>

        {error && <p className="text-sm text-[var(--owl-danger)]">{error}</p>}

        {entries.length > 0 && (
          <>
            <ul className="flex flex-col divide-y divide-[var(--owl-border)] rounded-md border border-[var(--owl-border)] max-h-[24rem] overflow-y-auto">
              {entries.map((entry) => {
                const owned = existingNumbers.includes(entry.number);
                return (
                  <li key={entry.url} className="flex items-center gap-3 px-3 py-2">
                    <input
                      type="checkbox"
                      checked={chosen.has(entry.url)}
                      disabled={pulling}
                      onChange={() => toggle(entry.url)}
                      aria-label={sectionLabel(entry)}
                      className="accent-[var(--owl-orange)] cursor-pointer"
                    />
                    <span className="flex-1 text-sm text-[var(--owl-brown-deep)]">
                      {sectionLabel(entry)}
                      {owned && <span className="ml-2 text-xs text-[var(--owl-brown-muted)]">already in this manga</span>}
                    </span>
                    <StatusBadge status={status[entry.url]} />
                  </li>
                );
              })}
            </ul>
            {chosen.size > 0 && (
              <button
                onClick={runPull}
                disabled={pulling}
                className="flex w-fit items-center gap-1.5 rounded-md bg-[var(--owl-brown)] px-3 py-1.5 text-sm text-[var(--owl-cream)] hover:bg-[var(--owl-brown-deep)] transition-colors cursor-pointer disabled:opacity-50"
              >
                {pulling && <Loader2 size={14} aria-hidden="true" className="animate-spin" />}
                {pulling ? "Pulling, one volume at a time…" : `Pull ${chosen.size} volume${chosen.size > 1 ? "s" : ""}`}
              </button>
            )}
          </>
        )}
      </div>
    </Modal>
  );
}

function StatusBadge({ status }: { status: SeriesPullStatus | undefined }) {
  if (!status) return null;
  switch (status.state) {
    case "waiting":
      return <span className="text-xs text-[var(--owl-brown-muted)]">Waiting</span>;
    case "pulling":
      return <Loader2 size={14} aria-label="Pulling" className="animate-spin text-[var(--owl-orange-deep)]" />;
    case "done":
      return (
        <span className="flex items-center gap-1 text-xs text-[var(--owl-brown-deep)]">
          <Check size={14} aria-hidden="true" /> {status.pages} pages
        </span>
      );
    case "error":
      return (
        <span title={status.message} className="flex items-center gap-1 text-xs text-[var(--owl-danger)]">
          <AlertCircle size={14} aria-hidden="true" /> Failed
        </span>
      );
  }
}
