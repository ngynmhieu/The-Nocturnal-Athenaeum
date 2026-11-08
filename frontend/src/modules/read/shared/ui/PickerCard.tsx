import { useState } from "react";
import { ImageOff, Check, Loader2, AlertTriangle } from "lucide-react";
import type { ImportStatus } from "../importStatus";

interface PickerCardProps {
  previewUrl: string;
  /** Tooltip/fallback text — defaults to `previewUrl` (fine for remote URLs,
   *  less useful for local blob URLs, so callers with a better label pass it). */
  label?: string;
  /** 0-based pick order when picked, or null when not picked. */
  order: number | null;
  /** Set while this specific candidate is being imported/uploaded — shows a
   *  spinner overlay, then swaps the pick badge for a checkmark once done. */
  status?: ImportStatus;
  onToggle: (event: React.MouseEvent) => void;
}

export function PickerCard({ previewUrl, label, order, status, onToggle }: PickerCardProps) {
  // Many sites hotlink-protect images, so a scraped preview may not load in the
  // browser even though the backend can import it — show a neutral tile then.
  const [broken, setBroken] = useState(false);
  const picked = order !== null;
  const title = label ?? previewUrl;

  return (
    <button
      onClick={onToggle}
      disabled={status !== undefined}
      className={`relative aspect-[3/4] rounded-md overflow-hidden border-2 transition-colors cursor-pointer disabled:cursor-default ${
        picked ? "border-[var(--owl-orange)]" : "border-[var(--owl-border)] hover:border-[var(--owl-tan-mid)]"
      }`}
      title={title}
    >
      {broken ? (
        <span className="flex size-full flex-col items-center justify-center gap-1 bg-[var(--owl-cream-mid)]/50 text-[var(--owl-brown-muted)]">
          <ImageOff size={20} aria-hidden="true" />
          <span className="px-1 text-[0.6rem] leading-tight break-all line-clamp-3">{title}</span>
        </span>
      ) : (
        <img
          src={previewUrl}
          alt=""
          loading="lazy"
          referrerPolicy="no-referrer"
          onError={() => setBroken(true)}
          className="size-full object-cover"
        />
      )}
      {picked && (
        <span className="absolute top-1 left-1 flex size-5 items-center justify-center rounded-full bg-[var(--owl-orange)] text-[0.65rem] font-medium text-[var(--owl-cream)]">
          {status === "done" ? <Check size={12} aria-hidden="true" /> : order + 1}
        </span>
      )}
      {status === "importing" && (
        <span className="absolute inset-0 flex items-center justify-center bg-black/40">
          <Loader2 size={20} aria-hidden="true" className="animate-spin text-white" />
        </span>
      )}
      {status === "error" && (
        <span className="absolute inset-0 flex items-center justify-center bg-[var(--owl-danger)]/60">
          <AlertTriangle size={20} aria-hidden="true" className="text-white" />
        </span>
      )}
    </button>
  );
}
