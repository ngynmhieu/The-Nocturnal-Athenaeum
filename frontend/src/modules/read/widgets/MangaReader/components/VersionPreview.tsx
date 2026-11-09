import { Check, X } from "lucide-react";
import type { PagePreview } from "../../../features";

interface VersionPreviewProps {
  preview: PagePreview;
  /** Accept / Discard is running — the buttons wait and the layer pulses. */
  busy: boolean;
  onAccept: () => void;
  onDiscard: () => void;
}

/** A generated upscale / translation laid over its page, awaiting a decision.
 *  The image is `previewUrl` straight from the backend (freshly signed and
 *  cache-busted), never re-signed here — a per-path signed-URL cache would show
 *  the previous run's image after a re-run. */
export function VersionPreview({ preview, busy, onAccept, onDiscard }: VersionPreviewProps) {
  const label = preview.kind === "translated" ? "English" : "Upscaled";
  return (
    <div className="absolute inset-0 z-20 bg-[var(--owl-cream-mid)]">
      <img
        src={preview.previewUrl}
        alt={`${label} preview`}
        decoding="async"
        className={`size-full object-contain ${busy ? "animate-pulse" : ""}`}
      />
      <span className="pointer-events-none absolute left-2 top-2 rounded-md bg-[var(--background)]/85 px-2 py-0.5 text-xs font-semibold text-[var(--owl-brown-deep)]">
        Preview · {label}
      </span>
      <div className="absolute inset-x-0 bottom-[2%] flex justify-center gap-2">
        <button
          type="button"
          onClick={onAccept}
          disabled={busy}
          className="flex items-center gap-1.5 rounded-md border border-[var(--owl-brown-deep)] bg-[var(--owl-brown-deep)] px-3 py-1.5 text-sm text-[var(--owl-cream)] shadow-sm transition-colors hover:bg-[var(--owl-brown-dark)] disabled:opacity-60 cursor-pointer disabled:cursor-default"
        >
          <Check size={15} aria-hidden="true" />
          Accept
        </button>
        <button
          type="button"
          onClick={onDiscard}
          disabled={busy}
          className="flex items-center gap-1.5 rounded-md border border-[var(--owl-border)] bg-[var(--owl-cream)]/95 px-3 py-1.5 text-sm text-[var(--owl-brown)] shadow-sm backdrop-blur-sm transition-colors hover:bg-[var(--owl-cream-mid)] disabled:opacity-60 cursor-pointer disabled:cursor-default"
        >
          <X size={15} aria-hidden="true" />
          Discard
        </button>
      </div>
    </div>
  );
}
