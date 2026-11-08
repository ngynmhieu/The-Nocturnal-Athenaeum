import { useState } from "react";
import { ImageOff, Check, Loader2, AlertTriangle, X } from "lucide-react";
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
  /** Shows an ✕ in the corner (click once to arm, again to remove). Omit for
   *  grids whose items can't be removed. */
  onRemove?: () => void;
  /** This card is being removed right now. */
  removing?: boolean;
}

export function PickerCard({ previewUrl, label, order, status, onToggle, onRemove, removing = false }: PickerCardProps) {
  const [armed, setArmed] = useState(false);
  // Many sites hotlink-protect images, so a scraped preview may not load in the
  // browser even though the backend can import it — show a neutral tile then.
  const [broken, setBroken] = useState(false);
  const picked = order !== null;
  const title = label ?? previewUrl;

  return (
    // The ✕ is a sibling of the pick button, not inside it (no nested buttons).
    <div className={`relative ${removing ? "opacity-50" : ""}`}>
    <button
      onClick={onToggle}
      disabled={status !== undefined}
      className={`relative w-full aspect-[3/4] rounded-md overflow-hidden border-2 transition-colors cursor-pointer disabled:cursor-default ${
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
    {onRemove && status === undefined && (
      <button
        type="button"
        aria-label={armed ? "Confirm removing this image" : "Remove this image"}
        disabled={removing}
        onClick={() => {
          if (armed) {
            setArmed(false);
            onRemove();
          } else {
            setArmed(true);
          }
        }}
        onMouseLeave={() => setArmed(false)}
        onBlur={() => setArmed(false)}
        className={`absolute right-1 top-1 flex items-center gap-1 rounded-full border border-[var(--owl-border)] shadow-sm transition-colors cursor-pointer disabled:cursor-wait ${
          armed
            ? "bg-[var(--owl-brown-deep)] px-2 py-0.5 text-[0.65rem] text-[var(--background)]"
            : "bg-[var(--background)]/90 p-1 text-[var(--owl-brown)] hover:text-[var(--owl-brown-deep)]"
        }`}
      >
        <X size={armed ? 11 : 13} aria-hidden="true" />
        {armed && "Remove?"}
      </button>
    )}
    </div>
  );
}
